"""Azure managed disk scanner."""

from __future__ import annotations

from azure.mgmt.compute import ComputeManagementClient

from orphanaut.scanners.azure_base import AzureBaseScanner


class AzureDiskScanner(AzureBaseScanner):
    service_name = "Compute"

    def scan(self) -> list:
        client = ComputeManagementClient(self.session.credential, self.session.subscription_id)
        resources = []
        for disk in client.disks.list():
            if not self._in_region(disk.location):
                continue
            disk_id = disk.id or ""
            name = disk.name or ""
            size = disk.disk_size_gb or 0
            sku = disk.sku.name if disk.sku else "unknown"
            attached = "attached" if disk.managed_by else "unattached"
            resources.append(
                self._resource(
                    resource_id=disk_id,
                    name=name,
                    service="Compute",
                    resource_type="Managed Disk",
                    region=disk.location,
                    status=f"{disk.disk_state} ({attached})" if disk.disk_state else attached,
                    details=f"{size} GiB, {sku}",
                    deletable=not bool(disk.managed_by),
                    extra={
                        "resource_group": disk.id.split("/")[4] if disk.id else "",
                        "disk_name": name,
                    },
                )
            )
        return resources
