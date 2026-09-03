"""Run the lab task from source instead of the exe.

The game is pygame, not PsychoPy, so there is no .psyexp to open.
PsychoPy's Runner runs any Python script, so it can run this one, as
can any Python 3.10+. It needs the source checkout and the packages
listed below; the exe next to this file needs neither.

Source: https://github.com/basil2fxs/Hand-Rehab-Thesis
This file must sit at docs/lab_package inside that checkout. If you
only have the lab folder, clone the repo and run the copy in there.
"""
import importlib.util
import sys
import subprocess
from pathlib import Path

# import name -> pip install name. Everything the game imports at run
# time, not just what it needs to open: rhythm's beat tracking loads
# librosa (and soundfile to decode), the block report draws with
# matplotlib, and the block metrics and the force trace filters use
# scipy. Those imports are lazy, so a Python missing one would open
# the game and then fail at the end of the first block or the first
# rhythm pick, with the lab session already under way.
PACKAGES = {"pygame": "pygame-ce", "serial": "pyserial",
            "yaml": "pyyaml", "numpy": "numpy", "scipy": "scipy",
            "librosa": "librosa", "soundfile": "soundfile",
            "matplotlib": "matplotlib"}


def _pygame_is_ce() -> bool:
    """True when the installed pygame is pygame-ce.

    Standalone PsychoPy ships CLASSIC pygame, so a plain import check
    passes and the game then dies on a pygame-ce call. Both packages
    import as "pygame", and only pygame-ce carries IS_CE.
    """
    try:
        import pygame
    except Exception:
        return False
    if getattr(pygame, "IS_CE", False):
        return True
    return "ce" in str(getattr(pygame, "version", "")).lower()


def main() -> int:
    here = Path(__file__).resolve().parent
    repo = here.parents[1]
    in_psychopy = any("psychopy" in str(p).lower() for p in sys.path)
    if in_psychopy:
        print("Running inside PsychoPy's Python. That is fine: this is a "
              "plain script, not a PsychoPy experiment.")

    if not (repo / "main.py").is_file() or not (repo / "finger_rehab").is_dir():
        print("No source checkout around this file. Either:")
        print("  - just double-click Finger Rehab.exe in this folder, or")
        print("  - git clone https://github.com/basil2fxs/Hand-Rehab-Thesis.git")
        print("    and run this same file from docs/lab_package in the clone.")
        return 1

    missing = [pip for mod, pip in PACKAGES.items()
               if importlib.util.find_spec(mod) is None]
    # Classic pygame present instead of pygame-ce is the PsychoPy case:
    # the import succeeds, so it has to be named separately or the game
    # fails later with something that looks unrelated.
    wrong_pygame = (not missing or "pygame-ce" not in missing) \
        and importlib.util.find_spec("pygame") is not None \
        and not _pygame_is_ce()
    if wrong_pygame:
        print("This Python has classic pygame; the game needs pygame-ce.")
        print("PsychoPy ships classic pygame, so install the ce build:")
        print(f'  "{sys.executable}" -m pip install --upgrade pygame-ce')
        print("(pygame-ce replaces pygame; PsychoPy keeps working.)")
        return 1
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
    # A subprocess rather than an import: PsychoPy's Runner keeps its
    # own pygame display state, and a fresh process cannot inherit it.
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
