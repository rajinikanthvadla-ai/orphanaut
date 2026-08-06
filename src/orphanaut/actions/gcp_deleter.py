"""GCP resource deletion handlers."""

from __future__ import annotations

from googleapiclient import discovery
from googleapiclient.errors import HttpError

from orphanaut.actions.deleter import DeleteError
from orphanaut.models import CloudResource
from orphanaut.providers.session import GcpSession


def delete_gcp_resource(session: GcpSession, resource: CloudResource) -> None:
    if not resource.deletable:
        raise DeleteError(
            f"{resource.resource_type} '{resource.name or resource.resource_id}' "
            "is in use or protected and cannot be deleted."
        )

    project = session.project_id
    try:
        match (resource.service, resource.resource_type):
            case ("Compute", "Instance"):
                compute = discovery.build(
                    "compute", "v1", credentials=session.credentials, cache_discovery=False
                )
                compute.instances().delete(
                    project=project,
                    zone=resource.extra["zone"],
                    instance=resource.extra["instance_name"],
                ).execute()

            case ("Compute", "Disk"):
                compute = discovery.build(
                    "compute", "v1", credentials=session.credentials, cache_discovery=False
                )
                compute.disks().delete(
                    project=project,
                    zone=resource.extra["zone"],
                    disk=resource.extra["disk_name"],
                ).execute()

            case ("Compute", "Static IP"):
                compute = discovery.build(
                    "compute", "v1", credentials=session.credentials, cache_discovery=False
                )
                region = resource.extra.get("region", resource.region)
                compute.addresses().delete(
                    project=project,
                    region=region,
                    address=resource.extra["address_name"],
                ).execute()

            case ("Storage", "Bucket"):
                storage = discovery.build(
                    "storage", "v1", credentials=session.credentials, cache_discovery=False
                )
                bucket = resource.extra["bucket_name"]
                request = storage.objects().list(bucket=bucket)
                while request is not None:
                    response = request.execute()
                    for item in response.get("items", []):
                        storage.objects().delete(bucket=bucket, object=item["name"]).execute()
                    request = storage.objects().list_next(
                        previous_request=request,
                        previous_response=response,
                    )
                storage.buckets().delete(bucket=bucket).execute()

            case _:
                raise DeleteError(
                    f"Deletion not supported for {resource.service} / {resource.resource_type}"
                )
    except HttpError as exc:
        raise DeleteError(str(exc)) from exc
