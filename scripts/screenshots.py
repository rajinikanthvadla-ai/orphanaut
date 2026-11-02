"""Render README screenshots with demo data (no cloud account needed).

    python scripts/screenshots.py docs/images
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from orphanaut.auth.router import Choice, ConnectResult
from orphanaut.dependencies import Action, dep
from orphanaut.models import CloudProvider, CloudResource
from orphanaut.providers.session import ProviderSession
from orphanaut.ui.main_window import MainWindow
from orphanaut.ui.styles import apply_theme


def demo_resources() -> list[CloudResource]:
    def r(service, rtype, rid, name, status, details, region="us-east-1", **extra):
        return CloudResource(rid, name, service, rtype, region, status, details, extra=extra)

    return [
        r("SageMaker", "Studio Domain", "d-8xk2lq0abc", "ml-class-domain", "InService",
          "3 user profiles, 2 spaces, 2 running apps", monthly_cost=203.0,
          impact_note="all apps are stopped, then everything inside is removed",
          dependents=[
              dep("User profile", "alice", children=[
                  dep("Studio app", "JupyterLab / default", note="ml.t3.medium"),
                  dep("Space", "alice-space", children=[
                      dep("Studio app", "CodeEditor / default", note="ml.g5.xlarge")])]),
              dep("User profile", "bob"),
              dep("User profile", "carol"),
              dep("Space", "team-shared"),
              dep("EFS file system (home folders)", "fs-0a1b2c3d",
                  note="all notebooks and files in Studio home folders"),
              dep("IAM execution role", "AmazonSageMaker-ExecutionRole", Action.KEEP,
                  "free — remove in IAM if nothing else uses it"),
          ]),
        r("SageMaker", "Endpoint", "llm-endpoint", "llm-endpoint", "InService",
          "1× ml.g5.2xlarge", monthly_cost=1106.0,
          dependents=[dep("Endpoint config", "llm-endpoint-config",
                          children=[dep("Model", "llama-3-8b", note="artifacts in S3 are kept")]),
                      dep("CloudWatch log group", "/aws/sagemaker/Endpoints/llm-endpoint")]),
        r("SageMaker", "Training Job", "bert-finetune-0412", "bert-finetune-0412", "InProgress",
          "RUNNING — billing now", delete_action="delete",
          impact_note="stopped first, then its record is deleted",
          dependents=[dep("Model artifacts in S3", "output path", Action.KEEP)]),
        r("Bedrock", "Knowledge Base", "KB12345", "course-notes-kb", "ACTIVE",
          "OPENSEARCH_SERVERLESS, embeddings titan-embed-text-v2, 1 data source",
          monthly_cost=701.0,
          dependents=[dep("Data source", "s3-course-notes"),
                      dep("OpenSearch Serverless collection (vector store)", "kb-vectors",
                          note="the main cost", children=[dep("Vector index", "bedrock-index")]),
                      dep("Source documents in S3", "bucket", Action.KEEP)]),
        r("Bedrock", "Provisioned Throughput", "arn:pt/claude", "claude-sonnet-pt", "InService",
          "1 model unit of anthropic.claude-sonnet, no commitment", monthly_cost=14600.0),
        r("Bedrock", "Agent", "AGENT01", "study-buddy-agent", "PREPARED",
          "model anthropic.claude-haiku — pay per use", monthly_cost=0.0,
          dependents=[dep("Alias", "prod"), dep("Action group", "lookup-grades")]),
        r("EC2", "Instance", "i-0abc12345", "jupyter-box", "running", "Type: t3.large",
          dependents=[dep("EBS volume", "vol-0123", note="/dev/xvda")]),
        r("EBS", "Volume", "vol-0999", "old-data", "available (unattached)", "100 GiB, gp3"),
        r("S3", "Bucket", "class-datasets-2026", "class-datasets-2026", "active", "Created 2026",
          dependents=[dep("All objects and object versions", "everything in the bucket")]),
        r("VPC", "NAT Gateway", "nat-0f00", "lab-nat", "available", "Public NAT"),
        r("RDS", "DB Instance", "lab-postgres", "lab-postgres", "available",
          "Engine: postgres db.t3.micro"),
    ]


def main(out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow()
    window.resize(1500, 900)
    window.show()
    app.processEvents()
    window.grab().save(str(out / "welcome.png"))

    ws = window.workspace(CloudProvider.AWS)
    session = ProviderSession(CloudProvider.AWS, object(), "123456789012",
                              "arn:aws:iam::123456789012:user/student")
    result = ConnectResult(session, "Account / role",
                           [Choice("123456789012|Admin", "Lab account (123456789012) — Admin")])
    ws._session = session
    ws._connect_result = result
    ws.connect_panel.set_connected(result)
    ws.connect_panel.region_panel.set_provider(CloudProvider.AWS)
    ws.connect_panel.region_panel.set_regions(
        ["us-east-1", "us-east-2", "us-west-2", "eu-west-1", "ap-south-1"],
        default_region="us-east-1")
    ws._tabs.setVisible(True)
    ws._stack.setCurrentIndex(2)
    ws._add_rows(demo_resources())
    ws._update_scan_label()
    window._on_state_changed(CloudProvider.AWS, True)
    ws._tabs.setCurrentIndex(1)  # AI & ML
    ws._table.sortItems(0)
    for row in range(ws._table.rowCount()):
        if ws._table.item(row, 3).text() == "ml-class-domain":
            ws._table.selectRow(row)
    app.processEvents()
    window.grab().save(str(out / "ai-impact-map.png"))
    print("saved to", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/images")
