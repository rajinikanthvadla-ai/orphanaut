"""Delete-impact maps: what else goes away when a resource is deleted.

Scanners attach associated resources to ``CloudResource.extra["dependents"]`` as
plain dicts built with :func:`dep`. The UI turns them into a tree so people can
see, before confirming, that deleting e.g. a SageMaker domain also removes its
user profiles, spaces, apps and home EFS volume.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from orphanaut.models import CloudResource


class Action(str, Enum):
    DELETE = "delete"
    STOP = "stop"
    KEEP = "keep"

    @property
    def label(self) -> str:
        match self:
            case Action.DELETE:
                return "Deleted"
            case Action.STOP:
                return "Stopped"
            case Action.KEEP:
                return "Kept"
            case _:
                return self.value


def dep(
    kind: str,
    name: str,
    action: Action | str = Action.DELETE,
    note: str = "",
    children: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Describe one associated resource for ``extra["dependents"]``."""
    return {
        "kind": kind,
        "name": name,
        "action": Action(action).value,
        "note": note,
        "children": children or [],
    }


@dataclass
class ImpactNode:
    kind: str
    name: str
    action: Action
    note: str = ""
    children: list[ImpactNode] = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


def _node(data: dict[str, Any]) -> ImpactNode:
    return ImpactNode(
        kind=data.get("kind", ""),
        name=data.get("name", ""),
        action=Action(data.get("action", Action.DELETE.value)),
        note=data.get("note", ""),
        children=[_node(child) for child in data.get("children", [])],
    )


def root_action(resource: CloudResource) -> Action:
    return Action(resource.extra.get("delete_action", Action.DELETE.value))


def impact_tree(resource: CloudResource) -> ImpactNode:
    return ImpactNode(
        kind=f"{resource.service} {resource.resource_type}",
        name=resource.name or resource.resource_id,
        action=root_action(resource),
        note=resource.extra.get("impact_note", ""),
        children=[_node(child) for child in resource.dependents],
    )


def impact_counts(resources: list[CloudResource]) -> dict[Action, int]:
    """Count every node (selected resources + associated) by action."""
    counts = {action: 0 for action in Action}
    for resource in resources:
        for node in impact_tree(resource).walk():
            counts[node.action] += 1
    return counts


def impact_text(resources: list[CloudResource], limit: int = 40) -> str:
    """Plain-text tree used in the delete confirmation dialog."""
    lines: list[str] = []

    def add(node: ImpactNode, depth: int) -> None:
        if len(lines) >= limit:
            return
        indent = "    " * depth
        bullet = "•" if depth == 0 else "└"
        note = f" - {node.note}" if node.note else ""
        lines.append(f"{indent}{bullet} [{node.action.label}] {node.kind}: {node.name}{note}")
        for child in node.children:
            add(child, depth + 1)

    for resource in resources:
        add(impact_tree(resource), 0)
    total = sum(1 for r in resources for _ in impact_tree(r).walk())
    if total > len(lines):
        lines.append(f"... and {total - len(lines)} more")
    return "\n".join(lines)


def link_related(resources: list[CloudResource]) -> None:
    """Add cross-resource notes, e.g. a vector store that a knowledge base depends on."""
    by_collection: dict[str, list[CloudResource]] = {}
    for resource in resources:
        arn = resource.extra.get("collection_arn")
        if arn and resource.resource_type == "Knowledge Base":
            by_collection.setdefault(arn, []).append(resource)
    for resource in resources:
        if resource.resource_type != "Collection":
            continue
        for kb in by_collection.get(resource.extra.get("collection_arn", ""), []):
            resource.extra.setdefault("dependents", []).insert(
                0,
                dep(
                    "Bedrock knowledge base",
                    kb.name or kb.resource_id,
                    Action.KEEP,
                    "stops working - delete the knowledge base instead to clean up both",
                ),
            )
