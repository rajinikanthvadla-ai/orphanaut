"""Tests for AWS AI & ML scanners and cascade deletion (fake clients, no network)."""

import pytest

from orphanaut.actions import aws_ai_deleter
from orphanaut.actions.deleter import delete_resource
from orphanaut.dependencies import Action, impact_tree
from orphanaut.scanners.bedrock import BedrockKnowledgeBaseScanner, BedrockModelScanner
from orphanaut.scanners.sagemaker import (
    SageMakerEndpointScanner,
    SageMakerJobScanner,
    SageMakerStudioScanner,
)
from tests.fakes import FakeClient, FakeSession


def _scanner(cls, clients):
    scanner = cls(FakeSession(clients), "us-east-1", account_id="1")
    scanner.client = lambda name, region=None: clients[name]
    return scanner


def test_studio_domain_map_includes_profiles_spaces_apps_and_efs():
    sm = FakeClient({
        "list_domains": {"Domains": [{"DomainId": "d-1", "DomainName": "class",
                                      "Status": "InService"}]},
        "describe_domain": {"HomeEfsFileSystemId": "fs-1",
                            "DefaultUserSettings": {"ExecutionRole": "arn:aws:iam::1:role/R"}},
        "list_user_profiles": {"UserProfiles": [{"UserProfileName": "alice",
                                                 "Status": "InService"}]},
        "list_spaces": {"Spaces": [
            {"SpaceName": "alice-space", "Status": "InService",
             "OwnershipSettingsSummary": {"OwnerUserProfileName": "alice"}},
            {"SpaceName": "shared", "Status": "InService"},
        ]},
        "list_apps": {"Apps": [
            {"AppType": "JupyterLab", "AppName": "default", "SpaceName": "alice-space",
             "Status": "InService", "ResourceSpec": {"InstanceType": "ml.t3.medium"}},
            {"AppType": "KernelGateway", "AppName": "old", "UserProfileName": "alice",
             "Status": "Deleted"},
        ]},
    })
    resources = _scanner(SageMakerStudioScanner, {"sagemaker": sm}).scan()
    domain = next(r for r in resources if r.resource_type == "Studio Domain")
    apps = [r for r in resources if r.resource_type == "Studio App"]
    assert len(apps) == 1 and apps[0].extra["space_name"] == "alice-space"

    tree = impact_tree(domain)
    kinds = [c.kind for c in tree.children]
    assert kinds[:2] == ["User profile", "Space"]
    alice = tree.children[0]
    assert alice.children[0].kind == "Space"
    assert alice.children[0].children[0].kind == "Studio app"
    assert any(c.kind.startswith("EFS") and c.action == Action.DELETE for c in tree.children)
    assert any(c.kind == "IAM execution role" and c.action == Action.KEEP for c in tree.children)
    assert domain.extra["monthly_cost"] > 0


def test_endpoint_keeps_models_shared_with_other_configs():
    sm = FakeClient({
        "list_endpoint_configs": {"EndpointConfigs": [{"EndpointConfigName": "cfg-a"},
                                                      {"EndpointConfigName": "cfg-b"}]},
        "describe_endpoint_config": lambda kw: {"ProductionVariants": [
            {"ModelName": "shared-model", "InstanceType": "ml.g5.xlarge",
             "InitialInstanceCount": 1}]},
        "list_endpoints": {"Endpoints": [{"EndpointName": "ep", "EndpointStatus": "InService"}]},
        "describe_endpoint": {"EndpointConfigName": "cfg-a"},
        "list_inference_components": {"InferenceComponents": []},
        "list_models": {"Models": [{"ModelName": "shared-model"}, {"ModelName": "orphan"}]},
    })
    resources = _scanner(SageMakerEndpointScanner, {"sagemaker": sm}).scan()
    types = sorted(r.resource_type for r in resources)
    assert types == ["Endpoint", "Endpoint Config", "Model"]
    endpoint = next(r for r in resources if r.resource_type == "Endpoint")
    assert endpoint.extra["delete_models"] == []  # shared with cfg-b
    assert endpoint.extra["endpoint_config"] == "cfg-a"
    assert endpoint.extra["monthly_cost"] > 900
    orphan = next(r for r in resources if r.resource_type == "Model")
    assert orphan.name == "orphan"


