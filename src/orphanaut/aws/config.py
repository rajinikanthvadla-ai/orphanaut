"""Shared boto3 client configuration."""

from botocore.config import Config

AWS_CONFIG = Config(
    connect_timeout=5,
    read_timeout=20,
    retries={"total_max_attempts": 2, "mode": "standard"},
)
