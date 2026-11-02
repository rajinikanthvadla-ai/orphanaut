"""Amazon Bedrock and related AI service scanners.

Covers knowledge bases (and their vector stores), agents, provisioned
throughput (e.g. for Anthropic Claude models), custom/imported models, running
customization and batch jobs, OpenSearch Serverless collections, Kendra indexes,
Comprehend endpoints and Rekognition Custom Labels models.
"""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.ai_pricing import hourly_to_monthly
from orphanaut.dependencies import Action, dep
from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner

# OpenSearch Serverless bills at least 2 OCUs (1 with redundancy off) for indexing
# and the same for search, at ~$0.24 per OCU-hour.
_OSS_MIN_MONTHLY = hourly_to_monthly(4 * 0.24)


def _res(
    service: str, region: str, rtype: str, rid: str, name: str, status: str, details: str, **extra
) -> AwsResource:
    return AwsResource(
        resource_id=rid,
        name=name,
        service=service,
        resource_type=rtype,
        region=region,
        status=status,
        details=details,
        extra=extra,
    )


def _short_model(arn_or_id: str) -> str:
    return arn_or_id.rsplit("/", 1)[-1] if arn_or_id else ""


class BedrockKnowledgeBaseScanner(BaseScanner):
    service_name = "Bedrock Knowledge Bases"
    boto_service = "bedrock-agent"

    def scan(self) -> list[AwsResource]:
        agent = self.client("bedrock-agent")
        kbs = []
        for summary in self.paginate(agent, "list_knowledge_bases", "knowledgeBaseSummaries"):
            if summary.get("status") in {"DELETING"}:
                continue
            try:
                kbs.append(
                    agent.get_knowledge_base(knowledgeBaseId=summary["knowledgeBaseId"])[
                        "knowledgeBase"
                    ]
                )
            except ClientError:
                kbs.append(summary)

        collection_users: dict[str, int] = {}
        for kb in kbs:
            arn = (
                kb.get("storageConfiguration", {})
                .get("opensearchServerlessConfiguration", {})
                .get("collectionArn", "")
            )
            if arn:
                collection_users[arn] = collection_users.get(arn, 0) + 1

        resources: list[AwsResource] = []
        for kb in kbs:
            kb_id = kb["knowledgeBaseId"]
            storage = kb.get("storageConfiguration", {})
            store_type = storage.get("type", "")
            embedding = (
                kb.get("knowledgeBaseConfiguration", {})
                .get("vectorKnowledgeBaseConfiguration", {})
                .get("embeddingModelArn", "")
            )
            sources = list(
                self.paginate(
                    agent, "list_data_sources", "dataSourceSummaries", knowledgeBaseId=kb_id
                )
            )
            dependents = [
                dep(
                    "Data source",
                    s.get("name", s["dataSourceId"]),
                    note="sync settings only — documents in S3 are kept",
                )
                for s in sources
            ]
            collection_arn = storage.get("opensearchServerlessConfiguration", {}).get(
                "collectionArn", ""
            )
            collection_id = collection_arn.rsplit("/", 1)[-1] if collection_arn else ""
            delete_collection = False
            cost = 0.0
            if collection_arn:
                index = storage["opensearchServerlessConfiguration"].get("vectorIndexName", "")
                if collection_users.get(collection_arn, 0) > 1:
                    dependents.append(
                        dep(
                            "OpenSearch Serverless collection",
                            collection_id,
                            Action.KEEP,
                            "shared with another knowledge base",
                        )
                    )
                else:
                    delete_collection = True
                    cost = _OSS_MIN_MONTHLY
                    dependents.append(
                        dep(
                            "OpenSearch Serverless collection (vector store)",
                            collection_id,
                            note=f"the main cost — ~${_OSS_MIN_MONTHLY:,.0f}+/mo minimum",
                            children=[dep("Vector index", index or "embeddings")],
                        )
                    )
            elif store_type:
                dependents.append(
                    dep(
                        f"Vector store ({store_type})",
                        "external",
                        Action.KEEP,
                        "delete it in its own service (e.g. RDS/Aurora list)",
                    )
                )
            dependents.append(
                dep(
                    "Source documents in S3", "bucket", Action.KEEP, "your S3 data is never touched"
                )
            )
            if kb.get("roleArn"):
                dependents.append(
                    dep("IAM service role", _short_model(kb["roleArn"]), Action.KEEP, "free")
                )
            resources.append(
                _res(
                    "Bedrock",
                    self.region,
                    "Knowledge Base",
                    kb_id,
                    kb.get("name", ""),
                    kb.get("status", ""),
                    f"{store_type or 'vector store'}, embeddings {_short_model(embedding)}, "
                    f"{len(sources)} data source(s)",
                    knowledge_base_id=kb_id,
                    data_source_ids=[s["dataSourceId"] for s in sources],
                    collection_id=collection_id if delete_collection else "",
                    collection_arn=collection_arn,
                    dependents=dependents,
                    monthly_cost=round(cost, 2),
                )
            )
        return resources


