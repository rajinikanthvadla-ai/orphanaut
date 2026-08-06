"""GCP Cloud Storage bucket scanner."""

from __future__ import annotations

from googleapiclient import discovery

from orphanaut.scanners.gcp_base import GcpBaseScanner


class GcpStorageScanner(GcpBaseScanner):
    service_name = "Storage"

    def scan(self) -> list:
        storage = discovery.build(
            "storage",
            "v1",
            credentials=self.session.credentials,
            cache_discovery=False,
        )
        resources = []
        request = storage.buckets().list(project=self.session.project_id)
        while request is not None:
            response = request.execute()
            for bucket in response.get("items", []):
                location = (bucket.get("location", "") or "").lower()
                if not self._location_in_regions(location):
                    continue
                name = bucket.get("name", "")
                storage_class = bucket.get("storageClass", "STANDARD")
                resources.append(
                    self._resource(
                        resource_id=name,
                        name=name,
                        service="Storage",
                        resource_type="Bucket",
                        region=location,
                        status="active",
                        details=f"Class: {storage_class}",
                        extra={"bucket_name": name},
                    )
                )
            request = storage.buckets().list_next(
                previous_request=request,
                previous_response=response,
            )
        return resources
