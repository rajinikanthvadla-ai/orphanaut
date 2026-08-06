"""GCP persistent disk scanner."""

from __future__ import annotations

from googleapiclient import discovery

from orphanaut.scanners.gcp_base import GcpBaseScanner


class GcpDiskScanner(GcpBaseScanner):
    service_name = "Compute"

    def scan(self) -> list:
        compute = discovery.build(
            "compute",
            "v1",
            credentials=self.session.credentials,
            cache_discovery=False,
        )
        resources = []
        request = compute.disks().aggregatedList(project=self.session.project_id)
        while request is not None:
            response = request.execute()
            for zone_key, data in response.get("items", {}).items():
                zone = zone_key.removeprefix("zones/")
                region = "-".join(zone.split("-")[:-1])
                if not self._zone_in_regions(zone):
                    continue
                for disk in data.get("disks", []):
                    disk_id = str(disk.get("id", ""))
                    name = disk.get("name", "")
                    size = disk.get("sizeGb", 0)
                    disk_type = disk.get("type", "").rsplit("/", 1)[-1]
                    users = disk.get("users", [])
                    attached = "attached" if users else "unattached"
                    resources.append(
                        self._resource(
                            resource_id=disk_id,
                            name=name,
                            service="Compute",
                            resource_type="Disk",
                            region=region,
                            status=f"{disk.get('status', 'unknown')} ({attached})",
                            details=f"{size} GiB, {disk_type}",
                            deletable=not bool(users),
                            extra={"zone": zone, "disk_name": name},
                        )
                    )
            request = compute.disks().aggregatedList_next(
                previous_request=request,
                previous_response=response,
            )
        return resources
