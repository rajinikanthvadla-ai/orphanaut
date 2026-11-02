"""Google Cloud AI scanners: Vertex AI, Vertex AI Workbench, Agent Engine and Vertex AI Search."""

from __future__ import annotations

import re
from collections.abc import Iterator

import requests

from orphanaut.ai_pricing import hourly_to_monthly
from orphanaut.dependencies import Action, dep
from orphanaut.providers.gcp_rest import GcpApiError, GcpRest, vertex_base
from orphanaut.scanners.gcp_base import GcpBaseScanner

_ACCEL_HOURLY = {
    "NVIDIA_TESLA_T4": 0.35,
    "NVIDIA_L4": 0.71,
    "NVIDIA_TESLA_V100": 2.48,
    "NVIDIA_TESLA_P100": 1.46,
    "NVIDIA_TESLA_A100": 2.93,
    "NVIDIA_A100_80GB": 3.93,
    "NVIDIA_H100_80GB": 11.06,
}
_VCPU_RE = re.compile(r"-(\d+)(?:g)?$")


def machine_hourly(machine_type: str, accelerator: str = "", accel_count: int = 0) -> float:
    """Very rough Vertex price: ~$0.055 per vCPU-hour plus GPUs."""
    match = _VCPU_RE.search(machine_type or "")
    vcpus = int(match.group(1)) if match else 4
    return vcpus * 0.055 + _ACCEL_HOURLY.get(accelerator, 1.0 if accelerator else 0.0) * max(
        accel_count, 0
    )


def _short(name: str) -> str:
    return name.rsplit("/", 1)[-1]


def _region_of(name: str) -> str:
    parts = name.split("/")
    return parts[parts.index("locations") + 1] if "locations" in parts else ""


class _VertexScanner(GcpBaseScanner):
    service = "Vertex AI"

    def rest(self) -> GcpRest:
        return GcpRest(self.session.credentials, self.session.project_id)

    def regional(self, rest: GcpRest, collection: str, key: str, **params) -> Iterator[dict]:
        """Yield items of a Vertex collection across the selected regions."""
        for region in sorted(self.regions):
            project = self.session.project_id
            url = f"{vertex_base(region)}/projects/{project}/locations/{region}/{collection}"
            try:
                yield from rest.list(url, key, **params)
            except GcpApiError as exc:
                if exc.api_disabled or exc.status in (400, 404):
                    if exc.api_disabled:
                        return  # Vertex AI isn't enabled, so nothing can exist.
                    continue
                raise
            except requests.exceptions.ConnectionError:
                continue  # Vertex AI isn't offered in this region.

    def res(self, rtype: str, item: dict, status: str, details: str, **extra):
        return self._resource(
            resource_id=item["name"],
            name=item.get("displayName", _short(item["name"])),
            service=self.service,
            resource_type=rtype,
            region=_region_of(item["name"]),
            status=status,
            details=details,
            extra={"rest_name": item["name"], **extra},
        )


class VertexEndpointScanner(_VertexScanner):
    service_name = "Vertex AI Endpoints"

    def scan(self) -> list:
        rest = self.rest()
        resources = []
        for ep in self.regional(rest, "endpoints", "endpoints"):
            deployed = ep.get("deployedModels", [])
            cost = 0.0
            children = []
            for d in deployed:
                res = d.get("dedicatedResources", {})
                spec = res.get("machineSpec", {})
                replicas = res.get("minReplicaCount", 1)
                cost += (
                    hourly_to_monthly(
                        machine_hourly(
                            spec.get("machineType", ""),
                            spec.get("acceleratorType", ""),
                            spec.get("acceleratorCount", 0),
                        )
                        * replicas
                    )
                    if res
                    else 0.0
                )
                children.append(
                    dep(
                        "Deployed model",
                        d.get("displayName", d.get("id", "")),
                        note=f"{replicas}× {spec.get('machineType', 'shared')} "
                        f"{spec.get('acceleratorType', '')}".strip()
                        + " - undeployed",
                        children=[
                            dep(
                                "Model in Model Registry",
                                _short(d.get("model", "")),
                                Action.KEEP,
                                "kept - delete it from the Models row",
                            )
                        ],
                    )
                )
            resources.append(
                self.res(
                    "Endpoint",
                    ep,
                    "deployed" if deployed else "empty",
                    f"{len(deployed)} deployed model(s)",
                    deployed_ids=[d["id"] for d in deployed],
                    dependents=children,
                    monthly_cost=round(cost, 2),
                )
            )
        return resources


