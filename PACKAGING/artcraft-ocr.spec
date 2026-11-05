# -*- mode: python ; coding: utf-8 -*-
"""Build spec for ArtCraft OCR.

Proves and preserves the three things DOCS/PACKAGING.md was written about:

1. rapidocr imports its stage modules by short name, so the subpackages are
   bundled and the adapter aliases them at runtime. Bundling alone is not enough.
2. opencv-python ships an FFmpeg DLL with obligations this project never uses;
   it is filtered out of the collected binaries.
3. The interface is HTML, so APP/ui travels with the build as data — a build
   without it starts to a blank window.
"""

import os

from PyInstaller.utils.hooks import collect_data_files

# Spec files run with paths relative to themselves, so everything is anchored to
# the project root explicitly.
ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [
    (os.path.join(ROOT, "APP", "ui"), "APP/ui"),
    (os.path.join(ROOT, "MODELS"), "MODELS"),
    # The 简↔繁 tables are read at runtime from CORE/data, not imported: a build
    # that omits them converts nothing, and the button silently reports
    # "改动 0 个字" — which reads as the feature breaking on its own.
    (os.path.join(ROOT, "CORE", "data"), "CORE/data"),
]
datas += collect_data_files("rapidocr_onnxruntime")
datas += collect_data_files("webview")

a = Analysis(
    [os.path.join(ROOT, "APP", "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # rapidocr's short-name imports (see DOCS/PACKAGING.md pitfall 1)
        "rapidocr_onnxruntime.ch_ppocr_v3_det",
        "rapidocr_onnxruntime.ch_ppocr_v3_rec",
        "rapidocr_onnxruntime.ch_ppocr_v2_cls",
        # pywebview's Windows backend loads .NET through pythonnet
        "webview.platforms.winforms",
        "clr",
        "pythonnet",
    ],
    hookspath=[],
    runtime_hooks=[],
    # tkinter stays in: the region overlay is a toolkit window, because a WebView
    # one never covered the desktop on this backend.
    excludes=["matplotlib", "scipy", "pandas", "pyperclip", "IPython"],
    noarchive=False,
)

before = len(a.binaries)
a.binaries = [b for b in a.binaries if "ffmpeg" not in b[0].lower()]
print(f"[spec] binaries {before} -> {len(a.binaries)}")

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ArtCraftOCR",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=os.path.join(ROOT, "DOCS", "mockup", "assets", "artcraft-ocr.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="ArtCraftOCR",
)
