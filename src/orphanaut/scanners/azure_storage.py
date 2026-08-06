"""Azure storage account scanner."""

from __future__ import annotations

from azure.mgmt.storage import StorageManagementClient

from orphanaut.scanners.azure_base import AzureBaseScanner


class AzureStorageScanner(AzureBaseScanner):
    service_name = "Storage"

    def scan(self) -> list:
        client = StorageManagementClient(self.session.credential, self.session.subscription_id)
        resources = []
        for account in client.storage_accounts.list():
            if not self._in_region(account.location):
                continue
            account_id = account.id or ""
            name = account.name or ""
            sku = account.sku.name if account.sku else "unknown"
            kind = account.kind or "Storage"
            resources.append(
                self._resource(
                    resource_id=account_id,
                    name=name,
                    service="Storage",
                    resource_type="Storage Account",
                    region=account.location,
                    status=account.provisioning_state or "unknown",
                    details=f"Kind: {kind}, SKU: {sku}",
                    extra={
                        "resource_group": account.id.split("/")[4] if account.id else "",
                        "account_name": name,
                    },
                )
            )
        return resources
