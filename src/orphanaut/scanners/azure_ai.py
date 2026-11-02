"""Azure AI scanners: Azure OpenAI / AI Services, Machine Learning (incl. AI Foundry hubs)
and AI Search - all through ARM REST so no extra SDKs are needed."""

from __future__ import annotations

from orphanaut.ai_pricing import hourly_to_monthly
from orphanaut.dependencies import Action, dep
from orphanaut.providers.azure_arm import ArmClient, ArmError, parse_id
from orphanaut.scanners.azure_base import AzureBaseScanner

COGNITIVE_API = "2023-05-01"
ML_API = "2024-04-01"
SEARCH_API = "2023-11-01"

# Rough monthly price per search unit (replica × partition) by tier.
_SEARCH_MONTHLY = {
    "free": 0.0,
    "basic": 75.0,
    "standard": 250.0,
    "standard2": 1000.0,
    "standard3": 2000.0,
    "storage_optimized_l1": 2800.0,
    "storage_optimized_l2": 5600.0,
}
# Rough hourly price of common Azure ML VM sizes.
_VM_HOURLY = {
    "standard_ds11_v2": 0.19,
    "standard_ds3_v2": 0.29,
    "standard_ds12_v2": 0.37,
    "standard_e4s_v3": 0.25,
    "standard_d4s_v3": 0.19,
    "standard_d13_v2": 0.74,
    "standard_nc6s_v3": 3.06,
    "standard_nc4as_t4_v3": 0.53,
    "standard_nc24ads_a100_v4": 3.67,
    "standard_f4s_v2": 0.17,
}


def _vm_monthly(size: str, count: int = 1) -> float | None:
    hourly = _VM_HOURLY.get((size or "").lower())
    return None if hourly is None else hourly_to_monthly(hourly * max(count, 1))


class _AzureAiScanner(AzureBaseScanner):
    def arm(self) -> ArmClient:
        return ArmClient(self.session.credential)

    def _sub(self, path: str) -> str:
        return f"/subscriptions/{self.session.subscription_id}{path}"

    def _safe_list(self, arm: ArmClient, path: str, api: str) -> list[dict]:
        try:
            return list(arm.list(path, api))
        except ArmError:
            return []


class AzureAiServicesScanner(_AzureAiScanner):
    """Azure OpenAI and other Azure AI Services (Cognitive Services) accounts."""

    service_name = "Azure OpenAI & AI Services"

    def scan(self) -> list:
        arm = self.arm()
        resources = []
        for account in arm.list(
            self._sub("/providers/Microsoft.CognitiveServices/accounts"), COGNITIVE_API
        ):
            location = account.get("location", "")
            if not self._in_region(location):
                continue
            rid = account["id"]
            kind = account.get("kind", "")
            deployments = self._safe_list(arm, f"{rid}/deployments", COGNITIVE_API)
            projects = self._safe_list(arm, f"{rid}/projects", "2025-06-01")
            ptu_units = 0
            dependents = []
            for d in deployments:
                model = d.get("properties", {}).get("model", {})
                sku = d.get("sku", {})
                if "provisioned" in sku.get("name", "").lower():
                    ptu_units += int(sku.get("capacity", 0) or 0)
                dependents.append(
                    dep(
                        "Model deployment",
                        d.get("name", ""),
                        note=f"{model.get('name', '')} {model.get('version', '')} · "
                        f"{sku.get('name', '')} {sku.get('capacity', '')}".strip(),
                    )
                )
            dependents += [
                dep("AI Foundry project", p.get("name", "").split("/")[-1]) for p in projects
            ]
            dependents.append(
                dep(
                    "Soft-deleted copy",
                    account.get("name", ""),
                    note="purged so nothing lingers and the name is free again",
                )
            )
            dependents.append(
                dep(
                    "Keys and endpoint URL",
                    "all apps using them stop working",
                    Action.KEEP,
                    "update any app or notebook that used them",
                )
            )
            resources.append(
                self._resource(
                    resource_id=rid,
                    name=account.get("name", ""),
                    service="Azure OpenAI" if kind == "OpenAI" else "AI Services",
                    resource_type=f"{kind or 'AI Services'} Account",
                    region=location,
                    status=account.get("properties", {}).get("provisioningState", ""),
                    details=f"{len(deployments)} deployment(s), "
                    f"SKU {account.get('sku', {}).get('name', '')}"
                    + (f", {ptu_units} PTU provisioned" if ptu_units else ""),
                    extra={
                        "arm_id": rid,
                        "resource_group": parse_id(rid).get("resource_group", ""),
                        "account_name": account.get("name", ""),
                        "deployments": [d.get("name", "") for d in deployments],
                        "dependents": dependents,
                        "monthly_cost": hourly_to_monthly(ptu_units * 1.0) if ptu_units else 0.0,
                    },
                )
            )
        return resources


