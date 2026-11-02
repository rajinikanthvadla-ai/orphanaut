"""Tests for delete-impact maps and categories."""

from orphanaut.categories import AI_ML, COMPUTE, NETWORKING, STORAGE, category_for
from orphanaut.dependencies import (
    Action,
    dep,
    impact_counts,
    impact_text,
    impact_tree,
    link_related,
    root_action,
)
from orphanaut.models import CloudProvider, CloudResource


def _res(service="SageMaker", rtype="Studio Domain", **extra) -> CloudResource:
    return CloudResource("id-1", "demo", service, rtype, "us-east-1", "ok", "", extra=extra)


def test_impact_tree_nests_children_and_actions():
    resource = _res(dependents=[
        dep("User profile", "alice", children=[dep("Studio app", "JupyterLab")]),
        dep("IAM role", "role", Action.KEEP, "free"),
    ])
    tree = impact_tree(resource)
    assert tree.action == Action.DELETE
    assert [c.kind for c in tree.children] == ["User profile", "IAM role"]
    assert tree.children[0].children[0].name == "JupyterLab"
    assert tree.children[1].action == Action.KEEP


def test_impact_counts_and_text():
    resources = [
        _res(dependents=[dep("Space", "s1"), dep("Role", "r", Action.KEEP)]),
        _res(rtype="Training Job", delete_action="stop"),
    ]
    counts = impact_counts(resources)
    assert counts[Action.DELETE] == 2  # domain + space
    assert counts[Action.KEEP] == 1
    assert counts[Action.STOP] == 1
    text = impact_text(resources)
    assert "[Deleted] Space: s1" in text
    assert "[Kept — review] Role: r" in text
    assert "[Stopped]" in text


def test_impact_text_is_truncated():
    resource = _res(dependents=[dep("Item", str(i)) for i in range(60)])
    text = impact_text([resource], limit=10)
    assert text.splitlines()[-1].startswith("... and ")


def test_root_action_defaults_to_delete():
    assert root_action(_res()) == Action.DELETE
    assert root_action(_res(delete_action="stop")) == Action.STOP


def test_link_related_marks_vector_store_used_by_knowledge_base():
    arn = "arn:aws:aoss:us-east-1:1:collection/abc"
    kb = _res(service="Bedrock", rtype="Knowledge Base", collection_arn=arn)
    collection = _res(service="OpenSearch Serverless", rtype="Collection", collection_arn=arn)
    link_related([kb, collection])
    first = collection.dependents[0]
    assert first["kind"] == "Bedrock knowledge base"
    assert first["action"] == "keep"


def test_categories():
    assert category_for(_res()) == AI_ML
    assert category_for(_res(service="Bedrock", rtype="Agent")) == AI_ML
    assert category_for(_res(service="EC2", rtype="Instance")) == COMPUTE
    assert category_for(_res(service="EC2", rtype="Elastic IP")) == NETWORKING
    assert category_for(_res(service="EBS", rtype="Snapshot")) == STORAGE
    azure = CloudResource("x", "x", "Azure OpenAI", "OpenAI Account", "eastus", "", "",
                          provider=CloudProvider.AZURE)
    assert azure.category == AI_ML
