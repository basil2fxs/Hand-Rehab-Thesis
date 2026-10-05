# PyInstaller spec. Build via build_app.sh / build_app.bat (those pass
# --workpath bin/build --distpath bin/dist so the root stays clean, then
# copy the finished app into builds/Mac or builds/Windows). Produces:
#   macOS:   bin/dist/Finger Rehab.app          (.app bundle)
#   Windows: bin/dist/Finger Rehab.exe          (single-file exe)
#   Linux:   bin/dist/Finger Rehab              (single-file binary)
#
# build_app.sh then wraps the .app in FingerRehab-macOS.dmg, and CI
# wraps the exe in FingerRehab-Setup-Windows.exe (installers/windows.iss).
#
# Windows and Linux use one-file mode so the deliverable is literally
# one double-clickable file. Trade-off: one-file unpacks itself to a
# temp folder on launch, so the first paint takes several seconds on
# a slow disk. macOS keeps the .app bundle because that IS the one
# double-clickable thing on a Mac, with no unpack delay.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


block_cipher = None

IS_MAC = sys.platform == "darwin"


# Data files that need to ship inside the bundle. config/ carries
# default.yaml; assets/ carries music + the icon set.
# config/default.yaml and the pattern template only. eeg_lab.yaml is
# deliberately NOT bundled: the main install is the game, with no EEG
# anything in it. The lab package puts eeg_lab.yaml BESIDE the exe and
# main.py picks it up from there, which is how Welber's copy turns the
# markers on without a separate build.
#
# user_settings.yaml is not bundled either: it is written at runtime,
# and shipping one would overwrite a machine's own settings on update.
datas = [
    ("config/default.yaml", "config"),
    ("config/pattern_sequence_template.yaml", "config"),
    ("assets", "assets"),
]

# avrdude, so Settings can flash the Arduino on a PC with no developer
# tools installed. The firmware hexes ride along inside assets/ already;
# only the uploader needs its own entries.
#
# The executable goes through `binaries`, not `datas`, because
# PyInstaller ad-hoc signs collected binaries on macOS and an unsigned
# helper inside a signed bundle will not launch. avrdude.conf and the
# two licence files are plain data.
#
# Nothing here is an error when missing: builds/fetch_avrdude.py
# downloads it, and a build without it still works. The Settings panel
# then says "no avrdude found" instead of offering a button that cannot
# do anything.
binaries = []
_plat = "win32" if sys.platform == "win32" else ("darwin" if IS_MAC
                                                 else "linux")
_tool_dir = Path("tools") / "avrdude" / _plat
_exe_name = "avrdude.exe" if _plat == "win32" else "avrdude"
if (_tool_dir / _exe_name).exists():
    _dest = f"tools/avrdude/{_plat}"
    binaries.append((str(_tool_dir / _exe_name), _dest))
    for _extra in ("avrdude.conf", "LICENSE.txt", "SOURCE.txt"):
        if (_tool_dir / _extra).exists():
            datas.append((str(_tool_dir / _extra), _dest))

# librosa pulls a lot in. Let PyInstaller's hook discover the lot.
hidden = []
hidden += collect_submodules("librosa")
hidden += collect_submodules("soundfile")
hidden += collect_submodules("scipy")
hidden += ["pkg_resources.extern", "sklearn.utils._cython_blas"]
# Settings, Audio delay records the microphone through SDL's capture
# device (audio/latency_measure.py), which nothing else imports.
hidden += ["pygame._sdl2", "pygame._sdl2.audio"]
# pyserial imports its URL handlers by name when a port opens, so
# socket://, which the simulator rehearsal uses, is invisible to the
# analysis (missing from the Windows build of 3 October 2026).
hidden += collect_submodules("serial.urlhandler")

# Platform icon: .icns on macOS, .ico on Windows (each format is what
# that OS expects; PyInstaller ignores an icon it cannot use).
icon_file = ("assets/icons/app_icon.icns" if IS_MAC
             else "assets/icons/app_icon.ico")


a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Things we don't need that would balloon the bundle.
        # matplotlib is NOT excluded: the post-block research report
        # renders its charts with it.
        "tkinter",
        "IPython",
        "jupyter",
        "notebook",
        "ipywidgets",
        "ipykernel",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
    ],
    cipher=block_cipher,
)


pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


if IS_MAC:
    # macOS: onedir EXE collected into a folder, wrapped in a .app.
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
        console=False,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_file,
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

    app = BUNDLE(
        coll,
        name="Finger Rehab.app",
        icon="assets/icons/app_icon.icns",
        bundle_identifier="au.edu.curtin.fingerrehab",
        info_plist={
            # Must equal SOFTWARE_VERSION in finger_rehab/data/session.py;
            # test_screen_layout pins the two together, and the Windows
            # installer reads the same number through builds/version.py.
            "CFBundleShortVersionString": "4.0",
            "CFBundleVersion": "4.0",
            "NSHighResolutionCapable": True,
            # Settings, Audio delay listens to the game's own sounds and
            # buzzes; without this macOS stops the app at the microphone.
            "NSMicrophoneUsageDescription":
                "Finger Rehab listens to its own sounds and buzzes once, "
                "to measure this computer's audio delay.",
            "LSApplicationCategoryType":
                "public.app-category.healthcare-fitness",
        },
    )
else:
    # Windows / Linux: one-file executable. Everything (binaries, data,
    # Python itself) ships inside the single file.
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="Finger Rehab",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,          # No terminal window.
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_file,
    )
