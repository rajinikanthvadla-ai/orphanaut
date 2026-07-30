"""Load balancer scanner (ALB, NLB, CLB)."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class LoadBalancerScanner(BaseScanner):
    service_name = "ELB"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            elbv2 = self.session.client("elbv2", region_name=self.region)
            paginator = elbv2.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page.get("LoadBalancers", []):
                    lb_type = lb.get("Type", "application").upper()
                    resources.append(
                        AwsResource(
                            resource_id=lb["LoadBalancerArn"],
                            name=lb.get("LoadBalancerName", ""),
                            service="ELB",
                            resource_type=f"{lb_type} Load Balancer",
                            region=self.region,
                            status=lb.get("State", {}).get("Code", "unknown"),
                            details=f"Scheme: {lb.get('Scheme', 'N/A')}",
                            extra={"load_balancer_arn": lb["LoadBalancerArn"]},
                        )
                    )
        except ClientError:
            pass

        try:
            elb = self.session.client("elb", region_name=self.region)
            paginator = elb.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page.get("LoadBalancerDescriptions", []):
                    resources.append(
                        AwsResource(
                            resource_id=lb["LoadBalancerName"],
                            name=lb["LoadBalancerName"],
                            service="ELB",
                            resource_type="Classic Load Balancer",
                            region=self.region,
                            status="active",
                            details=f"Scheme: {lb.get('Scheme', 'N/A')}",
                            extra={"load_balancer_name": lb["LoadBalancerName"]},
                        )
                    )
        except ClientError:
            pass

        return resources
