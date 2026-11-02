"""Tests for Azure and Google Cloud AI scanners (fake REST clients, no network)."""

from orphanaut.dependencies import Action, impact_tree
from orphanaut.providers.azure_arm import parse_id
from orphanaut.providers.gcp_rest import GcpApiError
from orphanaut.providers.session import AzureSession, GcpSession
from orphanaut.scanners import azure_ai, gcp_vertex

SUB = "/subscriptions/sub1"
RG = f"{SUB}/resourceGroups/rg1/providers"


class FakeArm:
    def __init__(self, listings: dict[str, list[dict]]) -> None:
        self.listings = listings

    def list(self, path, api_version=None, **_params):
        return iter(self.listings.get(path, []))


def _azure(cls, listings):
    scanner = cls(AzureSession(credential=None, subscription_id="sub1"), {"eastus"})
    scanner.arm = lambda: FakeArm(listings)
    return scanner


def test_parse_arm_id():
    parts = parse_id(f"{RG}/Microsoft.Search/searchServices/s1")
    assert parts == {"name": "s1", "subscription": "sub1", "resource_group": "rg1"}


def test_azure_openai_account_lists_deployments_and_ptu_cost():
    acct = f"{RG}/Microsoft.CognitiveServices/accounts/oai"
    scanner = _azure(azure_ai.AzureAiServicesScanner, {
        f"{SUB}/providers/Microsoft.CognitiveServices/accounts": [
            {"id": acct, "name": "oai", "kind": "OpenAI", "location": "eastus",
             "sku": {"name": "S0"}, "properties": {"provisioningState": "Succeeded"}},
            {"id": "other", "name": "elsewhere", "kind": "OpenAI", "location": "westeurope"},
        ],
        f"{acct}/deployments": [
            {"name": "gpt-4o", "sku": {"name": "ProvisionedManaged", "capacity": 50},
             "properties": {"model": {"name": "gpt-4o", "version": "2024-08-06"}}},
            {"name": "mini", "sku": {"name": "GlobalStandard", "capacity": 10}},
        ],
    })
    [account] = scanner.scan()
    assert account.service == "Azure OpenAI"
    assert account.extra["deployments"] == ["gpt-4o", "mini"]
    assert account.extra["monthly_cost"] == 50 * 730
    kinds = [c.kind for c in impact_tree(account).children]
    assert kinds.count("Model deployment") == 2
    assert "Soft-deleted copy" in kinds


def test_azure_ml_workspace_keeps_shared_storage():
    ws1 = f"{RG}/Microsoft.MachineLearningServices/workspaces/ws1"
    ws2 = f"{RG}/Microsoft.MachineLearningServices/workspaces/ws2"
    shared = f"{RG}/Microsoft.Storage/storageAccounts/shared"
    own_kv = f"{RG}/Microsoft.KeyVault/vaults/kv1"
    scanner = _azure(azure_ai.AzureMachineLearningScanner, {
        f"{SUB}/providers/Microsoft.MachineLearningServices/workspaces": [
            {"id": ws1, "name": "ws1", "location": "eastus",
             "properties": {"storageAccount": shared, "keyVault": own_kv}},
            {"id": ws2, "name": "ws2", "location": "eastus",
             "properties": {"storageAccount": shared}},
        ],
        f"{ws1}/computes": [
            {"id": f"{ws1}/computes/ci", "name": "ci", "properties": {
                "computeType": "ComputeInstance",
                "properties": {"vmSize": "Standard_DS3_v2", "state": "Running"}}},
        ],
    })
    resources = scanner.scan()
    ws = next(r for r in resources if r.name == "ws1")
    assert ws.extra["exclusive_ids"] == [own_kv]
    actions = {c.kind: c.action for c in impact_tree(ws).children}
    assert actions["Storage account"] == Action.KEEP
    assert actions["Key vault"] == Action.DELETE
    compute = next(r for r in resources if r.resource_type == "Compute Instance")
    assert compute.extra["monthly_cost"] > 0


class FakeRest:
    def __init__(self, pages: dict[str, list[dict]], disabled: bool = False) -> None:
        self.pages = pages
        self.disabled = disabled

    def list(self, url, key, **_params):
        if self.disabled:
            raise GcpApiError(403, "Vertex AI API has not been used in project", "SERVICE_DISABLED")
        for suffix, items in self.pages.items():
            if url.endswith(suffix):
                return iter(items)
        return iter([])


def _gcp(cls, rest):
    scanner = cls(GcpSession(credentials=None, project_id="p1"), {"us-central1"})
    scanner.rest = lambda: rest
    return scanner


def test_vertex_endpoint_lists_deployed_models():
    name = "projects/p1/locations/us-central1/endpoints/123"
    rest = FakeRest({"/endpoints": [{"name": name, "displayName": "chat", "deployedModels": [
        {"id": "d1", "model": "projects/p1/locations/us-central1/models/9",
         "displayName": "gemma", "dedicatedResources": {
             "machineSpec": {"machineType": "g2-standard-8", "acceleratorType": "NVIDIA_L4",
                             "acceleratorCount": 1}, "minReplicaCount": 1}}]}]})
    [endpoint] = _gcp(gcp_vertex.VertexEndpointScanner, rest).scan()
    assert endpoint.region == "us-central1"
    assert endpoint.extra["deployed_ids"] == ["d1"]
    assert endpoint.extra["monthly_cost"] > 0
    assert impact_tree(endpoint).children[0].kind == "Deployed model"


def test_vertex_deployed_model_is_locked():
    rest = FakeRest({"/models": [{"name": "projects/p1/locations/us-central1/models/9",
                                  "deployedModels": [{"endpoint": "e"}]}]})
    [model] = _gcp(gcp_vertex.VertexModelScanner, rest).scan()
    assert model.deletable is False


def test_vertex_disabled_api_returns_nothing():
    assert _gcp(gcp_vertex.VertexEndpointScanner, FakeRest({}, disabled=True)).scan() == []


def test_machine_hourly_adds_gpus():
    cpu = gcp_vertex.machine_hourly("n1-standard-4")
    gpu = gcp_vertex.machine_hourly("n1-standard-4", "NVIDIA_TESLA_T4", 1)
    assert gpu > cpu > 0
