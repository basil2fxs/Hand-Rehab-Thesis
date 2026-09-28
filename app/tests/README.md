# tests

3,721 tests, all headless: no screen, sound or board needed.

```bash
cd app
python -m pytest tests                    # everything, about four minutes
python -m pytest tests/test_srt_mode.py   # one file
```

Tests read the real config and write only to temporary folders, never to `sessions/`. The `*_review.py` files reproduce the faults of the 27 September 2026 code review and fail on the code as it was. [`test_readme.py`](test_readme.py) keeps the front page's sections, game table, screenshots and troubleshooting entries true to the code.
