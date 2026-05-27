# PyInstaller spec. Build via build_app.sh / build_app.bat (those
# pass --workpath bin/build --distpath bin/dist so the root stays
# clean). Produces:
#   macOS:   bin/dist/Finger Rehab.app
#   Windows: bin/dist/Finger Rehab.exe
#   Linux:   bin/dist/Finger Rehab (binary)

from PyInstaller.utils.hooks import collect_submodules, collect_data_files


block_cipher = None


# Data files that need to ship inside the bundle.
datas = [
    ("config", "config"),
    ("assets", "assets"),
]

# librosa pulls a lot in. Let PyInstaller's hook discover the lot.
hidden = []
hidden += collect_submodules("librosa")
hidden += collect_submodules("soundfile")
hidden += collect_submodules("scipy")
hidden += ["pkg_resources.extern", "sklearn.utils._cython_blas"]


a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Things we don't need that would balloon the bundle.
        "tkinter",
        "matplotlib",
        "IPython",
        "jupyter",
        "notebook",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
    ],
    cipher=block_cipher,
)


pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Finger Rehab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,         # No terminal window on Windows / Mac.
    disable_windowed_traceback=False,
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
    name="Finger Rehab",
)


# macOS-specific .app bundle. PyInstaller silently ignores this on other OSes.
app = BUNDLE(
    coll,
    name="Finger Rehab.app",
    icon=None,
    bundle_identifier="au.edu.curtin.fingerrehab",
    info_plist={
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
        # Required for macOS to grant the app microphone-free audio access.
        "LSApplicationCategoryType": "public.app-category.healthcare-fitness",
    },
)