class VertexModelScanner(_VertexScanner):
    service_name = "Vertex AI Models"

    def scan(self) -> list:
        rest = self.rest()
        resources = []
        for model in self.regional(rest, "models", "models"):
            deployed = model.get("deployedModels", [])
            resources.append(
                self.res(
                    "Model",
                    model,
                    "deployed" if deployed else "not deployed",
                    f"version {model.get('versionId', '1')}"
                    + (f", deployed to {len(deployed)} endpoint(s)" if deployed else ""),
                    dependents=[dep("All model versions", "every version")]
                    + [
                        dep(
                            "Model artifacts in Cloud Storage",
                            "gs://...",
                            Action.KEEP,
                            "your bucket data is never touched",
                        )
                    ],
                    monthly_cost=0.0,
                )
            )
            if deployed:
                resources[-1].deletable = False
                resources[-1].extra["impact_note"] = "undeploy it first by deleting its endpoint"
        return resources


class VertexVectorSearchScanner(_VertexScanner):
    service_name = "Vertex AI Vector Search"

    def scan(self) -> list:
        rest = self.rest()
        resources = []
        deployed_index_names: set[str] = set()
        for ie in self.regional(rest, "indexEndpoints", "indexEndpoints"):
            deployed = ie.get("deployedIndexes", [])
            cost = 0.0
            children = []
            for d in deployed:
                deployed_index_names.add(d.get("index", ""))
                res = d.get("dedicatedResources", {})
                spec = res.get("machineSpec", {})
                replicas = res.get("minReplicaCount", 1) or 1
                cost += hourly_to_monthly(
                    machine_hourly(spec.get("machineType", "e2-standard-16")) * replicas
                )
                children.append(
                    dep(
                        "Deployed index",
                        d.get("id", ""),
                        note=f"{replicas}× {spec.get('machineType', 'auto')} - undeployed",
                        children=[
                            dep(
                                "Index data",
                                _short(d.get("index", "")),
                                Action.KEEP,
                                "kept - delete from the Index row",
                            )
                        ],
                    )
                )
            resources.append(
                self.res(
                    "Vector Search Endpoint",
                    ie,
                    "deployed" if deployed else "empty",
                    f"{len(deployed)} deployed index(es)",
                    deployed_ids=[d["id"] for d in deployed],
                    dependents=children,
                    monthly_cost=round(cost, 2),
                )
            )
        for index in self.regional(rest, "indexes", "indexes"):
            in_use = index["name"] in deployed_index_names
            stats = index.get("indexStats", {})
            resources.append(
                self.res(
                    "Vector Search Index",
                    index,
                    "deployed" if in_use else "not deployed",
                    f"{stats.get('vectorsCount', '?')} vectors",
                    dependents=[dep("Embeddings stored in the index", "all vectors")],
                    monthly_cost=0.0,
                )
            )
            if in_use:
                resources[-1].deletable = False
                resources[-1].extra["impact_note"] = "undeploy it first by deleting its endpoint"
        return resources


class VertexJobScanner(_VertexScanner):
    """Running custom training jobs, training pipelines and tuning jobs."""

    service_name = "Vertex AI Jobs"

    def scan(self) -> list:
        rest = self.rest()
        resources = []
        running = (
            'state="JOB_STATE_RUNNING" OR state="JOB_STATE_PENDING" OR state="JOB_STATE_QUEUED"'
        )
        pipeline_running = (
            'state="PIPELINE_STATE_RUNNING" OR state="PIPELINE_STATE_PENDING" '
            'OR state="PIPELINE_STATE_QUEUED"'
        )
        for kind, collection, key, flt in (
            ("Custom Job", "customJobs", "customJobs", running),
            ("Training Pipeline", "trainingPipelines", "trainingPipelines", pipeline_running),
            ("Tuning Job", "hyperparameterTuningJobs", "hyperparameterTuningJobs", running),
            ("Pipeline Run", "pipelineJobs", "pipelineJobs", pipeline_running),
        ):
            for job in self.regional(rest, collection, key, filter=flt):
                resources.append(
                    self.res(
                        kind,
                        job,
                        job.get("state", "").split("_")[-1].lower(),
                        "RUNNING - billing now",
                        delete_action=Action.STOP.value,
                        impact_note="the job is cancelled; finished outputs stay in Cloud Storage",
                    )
                )
        return resources


class VertexPlatformScanner(_VertexScanner):
    """Agent Engine, Colab Enterprise runtimes and Feature Store online stores."""

    service_name = "Vertex AI Agents & Notebooks"

    def scan(self) -> list:
        rest = self.rest()
        resources = []
        for engine in self.regional(rest, "reasoningEngines", "reasoningEngines"):
            resources.append(
                self.res(
                    "Agent Engine",
                    engine,
                    "deployed",
                    "deployed agent (Agent Engine)",
                    dependents=[
                        dep("Sessions and memory", "all"),
                        dep(
                            "Staging bucket",
                            "gs://...",
                            Action.KEEP,
                            "your bucket data is never touched",
                        ),
                    ],
                )
            )
        for runtime in self.regional(rest, "notebookRuntimes", "notebookRuntimes"):
            state = runtime.get("runtimeState", "")
            resources.append(
                self.res(
                    "Colab Runtime",
                    runtime,
                    state.lower(),
                    runtime.get("machineSpec", {}).get("machineType", "Colab Enterprise runtime"),
                    dependents=[dep("Runtime disk", "files saved only on the runtime")],
                )
            )
        for store in self.regional(rest, "featureOnlineStores", "featureOnlineStores"):
            resources.append(
                self.res(
                    "Feature Online Store",
                    store,
                    store.get("state", "").lower(),
                    "Feature Store",
                    dependents=[dep("Feature views", "all views in the store")],
                )
            )
        return resources


