"""Cascade deletion for Azure AI resources (ARM REST)."""

from __future__ import annotations

from collections.abc import Callable

from orphanaut.models import CloudResource
from orphanaut.providers.azure_arm import ArmClient, ArmError, parse_id
from orphanaut.providers.session import AzureSession
from orphanaut.scanners.azure_ai import COGNITIVE_API, ML_API, SEARCH_API

AI_SERVICES = {"Azure OpenAI", "AI Services", "Machine Learning", "AI Search"}

# api-version for associated resources created with an ML workspace.
_LINKED_API = {
    "microsoft.storage/storageaccounts": "2023-05-01",
    "microsoft.keyvault/vaults": "2023-07-01",
    "microsoft.insights/components": "2020-02-02",
    "microsoft.containerregistry/registries": "2023-07-01",
}


def _type_of(arm_id: str) -> str:
    parts = arm_id.strip("/").split("/")
    lowered = [p.lower() for p in parts]
    i = lowered.index("providers")
    return f"{lowered[i + 1]}/{lowered[i + 2]}"


def delete_azure_ai_resource(
    session: AzureSession, resource: CloudResource, progress: Callable[[str], None]
) -> None:
    arm = ArmClient(session.credential)
    x = resource.extra
    rid = x["arm_id"]
    match resource.service:
        case "Azure OpenAI" | "AI Services":
            _delete_cognitive_account(arm, session, resource, progress)
        case "Machine Learning" if resource.resource_type in {
            "Workspace",
            "AI Foundry Hub",
            "AI Foundry Project",
        }:
            _delete_workspace(arm, x, progress)
        case "Machine Learning":
            progress(f"Deleting {resource.resource_type.lower()} {resource.name}...")
            arm.delete(
                rid,
                ML_API,
                **({"underlyingResourceAction": "Delete"} if "/computes/" in rid.lower() else {}),
            )
        case "AI Search":
            arm.delete(rid, SEARCH_API)
        case _:
            raise ArmError(400, f"Deletion not supported for {resource.service}")


def _delete_cognitive_account(arm, session, resource, progress) -> None:
    x = resource.extra
    rid = x["arm_id"]
    for name in x.get("deployments", []):
        progress(f"Deleting model deployment {name}...")
        arm.delete(f"{rid}/deployments/{name}", COGNITIVE_API)
    progress(f"Deleting {resource.name}...")
    arm.delete(rid, COGNITIVE_API)
    progress("Purging the soft-deleted account...")
    rg = parse_id(rid).get("resource_group", "")
    try:
        arm.delete(
            f"/subscriptions/{session.subscription_id}/providers/Microsoft.CognitiveServices"
            f"/locations/{resource.region}/resourceGroups/{rg}/deletedAccounts/{resource.name}",
            COGNITIVE_API,
        )
    except ArmError:
        pass  # Purge is best-effort; billing already stopped with the delete.


def _delete_workspace(arm: ArmClient, x: dict, progress: Callable[[str], None]) -> None:
    for project_id in x.get("project_ids", []):
        progress(f"Deleting AI Foundry project {project_id.rsplit('/', 1)[-1]}...")
        arm.delete(project_id, ML_API, forceToPurge="true")
    for endpoint_id in x.get("endpoint_ids", []) + x.get("serverless_ids", []):
        progress(f"Deleting endpoint {endpoint_id.rsplit('/', 1)[-1]}...")
        arm.delete(endpoint_id, ML_API)
    for compute_id in x.get("compute_ids", []):
        progress(f"Deleting compute {compute_id.rsplit('/', 1)[-1]}...")
        arm.delete(compute_id, ML_API, underlyingResourceAction="Delete")
    progress("Deleting and purging the workspace...")
    arm.delete(x["arm_id"], ML_API, forceToPurge="true")
    for linked in x.get("exclusive_ids", []):
        api = _LINKED_API.get(_type_of(linked))
        if not api:
            continue
        progress(f"Deleting associated {linked.rsplit('/', 1)[-1]}...")
        try:
            arm.delete(linked, api)
        except ArmError as exc:
            progress(f"Could not delete {linked.rsplit('/', 1)[-1]}: {exc}")
