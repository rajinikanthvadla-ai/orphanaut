## Orphanaut 2.1.1 — AI & ML cleanup, delete impact map, and a brand-new app

### Highlights
- **AI & ML resources on all three clouds.** SageMaker (Studio domains, apps, endpoints, notebooks, training/processing/tuning jobs, MLflow, HyperPod, feature groups), Bedrock (knowledge bases + vector stores, agents, provisioned throughput for Claude and other models, custom/imported models, running jobs), OpenSearch Serverless, Kendra, Comprehend, Rekognition; Azure OpenAI / AI Services / AI Foundry, Azure Machine Learning, Azure AI Search; Vertex AI endpoints, models, Vector Search, jobs, Agent Engine, Workbench, Colab runtimes and Vertex AI Search.
- **Delete impact map.** Select a resource to see every associated item that is deleted, stopped or kept — shown again in the confirmation dialog.
- **Cascade deletion in the right order**, e.g. a SageMaker domain removes its apps, spaces, user profiles and home EFS volume.
- **New sign-in options on every cloud:** keys, **sign in with browser** (AWS IAM Identity Center without the CLI, Microsoft, Google), or **reuse the login already on this computer** — detected automatically. Switch account / subscription / project after signing in.
- **New look:** cloud tabs at the top with their own workspace each, category tabs (AI & ML, Compute, Storage, Networking, Databases, Monitoring), built-in guide (F1), new colour theme.

### Downloads
| | |
|---|---|
| Windows installer | `Orphanaut-Setup-Windows.exe` |
| Windows portable | `Orphanaut-Windows-Portable.zip` |
| macOS Apple Silicon | `Orphanaut-macOS-AppleSilicon.dmg` (or `.zip`) |
| macOS Intel | `Orphanaut-macOS-Intel.dmg` (or `.zip`) |
| Python package | `orphanaut-*.whl` — `pip install orphanaut-*.whl` |

Windows: if SmartScreen appears, click **More info → Run anyway**. macOS: right-click → **Open**.

### Fixes
- Azure and Google Cloud now work in the packaged app (their SDK modules and Google API discovery files are bundled).
- Signing in no longer freezes the window.
- EKS clusters with node groups and Aurora clusters with instances are now deleted in the right order.
