"""Amazon SageMaker scanners: Studio domains & apps, endpoints, notebooks, jobs, and more."""

from __future__ import annotations

from collections import defaultdict

from botocore.exceptions import ClientError

from orphanaut.ai_pricing import hourly_to_monthly, ml_monthly
from orphanaut.dependencies import Action, dep
from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner

_GONE = {"Deleted", "Deleting", "Failed", "Delete_Failed"}
_JOB_RUNNING = {"InProgress", "Stopping"}
# How many finished jobs per type to list (newest first) - keeps scans quick.
_MAX_FINISHED_JOBS = 200


def _resource(
    region: str, resource_type: str, rid: str, name: str, status: str, details: str, **extra
) -> AwsResource:
    return AwsResource(
        resource_id=rid,
        name=name,
        service="SageMaker",
        resource_type=resource_type,
        region=region,
        status=status,
        details=details,
        extra=extra,
    )


class SageMakerStudioScanner(BaseScanner):
    """Studio domains (with profiles, spaces, apps, EFS) and the running apps inside them."""

    service_name = "SageMaker Studio"
    boto_service = "sagemaker"

    def scan(self) -> list[AwsResource]:
        sm = self.client("sagemaker")
        resources: list[AwsResource] = []
        for domain in self.paginate(sm, "list_domains", "Domains"):
            domain_id = domain["DomainId"]
            if domain.get("Status") in _GONE:
                continue
            try:
                info = sm.describe_domain(DomainId=domain_id)
            except ClientError:
                info = {}
            profiles = [
                p
                for p in self.paginate(
                    sm, "list_user_profiles", "UserProfiles", DomainIdEquals=domain_id
                )
                if p.get("Status") not in _GONE
            ]
            spaces = [
                s
                for s in self.paginate(sm, "list_spaces", "Spaces", DomainIdEquals=domain_id)
                if s.get("Status") not in _GONE
            ]
            apps = [
                a
                for a in self.paginate(sm, "list_apps", "Apps", DomainIdEquals=domain_id)
                if a.get("Status") not in _GONE
            ]

            def app_nodes(owner_key: str, owner: str) -> list[dict]:
                return [
                    dep(
                        "Studio app",
                        f"{a['AppType']} / {a['AppName']}",
                        note=a.get("ResourceSpec", {}).get("InstanceType", ""),
                    )
                    for a in apps
                    if a.get(owner_key) == owner
                ]

            def space_node(space: dict) -> dict:
                name = space["SpaceName"]
                return dep("Space", name, children=app_nodes("SpaceName", name))

            owned: dict[str, list[dict]] = defaultdict(list)
            shared: list[dict] = []
            for space in spaces:
                owner = space.get("OwnershipSettingsSummary", {}).get("OwnerUserProfileName")
                (owned[owner] if owner else shared).append(space)

            dependents = [
                dep(
                    "User profile",
                    p["UserProfileName"],
                    children=app_nodes("UserProfileName", p["UserProfileName"])
                    + [space_node(s) for s in owned.get(p["UserProfileName"], [])],
                )
                for p in profiles
            ]
            dependents += [space_node(s) for s in shared]
            efs_id = info.get("HomeEfsFileSystemId")
            if efs_id:
                dependents.append(
                    dep(
                        "EFS file system (home folders)",
                        efs_id,
                        note="all notebooks and files in Studio home folders",
                    )
                )
            role = info.get("DefaultUserSettings", {}).get("ExecutionRole", "")
            if role:
                dependents.append(
                    dep(
                        "IAM execution role",
                        role.rsplit("/", 1)[-1],
                        Action.KEEP,
                        "free - remove in IAM if nothing else uses it",
                    )
                )
            dependents.append(
                dep(
                    "VPC security groups for Studio",
                    domain_id,
                    Action.KEEP,
                    "free - created by SageMaker, remove in VPC console if left over",
                )
            )

            running = [a for a in apps if a.get("Status") in {"InService", "Pending"}]
            cost = sum(
                ml_monthly(a.get("ResourceSpec", {}).get("InstanceType", "")) or 0.0
                for a in running
            )
            resources.append(
                _resource(
                    self.region,
                    "Studio Domain",
                    domain_id,
                    domain.get("DomainName", ""),
                    domain.get("Status", ""),
                    f"{len(profiles)} user profiles, {len(spaces)} spaces, "
                    f"{len(running)} running apps",
                    domain_id=domain_id,
                    dependents=dependents,
                    impact_note="all apps are stopped, then everything inside is removed",
                    monthly_cost=round(cost, 2),
                )
            )

            for app in running:
                instance = app.get("ResourceSpec", {}).get("InstanceType", "")
                owner = app.get("UserProfileName") or app.get("SpaceName", "")
                resources.append(
                    _resource(
                        self.region,
                        "Studio App",
                        f"{domain_id}/{owner}/{app['AppType']}/{app['AppName']}",
                        app["AppName"],
                        app.get("Status", ""),
                        f"{app['AppType']} on {instance or 'default'} - owner {owner}",
                        domain_id=domain_id,
                        app_type=app["AppType"],
                        app_name=app["AppName"],
                        user_profile=app.get("UserProfileName", ""),
                        space_name=app.get("SpaceName", ""),
                        impact_note="stops the compute; files in the home folder are kept",
                        monthly_cost=ml_monthly(instance) if instance else None,
                    )
                )
        return resources


