# Tests

One command checks the whole app in a phone-sized browser. Nothing here touches the real database.

## Run it

From the repo root:

    pip install -r tests/requirements.txt
    playwright install chromium
    python3 tests/run_all.py

It needs Node.js for the syntax check. It prints PASS or FAIL for each check and ends with ALL PASSED or SOMETHING FAILED. Run it after every change to `index.html`, before opening a pull request.

To test a different copy of the app, set `SPELLCHECK_APP` to its path.

## What it does

- Syntax check on every script inside `index.html`.
- `t_main.py`: photo row layout, the place picker, photo location from the file, saving feedback, and the profile icons.
- `t_saved.py`: saved fields folding to text with a check, editing them again, failed saves, and other people's read-only view.
- `t_photo.py`: big phone photos, shrinking, orientation, dropping the location stamp, and bad files.
- `errs.py`: walks every tab and fails on any unexpected browser error.

## How it stays safe

- Firebase is replaced by an in-memory stand-in (`h.py`), so no real entries, photos, or tokens are read or written.
- The place lookups (Overpass and BigDataCloud) are mocked.
- The clock is pinned to Oct 1, 2026, so "today" is Day 1.
- Screenshots go to a temporary folder, not the repo.

## When it fails

If a test fails after an intended design change, update that test in the same pull request. If it fails after a change that was not meant to affect it, treat it as a bug in the change.

These tests describe the app as it is now. When you add a feature, add a test for it.
