# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Orphanaut."""

import sys
from pathlib import Path

block_cipher = None
src = Path(SPECPATH)

a = Analysis(
    [str(src / "src" / "orphanaut" / "main.py")],
    pathex=[str(src / "src")],
    binaries=[],
    datas=[],
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
        "orphanaut.auth.credentials",
        "orphanaut.aws.pricing",
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
    upx=True,
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