class SageMakerEndpointScanner(BaseScanner):
    """Real-time endpoints plus the endpoint configs and models behind them."""

    service_name = "SageMaker Endpoints"
    boto_service = "sagemaker"

    def scan(self) -> list[AwsResource]:
        sm = self.client("sagemaker")
        configs: dict[str, dict] = {}
        for summary in self.paginate(sm, "list_endpoint_configs", "EndpointConfigs"):
            name = summary["EndpointConfigName"]
            try:
                configs[name] = sm.describe_endpoint_config(EndpointConfigName=name)
            except ClientError:
                configs[name] = {}
        models_by_config = {
            name: [v["ModelName"] for v in cfg.get("ProductionVariants", []) if v.get("ModelName")]
            for name, cfg in configs.items()
        }
        model_users: dict[str, set[str]] = defaultdict(set)
        for cfg_name, models in models_by_config.items():
            for model in models:
                model_users[model].add(cfg_name)

        endpoints = list(self.paginate(sm, "list_endpoints", "Endpoints"))
        endpoint_cfg: dict[str, str] = {}
        for endpoint in endpoints:
            try:
                info = sm.describe_endpoint(EndpointName=endpoint["EndpointName"])
            except ClientError:
                info = {}
            endpoint_cfg[endpoint["EndpointName"]] = info.get("EndpointConfigName", "")
        used_configs = set(endpoint_cfg.values())
        resources: list[AwsResource] = []
        for endpoint in endpoints:
            name = endpoint["EndpointName"]
            cfg_name = endpoint_cfg[name]
            cfg = configs.get(cfg_name, {})
            variants = cfg.get("ProductionVariants", [])
            components = list(
                self.paginate(
                    sm, "list_inference_components", "InferenceComponents", EndpointNameEquals=name
                )
            )
            other_users_of_cfg = sum(
                1 for other, c in endpoint_cfg.items() if other != name and c == cfg_name
            )

            model_nodes = []
            delete_models = []
            for model in models_by_config.get(cfg_name, []):
                others = model_users[model] - {cfg_name}
                if others:
                    model_nodes.append(
                        dep(
                            "Model", model, Action.KEEP, f"also used by {', '.join(sorted(others))}"
                        )
                    )
                else:
                    model_nodes.append(dep("Model", model, note="artifacts in S3 are kept"))
                    delete_models.append(model)
            dependents = [
                dep("Inference component", c["InferenceComponentName"]) for c in components
            ]
            if cfg_name:
                dependents.append(
                    dep(
                        "Endpoint config",
                        cfg_name,
                        Action.KEEP if other_users_of_cfg else Action.DELETE,
                        "used by another endpoint" if other_users_of_cfg else "",
                        children=model_nodes,
                    )
                )
            dependents.append(dep("CloudWatch log group", f"/aws/sagemaker/Endpoints/{name}"))
            dependents.append(
                dep(
                    "Model artifacts / data capture in S3",
                    "s3://...",
                    Action.KEEP,
                    "your S3 data is never touched",
                )
            )

            cost = 0.0
            shapes = []
            for variant in variants:
                if variant.get("ServerlessConfig"):
                    shapes.append("serverless")
                    continue
                instance = variant.get("InstanceType", "")
                count = variant.get("InitialInstanceCount", 1)
                shapes.append(f"{count}× {instance}")
                cost += ml_monthly(instance, count) or 0.0
            resources.append(
                _resource(
                    self.region,
                    "Endpoint",
                    name,
                    name,
                    endpoint.get("EndpointStatus", ""),
                    ", ".join(shapes) or "inference components",
                    endpoint_name=name,
                    endpoint_config=cfg_name if not other_users_of_cfg else "",
                    delete_models=delete_models,
                    inference_components=[c["InferenceComponentName"] for c in components],
                    dependents=dependents,
                    monthly_cost=round(cost, 2),
                )
            )

        for cfg_name, cfg in configs.items():
            if cfg_name in used_configs:
                continue
            resources.append(
                _resource(
                    self.region,
                    "Endpoint Config",
                    cfg_name,
                    cfg_name,
                    "unused",
                    "not attached to any endpoint",
                    endpoint_config=cfg_name,
                    dependents=[
                        dep("Model", m, Action.KEEP, "delete separately if unused")
                        for m in models_by_config.get(cfg_name, [])
                    ],
                    monthly_cost=0.0,
                )
            )

        for model in self.paginate(sm, "list_models", "Models"):
            name = model["ModelName"]
            if name in model_users:
                continue
            resources.append(
                _resource(
                    self.region,
                    "Model",
                    name,
                    name,
                    "unused",
                    "not used by any endpoint config",
                    model_name=name,
                    dependents=[
                        dep(
                            "Model artifacts in S3",
                            "s3://...",
                            Action.KEEP,
                            "your S3 data is never touched",
                        )
                    ],
                    monthly_cost=0.0,
                )
            )
        return resources


