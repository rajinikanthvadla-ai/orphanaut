"""In-app guide text: how to connect, what gets scanned, permissions and safety."""

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
<h3>How it works</h3>
<ol>
<li><b>Pick a cloud</b> with the tabs at the top — each cloud keeps its own connection and
results.</li>
<li><b>Connect</b> on the left: paste keys, sign in with your browser, or reuse a login that is
already on this computer.</li>
<li><b>Choose regions</b> you used (start with one — it's fastest) and click <b>Scan</b>.</li>
<li>Use the <b>category tabs</b> (AI &amp; ML, Compute, Storage…) to focus on what matters.</li>
<li><b>Click a row</b> — the <b>Delete impact map</b> on the right shows every associated item that
will be deleted, stopped, or kept with it.</li>
<li>Select what you don't need and press <b>Delete selected</b>. You confirm once more before
anything is removed.</li>
</ol>
"""

_SAFETY = """
<h3>Safety first</h3>
<ul>
<li>Credentials stay in memory only — nothing is saved to disk or sent anywhere except the cloud
provider itself.</li>
<li>Nothing is deleted until you confirm in the delete dialog. Deletions cannot be undone.</li>
<li>Items marked <span style="color:#067647"><b>Kept — review</b></span> in the map are never
touched (your S3/Blob/GCS data, IAM roles, shared resources). Clean them up yourself if needed.</li>
<li>Items in use or under a commitment are locked and can't be selected for deletion.</li>
<li>Monthly costs are rough list-price estimates to show scale — not your bill.</li>
</ul>
"""

GUIDES: dict[CloudProvider, str] = {
    CloudProvider.AWS: """
<h2>Amazon Web Services</h2>
<h3>Ways to connect</h3>
<p><b>Access keys</b> — the simplest for students. In the AWS Console click your name (top right)
→ <b>Security credentials</b> → <b>Access keys</b> → <b>Create access key</b>. Paste the
<i>Access Key ID</i> (starts with AKIA) and the <i>Secret Access Key</i>. Temporary keys (ASIA…)
also need the <i>Session token</i>.</p>
<p><b>Sign in with browser</b> — for AWS IAM Identity Center (SSO). Enter your access portal URL
(like <i>https://my-org.awsapps.com/start</i>) and its region, click <b>Sign in with browser</b>,
confirm the code in the page that opens, then pick the account and role.</p>
<p><b>This computer</b> — reuses a profile from <i>aws configure</i> or <i>aws sso login</i>, or the
AWS_* environment variables.</p>
<h3>Permissions</h3>
<p>Scanning needs read access (the AWS managed <b>ReadOnlyAccess</b> policy is enough). Deleting
needs delete rights for each service — in a personal or lab account <b>AdministratorAccess</b> or
<b>PowerUserAccess</b> works.</p>
<h3>What gets found</h3>
<p><b>AI &amp; ML</b>: SageMaker Studio domains (user profiles, spaces, apps, home EFS), running
Studio apps, endpoints (+ configs, models, inference components), notebook instances, training /
processing / tuning / transform jobs, MLflow servers, HyperPod clusters, feature groups; Bedrock
knowledge bases (+ data sources and the OpenSearch Serverless vector store), agents, provisioned
throughput (e.g. for Claude), custom &amp; imported models, running fine-tuning and batch jobs;
OpenSearch Serverless, Kendra, Comprehend endpoints, Rekognition Custom Labels.</p>
<p><b>Everything else</b>: EC2, EBS, snapshots, Elastic IPs, NAT gateways, load balancers, VPC
endpoints, security groups, RDS, DynamoDB, ElastiCache, Lambda, ECS, EKS (+ node groups), S3,
Route 53, CloudWatch logs, Lightsail.</p>
""",
    CloudProvider.AZURE: """
<h2>Microsoft Azure</h2>
<h3>Ways to connect</h3>
<p><b>Sign in with browser</b> — the easiest: sign in with your Microsoft / university account in
the browser window that opens, then pick a subscription. Enter a Tenant ID only if you have more
than one directory.</p>
<p><b>This computer</b> — reuses <i>az login</i>, <i>azd auth login</i>, Azure PowerShell, or the
AZURE_* environment variables.</p>
<p><b>Service principal</b> — for automation: Tenant ID, Client (application) ID and a Client
Secret from an App Registration in Microsoft Entra ID.</p>
<h3>Permissions</h3>
<p><b>Reader</b> on the subscription to scan, <b>Contributor</b> to delete.</p>
<h3>What gets found</h3>
<p><b>AI &amp; ML</b>: Azure OpenAI and AI Services accounts (with model deployments, AI Foundry
projects, provisioned throughput), Azure Machine Learning workspaces / AI Foundry hubs (with
compute instances, clusters, online and serverless endpoints, and the storage account, key vault,
App Insights and registry created with them), Azure AI Search services.</p>
<p><b>Everything else</b>: virtual machines, managed disks, public IPs, storage accounts.</p>
""",
    CloudProvider.GCP: """
<h2>Google Cloud</h2>
<h3>Ways to connect</h3>
<p><b>Sign in with browser</b> — sign in with your Google account in the browser, then pick a
project. This uses the free <a href="https://cloud.google.com/sdk/docs/install">gcloud CLI</a>
behind the scenes, so install it first.</p>
<p><b>This computer</b> — reuses Application Default Credentials from
<i>gcloud auth application-default login</i> or GOOGLE_APPLICATION_CREDENTIALS.</p>
<p><b>Service account key</b> — IAM &amp; Admin → Service Accounts → your account → Keys → Add key
→ JSON. Pick the downloaded file.</p>
<h3>Permissions</h3>
<p><b>Viewer</b> on the project to scan, <b>Editor</b> to delete. APIs that are not enabled are
skipped automatically (nothing can exist there).</p>
<h3>What gets found</h3>
<p><b>AI &amp; ML</b>: Vertex AI endpoints (+ deployed models), models, Vector Search index
endpoints and indexes, running custom / pipeline / tuning jobs, Agent Engine agents, Colab
Enterprise runtimes, Feature Store online stores, Vertex AI Workbench instances, Vertex AI Search
apps and data stores.</p>
<p><b>Everything else</b>: Compute Engine instances, disks, static IPs, Cloud Storage buckets.</p>
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
        self.setWindowTitle("Orphanaut guide")
        self.resize(760, 640)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(_scroll_label(_STEPS + _SAFETY), "Getting started")
        for cloud in CloudProvider:
            tabs.addTab(_scroll_label(GUIDES[cloud]), cloud.long_label)
        if provider is not None:
            tabs.setCurrentIndex(list(CloudProvider).index(provider) + 1)
        layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