def test_running_training_job_is_listed_with_warm_pool():
    sm = FakeClient({
        "list_training_jobs": {"TrainingJobSummaries": [
            {"TrainingJobName": "t1", "TrainingJobStatus": "InProgress"},
            {"TrainingJobName": "t2", "TrainingJobStatus": "Completed",
             "WarmPoolStatus": {"Status": "Available"}},
        ]},
    })
    resources = _scanner(SageMakerJobScanner, {"sagemaker": sm}).scan()
    names = {r.name: r for r in resources}
    assert names["t1"].extra["running"] is True
    assert names["t2"].extra["warm_pool"] is True
    assert impact_tree(names["t2"]).children[0].kind == "Warm pool instances"


def test_knowledge_base_includes_unshared_vector_store():
    agent = FakeClient({
        "list_knowledge_bases": {"knowledgeBaseSummaries": [{"knowledgeBaseId": "kb1",
                                                             "status": "ACTIVE"}]},
        "get_knowledge_base": {"knowledgeBase": {
            "knowledgeBaseId": "kb1", "name": "notes", "status": "ACTIVE",
            "roleArn": "arn:aws:iam::1:role/kb",
            "storageConfiguration": {"type": "OPENSEARCH_SERVERLESS",
                                     "opensearchServerlessConfiguration": {
                                         "collectionArn": "arn:aws:aoss:us-east-1:1:collection/c1",
                                         "vectorIndexName": "idx"}}}},
        "list_data_sources": {"dataSourceSummaries": [{"dataSourceId": "ds1", "name": "s3"}]},
    })
    kb = _scanner(BedrockKnowledgeBaseScanner, {"bedrock-agent": agent}).scan()[0]
    assert kb.extra["collection_id"] == "c1"
    assert kb.extra["data_source_ids"] == ["ds1"]
    kinds = [c.kind for c in impact_tree(kb).children]
    assert "OpenSearch Serverless collection (vector store)" in kinds


def test_committed_provisioned_throughput_is_locked():
    bedrock = FakeClient({
        "list_provisioned_model_throughputs": {"provisionedModelSummaries": [
            {"provisionedModelArn": "arn:pt/1", "provisionedModelName": "claude-pt",
             "modelArn": "arn:model", "foundationModelArn": "arn:fm/anthropic.claude",
             "modelUnits": 1, "commitmentDuration": "OneMonth", "status": "InService"}]},
        "list_custom_models": {"modelSummaries": []},
        "list_imported_models": {"modelSummaries": []},
        "list_model_customization_jobs": {"modelCustomizationJobSummaries": []},
        "list_model_invocation_jobs": {"invocationJobSummaries": []},
    })
    pt = _scanner(BedrockModelScanner, {"bedrock": bedrock}).scan()[0]
    assert pt.deletable is False
    assert "anthropic.claude" in pt.details


def test_domain_delete_cascades_in_order(monkeypatch):
    monkeypatch.setattr(aws_ai_deleter, "_POLL_SECONDS", 0)
    state = {"apps": True, "spaces": True, "profiles": True}

    def listing(key, items, flag):
        def respond(_kw):
            return {key: items if state[flag] else []}
        return respond

    def delete_apps(_kw):
        state["apps"] = False
        return {}

    def delete_space(_kw):
        state["spaces"] = False
        return {}

    def delete_profile(_kw):
        state["profiles"] = False
        return {}

    sm = FakeClient({
        "list_apps": listing("Apps", [{"AppType": "JupyterLab", "AppName": "default",
                                       "SpaceName": "s", "Status": "InService"}], "apps"),
        "list_spaces": listing("Spaces", [{"SpaceName": "s", "Status": "InService"}], "spaces"),
        "list_user_profiles": listing("UserProfiles", [{"UserProfileName": "u",
                                                        "Status": "InService"}], "profiles"),
        "delete_app": delete_apps,
        "delete_space": delete_space,
        "delete_user_profile": delete_profile,
    })
    from orphanaut.models import CloudResource

    domain = CloudResource("d-1", "class", "SageMaker", "Studio Domain", "us-east-1", "", "",
                           extra={"domain_id": "d-1"})
    messages = []
    delete_resource(FakeSession({"sagemaker": sm}), domain, on_progress=messages.append)
    deletes = [op for op in sm.ops() if op.startswith("delete_")]
    assert deletes == ["delete_app", "delete_space", "delete_user_profile", "delete_domain"]
    assert sm.calls[-1][1]["RetentionPolicy"] == {"HomeEfsFileSystem": "Delete"}
    assert any("Studio app" in m for m in messages)


def test_locked_resource_cannot_be_deleted():
    from orphanaut.actions.deleter import DeleteError
    from orphanaut.models import CloudResource

    pt = CloudResource("arn", "pt", "Bedrock", "Provisioned Throughput", "us-east-1", "", "",
                       deletable=False)
    with pytest.raises(DeleteError, match="protected"):
        delete_resource(FakeSession({}), pt)
