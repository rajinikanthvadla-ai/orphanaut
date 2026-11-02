"""In-app guide: sign-in options, permissions and what gets scanned."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from orphanaut.models import CloudProvider

_STEPS = """
<h3>How to use it</h3>
<ol>
<li>Pick a cloud at the top.</li>
<li>Sign in on the left.</li>
<li>Choose your regions and click Scan.</li>
<li>Tick the resources you want to remove. The map on the right shows what they are connected
to.</li>
<li>Click Delete and confirm.</li>
</ol>
"""

_SAFETY = """
<h3>Good to know</h3>
<ul>
<li>Your keys stay in memory and are never saved.</li>
<li>Nothing is deleted until you confirm.</li>
<li>Items marked <b>kept</b> on the map are not touched, for example your S3 data or IAM roles.</li>
<li>Resources that are in use or under a commitment are locked.</li>
<li>Costs are rough estimates, not your bill.</li>
</ul>
"""

GUIDES: dict[CloudProvider, str] = {
    CloudProvider.AWS: """
<h2>AWS</h2>
<h3>Sign in</h3>
<p><b>Access keys:</b> AWS Console &gt; your name &gt; Security credentials &gt; Create access key.
Keys starting with ASIA also need the session token.</p>
<p><b>Browser:</b> for IAM Identity Center (SSO). Enter your access portal URL and region,
approve the code in the browser, then pick an account and role.</p>
<p><b>This computer:</b> uses a profile from <i>aws configure</i> or <i>aws sso login</i>.</p>
<h3>Permissions</h3>
<p>ReadOnlyAccess to scan. To delete, use PowerUserAccess or AdministratorAccess in a lab
account.</p>
<h3>What it finds</h3>
<p><b>AI:</b> SageMaker domains, apps, endpoints, notebooks, jobs, MLflow, HyperPod, feature
groups. Bedrock knowledge bases, agents, provisioned throughput, custom models. OpenSearch
Serverless, Kendra, Comprehend, Rekognition.</p>
<p><b>Other:</b> EC2, EBS, snapshots, Elastic IPs, NAT gateways, load balancers, VPC endpoints,
security groups, RDS, DynamoDB, ElastiCache, Lambda, ECS, EKS, S3, Route 53, CloudWatch logs,
Lightsail.</p>
""",
    CloudProvider.AZURE: """
<h2>Azure</h2>
<h3>Sign in</h3>
<p><b>Browser:</b> sign in with your Microsoft account, then pick a subscription.</p>
<p><b>This computer:</b> uses <i>az login</i>, <i>azd</i> or Azure PowerShell.</p>
<p><b>Service principal:</b> tenant ID, client ID and client secret from an App
Registration.</p>
<h3>Permissions</h3>
<p>Reader to scan, Contributor to delete.</p>
<h3>What it finds</h3>
<p><b>AI:</b> Azure OpenAI and AI Services accounts, AI Foundry, Azure Machine Learning
workspaces with their compute and endpoints, AI Search.</p>
<p><b>Other:</b> virtual machines, disks, public IPs, storage accounts.</p>
""",
    CloudProvider.GCP: """
<h2>Google Cloud</h2>
<h3>Sign in</h3>
<p><b>Browser:</b> needs the <a href="https://cloud.google.com/sdk/docs/install">gcloud CLI</a>.
Sign in with your Google account, then pick a project.</p>
<p><b>This computer:</b> uses <i>gcloud auth application-default login</i>.</p>
<p><b>Service account key:</b> IAM &amp; Admin &gt; Service accounts &gt; Keys &gt; Add key &gt;
JSON.</p>
<h3>Permissions</h3>
<p>Viewer to scan, Editor to delete. APIs that aren't enabled are skipped.</p>
<h3>What it finds</h3>
<p><b>AI:</b> Vertex AI endpoints, models, Vector Search, running jobs, Agent Engine,
Workbench, Colab runtimes, Feature Store, Vertex AI Search.</p>
<p><b>Other:</b> VM instances, disks, static IPs, Cloud Storage buckets.</p>
""",
}


def guide_html(provider: CloudProvider) -> str:
    return GUIDES[provider] + _STEPS + _SAFETY


def _scroll_label(html: str) -> QScrollArea:
    label = QLabel(html)
    label.setObjectName("guide")
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setOpenExternalLinks(True)
    label.setAlignment(Qt.AlignmentFlag.AlignTop)
    label.setContentsMargins(18, 12, 18, 18)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(label)
    return scroll


class GuideDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, provider: CloudProvider | None = None):
        super().__init__(parent)
        self.setWindowTitle("Guide")
        self.resize(760, 640)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(_scroll_label(_STEPS + _SAFETY), "Start")
        for cloud in CloudProvider:
            tabs.addTab(_scroll_label(GUIDES[cloud]), cloud.long_label)
        if provider is not None:
            tabs.setCurrentIndex(list(CloudProvider).index(provider) + 1)
        layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