class AzureMachineLearningScanner(_AzureAiScanner):
    """Azure ML workspaces / AI Foundry hubs & projects, with their compute and endpoints."""

    service_name = "Azure Machine Learning"

    def scan(self) -> list:
        arm = self.arm()
        workspaces = [
            w
            for w in arm.list(
                self._sub("/providers/Microsoft.MachineLearningServices/workspaces"), ML_API
            )
            if self._in_region(w.get("location", ""))
        ]
        # Associated resources shared by more than one workspace must be kept.
        usage: dict[str, int] = {}
        for w in workspaces:
            for key in ("storageAccount", "keyVault", "applicationInsights", "containerRegistry"):
                linked = (w.get("properties", {}).get(key) or "").lower()
                if linked:
                    usage[linked] = usage.get(linked, 0) + 1
        children_of: dict[str, list[str]] = {}
        for w in workspaces:
            hub = (w.get("properties", {}).get("hubResourceId") or "").lower()
            if hub:
                children_of.setdefault(hub, []).append(w.get("name", ""))

        resources = []
        for w in workspaces:
            rid = w["id"]
            props = w.get("properties", {})
            location = w.get("location", "")
            kind = (w.get("kind") or "Default").title()
            label = {"Hub": "AI Foundry Hub", "Project": "AI Foundry Project"}.get(
                kind, "Workspace"
            )
            computes = self._safe_list(arm, f"{rid}/computes", ML_API)
            endpoints = self._safe_list(arm, f"{rid}/onlineEndpoints", ML_API)
            serverless = self._safe_list(arm, f"{rid}/serverlessEndpoints", ML_API)

            compute_cost = 0.0
            dependents = []
            for c in computes:
                cprops = c.get("properties", {})
                ctype = cprops.get("computeType", "")
                inner = cprops.get("properties") or {}
                size = inner.get("vmSize", "")
                state = inner.get("state", "") or cprops.get("provisioningState", "")
                dependents.append(
                    dep(
                        "Compute instance" if ctype == "ComputeInstance" else f"Compute ({ctype})",
                        c.get("name", ""),
                        note=f"{size} {state}".strip(),
                    )
                )
                running = ctype == "ComputeInstance" and str(state).lower() == "running"
                min_nodes = (inner.get("scaleSettings") or {}).get("minNodeCount", 0) or 0
                cost = (
                    _vm_monthly(size, min_nodes)
                    if ctype == "AmlCompute" and min_nodes
                    else (_vm_monthly(size) if running else 0.0)
                )
                compute_cost += cost or 0.0
                if running or (ctype == "AmlCompute" and min_nodes):
                    resources.append(
                        self._resource(
                            resource_id=c["id"],
                            name=c.get("name", ""),
                            service="Machine Learning",
                            resource_type="Compute Instance"
                            if ctype == "ComputeInstance"
                            else "Compute Cluster",
                            region=location,
                            status=str(state),
                            details=f"{size} in workspace {w.get('name', '')}"
                            + (f", min {min_nodes} nodes" if min_nodes else ""),
                            extra={
                                "arm_id": c["id"],
                                "monthly_cost": cost,
                                "impact_note": "files on the compute's own disk are lost",
                                "dependents": [
                                    dep(
                                        "Data in the workspace storage",
                                        "kept",
                                        Action.KEEP,
                                        "only the VM is removed",
                                    )
                                ],
                            },
                        )
                    )
            for e in endpoints:
                deployments = self._safe_list(arm, f"{e['id']}/deployments", ML_API)
                endpoint_cost = 0.0
                for d in deployments:
                    sku = d.get("sku", {})
                    size = d.get("properties", {}).get("instanceType", "")
                    endpoint_cost += _vm_monthly(size, int(sku.get("capacity", 1) or 1)) or 0.0
                compute_cost += endpoint_cost
                children = [
                    dep(
                        "Deployment",
                        d.get("name", ""),
                        note=d.get("properties", {}).get("instanceType", ""),
                    )
                    for d in deployments
                ]
                dependents.append(dep("Online endpoint", e.get("name", ""), children=children))
                resources.append(
                    self._resource(
                        resource_id=e["id"],
                        name=e.get("name", ""),
                        service="Machine Learning",
                        resource_type="Online Endpoint",
                        region=location,
                        status=e.get("properties", {}).get("provisioningState", ""),
                        details=f"{len(deployments)} deployment(s) in {w.get('name', '')}",
                        extra={
                            "arm_id": e["id"],
                            "monthly_cost": round(endpoint_cost, 2),
                            "dependents": children,
                        },
                    )
                )
            dependents += [
                dep("Serverless endpoint (Models-as-a-Service)", s.get("name", ""))
                for s in serverless
            ]
            hub_children = children_of.get(rid.lower(), [])
            dependents += [dep("AI Foundry project", name) for name in hub_children]

            exclusive: list[str] = []
            for key, kind_label in (
                ("storageAccount", "Storage account"),
                ("keyVault", "Key vault"),
                ("applicationInsights", "Application Insights"),
                ("containerRegistry", "Container registry"),
            ):
                linked = props.get(key) or ""
                if not linked or kind == "Project":
                    continue
                name = linked.rsplit("/", 1)[-1]
                if usage.get(linked.lower(), 0) > 1:
                    dependents.append(
                        dep(kind_label, name, Action.KEEP, "shared with another workspace")
                    )
                else:
                    exclusive.append(linked)
                    dependents.append(
                        dep(kind_label, name, note="created with the workspace - all its data")
                    )
            resources.append(
                self._resource(
                    resource_id=rid,
                    name=w.get("name", ""),
                    service="Machine Learning",
                    resource_type=label,
                    region=location,
                    status=props.get("provisioningState", ""),
                    details=f"{len(computes)} compute, {len(endpoints)} endpoint(s)"
                    + (f", {len(hub_children)} project(s)" if hub_children else ""),
                    extra={
                        "arm_id": rid,
                        "resource_group": parse_id(rid).get("resource_group", ""),
                        "compute_ids": [c["id"] for c in computes],
                        "endpoint_ids": [e["id"] for e in endpoints],
                        "serverless_ids": [s["id"] for s in serverless],
                        "project_ids": [
                            x["id"]
                            for x in workspaces
                            if (x.get("properties", {}).get("hubResourceId") or "").lower()
                            == rid.lower()
                        ],
                        "exclusive_ids": exclusive,
                        "dependents": dependents,
                        "impact_note": "everything inside is removed first, then it is purged",
                        "monthly_cost": round(compute_cost, 2),
                    },
                )
            )
        return resources


