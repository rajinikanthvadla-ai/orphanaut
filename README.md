# Orphanaut

Find and delete leftover cloud resources on AWS, Azure and Google Cloud before they run up a bill. Includes AI services like SageMaker, Bedrock, Azure OpenAI and Vertex AI.

Desktop app for Windows and macOS. Free and open source.

[Download the latest release](https://github.com/rajinikanthvadla-ai/orphanaut/releases/latest)

![Orphanaut](docs/images/ai-impact-map.png)

## Features

- AWS, Azure and Google Cloud, each in its own tab
- AI services: SageMaker, Bedrock, OpenSearch Serverless, Kendra, Azure OpenAI, Azure ML, AI Search, Vertex AI and more
- Resource map that shows what each resource is connected to and what happens to it on delete
- Deletes things in the right order (for example a SageMaker domain's apps, spaces and user profiles first)
- Sign in with keys, through the browser, or with the CLI login already on your computer
- Rough monthly cost for each resource
- Checks for new versions and updates itself

## Download

| System | File |
|---|---|
| Windows | `Orphanaut-Setup-Windows.exe` (or the portable zip) |
| Mac with Apple Silicon | `Orphanaut-macOS-AppleSilicon.dmg` |
| Mac with Intel | `Orphanaut-macOS-Intel.dmg` |

The apps are not code signed yet. On Windows click **More info > Run anyway**. On a Mac, right-click the app and choose **Open**.

## Usage

1. Pick a cloud at the top and sign in on the left.
2. Choose your regions and click **Scan**.
3. Tick the resources you want to remove and check the map on the right.
4. Click **Delete** and confirm.

## Permissions

| Cloud | Scan | Delete |
|---|---|---|
| AWS | ReadOnlyAccess | PowerUserAccess or AdministratorAccess |
| Azure | Reader | Contributor |
| Google Cloud | Viewer | Editor |

Use a sandbox or lab account. Deleted resources can't be recovered.

## Run from source

```bash
git clone https://github.com/rajinikanthvadla-ai/orphanaut.git
cd orphanaut
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux
pip install -e .
orphanaut
```

For development: `pip install -e ".[dev]"`, then `pytest` and `ruff check src tests`.
Pushing a tag like `v2.2.0` builds the installers and publishes a release.

## License

MIT. Made by Rajinikanth Vadla.
