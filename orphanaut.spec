# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Orphanaut."""

import sys
from pathlib import Path

block_cipher = None
src = Path(SPECPATH)

# Windows zip build includes a short student guide next to the executable.
datas = []
if sys.platform == "win32":
    datas.append((str(src / "WINDOWS-STUDENTS.txt"), "."))

a = Analysis(
    [str(src / "src" / "orphanaut" / "main.py")],
    pathex=[str(src / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "orphanaut",
        "orphanaut.main",
        "orphanaut.ui.main_window",
        "orphanaut.ui.auth_panel",
        "orphanaut.ui.region_panel",
        "orphanaut.ui.workers",
        "orphanaut.ui.styles",
        "orphanaut.scanners.registry",
        "orphanaut.scanners.ec2",
        "orphanaut.scanners.ebs",
        "orphanaut.scanners.snapshots",
        "orphanaut.scanners.eip",
        "orphanaut.scanners.nat",
        "orphanaut.scanners.elb",
        "orphanaut.scanners.rds",
        "orphanaut.scanners.lambda_fn",
        "orphanaut.scanners.s3",
        "orphanaut.scanners.security_groups",
        "orphanaut.scanners.ecs",
        "orphanaut.scanners.eks",
        "orphanaut.scanners.elasticache",
        "orphanaut.scanners.dynamodb",
        "orphanaut.scanners.cloudwatch",
        "orphanaut.scanners.route53",
        "orphanaut.scanners.vpc_endpoints",
        "orphanaut.scanners.lightsail",
        "orphanaut.actions.deleter",
        "orphanaut.auth.router",
        "orphanaut.auth.aws",
        "orphanaut.auth.azure",
        "orphanaut.auth.gcp",
        "orphanaut.aws.pricing",
        "orphanaut.providers.pricing",
        "orphanaut.providers.azure_pricing",
        "orphanaut.providers.gcp_pricing",
        "orphanaut.scanners.azure_registry",
        "orphanaut.scanners.gcp_registry",
        "orphanaut.scanners.azure_vms",
        "orphanaut.scanners.azure_disks",
        "orphanaut.scanners.azure_public_ips",
        "orphanaut.scanners.azure_storage",
        "orphanaut.scanners.gcp_instances",
        "orphanaut.scanners.gcp_disks",
        "orphanaut.scanners.gcp_addresses",
        "orphanaut.scanners.gcp_storage",
        "orphanaut.actions.azure_deleter",
        "orphanaut.actions.gcp_deleter",
        "orphanaut.ui.cloud_sidebar",
        "orphanaut.ui.provider_selector",
        "orphanaut.auth.credentials",
        "orphanaut.aws.config",
        "orphanaut.aws.regions",
        "boto3",
        "botocore",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Windows: folder build (onedir) — more reliable than single-file .exe on student PCs.
# Antivirus and SmartScreen often block one-file PyInstaller apps that unpack to TEMP.
if sys.platform == "win32":
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="Orphanaut",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name="Orphanaut",
    )
else:
    # macOS / other: single-file exe (macOS wraps it in .app below).
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="Orphanaut",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=sys.platform == "darwin",
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Orphanaut.app",
        icon=None,
        bundle_identifier="com.orphanaut.app",
    )