class BedrockAgentScanner(BaseScanner):
    service_name = "Bedrock Agents"
    boto_service = "bedrock-agent"

    def scan(self) -> list[AwsResource]:
        agent_client = self.client("bedrock-agent")
        resources: list[AwsResource] = []
        for summary in self.paginate(agent_client, "list_agents", "agentSummaries"):
            agent_id = summary["agentId"]
            if summary.get("agentStatus") == "DELETING":
                continue
            try:
                info = agent_client.get_agent(agentId=agent_id)["agent"]
            except ClientError:
                info = {}
            model = info.get("foundationModel", "")
            dependents = [
                dep("Alias", a.get("agentAliasName", a["agentAliasId"]))
                for a in self.paginate(
                    agent_client, "list_agent_aliases", "agentAliasSummaries", agentId=agent_id
                )
            ]
            dependents.append(dep("Agent versions", "all versions"))
            try:
                for group in self.paginate(
                    agent_client,
                    "list_agent_action_groups",
                    "actionGroupSummaries",
                    agentId=agent_id,
                    agentVersion="DRAFT",
                ):
                    dependents.append(
                        dep(
                            "Action group",
                            group.get("actionGroupName", ""),
                            note="its Lambda function is kept",
                        )
                    )
                for link in self.paginate(
                    agent_client,
                    "list_agent_knowledge_bases",
                    "agentKnowledgeBaseSummaries",
                    agentId=agent_id,
                    agentVersion="DRAFT",
                ):
                    dependents.append(
                        dep(
                            "Knowledge base link",
                            link["knowledgeBaseId"],
                            note="only the link — the knowledge base is kept",
                        )
                    )
            except ClientError:
                pass
            resources.append(
                _res(
                    "Bedrock",
                    self.region,
                    "Agent",
                    agent_id,
                    summary.get("agentName", ""),
                    summary.get("agentStatus", ""),
                    f"model {_short_model(model) or 'n/a'} — pay per use",
                    agent_id=agent_id,
                    dependents=dependents,
                    monthly_cost=0.0,
                )
            )
        return resources


