"""Session metadata written alongside the trial/raw CSVs."""
from __future__ import annotations

import json
import os
import platform
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path


SOFTWARE_VERSION = "1.0.0"


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
        the original file is untouched.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            asdict(self), indent=2,
            default=lambda o: getattr(o, "__dict__", str(o)),
        )
        tmp = path.with_name(path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            try:
                os.fsync(f.fileno())
            except (OSError, AttributeError):
                # fsync isn't available on every platform / file type
                # (e.g. some mocked filesystems). The atomic replace
                # below still gives us the no-truncated-file guarantee.
                pass
        os.replace(tmp, path)
