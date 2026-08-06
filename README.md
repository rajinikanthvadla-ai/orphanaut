# Orphanaut

**Find and clean up billable AWS, Azure, and GCP resources — with a simple desktop GUI.**

Orphanaut helps students and developers discover leftover cloud resources that can incur charges, review them in one place, and delete them safely from the app.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey)
![Clouds](https://img.shields.io/badge/clouds-AWS%20%7C%20Azure%20%7C%20GCP-orange)

---

## Features

- **Multi-cloud** — AWS, Azure, and GCP in one app with a clean provider switcher
- **Zero-install download** — students get a ready-to-run `.exe`/`.app`, no Python needed
- **Cost estimation** — see roughly what each leftover resource costs per month before it bills you
- **Cross-platform GUI** — native desktop app for **Windows** and **macOS**
- **Two auth methods** — AWS Access Key + Secret Key, or **AWS SSO** profile
- **All regions** — scans every enabled AWS region in parallel
- **18+ resource types** — EC2, EBS, RDS, Lambda, S3, Security Groups, and more
- **Safe deletion** — protected/in-use resources are blocked; confirmation before anything is destroyed
- **Export to CSV** — share or archive scan results
- **No credential storage** — keys stay in memory for the session only

## Download — no code required

**Students: you don't need to clone this repo or install Python.** Just grab the pre-built app for your OS from the [Releases](https://github.com/rajinikanthvadla-ai/orphanaut/releases) page:

| Platform | File | How to run |
|----------|------|------------|
| **Windows** | `Orphanaut-Windows.zip` | Extract to e.g. `C:\Orphanaut` → open `Orphanaut.exe` |
| **macOS** | `Orphanaut-macOS.zip` | Extract → open `Orphanaut.app` |

> **Windows:** This is **not an installer** — nothing installs to Program Files. Extract the zip, then double-click `Orphanaut.exe`. If SmartScreen warns, click **More info** → **Run anyway**. If the app vanishes, check **Windows Security → Protection history** and **Allow** Orphanaut. See `WINDOWS-STUDENTS.txt` in the zip for full steps.

> **macOS first launch:** If Gatekeeper blocks the app, right-click it → **Open** → **Open anyway**. This is normal for unsigned community apps.

## Quick Start (2 minutes)

1. Download the file for your OS from [Releases](https://github.com/rajinikanthvadla-ai/orphanaut/releases)
2. Launch **Orphanaut**
3. Paste your **Access Key ID** and **Secret Access Key** (from your instructor or AWS Console)
4. Click **Connect**, pick your lab regions, then click **Scan**
5. Review resources, see their estimated monthly cost, and delete anything you don't need

That's it — no terminal, no Python, no dependencies.

---

### Advanced: run from source

Only needed if you want to contribute to the code itself. Most users should just download the app above.

```bash
git clone https://github.com/rajinikanthvadla-ai/orphanaut.git
cd orphanaut
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -e .
orphanaut
```

## Authentication

### AWS — Access Keys

Enter your **Access Key ID** and **Secret Access Key**. Optionally add a **Session Token** for temporary credentials.

### AWS — SSO

1. Configure SSO with the AWS CLI:
   ```bash
   aws configure sso
   ```
2. Log in before opening Orphanaut:
   ```bash
   aws sso login --profile YOUR_PROFILE
   ```
3. In Orphanaut, select **AWS** → **SSO** tab, choose your profile, and click **Connect**.

### Azure — Service Principal

1. In Azure Portal → **App registrations** → create or use an app
2. Copy **Tenant ID**, **Client ID**, create a **Client secret**
3. Copy your **Subscription ID**
4. Grant the app **Contributor** (or Reader + delete roles) on the subscription
5. In Orphanaut, select **Azure**, paste all four values, click **Connect**

### GCP — Service Account

1. In Google Cloud Console → **IAM** → **Service accounts** → create key (JSON)
2. Grant roles like **Viewer** plus delete permissions for resources you want to clean
3. In Orphanaut, select **GCP**, enter **Project ID**, paste or load the JSON key, click **Connect**

## Scanned Resources

| Cloud | Services scanned |
|-------|------------------|
| **AWS** | EC2, EBS, RDS, Lambda, S3, Security Groups, ELB, NAT, EKS, ECS, and more (18+ types) |
| **Azure** | Virtual Machines, Managed Disks, Public IPs, Storage Accounts |
| **GCP** | Compute Instances, Disks, Static IPs, Storage Buckets |

## IAM Permissions

Orphanaut needs **read** access to list resources and **delete** access if you use the delete feature. For educational accounts, a broad policy is often acceptable. Example policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "ec2:TerminateInstances",
        "ec2:DeleteVolume",
        "ec2:DeleteSnapshot",
        "ec2:ReleaseAddress",
        "ec2:DeleteNatGateway",
        "ec2:DeleteVpcEndpoints",
        "ec2:DeleteSecurityGroup",
        "elasticloadbalancing:Describe*",
        "elasticloadbalancing:DeleteLoadBalancer",
        "rds:Describe*",
        "rds:DeleteDBInstance",
        "rds:DeleteDBCluster",
        "lambda:ListFunctions",
        "lambda:DeleteFunction",
        "s3:ListAllMyBuckets",
        "s3:ListBucket",
        "s3:DeleteObject",
        "s3:DeleteBucket",
        "ecs:List*",
        "ecs:Describe*",
        "ecs:DeleteCluster",
        "eks:ListClusters",
        "eks:DescribeCluster",
        "eks:DeleteCluster",
        "elasticache:Describe*",
        "elasticache:DeleteCacheCluster",
        "dynamodb:ListTables",
        "dynamodb:DescribeTable",
        "dynamodb:DeleteTable",
        "logs:DescribeLogGroups",
        "logs:DeleteLogGroup",
        "route53:ListHostedZones",
        "route53:ListResourceRecordSets",
        "route53:ChangeResourceRecordSets",
        "route53:DeleteHostedZone",
        "lightsail:GetInstances",
        "lightsail:DeleteInstance",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

> Restrict permissions in production. Students should use a dedicated AWS account or sandbox.

## Building Executables

```bash
pip install -e ".[dev]"
pyinstaller orphanaut.spec --noconfirm
```

- **Windows:** `dist/Orphanaut/Orphanaut.exe` (folder build; zip as `Orphanaut-Windows.zip` for releases)
- **macOS:** `dist/Orphanaut.app`

Releases are built automatically when you push a tag like `v1.0.0`.

## Project Structure

```
orphanaut/
├── src/orphanaut/
│   ├── auth/          # AWS authentication (keys + SSO)
│   ├── aws/           # Region utilities
│   ├── scanners/      # Per-service resource scanners
│   ├── actions/       # Delete handlers
│   └── ui/            # PySide6 GUI
├── tests/
├── .github/workflows/ # CI and release builds
└── orphanaut.spec     # PyInstaller configuration
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and pull requests are welcome.

## Security

See [SECURITY.md](SECURITY.md). **Never commit AWS credentials.**

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Rajinikanth Vadla.

## Disclaimer

Orphanaut is an educational tool. **Deletion is permanent.** Always review resources before deleting. The authors are not responsible for accidental data loss or AWS charges.
