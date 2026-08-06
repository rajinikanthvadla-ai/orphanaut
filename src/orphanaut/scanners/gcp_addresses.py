"""GCP static external IP scanner."""

from __future__ import annotations

from googleapiclient import discovery

from orphanaut.scanners.gcp_base import GcpBaseScanner


class GcpAddressScanner(GcpBaseScanner):
    service_name = "Compute"

    def scan(self) -> list:
        compute = discovery.build(
            "compute",
            "v1",
            credentials=self.session.credentials,
            cache_discovery=False,
        )
        resources = []
        request = compute.addresses().aggregatedList(project=self.session.project_id)
        while request is not None:
            response = request.execute()
            for scope_key, data in response.get("items", {}).items():
                scope = scope_key.removeprefix("regions/").removeprefix("zones/")
                if scope_key.startswith("regions/"):
                    region = scope
                else:
                    region = "-".join(scope.split("-")[:-1])
                if region not in self.regions and not any(
                    scope.startswith(selected) for selected in self.regions
                ):
                    continue
                for address in data.get("addresses", []):
                    addr_id = str(address.get("id", ""))
                    name = address.get("name", "")
                    ip = address.get("address", "N/A")
                    in_use = "in use" if address.get("users") else "reserved"
                    resources.append(
                        self._resource(
                            resource_id=addr_id,
                            name=name,
                            service="Compute",
                            resource_type="Static IP",
                            region=region,
                            status=in_use,
                            details=f"IP: {ip}",
                            deletable=not bool(address.get("users")),
                            extra={"address_name": name, "region": region},
                        )
                    )
            request = compute.addresses().aggregatedList_next(
                previous_request=request,
                previous_response=response,
            )
        return resources