class BedrockModelScanner(BaseScanner):
    """Provisioned throughput, custom/imported models and running jobs."""

    service_name = "Bedrock Models"
    boto_service = "bedrock"

    def scan(self) -> list[AwsResource]:
        bedrock = self.client("bedrock")
        resources: list[AwsResource] = []
        pts = [
            p
            for p in self.paginate(
                bedrock, "list_provisioned_model_throughputs", "provisionedModelSummaries"
            )
            if p.get("status") != "Deleting"
        ]
        pts_by_model: dict[str, list[dict]] = {}
        for pt in pts:
            pts_by_model.setdefault(pt.get("modelArn", ""), []).append(pt)
            commitment = pt.get("commitmentDuration", "")
            units = pt.get("modelUnits", 1)
            committed = bool(commitment)
            resources.append(
                _res(
                    "Bedrock",
                    self.region,
                    "Provisioned Throughput",
                    pt["provisionedModelArn"],
                    pt.get("provisionedModelName", ""),
                    pt.get("status", ""),
                    f"{units} model unit(s) of {_short_model(pt.get('foundationModelArn', ''))}"
                    + (f", {commitment} commitment" if committed else ", no commitment"),
                    provisioned_model_arn=pt["provisionedModelArn"],
                    impact_note=(
                        "committed term — AWS only allows deleting it after the commitment ends"
                    )
                    if committed
                    else "",
                    monthly_cost=hourly_to_monthly(units * 20.0),
                )
            )
            if committed:
                resources[-1].deletable = False

        for model in self.paginate(bedrock, "list_custom_models", "modelSummaries"):
            arn = model["modelArn"]
            pt_nodes = [
                dep(
                    "Provisioned throughput",
                    p.get("provisionedModelName", ""),
                    note="must go first — it serves this model",
                )
                for p in pts_by_model.get(arn, [])
            ]
            resources.append(
                _res(
                    "Bedrock",
                    self.region,
                    "Custom Model",
                    arn,
                    model.get("modelName", ""),
                    "ready",
                    f"based on {_short_model(model.get('baseModelArn', ''))}",
                    model_identifier=arn,
                    provisioned_arns=[p["provisionedModelArn"] for p in pts_by_model.get(arn, [])],
                    dependents=pt_nodes
                    + [
                        dep(
                            "Training data in S3",
                            "s3://…",
                            Action.KEEP,
                            "your S3 data is never touched",
                        )
                    ],
                    monthly_cost=1.95,
                )
            )

        for model in self.paginate(bedrock, "list_imported_models", "modelSummaries"):
            resources.append(
                _res(
                    "Bedrock",
                    self.region,
                    "Imported Model",
                    model["modelArn"],
                    model.get("modelName", ""),
                    "ready",
                    "Custom Model Import",
                    model_identifier=model["modelArn"],
                    dependents=[
                        dep(
                            "Model files in S3",
                            "s3://…",
                            Action.KEEP,
                            "your S3 data is never touched",
                        )
                    ],
                )
            )

        for job in self.paginate(
            bedrock,
            "list_model_customization_jobs",
            "modelCustomizationJobSummaries",
            statusEquals="InProgress",
        ):
            resources.append(
                _res(
                    "Bedrock",
                    self.region,
                    "Customization Job",
                    job["jobArn"],
                    job.get("jobName", ""),
                    job.get("status", ""),
                    f"fine-tuning {_short_model(job.get('baseModelArn', ''))} — billing now",
                    job_identifier=job["jobArn"],
                    delete_action=Action.STOP.value,
                    impact_note="the job is stopped; no custom model is produced",
                )
            )
        for job in self.paginate(
            bedrock,
            "list_model_invocation_jobs",
            "invocationJobSummaries",
            statusEquals="InProgress",
        ):
            resources.append(
                _res(
                    "Bedrock",
                    self.region,
                    "Batch Inference Job",
                    job["jobArn"],
                    job.get("jobName", ""),
                    job.get("status", ""),
                    f"batch inference on {_short_model(job.get('modelId', ''))}",
                    job_identifier=job["jobArn"],
                    delete_action=Action.STOP.value,
                )
            )
        return resources


class OpenSearchServerlessScanner(BaseScanner):
    service_name = "OpenSearch Serverless"
    boto_service = "opensearchserverless"

    def scan(self) -> list[AwsResource]:
        aoss = self.client("opensearchserverless")
        summaries = [
            c
            for c in self.paginate(aoss, "list_collections", "collectionSummaries")
            if c.get("status") not in {"DELETING"}
        ]
        details: dict[str, dict] = {}
        for i in range(0, len(summaries), 100):
            ids = [c["id"] for c in summaries[i : i + 100]]
            try:
                for info in aoss.batch_get_collection(ids=ids).get("collectionDetails", []):
                    details[info["id"]] = info
            except ClientError:
                pass
        resources: list[AwsResource] = []
        for c in summaries:
            info = details.get(c["id"], {})
            ctype = info.get("type", "")
            resources.append(
                _res(
                    "OpenSearch Serverless",
                    self.region,
                    "Collection",
                    c["id"],
                    c.get("name", ""),
                    c.get("status", ""),
                    f"{ctype.title() or 'Collection'} — billed per OCU-hour",
                    collection_id=c["id"],
                    collection_arn=c.get("arn", ""),
                    dependents=[
                        dep("All indexes and documents", "in this collection"),
                        dep(
                            "Encryption / network / data-access policies",
                            c.get("name", ""),
                            Action.KEEP,
                            "free — remove in the console if unused",
                        ),
                    ],
                    monthly_cost=round(_OSS_MIN_MONTHLY, 2),
                )
            )
        return resources


