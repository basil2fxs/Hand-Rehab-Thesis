"""Run the lab task from source instead of the exe.

The game is pygame, not PsychoPy, so there is no .psyexp to open.
PsychoPy's runner can still run this file (it runs any Python
script), as can any Python 3.10+. It needs the source checkout and
four packages; the exe next to this file needs neither.

Source: https://github.com/basil2fxs/Hand-Rehab-Thesis
This file must sit at docs/lab_package inside that checkout. If you
only have the lab folder, clone the repo and run the copy in there.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

# import name -> pip install name
PACKAGES = {"pygame": "pygame-ce", "serial": "pyserial",
            "yaml": "pyyaml", "numpy": "numpy"}


def main() -> int:
    here = Path(__file__).resolve().parent
    repo = here.parents[1]
    if not (repo / "main.py").is_file() or not (repo / "finger_rehab").is_dir():
        print("No source checkout around this file. Clone the repo:")
        print("  git clone https://github.com/basil2fxs/Hand-Rehab-Thesis.git")
        print("then run this same file from docs/lab_package in the clone.")
        return 1
    missing = [pip for mod, pip in PACKAGES.items()
               if importlib.util.find_spec(mod) is None]
    if missing:
        print("This Python is missing packages the game needs. Run:")
        print(f'  "{sys.executable}" -m pip install ' + " ".join(missing))
        return 1
    # Prefer the lab folder's own config so an edited eeg.port is
    # honoured; fall back to the repo's copy on a fresh checkout.
    lab_cfg = here / "eeg_lab.yaml"
    if not lab_cfg.is_file():
        lab_cfg = repo / "config" / "eeg_lab.yaml"
    entry = repo / "main.py"
    print(f"Starting lab mode: {entry} --config {lab_cfg}")
    return subprocess.call([sys.executable, str(entry),
                            "--config", str(lab_cfg)], cwd=str(repo))


if __name__ == "__main__":
    rc = main()
    if rc != 0:
        try:
            input("Press Enter to close.")
        except EOFError:
            pass
    sys.exit(rc)
