"""Azure public IP scanner."""

from __future__ import annotations

from azure.mgmt.network import NetworkManagementClient

from orphanaut.scanners.azure_base import AzureBaseScanner


class AzurePublicIpScanner(AzureBaseScanner):
    service_name = "Network"

    def scan(self) -> list:
        client = NetworkManagementClient(self.session.credential, self.session.subscription_id)
        resources = []
        for ip in client.public_ip_addresses.list_all():
            if not self._in_region(ip.location):
                continue
            ip_id = ip.id or ""
            name = ip.name or ""
            address = ip.ip_address or "unassigned"
            attached = "associated" if ip.ip_configuration else "unassociated"
            resources.append(
                self._resource(
                    resource_id=ip_id,
                    name=name,
                    service="Network",
                    resource_type="Public IP",
                    region=ip.location,
                    status=attached,
                    details=f"IP: {address}",
                    deletable=not bool(ip.ip_configuration),
                    extra={
                        "resource_group": ip.id.split("/")[4] if ip.id else "",
                        "ip_name": name,
                    },
                )
            )
        return resources
