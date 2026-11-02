"""Group services into the category tabs shown in each cloud workspace."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orphanaut.models import CloudResource

ALL = "All resources"
AI_ML = "AI & ML"
COMPUTE = "Compute"
STORAGE = "Storage"
NETWORKING = "Networking"
DATABASES = "Databases"
OTHER = "Monitoring & other"

# Order of the category tabs in the UI.
CATEGORIES = [ALL, AI_ML, COMPUTE, STORAGE, NETWORKING, DATABASES, OTHER]

_BY_SERVICE: dict[str, str] = {
    # AWS
    "SageMaker": AI_ML,
    "Bedrock": AI_ML,
    "OpenSearch Serverless": AI_ML,
    "Kendra": AI_ML,
    "Comprehend": AI_ML,
    "Rekognition": AI_ML,
    "EC2": COMPUTE,
    "Lambda": COMPUTE,
    "ECS": COMPUTE,
    "EKS": COMPUTE,
    "Lightsail": COMPUTE,
    "EBS": STORAGE,
    "S3": STORAGE,
    "VPC": NETWORKING,
    "ELB": NETWORKING,
    "Route53": NETWORKING,
    "RDS": DATABASES,
    "DynamoDB": DATABASES,
    "ElastiCache": DATABASES,
    "CloudWatch": OTHER,
    # Azure
    "Azure OpenAI": AI_ML,
    "AI Services": AI_ML,
    "Machine Learning": AI_ML,
    "AI Search": AI_ML,
    "Network": NETWORKING,
    # GCP
    "Vertex AI": AI_ML,
    # Azure + GCP share "Compute" / "Storage" service names.
    "Compute": COMPUTE,
    "Storage": STORAGE,
}

# Some generic services mix compute and networking resource types.
_BY_TYPE: dict[str, str] = {
    "Elastic IP": NETWORKING,
    "Static IP": NETWORKING,
    "Public IP": NETWORKING,
    "Managed Disk": STORAGE,
    "Disk": STORAGE,
    "Snapshot": STORAGE,
}


def category_for(resource: CloudResource) -> str:
    return _BY_TYPE.get(resource.resource_type) or _BY_SERVICE.get(resource.service, OTHER)
