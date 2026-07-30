# Orphanaut

**Find and clean up billable AWS resources across every region — with a simple desktop GUI.**

Orphanaut helps students and developers discover leftover AWS resources that can incur charges (EC2, RDS, EBS, Lambda, S3, and more), review them in one place, and delete them safely from the app.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey)

---

## Features

- **Cross-platform GUI** — native desktop app for **Windows** and **macOS**
- **Two auth methods** — AWS Access Key + Secret Key, or **AWS SSO** profile
- **All regions** — scans every enabled AWS region in parallel
- **18+ resource types** — EC2, EBS, RDS, Lambda, S3, Security Groups, and more
- **Delete from the app** — select resources and delete with confirmation
- **Export to CSV** — share or archive scan results
- **No credential storage** — keys stay in memory for the session only

## Download

Pre-built executables are available on the [Releases](https://github.com/rajinikanthvadla/orphanaut/releases) page:

| Platform | File |
|----------|------|
| Windows  | `Orphanaut.exe` |
| macOS    | `Orphanaut-macOS.zip` (extract and open `Orphanaut.app`) |

> **macOS:** On first launch, right-click the app → **Open** if Gatekeeper blocks unsigned builds.

## Quick Start

### Option 1: Download the executable

1. Download the build for your OS from [Releases](https://github.com/rajinikanthvadla/orphanaut/releases).
2. Launch **Orphanaut**.
3. Connect with **Access Keys** or an **SSO Profile**.
4. Click **Scan All Regions**.
5. Review resources, delete unwanted ones, or export a CSV.

### Option 2: Run from source

```bash
git clone https://github.com/rajinikanthvadla/orphanaut.git
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

### Access Keys

Enter your **Access Key ID** and **Secret Access Key**. Optionally add a **Session Token** for temporary credentials.

### AWS SSO

1. Configure SSO with the AWS CLI:
   ```bash
   aws configure sso
   ```
2. Log in before opening Orphanaut:
   ```bash
   aws sso login --profile YOUR_PROFILE
   ```
3. In Orphanaut, select the **SSO Profile** tab, choose your profile, and click **Connect**.

## Scanned Resources

Orphanaut scans for billable or commonly forgotten resources:

| Service | Resources |
|---------|-----------|
| EC2 | Instances, Elastic IPs |
| EBS | Volumes, Snapshots |
| VPC | NAT Gateways, VPC Endpoints, Security Groups |
| ELB | Application, Network, Classic Load Balancers |
| RDS | DB Instances, DB Clusters |
| Lambda | Functions |
| S3 | Buckets (all regions) |
| ECS | Clusters |
| EKS | Clusters |
| ElastiCache | Cache Clusters |
| DynamoDB | Tables |
| CloudWatch | Log Groups |
| Route 53 | Hosted Zones |
| Lightsail | Instances |

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

- **Windows:** `dist/Orphanaut.exe`
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
