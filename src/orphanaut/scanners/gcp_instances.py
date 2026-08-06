"""GCP Compute Engine instance scanner."""

from __future__ import annotations

from googleapiclient import discovery

from orphanaut.scanners.gcp_base import GcpBaseScanner


class GcpInstanceScanner(GcpBaseScanner):
    service_name = "Compute"

    def scan(self) -> list:
        compute = discovery.build(
            "compute",
            "v1",
            credentials=self.session.credentials,
            cache_discovery=False,
        )
        resources = []
        request = compute.instances().aggregatedList(project=self.session.project_id)
        while request is not None:
            response = request.execute()
            for zone_key, data in response.get("items", {}).items():
                zone = zone_key.removeprefix("zones/")
                region = "-".join(zone.split("-")[:-1])
                if not self._zone_in_regions(zone):
                    continue
                for instance in data.get("instances", []):
                    instance_id = str(instance.get("id", ""))
                    name = instance.get("name", "")
                    machine = instance.get("machineType", "").rsplit("/", 1)[-1]
                    status = instance.get("status", "unknown").lower()
                    resources.append(
                        self._resource(
                            resource_id=instance_id,
                            name=name,
                            service="Compute",
                            resource_type="Instance",
                            region=region,
                            status=status,
                            details=f"Type: {machine}, Zone: {zone}",
                            extra={"zone": zone, "instance_name": name},
                        )
                    )
            request = compute.instances().aggregatedList_next(
                previous_request=request,
                previous_response=response,
            )
        return resources
