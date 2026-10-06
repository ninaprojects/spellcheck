# Tests

One command checks the whole app in a phone-sized browser, and the push Worker with it. Nothing here touches the real database.

## Run it

From the repo root:

    pip install -r tests/requirements.txt
    playwright install chromium
    python3 tests/run_all.py

It needs Node.js 18 or newer for the syntax check and the Worker test. It prints PASS or FAIL for each check and ends with ALL PASSED or SOMETHING FAILED. Run it after every change to `index.html` or the Worker, before opening a pull request.

To test a different copy of the app, set `SPELLCHECK_APP` to its path. For a different Worker file, set `SPELLCHECK_WORKER`.

## What it does

- Syntax check on every script inside `index.html`.
- `t_main.py`: photo row layout, the place picker, photo location from the file, saving feedback, and the profile icons.
- `t_saved.py`: saved fields folding to text with a check, editing them again, failed saves, and other people's read-only view.
- `t_photo.py`: big phone photos, shrinking, orientation, dropping the location stamp, and bad files.
- `t_social.py`: labeled reactions, the optional note, comments, the typing guard, and the notification prompt in every situation.
- `t_zoom.py`: every text box on every screen is 16px or larger (so iPhone never zooms in), double-tap zoom is off, and nothing scrolls sideways.
- `t_big3.py`: the Big 3 card. Every symbol sits at the true centre of its circle, the labels and names are centred under it, and the small Edit link is in the corner.
- `t_pages.py`: the pages inside the tabs (page row per tab, hashes, remembered page, Settings only on your own profile), the "Also this week" rows on Today (open in place, one at a time), and Log a move (one tap logs, optional photo and place, third move fills the row, the sheet fits at three phone widths).
- `t_receipts.py`: the Journey receipts ("What we conjured") and the Me tab. Each chapter ends with a receipt, one opens at a time, the quote saves and survives a redraw, the card fits in both shapes at three phone widths with every optional line on, the download is exactly 1080x1350 or 1080x1920, and Me always shows your own profile.
- `errs.py`: walks every tab and fails on any unexpected browser error.
- `worker_test.mjs`: the push Worker end to end, covering reaction, comment, all-four, streak, and recap pushes, plus the rules that stop duplicates.

## How it stays safe

- Firebase is replaced by an in-memory stand-in (`h.py` for the app, `worker_test.mjs` for the Worker), so no real entries, photos, or tokens are read or written.
- The place lookups (Overpass and BigDataCloud), the notification service, and the Google sign-in step are all mocked.
- The clock is pinned to Oct 1, 2026 for the app tests, and to chosen moments for the Worker tests.
- Screenshots go to a temporary folder, not the repo.

## When it fails

If a test fails after an intended design change, update that test in the same pull request. If it fails after a change that was not meant to affect it, treat it as a bug in the change.

These tests describe the app as it is now. When you add a feature, add a test for it.