class AzureAiSearchScanner(_AzureAiScanner):
    service_name = "Azure AI Search"

    def scan(self) -> list:
        arm = self.arm()
        resources = []
        for svc in arm.list(self._sub("/providers/Microsoft.Search/searchServices"), SEARCH_API):
            location = svc.get("location", "")
            if not self._in_region(location):
                continue
            props = svc.get("properties", {})
            sku = svc.get("sku", {}).get("name", "")
            units = int(props.get("replicaCount", 1) or 1) * int(
                props.get("partitionCount", 1) or 1
            )
            resources.append(
                self._resource(
                    resource_id=svc["id"],
                    name=svc.get("name", ""),
                    service="AI Search",
                    resource_type="Search Service",
                    region=location,
                    status=props.get("status", props.get("provisioningState", "")),
                    details=f"{sku} tier, {props.get('replicaCount', 1)} replica(s) × "
                    f"{props.get('partitionCount', 1)} partition(s)",
                    extra={
                        "arm_id": svc["id"],
                        "monthly_cost": round(_SEARCH_MONTHLY.get(sku.lower(), 0.0) * units, 2)
                        if sku.lower() in _SEARCH_MONTHLY
                        else None,
                        "dependents": [
                            dep("Indexes, indexers, skillsets and data sources", "all"),
                            dep(
                                "Source data (Blob, Cosmos DB...)",
                                "kept",
                                Action.KEEP,
                                "only the search copy is removed",
                            ),
                        ],
                    },
                )
            )
        return resources
