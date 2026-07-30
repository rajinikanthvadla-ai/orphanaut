# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not** open a public issue.

Instead, email the maintainer or use GitHub's private vulnerability reporting if enabled.

## Credential Handling

- Orphanaut stores credentials **only in memory** during the session.
- Access keys are never written to disk by the application.
- For SSO, use standard AWS CLI profiles (`~/.aws/config`).
- Never commit `.aws/` credentials or share keys in issues or pull requests.

## IAM Permissions

Orphanaut requires broad read access across AWS services and delete permissions for cleanup. Use a dedicated IAM user or role with least privilege where possible. See the README for recommended IAM policies.