class KendraScanner(BaseScanner):
    service_name = "Kendra"
    boto_service = "kendra"

    def scan(self) -> list[AwsResource]:
        kendra = self.client("kendra")
        resources: list[AwsResource] = []
        edition_monthly = {
            "DEVELOPER_EDITION": 810.0,
            "ENTERPRISE_EDITION": 1008.0,
            "GEN_AI_ENTERPRISE_EDITION": 230.0,
        }
        for index in self.paginate(kendra, "list_indices", "IndexConfigurationSummaryItems"):
            if index.get("Status") == "DELETING":
                continue
            index_id = index["Id"]
            sources = []
            try:
                sources = kendra.list_data_sources(IndexId=index_id).get("SummaryItems", [])
            except ClientError:
                pass
            edition = index.get("Edition", "")
            resources.append(
                _res(
                    "Kendra",
                    self.region,
                    "Index",
                    index_id,
                    index.get("Name", ""),
                    index.get("Status", ""),
                    edition.replace("_", " ").title(),
                    index_id=index_id,
                    dependents=[dep("Data source", s.get("Name", s.get("Id", ""))) for s in sources]
                    + [dep("FAQs, experiences and indexed documents", "all")],
                    monthly_cost=edition_monthly.get(edition),
                )
            )
        return resources


class ComprehendScanner(BaseScanner):
    service_name = "Comprehend"
    boto_service = "comprehend"

    def scan(self) -> list[AwsResource]:
        comprehend = self.client("comprehend")
        resources: list[AwsResource] = []
        for ep in self.paginate(comprehend, "list_endpoints", "EndpointPropertiesList"):
            if ep.get("Status") == "DELETING":
                continue
            units = ep.get("CurrentInferenceUnits", 1)
            arn = ep["EndpointArn"]
            resources.append(
                _res(
                    "Comprehend",
                    self.region,
                    "Endpoint",
                    arn,
                    _short_model(arn),
                    ep.get("Status", ""),
                    f"{units} inference unit(s) for {_short_model(ep.get('ModelArn', ''))}",
                    endpoint_arn=arn,
                    dependents=[
                        dep(
                            "Custom model",
                            _short_model(ep.get("ModelArn", "")),
                            Action.KEEP,
                            "model is kept; only the endpoint is removed",
                        )
                    ],
                    monthly_cost=hourly_to_monthly(units * 1.8),
                )
            )
        return resources


class RekognitionCustomLabelsScanner(BaseScanner):
    service_name = "Rekognition"
    boto_service = "rekognition"

    def scan(self) -> list[AwsResource]:
        rek = self.client("rekognition")
        resources: list[AwsResource] = []
        for project in self.paginate(rek, "describe_projects", "ProjectDescriptions"):
            arn = project["ProjectArn"]
            for version in self.paginate(
                rek, "describe_project_versions", "ProjectVersionDescriptions", ProjectArn=arn
            ):
                if version.get("Status") not in {"RUNNING", "STARTING"}:
                    continue
                units = version.get("MinInferenceUnits", 1)
                varn = version["ProjectVersionArn"]
                resources.append(
                    _res(
                        "Rekognition",
                        self.region,
                        "Running Model",
                        varn,
                        _short_model(arn) + " / " + varn.split("/")[-2],
                        version.get("Status", ""),
                        f"{units} inference unit(s)",
                        project_version_arn=varn,
                        delete_action=Action.STOP.value,
                        impact_note="the model is stopped; it can be started again later",
                        monthly_cost=hourly_to_monthly(units * 4.0),
                    )
                )
        return resources