class VertexWorkbenchScanner(_VertexScanner):
    service_name = "Vertex AI Workbench"

    def scan(self) -> list:
        rest = self.rest()
        resources = []
        url = f"https://notebooks.googleapis.com/v2/projects/{self.session.project_id}/locations/-/instances"
        try:
            instances = list(rest.list(url, "instances"))
        except GcpApiError as exc:
            if exc.api_disabled:
                return []
            raise
        for inst in instances:
            zone = _region_of(inst["name"])
            if not self._zone_in_regions(zone):
                continue
            setup = inst.get("gceSetup", {})
            machine = setup.get("machineType", "")
            accel = (setup.get("acceleratorConfigs") or [{}])[0]
            state = inst.get("state", "")
            active = state in {"ACTIVE", "PROVISIONING", "STARTING"}
            data_gb = int((setup.get("dataDisks") or [{}])[0].get("diskSizeGb", 100) or 100)
            boot_gb = int(setup.get("bootDisk", {}).get("diskSizeGb", 150) or 150)
            compute = (
                hourly_to_monthly(
                    machine_hourly(
                        machine, accel.get("type", ""), int(accel.get("coreCount", 0) or 0)
                    )
                )
                if active
                else 0
            )
            resources.append(
                self._resource(
                    resource_id=inst["name"],
                    name=_short(inst["name"]),
                    service=self.service,
                    resource_type="Workbench Instance",
                    region="-".join(zone.split("-")[:-1]),
                    status=state.lower(),
                    details=f"{machine} in {zone}",
                    extra={
                        "rest_name": inst["name"],
                        "monthly_cost": round(compute + (data_gb + boot_gb) * 0.04, 2),
                        "dependents": [
                            dep("Boot disk", f"{boot_gb} GB"),
                            dep(
                                "Data disk (/home/jupyter)",
                                f"{data_gb} GB",
                                note="all notebooks saved on the instance",
                            ),
                        ],
                    },
                )
            )
        return resources


class VertexAiSearchScanner(_VertexScanner):
    """Vertex AI Search / Agent Builder apps and data stores (multi-region)."""

    service_name = "Vertex AI Search"

    def scan(self) -> list:
        rest = self.rest()
        resources = []
        for location in ("global", "us", "eu"):
            host = (
                "discoveryengine.googleapis.com"
                if location == "global"
                else (f"{location}-discoveryengine.googleapis.com")
            )
            base = (
                f"https://{host}/v1/projects/{self.session.project_id}/locations/{location}"
                "/collections/default_collection"
            )
            try:
                engines = list(rest.list(f"{base}/engines", "engines"))
                stores = list(rest.list(f"{base}/dataStores", "dataStores"))
            except GcpApiError as exc:
                if exc.api_disabled:
                    return []
                if exc.status in (400, 404):
                    continue
                raise
            except requests.exceptions.ConnectionError:
                continue
            used = set()
            for engine in engines:
                store_ids = engine.get("dataStoreIds", [])
                used.update(store_ids)
                resources.append(
                    self._resource(
                        resource_id=engine["name"],
                        name=engine.get("displayName", _short(engine["name"])),
                        service=self.service,
                        resource_type="Search App",
                        region=location,
                        status="active",
                        details=engine.get("solutionType", "")
                        .replace("SOLUTION_TYPE_", "")
                        .title(),
                        extra={
                            "rest_name": engine["name"],
                            "dependents": [
                                dep("Data store", s, Action.KEEP, "delete it from its own row")
                                for s in store_ids
                            ],
                        },
                    )
                )
            for store in stores:
                sid = _short(store["name"])
                resources.append(
                    self._resource(
                        resource_id=store["name"],
                        name=store.get("displayName", sid),
                        service=self.service,
                        resource_type="Data Store",
                        region=location,
                        status="in use" if sid in used else "unused",
                        details=store.get("contentConfig", "").replace("_", " ").lower(),
                        deletable=sid not in used,
                        extra={
                            "rest_name": store["name"],
                            "impact_note": "delete the Search App that uses it first"
                            if sid in used
                            else "",
                            "dependents": [dep("Imported documents and index", "all")],
                        },
                    )
                )
        return resources


VERTEX_SCANNERS = [
    VertexEndpointScanner,
    VertexModelScanner,
    VertexVectorSearchScanner,
    VertexJobScanner,
    VertexPlatformScanner,
    VertexWorkbenchScanner,
    VertexAiSearchScanner,
]
