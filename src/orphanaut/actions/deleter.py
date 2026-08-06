"""Resource deletion handlers."""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError

from orphanaut.models import CloudProvider, CloudResource


class DeleteError(Exception):
    """Raised when a resource cannot be deleted."""


def delete_resource(session: object, resource: CloudResource) -> None:
    """Delete a single cloud resource. Raises DeleteError on failure."""
    from orphanaut.actions.azure_deleter import delete_azure_resource
    from orphanaut.actions.gcp_deleter import delete_gcp_resource
    from orphanaut.providers.session import ProviderSession

    if isinstance(session, ProviderSession):
        match session.provider:
            case CloudProvider.AZURE:
                return delete_azure_resource(session.session, resource)
            case CloudProvider.GCP:
                return delete_gcp_resource(session.session, resource)
            case CloudProvider.AWS:
                return _delete_aws_resource(session.session, resource)
            case _:
                raise DeleteError(f"Unsupported provider: {session.provider}")

    return _delete_aws_resource(session, resource)  # type: ignore[arg-type]


def _delete_aws_resource(session: boto3.Session, resource: CloudResource) -> None:
    if not resource.deletable:
        raise DeleteError(
            f"{resource.resource_type} '{resource.name or resource.resource_id}' "
            "is in use or protected and cannot be deleted."
        )

    region = resource.region if resource.region != "global" else "us-east-1"

    try:
        match (resource.service, resource.resource_type):
            case ("EC2", "Instance"):
                session.client("ec2", region_name=region).terminate_instances(
                    InstanceIds=[resource.extra["instance_id"]]
                )

            case ("EBS", "Volume"):
                session.client("ec2", region_name=region).delete_volume(
                    VolumeId=resource.extra["volume_id"]
                )

            case ("EBS", "Snapshot"):
                session.client("ec2", region_name=region).delete_snapshot(
                    SnapshotId=resource.extra["snapshot_id"]
                )

            case ("EC2", "Elastic IP"):
                ec2 = session.client("ec2", region_name=region)
                allocation_id = resource.extra.get("allocation_id")
                if allocation_id:
                    ec2.release_address(AllocationId=allocation_id)
                else:
                    ec2.release_address(PublicIp=resource.extra["public_ip"])

            case ("VPC", "NAT Gateway"):
                session.client("ec2", region_name=region).delete_nat_gateway(
                    NatGatewayId=resource.extra["nat_gateway_id"]
                )

            case ("VPC", "Security Group"):
                session.client("ec2", region_name=region).delete_security_group(
                    GroupId=resource.extra["group_id"]
                )

            case ("ELB", type_) if "Load Balancer" in type_:
                if "Classic" in type_:
                    session.client("elb", region_name=region).delete_load_balancer(
                        LoadBalancerName=resource.extra["load_balancer_name"]
                    )
                else:
                    session.client("elbv2", region_name=region).delete_load_balancer(
                        LoadBalancerArn=resource.extra["load_balancer_arn"]
                    )

            case ("RDS", "DB Instance"):
                session.client("rds", region_name=region).delete_db_instance(
                    DBInstanceIdentifier=resource.extra["db_instance_identifier"],
                    SkipFinalSnapshot=True,
                    DeleteAutomatedBackups=True,
                )

            case ("RDS", "DB Cluster"):
                session.client("rds", region_name=region).delete_db_cluster(
                    DBClusterIdentifier=resource.extra["db_cluster_identifier"],
                    SkipFinalSnapshot=True,
                )

            case ("Lambda", "Function"):
                session.client("lambda", region_name=region).delete_function(
                    FunctionName=resource.extra["function_name"]
                )

            case ("S3", "Bucket"):
                _empty_and_delete_bucket(session, resource.extra["bucket_name"])

            case ("ECS", "Cluster"):
                session.client("ecs", region_name=region).delete_cluster(
                    cluster=resource.extra["cluster_arn"]
                )

            case ("EKS", "Cluster"):
                session.client("eks", region_name=region).delete_cluster(
                    name=resource.extra["cluster_name"]
                )

            case ("ElastiCache", "Cache Cluster"):
                session.client("elasticache", region_name=region).delete_cache_cluster(
                    CacheClusterId=resource.extra["cache_cluster_id"]
                )

            case ("DynamoDB", "Table"):
                session.client("dynamodb", region_name=region).delete_table(
                    TableName=resource.extra["table_name"]
                )

            case ("CloudWatch", "Log Group"):
                session.client("logs", region_name=region).delete_log_group(
                    logGroupName=resource.extra["log_group_name"]
                )

            case ("Route53", "Hosted Zone"):
                _delete_hosted_zone(session, resource.extra["hosted_zone_id"])

            case ("VPC", type_) if "Endpoint" in type_:
                session.client("ec2", region_name=region).delete_vpc_endpoints(
                    VpcEndpointIds=[resource.extra["vpc_endpoint_id"]]
                )

            case ("Lightsail", "Instance"):
                session.client("lightsail", region_name=region).delete_instance(
                    instanceName=resource.extra["instance_name"]
                )

            case _:
                raise DeleteError(
                    f"Deletion not supported for {resource.service} / {resource.resource_type}"
                )

    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        message = exc.response.get("Error", {}).get("Message", str(exc))
        if code == "DependencyViolation":
            message = (
                f"{message} This resource is still referenced by another AWS "
                "resource (e.g. a security group rule, network interface, or "
                "something outside this scan's visibility). Remove the "
                "reference in the AWS Console first, then try deleting again."
            )
        raise DeleteError(message) from exc


def _empty_and_delete_bucket(session: boto3.Session, bucket_name: str) -> None:
    s3 = session.resource("s3")
    bucket = s3.Bucket(bucket_name)

    for version in bucket.object_versions.all():
        version.delete()

    for obj in bucket.objects.all():
        obj.delete()

    bucket.delete()


def _delete_hosted_zone(session: boto3.Session, hosted_zone_id: str) -> None:
    route53 = session.client("route53")
    records = route53.list_resource_record_sets(HostedZoneId=hosted_zone_id)
    changes = []
    for record in records.get("ResourceRecordSets", []):
        if record["Type"] in ("NS", "SOA"):
            continue
        changes.append({"Action": "DELETE", "ResourceRecordSet": record})

    if changes:
        route53.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={"Changes": changes},
        )

    route53.delete_hosted_zone(Id=hosted_zone_id)
