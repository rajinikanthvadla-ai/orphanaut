"""Azure resource deletion handlers."""

from __future__ import annotations

from azure.core.exceptions import HttpResponseError
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.storage import StorageManagementClient

from orphanaut.actions.deleter import DeleteError
from orphanaut.models import CloudResource
from orphanaut.providers.session import AzureSession


def delete_azure_resource(session: AzureSession, resource: CloudResource) -> None:
    if not resource.deletable:
        raise DeleteError(
            f"{resource.resource_type} '{resource.name or resource.resource_id}' "
            "is in use or protected and cannot be deleted."
        )

    rg = resource.extra.get("resource_group", "")
    compute = ComputeManagementClient(session.credential, session.subscription_id)
    network = NetworkManagementClient(session.credential, session.subscription_id)
    storage = StorageManagementClient(session.credential, session.subscription_id)

    try:
        match (resource.service, resource.resource_type):
            case ("Compute", "Virtual Machine"):
                compute.virtual_machines.begin_delete(rg, resource.extra["vm_name"]).result()

            case ("Compute", "Managed Disk"):
                compute.disks.begin_delete(rg, resource.extra["disk_name"]).result()

            case ("Network", "Public IP"):
                network.public_ip_addresses.begin_delete(rg, resource.extra["ip_name"]).result()

            case ("Storage", "Storage Account"):
                storage.storage_accounts.delete(rg, resource.extra["account_name"])

            case _:
                raise DeleteError(
                    f"Deletion not supported for {resource.service} / {resource.resource_type}"
                )
    except HttpResponseError as exc:
        raise DeleteError(exc.message or str(exc)) from exc
