# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Native (CustomTkinter) desktop app - no Flask, no browser wrapper.
datas = [
    ('icon.ico', '.'),
]
binaries = []
hiddenimports = [
    'customtkinter',
    'customtkinter.windows',
    'darkdetect',
    'tkinter',
    'tkinter.filedialog',
    'catalogue_extractor',
]

# pymupdf ships native libraries + resources; pull all of it.
pymupdf_datas, pymupdf_binaries, pymupdf_hiddenimports = collect_all('pymupdf')
datas += pymupdf_datas
binaries += pymupdf_binaries
hiddenimports += pymupdf_hiddenimports

# customtkinter ships theme JSON + font assets that must be bundled.
ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all('customtkinter')
datas += ctk_datas
binaries += ctk_binaries
hiddenimports += ctk_hiddenimports

a = Analysis(
    ['desktop_app.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['flask', 'werkzeug', 'jinja2', 'pywebview', 'webview', 'clr', 'pythonnet',
              'unittest', 'pydoc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Standalone single executable (onefile) configuration.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CatalogueImporter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