class SageMakerNotebookScanner(BaseScanner):
    service_name = "SageMaker Notebooks"
    boto_service = "sagemaker"

    def scan(self) -> list[AwsResource]:
        sm = self.client("sagemaker")
        resources: list[AwsResource] = []
        for nb in self.paginate(sm, "list_notebook_instances", "NotebookInstances"):
            name = nb["NotebookInstanceName"]
            status = nb.get("NotebookInstanceStatus", "")
            if status in _GONE:
                continue
            try:
                info = sm.describe_notebook_instance(NotebookInstanceName=name)
            except ClientError:
                info = {}
            volume = info.get("VolumeSizeInGB", 5)
            instance = nb.get("InstanceType", "")
            dependents = [dep("ML storage volume", f"{volume} GB", note="notebook files on it")]
            if nb.get("NotebookInstanceLifecycleConfigName"):
                dependents.append(
                    dep(
                        "Lifecycle config",
                        nb["NotebookInstanceLifecycleConfigName"],
                        Action.KEEP,
                        "free - may be shared",
                    )
                )
            running = status in {"InService", "Pending", "Updating"}
            compute = (ml_monthly(instance) or 0.0) if running else 0.0
            resources.append(
                _resource(
                    self.region,
                    "Notebook Instance",
                    name,
                    name,
                    status,
                    f"{instance}, {volume} GB volume",
                    notebook_name=name,
                    dependents=dependents,
                    impact_note="stopped first if running" if running else "",
                    monthly_cost=round(compute + volume * 0.14, 2),
                )
            )
        return resources


_JOB_KINDS = [
    # (resource type, list op, list key, name key, status key, delete supported)
    (
        "Training Job",
        "list_training_jobs",
        "TrainingJobSummaries",
        "TrainingJobName",
        "TrainingJobStatus",
        True,
    ),
    (
        "Processing Job",
        "list_processing_jobs",
        "ProcessingJobSummaries",
        "ProcessingJobName",
        "ProcessingJobStatus",
        True,
    ),
    (
        "Tuning Job",
        "list_hyper_parameter_tuning_jobs",
        "HyperParameterTuningJobSummaries",
        "HyperParameterTuningJobName",
        "HyperParameterTuningJobStatus",
        True,
    ),
    (
        "Transform Job",
        "list_transform_jobs",
        "TransformJobSummaries",
        "TransformJobName",
        "TransformJobStatus",
        False,
    ),
]


