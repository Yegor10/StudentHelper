# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all


ROOT = Path(SPECPATH).parent
datas = []
binaries = []
hiddenimports = []

for package in ("customtkinter", "google.generativeai", "google_auth_oauthlib"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_hiddenimports)

datas.append(
    (
        str(ROOT / "src" / "studenthelper" / "default-schedule.json"),
        "studenthelper",
    )
)

a = Analysis(
    [str(ROOT / "src" / "studenthelper" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["mkdocs", "pytest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="StudentHelper",
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
)
