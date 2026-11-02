"""Cascade deletion for AWS AI & ML resources.

Many AI resources can only be removed after their children are gone (a
SageMaker domain needs its apps, spaces and user profiles deleted first; a
knowledge base its data sources). These handlers do that in the right order
and wait between steps, reporting progress as they go.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import boto3
from botocore.exceptions import ClientError

from orphanaut.aws.config import AWS_CONFIG
from orphanaut.models import CloudResource

Progress = Callable[[str], None]
AI_SERVICES = {
    "SageMaker",
    "Bedrock",
    "OpenSearch Serverless",
    "Kendra",
    "Comprehend",
    "Rekognition",
}
_POLL_SECONDS = 10
_WAIT_TIMEOUT = 30 * 60


class _Timeout(Exception):
    pass


def _wait_until(check: Callable[[], bool], what: str, progress: Progress) -> None:
    deadline = time.monotonic() + _WAIT_TIMEOUT
    while time.monotonic() < deadline:
        if check():
            return
        progress(f"Waiting for {what}...")
        time.sleep(_POLL_SECONDS)
    raise _Timeout(f"Timed out waiting for {what}. Run the delete again to continue.")


def _not_found(exc: ClientError) -> bool:
    code = exc.response.get("Error", {}).get("Code", "")
    message = exc.response.get("Error", {}).get("Message", "")
    return code in {"ResourceNotFound", "ResourceNotFoundException", "ValidationException"} and (
        code != "ValidationException"
        or "not found" in message.lower()
        or "does not exist" in message.lower()
        or "could not find" in message.lower()
    )


def _all(client, op: str, key: str, **kwargs) -> list[dict]:
    items: list[dict] = []
    for page in client.get_paginator(op).paginate(**kwargs):
        items.extend(page.get(key, []))
    return items


def delete_aws_ai_resource(
    session: boto3.Session, resource: CloudResource, progress: Progress = lambda _m: None
) -> None:
    region = resource.region
    client = lambda name: session.client(name, region_name=region, config=AWS_CONFIG)  # noqa: E731
    x = resource.extra
    try:
        match (resource.service, resource.resource_type):
            case ("SageMaker", "Studio Domain"):
                _delete_domain(client("sagemaker"), x["domain_id"], progress)
            case ("SageMaker", "Studio App"):
                kwargs = {
                    "DomainId": x["domain_id"],
                    "AppType": x["app_type"],
                    "AppName": x["app_name"],
                }
                if x.get("space_name"):
                    kwargs["SpaceName"] = x["space_name"]
                else:
                    kwargs["UserProfileName"] = x["user_profile"]
                client("sagemaker").delete_app(**kwargs)
            case ("SageMaker", "Endpoint"):
                _delete_endpoint(client("sagemaker"), client("logs"), x, progress)
            case ("SageMaker", "Endpoint Config"):
                client("sagemaker").delete_endpoint_config(EndpointConfigName=x["endpoint_config"])
            case ("SageMaker", "Model"):
                client("sagemaker").delete_model(ModelName=x["model_name"])
            case ("SageMaker", "Notebook Instance"):
                _delete_notebook(client("sagemaker"), x["notebook_name"], progress)
            case ("SageMaker", kind) if kind.endswith("Job"):
                _delete_job(client("sagemaker"), x, progress)
            case ("SageMaker", "MLflow Tracking Server"):
                client("sagemaker").delete_mlflow_tracking_server(
                    TrackingServerName=x["tracking_server"]
                )
            case ("SageMaker", "HyperPod Cluster"):
                client("sagemaker").delete_cluster(ClusterName=x["cluster_name"])
            case ("SageMaker", "Feature Group"):
                client("sagemaker").delete_feature_group(FeatureGroupName=x["feature_group"])
            case ("Bedrock", "Knowledge Base"):
                _delete_knowledge_base(
                    client("bedrock-agent"), client("opensearchserverless"), x, progress
                )
            case ("Bedrock", "Agent"):
                client("bedrock-agent").delete_agent(
                    agentId=x["agent_id"], skipResourceInUseCheck=True
                )
            case ("Bedrock", "Provisioned Throughput"):
                client("bedrock").delete_provisioned_model_throughput(
                    provisionedModelId=x["provisioned_model_arn"]
                )
            case ("Bedrock", "Custom Model"):
                bedrock = client("bedrock")
                for arn in x.get("provisioned_arns", []):
                    progress("Deleting provisioned throughput that serves the model...")
                    bedrock.delete_provisioned_model_throughput(provisionedModelId=arn)
                bedrock.delete_custom_model(modelIdentifier=x["model_identifier"])
            case ("Bedrock", "Imported Model"):
                client("bedrock").delete_imported_model(modelIdentifier=x["model_identifier"])
            case ("Bedrock", "Customization Job"):
                client("bedrock").stop_model_customization_job(jobIdentifier=x["job_identifier"])
            case ("Bedrock", "Batch Inference Job"):
                client("bedrock").stop_model_invocation_job(jobIdentifier=x["job_identifier"])
            case ("OpenSearch Serverless", "Collection"):
                client("opensearchserverless").delete_collection(id=x["collection_id"])
            case ("Kendra", "Index"):
                client("kendra").delete_index(Id=x["index_id"])
            case ("Comprehend", "Endpoint"):
                client("comprehend").delete_endpoint(EndpointArn=x["endpoint_arn"])
            case ("Rekognition", "Running Model"):
                client("rekognition").stop_project_version(
                    ProjectVersionArn=x["project_version_arn"]
                )
            case _:
                from orphanaut.actions.deleter import DeleteError

                raise DeleteError(
                    f"Deletion not supported for {resource.service} / {resource.resource_type}"
                )
    except _Timeout as exc:
        from orphanaut.actions.deleter import DeleteError

        raise DeleteError(str(exc)) from exc


def _delete_domain(sm, domain_id: str, progress: Progress) -> None:
    def live(op: str, key: str) -> list[dict]:
        return [
            i
            for i in _all(sm, op, key, DomainIdEquals=domain_id)
            if i.get("Status") not in {"Deleted", "Failed", "Delete_Failed"}
        ]

    apps = live("list_apps", "Apps")
    for app in apps:
        if app.get("Status") == "Deleting":
            continue
        progress(f"Stopping Studio app {app['AppName']}...")
        kwargs = {"DomainId": domain_id, "AppType": app["AppType"], "AppName": app["AppName"]}
        if app.get("SpaceName"):
            kwargs["SpaceName"] = app["SpaceName"]
        else:
            kwargs["UserProfileName"] = app["UserProfileName"]
        try:
            sm.delete_app(**kwargs)
        except ClientError as exc:
            if not _not_found(exc):
                raise
    _wait_until(lambda: not live("list_apps", "Apps"), "Studio apps to stop", progress)

    for space in live("list_spaces", "Spaces"):
        if space.get("Status") != "Deleting":
            progress(f"Deleting space {space['SpaceName']}...")
            sm.delete_space(DomainId=domain_id, SpaceName=space["SpaceName"])
    _wait_until(lambda: not live("list_spaces", "Spaces"), "spaces to be deleted", progress)

    for profile in live("list_user_profiles", "UserProfiles"):
        if profile.get("Status") != "Deleting":
            progress(f"Deleting user profile {profile['UserProfileName']}...")
            sm.delete_user_profile(DomainId=domain_id, UserProfileName=profile["UserProfileName"])
    _wait_until(
        lambda: not live("list_user_profiles", "UserProfiles"),
        "user profiles to be deleted",
        progress,
    )

    progress("Deleting the Studio domain and its home EFS volume...")
    sm.delete_domain(DomainId=domain_id, RetentionPolicy={"HomeEfsFileSystem": "Delete"})


def _delete_endpoint(sm, logs, x: dict, progress: Progress) -> None:
    name = x["endpoint_name"]
    components = x.get("inference_components", [])
    for component in components:
        progress(f"Deleting inference component {component}...")
        try:
            sm.delete_inference_component(InferenceComponentName=component)
        except ClientError as exc:
            if not _not_found(exc):
                raise
    if components:
        _wait_until(
            lambda: (
                not _all(
                    sm, "list_inference_components", "InferenceComponents", EndpointNameEquals=name
                )
            ),
            "inference components to be deleted",
            progress,
        )
    progress(f"Deleting endpoint {name}...")
    sm.delete_endpoint(EndpointName=name)
    if x.get("endpoint_config"):
        try:
            sm.delete_endpoint_config(EndpointConfigName=x["endpoint_config"])
        except ClientError as exc:
            if not _not_found(exc):
                raise
    for model in x.get("delete_models", []):
        try:
            sm.delete_model(ModelName=model)
        except ClientError as exc:
            if not _not_found(exc):
                raise
    try:
        logs.delete_log_group(logGroupName=f"/aws/sagemaker/Endpoints/{name}")
    except ClientError:
        pass


def _delete_notebook(sm, name: str, progress: Progress) -> None:
    status = sm.describe_notebook_instance(NotebookInstanceName=name)["NotebookInstanceStatus"]
    if status in {"InService", "Pending", "Updating"}:
        if status == "InService":
            progress(f"Stopping notebook {name}...")
            sm.stop_notebook_instance(NotebookInstanceName=name)
        _wait_until(
            lambda: (
                sm.describe_notebook_instance(NotebookInstanceName=name)["NotebookInstanceStatus"]
                in {"Stopped", "Failed"}
            ),
            f"notebook {name} to stop",
            progress,
        )
    sm.delete_notebook_instance(NotebookInstanceName=name)


_JOB_API = {
    "Training Job": (
        "TrainingJobName",
        "stop_training_job",
        "describe_training_job",
        "TrainingJobStatus",
        "delete_training_job",
    ),
    "Processing Job": (
        "ProcessingJobName",
        "stop_processing_job",
        "describe_processing_job",
        "ProcessingJobStatus",
        "delete_processing_job",
    ),
    "Tuning Job": (
        "HyperParameterTuningJobName",
        "stop_hyper_parameter_tuning_job",
        "describe_hyper_parameter_tuning_job",
        "HyperParameterTuningJobStatus",
        "delete_hyper_parameter_tuning_job",
    ),
    "Transform Job": (
        "TransformJobName",
        "stop_transform_job",
        "describe_transform_job",
        "TransformJobStatus",
        "",
    ),
}


def _delete_job(sm, x: dict, progress: Progress) -> None:
    key, stop_op, describe_op, status_key, delete_op = _JOB_API[x["job_kind"]]
    name = x["job_name"]
    status = lambda: getattr(sm, describe_op)(**{key: name})[status_key]  # noqa: E731
    if status() in {"InProgress"}:
        progress(f"Stopping {x['job_kind'].lower()} {name}...")
        getattr(sm, stop_op)(**{key: name})
    if not delete_op:
        return
    _wait_until(lambda: status() in {"Completed", "Failed", "Stopped"}, f"{name} to stop", progress)
    if x.get("warm_pool"):
        progress("Releasing warm pool instances...")
        try:
            sm.update_training_job(
                TrainingJobName=name, ResourceConfig={"KeepAlivePeriodInSeconds": 0}
            )
        except ClientError:
            pass
        _wait_until(
            lambda: (
                sm.describe_training_job(TrainingJobName=name)
                .get("WarmPoolStatus", {})
                .get("Status")
                not in {"Available", "InUse"}
            ),
            "warm pool to be released",
            progress,
        )
    getattr(sm, delete_op)(**{key: name})


def _delete_knowledge_base(agent, aoss, x: dict, progress: Progress) -> None:
    kb_id = x["knowledge_base_id"]
    for source_id in x.get("data_source_ids", []):
        progress(f"Deleting data source {source_id}...")
        try:
            agent.delete_data_source(knowledgeBaseId=kb_id, dataSourceId=source_id)
        except ClientError as exc:
            if not _not_found(exc):
                raise
    if x.get("data_source_ids"):
        _wait_until(
            lambda: (
                not _all(agent, "list_data_sources", "dataSourceSummaries", knowledgeBaseId=kb_id)
            ),
            "data sources to be deleted",
            progress,
        )
    progress("Deleting the knowledge base...")
    agent.delete_knowledge_base(knowledgeBaseId=kb_id)

    def kb_gone() -> bool:
        try:
            agent.get_knowledge_base(knowledgeBaseId=kb_id)
            return False
        except ClientError as exc:
            return _not_found(exc)

    _wait_until(kb_gone, "the knowledge base to be deleted", progress)
    if x.get("collection_id"):
        progress("Deleting the OpenSearch Serverless vector store...")
        try:
            aoss.delete_collection(id=x["collection_id"])
        except ClientError as exc:
            if not _not_found(exc):
                raise
