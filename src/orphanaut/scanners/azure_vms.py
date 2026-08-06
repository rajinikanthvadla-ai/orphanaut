"""Azure virtual machine scanner."""

from __future__ import annotations

from azure.mgmt.compute import ComputeManagementClient

from orphanaut.scanners.azure_base import AzureBaseScanner


class AzureVmScanner(AzureBaseScanner):
    service_name = "Compute"

    def scan(self) -> list:
        client = ComputeManagementClient(self.session.credential, self.session.subscription_id)
        resources = []
        for vm in client.virtual_machines.list_all():
            if not self._in_region(vm.location):
                continue
            vm_id = vm.id or ""
            name = vm.name or vm_id.rsplit("/", 1)[-1]
            size = vm.hardware_profile.vm_size if vm.hardware_profile else "unknown"
            power = vm.provisioning_state or "unknown"
            resources.append(
                self._resource(
                    resource_id=vm_id,
                    name=name,
                    service="Compute",
                    resource_type="Virtual Machine",
                    region=vm.location,
                    status=power,
                    details=f"Size: {size}",
                    extra={"resource_group": vm.id.split("/")[4] if vm.id else "", "vm_name": name},
                )
            )
        return resources
