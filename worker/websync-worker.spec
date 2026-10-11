# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification file for WebSync AI Worker Agent."""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['agent/main.py'],
    pathex=['.', '..'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'psutil',
        'websockets',
        'websockets.client',
        'httpx',
        'pydantic',
        'pydantic_settings',
        'worker.agent',
        'worker.agent.config',
        'worker.agent.metrics',
        'worker.agent.capabilities',
        'worker.agent.transport',
        'worker.agent.registration',
        'worker.agent.heartbeat',
        'worker.agent.executor',
        'worker.agent.dispatcher',
        'worker.agent.ws_client',
        'worker.agent.logging_config',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'test'],
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
    name='websync-worker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