class SageMakerJobScanner(BaseScanner):
    """Training, processing, tuning and batch-transform jobs (running ones first)."""

    service_name = "SageMaker Jobs"
    boto_service = "sagemaker"

    def scan(self) -> list[AwsResource]:
        sm = self.client("sagemaker")
        resources: list[AwsResource] = []
        for rtype, op, key, name_key, status_key, deletable in _JOB_KINDS:
            seen = 0
            for job in self.paginate(sm, op, key, SortBy="CreationTime", SortOrder="Descending"):
                status = job.get(status_key, "")
                running = status in _JOB_RUNNING
                if not running and (not deletable or seen >= _MAX_FINISHED_JOBS):
                    continue
                seen += 0 if running else 1
                name = job[name_key]
                warm_pool = job.get("WarmPoolStatus", {}).get("Status", "")
                children = []
                if rtype == "Training Job":
                    children.append(
                        dep(
                            "Model artifacts in S3",
                            "output path",
                            Action.KEEP,
                            "your trained model files stay in S3",
                        )
                    )
                    children.append(
                        dep(
                            "CloudWatch logs",
                            f"/aws/sagemaker/TrainingJobs/{name}",
                            Action.KEEP,
                            "delete the log group separately",
                        )
                    )
                    if warm_pool in {"Available", "InUse"}:
                        children.insert(
                            0,
                            dep(
                                "Warm pool instances",
                                warm_pool,
                                note="released so they stop billing",
                            ),
                        )
                if rtype == "Tuning Job":
                    children.append(
                        dep(
                            "Training jobs it launched",
                            "child jobs",
                            Action.KEEP,
                            "listed separately as Training Jobs",
                        )
                    )
                if running:
                    action = Action.DELETE if deletable else Action.STOP
                    note = "stopped first, then its record is deleted" if deletable else ""
                else:
                    action, note = Action.DELETE, "only the job record - it is not running"
                resources.append(
                    _resource(
                        self.region,
                        rtype,
                        name,
                        name,
                        status,
                        ("RUNNING - billing now" if running else "finished")
                        + (f", warm pool {warm_pool}" if warm_pool else ""),
                        job_name=name,
                        job_kind=rtype,
                        running=running,
                        warm_pool=warm_pool in {"Available", "InUse"},
                        delete_action=action.value,
                        impact_note=note,
                        dependents=children,
                        monthly_cost=None if running else 0.0,
                    )
                )
        return resources


class SageMakerPlatformScanner(BaseScanner):
    """MLflow tracking servers, HyperPod clusters and feature groups."""

    service_name = "SageMaker MLflow & HyperPod"
    boto_service = "sagemaker"

    def scan(self) -> list[AwsResource]:
        sm = self.client("sagemaker")
        resources: list[AwsResource] = []
        mlflow_hourly = {"Small": 0.60, "Medium": 1.20, "Large": 2.40}
        for server in self.paginate(sm, "list_mlflow_tracking_servers", "TrackingServerSummaries"):
            name = server["TrackingServerName"]
            status = server.get("TrackingServerStatus", "")
            if status in {"Deleting", "Deleted"}:
                continue
            try:
                size = sm.describe_mlflow_tracking_server(TrackingServerName=name).get(
                    "TrackingServerSize", "Small"
                )
            except ClientError:
                size = "Small"
            resources.append(
                _resource(
                    self.region,
                    "MLflow Tracking Server",
                    name,
                    name,
                    status,
                    f"size {size}",
                    tracking_server=name,
                    dependents=[
                        dep(
                            "Artifact store in S3",
                            "s3://...",
                            Action.KEEP,
                            "your experiment artifacts stay in S3",
                        )
                    ],
                    monthly_cost=hourly_to_monthly(mlflow_hourly.get(size, 0.6)),
                )
            )
        for cluster in self.paginate(sm, "list_clusters", "ClusterSummaries"):
            name = cluster["ClusterName"]
            if cluster.get("ClusterStatus") in {"Deleting"}:
                continue
            resources.append(
                _resource(
                    self.region,
                    "HyperPod Cluster",
                    name,
                    name,
                    cluster.get("ClusterStatus", ""),
                    "HyperPod training cluster",
                    cluster_name=name,
                    dependents=[dep("All cluster nodes", "instance groups")],
                    monthly_cost=None,
                )
            )
        for group in self.paginate(sm, "list_feature_groups", "FeatureGroupSummaries"):
            name = group["FeatureGroupName"]
            if group.get("FeatureGroupStatus") in {"Deleting", "DeleteFailed"}:
                continue
            resources.append(
                _resource(
                    self.region,
                    "Feature Group",
                    name,
                    name,
                    group.get("FeatureGroupStatus", ""),
                    "Feature Store",
                    feature_group=name,
                    dependents=[
                        dep("Online store records", name, note="online store billing stops"),
                        dep(
                            "Offline store data in S3",
                            "s3://...",
                            Action.KEEP,
                            "your S3 data is never touched",
                        ),
                    ],
                )
            )
        return resources
