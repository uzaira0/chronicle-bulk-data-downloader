# -*- mode: python ; coding: utf-8 -*-

import sys

block_cipher = None

is_windows = sys.platform.startswith('win')
is_macos = sys.platform.startswith('darwin')

hidden_imports = [
    'asyncio',
    'aiofiles',
    'httpx',
    'httpx._transports.default',
    'regex',
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'datetime',
    'json',
    'shutil',
    'chronicle_bulk_data_downloader',
    'chronicle_bulk_data_downloader.core',
    'chronicle_bulk_data_downloader.core.downloader',
    'chronicle_bulk_data_downloader.core.config',
    'chronicle_bulk_data_downloader.core.callbacks',
    'chronicle_bulk_data_downloader.core.exceptions',
    'chronicle_bulk_data_downloader.gui',
    'chronicle_bulk_data_downloader.gui.main_window',
    'chronicle_bulk_data_downloader.download_worker',
    'chronicle_bulk_data_downloader.utils',
    'chronicle_bulk_data_downloader.constants',
    'chronicle_bulk_data_downloader.enums',
]

datas = [
    ('chronicle_bulk_data_downloader', 'chronicle_bulk_data_downloader'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['_tkinter', 'tcl', 'tk', 'test', 'unittest', 'pydoc', 'doctest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
    compress=True
)

if is_windows:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='ChronicleBulkDataDownloader',
        debug=False,
        bootloader_ignore_signals=True,
        strip=True,
        upx=True,
        upx_exclude=['vcruntime140.dll', 'python*.dll', '*.pyd'],
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
        uac_admin=False,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=['vcruntime140.dll', 'python*.dll', '*.pyd'],
        name='ChronicleBulkDataDownloader',
    )

if is_macos:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='ChronicleBulkDataDownloader',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=True,
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
        upx=True,
        name='ChronicleBulkDataDownloader',
    )

    app = BUNDLE(
        coll,
        name='ChronicleBulkDataDownloader.app',
        icon=None,
        bundle_identifier='com.uzaira0.chroniclebulkdatadownloader',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSAppleScriptEnabled': False,
            'NSHighResolutionCapable': True,
            'CFBundleDisplayName': 'Chronicle Bulk Data Downloader',
            'CFBundleName': 'ChronicleBulkDataDownloader',
        },
    )
