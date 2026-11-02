"""Cascade deletion for Google Cloud AI resources (Vertex AI REST)."""

from __future__ import annotations

from collections.abc import Callable

from orphanaut.models import CloudResource
from orphanaut.providers.gcp_rest import GcpRest, vertex_base
from orphanaut.providers.session import GcpSession

AI_SERVICES = {"Vertex AI"}


def _base_for(name: str, region: str) -> str:
    if name.startswith("projects/") and "/instances/" in name:
        return "https://notebooks.googleapis.com/v2"
    if "/collections/" in name:
        host = (
            "discoveryengine.googleapis.com"
            if region == "global"
            else (f"{region}-discoveryengine.googleapis.com")
        )
        return f"https://{host}/v1"
    return vertex_base(region)


def delete_gcp_ai_resource(
    session: GcpSession, resource: CloudResource, progress: Callable[[str], None]
) -> None:
    rest = GcpRest(session.credentials, session.project_id)
    name = resource.extra["rest_name"]
    base = _base_for(name, resource.region)
    url = f"{base}/{name}"

    match resource.resource_type:
        case "Endpoint":
            for deployed_id in resource.extra.get("deployed_ids", []):
                progress(f"Undeploying model {deployed_id}...")
                op = rest.post(f"{url}:undeployModel", {"deployedModelId": deployed_id})
                rest.wait(op, base)
            progress("Deleting the endpoint...")
            rest.wait(rest.delete(url), base)
        case "Vector Search Endpoint":
            for deployed_id in resource.extra.get("deployed_ids", []):
                progress(f"Undeploying index {deployed_id}...")
                op = rest.post(f"{url}:undeployIndex", {"deployedIndexId": deployed_id})
                rest.wait(op, base)
            progress("Deleting the index endpoint...")
            rest.wait(rest.delete(url), base)
        case "Custom Job" | "Training Pipeline" | "Tuning Job" | "Pipeline Run":
            rest.post(f"{url}:cancel")
        case "Agent Engine" | "Feature Online Store":
            rest.wait(rest.delete(url, force="true"), base)
        case "Search App" | "Data Store":
            rest.delete(url)
        case _:
            progress(f"Deleting {resource.resource_type.lower()}...")
            rest.wait(rest.delete(url), base)
