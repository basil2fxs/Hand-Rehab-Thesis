# PyInstaller spec for the setup and diagnostics tool. Built alongside
# the game by build_app.sh / build_app.bat. Produces:
#   macOS:   bin/dist/Finger Rehab Setup.app
#   Windows: bin/dist/Finger Rehab Setup.exe
#   Linux:   bin/dist/Finger Rehab Setup
#
# Much smaller than the game: no librosa, no scipy, no matplotlib. The
# setup tool draws seven buttons and shells out to avrdude, so pulling
# the audio and analysis stack in would add a couple of hundred
# megabytes for nothing. That is also why it is a separate spec rather
# than a second EXE() inside the game's: the excludes differ.

import sys
from pathlib import Path

block_cipher = None

IS_MAC = sys.platform == "darwin"

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

# avrdude rides along so a fresh machine can flash a board without
# developer tools. Missing is not an error: the flash button then says
# so rather than failing halfway.
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

icon_file = ("assets/icons/app_icon.icns" if IS_MAC
             else "assets/icons/app_icon.ico")

a = Analysis(
    ["setup_tool.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
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
        # The heavy half of the game. The setup tool never scores a
        # trial, plays a song or draws a chart.
        "librosa",
        "soundfile",
        "scipy",
        "matplotlib",
        "numba",
        "sklearn",
    ],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if IS_MAC:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="Finger Rehab Setup",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        icon=icon_file,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        name="Finger Rehab Setup",
    )
    app = BUNDLE(
        coll,
        name="Finger Rehab Setup.app",
        icon=icon_file,
        bundle_identifier="com.fingerrehab.setup",
        info_plist={
            "NSHighResolutionCapable": True,
            # No microphone, camera or network use, so nothing to ask
            # the user for.
            "LSMinimumSystemVersion": "11.0",
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="Finger Rehab Setup",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=False,
        icon=icon_file,
    )
