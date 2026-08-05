"""Session metadata written alongside the trial/raw CSVs."""
from __future__ import annotations

import json
import os
import platform
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path


SOFTWARE_VERSION = "3.2"


@dataclass
class Session:
    participant: str = "NA"
    # Age in years, captured on the title screen alongside the
    # participant name. Stored as a string so the JSON round-trips
    # raw user input (a researcher might write "65", "65y", "NA",
    # or leave it blank for a patient who declined). Empty string is
    # a valid value meaning "not provided" and is what the title
    # screen leaves it as when the age field stays unfilled.
    age: str = ""
    hand: str = "right"     # "left" / "right" / "both"
    # ---- participant details recorded once, at consent -------------
    # These cannot be recovered after a session, and without them
    # several analyses cannot be run at all. Set them in
    # config/user_settings.yaml under session.* before the participant
    # starts, or leave blank for a non-participant test run.
    #
    # affected_side is the important one. The bilateral asymmetry index
    # is a signed number, so in a stroke cohort where half the people
    # are impaired on the left and half on the right, group means
    # cancel toward zero and read as "no asymmetry" when the asymmetry
    # is in fact large. Knowing the affected side lets the analysis
    # flip the sign per participant and pool them properly.
    affected_side: str = ""        # "left" / "right" / "" if not applicable
    dominant_hand: str = ""        # "left" / "right"
    # Impairment score at consent, e.g. Fugl-Meyer upper extremity out
    # of 66. Free text so any scale can be recorded with its name.
    # Needed to show the cohort matches the moderate-impairment group
    # the 65 to 80 percent challenge band was chosen for.
    impairment_score: str = ""
    # Hand measurements in mm, for the ANSUR II percentile check that
    # the chassis sizing objective rests on.
    hand_length_mm: str = ""
    hand_breadth_mm: str = ""
    # Whether the left/right port assignment came from auto-detection
    # or a manual Settings override, which is what the zero-setup
    # objective is measured on.
    assignment_source: str = ""
    started_at: str = field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S")
    )
    finished_at: str = ""
    source_name: str = ""
    config_snapshot: dict = field(default_factory=dict)
    # block_summary is populated at finish_block / abandon with the
    # aggregates a researcher actually wants alongside the row-level
    # CSV: trial count, hit rate, peak streak, BPM range, average RT,
    # duration. Saves loading the whole trials.csv for a quick scan.
    block_summary: dict = field(default_factory=dict)
    # The press calibration this block ran under: the measured zero,
    # resting and press levels per finger, and the thresholds derived
    # from them. Copied in rather than referenced by filename, so a
    # session folder stays self-describing if it is moved or archived.
    # Empty when the block ran on config defaults with no calibration
    # taken, which an analysis should treat as lower-confidence force
    # data.
    calibration: dict = field(default_factory=dict)
    software_version: str = SOFTWARE_VERSION
    python_version: str = field(default_factory=lambda: sys.version.split()[0])
    platform: str = field(default_factory=platform.platform)
    notes: str = ""

    def save(self, path: Path) -> None:
        """Write metadata atomically.

        The engine calls this three times per session: once at block
        start (notes='block in progress'), again at finish_block, and
        again on abandon. Writing directly to `path` meant a crash
        mid-write left a truncated file AND wiped the prior snapshot,
        so a power loss during the final write lost the forensic
        record too. Now we serialise into a sibling tmp file and
        atomically replace - if anything raises before the replace,
        the original file is untouched AND the tmp file is unlinked
        so the sessions/ directory doesn't accumulate orphan
        metadata.json.tmp files over time.

        Uses ensure_ascii=False so a researcher inspecting session.json
        sees real unicode names (e.g. "Müller", "张") rather than the
        escaped "M\\u00fcller" form, while still producing valid JSON.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            asdict(self), indent=2, ensure_ascii=False,
            default=lambda o: getattr(o, "__dict__", str(o)),
        )
        tmp = path.with_name(path.name + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except (OSError, AttributeError):
                    # fsync isn't available on every platform / file
                    # type (e.g. some mocked filesystems). The atomic
                    # replace below still gives us the no-truncated-
                    # file guarantee.
                    pass
            os.replace(tmp, path)
        except BaseException:
            # On ANY failure (write, flush, replace, KeyboardInterrupt)
            # remove the partial tmp file before re-raising. The
            # original session.json is untouched because os.replace
            # either succeeded fully or wasn't reached. Catching
            # BaseException (rather than Exception) covers Ctrl-C
            # mid-write too, which is a real scenario when a
            # researcher abandons a session at the keyboard.
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            raise
