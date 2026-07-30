"""Load balancer scanner (ALB, NLB, CLB)."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class LoadBalancerScanner(BaseScanner):
    service_name = "ELB"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        errors: list[ClientError] = []
        try:
            elbv2 = self.client("elbv2")
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
        except ClientError as exc:
            errors.append(exc)

        try:
            elb = self.client("elb")
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
        except ClientError as exc:
            errors.append(exc)

        if errors and not resources:
            raise errors[0]
        return resources
