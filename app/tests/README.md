# tests

About 3,500 tests in 124 files. All run headless: no screen, sound or board is needed.

```bash
cd app
python -m pytest tests                         # everything, about 4 minutes
python -m pytest tests/test_srt_mode.py        # one file
```

Tests read the real config and write only to temporary folders, never to `sessions/`. Some of them hold the
documentation to the code: [`test_readme.py`](test_readme.py) keeps the main README's sections, game table and
troubleshooting in step, and the notebook tests keep `analysis/session_analysis.ipynb` reading the formats the
game writes.

<sub>[Back to app](../README.md)</sub>
