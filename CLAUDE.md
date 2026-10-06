# Spell Check

A 31-day astrology-timed group wellness tracker for four friends: Nina, Kellye, Lauren, Carolina. Round 2 runs Oct 1 to Oct 31, 2026. It is live and used daily. Treat every change as a production change.

Public name is always "Spell Check". "Practical Magic" is a private nickname only. Never use it in anything public-facing (it is Alice Hoffman / Warner Bros IP). The tagline phrase "a month of practical magic" is the one tolerated use. Do not promote it to a name, logo, or headline.

## Source of truth

- This repo (github.com/ninaprojects/spellcheck, branch `main`) is the source of truth for the app. GitHub Pages serves `main` at ninaprojects.github.io/spellcheck.
- Cloudflare Workers and Firebase settings live outside the repo. See "Lives outside the repo" below. Keep their source and notes in `workers/` so this file never goes stale.
- Never build from a copy pasted into chat or from the Claude Project's files. Read the file in this repo first, and run `git log -5 --stat` to see what changed recently.
- Before assuming a feature does not exist, search the repo (`grep`) and check recent commits.
- One canonical `index.html`. Do not fork it into parallel versions. `round1.html` is the read-only Round 1 archive and must never write to the shared database.

## Files

- `index.html`: the entire app. Single file, HTML/CSS/JS, no build step. Views: Today, Coven, Journey, and Me. Me is the profile view (`data-view="profile"`, `#profile`). It is also reached from the top bar avatar and from any person's avatar, which show that person's profile. The Me tab always shows your own. There is no Receipts tab: an old `#receipts` link lands on Journey.
- `round1.html`: read-only Round 1 archive. Its storage layer is stubbed so it cannot write to Firebase.
- `sw.js`: service worker. Offline support, installability, and manual display of push notifications through a raw `push` listener.
- `manifest.json` and the icon PNGs: PWA install files.
- `firebase-rules.json`: reference copy of the Realtime Database rules. The console is where they are actually published, so confirm they match before relying on this file.
- `workers/push/`: the push Worker source (`spellcheck-push-worker.js`) and its README. A copy of what is deployed.
- `workers/media/`: the media Worker source (`spellcheck-media-worker.js`) and its README. A copy of what is deployed.
- `tests/`: the test suite. Run `python3 tests/run_all.py`. See `tests/README.md`.
- `README.md`: describes the original Round 1 standalone setup and is out of date.
- RETIRED and deleted: `notify.js` and the two GitHub Actions workflows (`daily-notify.yml`, `evening-nudge.yml`) were removed from the repo in Oct 2026 (pull request #1), and their GitHub secret was deleted. Pushes moved to the Cloudflare push Worker because GitHub Actions started 3 to 6 hours late. Never bring them back: `notify.js` counted days from Sep 18 and would send duplicate, wrongly numbered pushes.

## Data layer

- Firebase Realtime Database, free Spark plan. Config is baked into `index.html` and `sw.js`.
- Shared data lives under `recalData/`. Round 2 records are prefixed `r2:` (the app uses its `rk()` helper), for example `r2:recal:<Person>` and `r2:recal-reactions:<Person>`. Device tokens (`recal-fcm-token:<Person>`) and notification switches (`recal-notif-prefs:<Person>`) are shared between rounds and are NOT prefixed.
- The push Worker keeps its own state at `r2:recal-push-state`. Do not edit it by hand unless you are deliberately resetting dedupe.
- Photos are stored as JPEG data URLs under their own keys, for example `r2:recal-photo:<Person>:<week>:<i>` and `r2:recal-daily-photo:<Person>:<day>`.
- Comments live in `r2:recal-comments:<Person>`: JSON of `{eventKey: [{id, t, at, g?}]}`, keyed the same way as reactions. Each person writes only her own record. A "note" is a comment that carries a reaction symbol in `g`; it shows in the list and rides along in that reaction's push.

## Lives outside the repo

1. Cloudflare Worker, push (name `spellcheck-push`): source is in `workers/push/`. It is deployed by pasting the file into the Cloudflare dashboard (Edit code, then Deploy). There is no wrangler setup, so Claude Code cannot deploy it. The code says it runs on a Cron Trigger every 5 minutes, but confirm in the dashboard (Settings > Triggers), because older notes say every minute. It sends the morning spell (8:00am Pacific), the evening nudge (7:00pm Pacific), reaction pushes (held about a minute so a note typed right after the tap can ride along), comment pushes (to the poster and anyone who already commented, under the Reactions and comments switch), a push every time all four have cast (with milestone versions at streak days 3, 7, 14, 21, and 31), private and group "on a roll" pushes at personal streaks of 5, 10, 15, 20, and 25, and a Sunday recap at 6pm Pacific from day 7 on. The last two use the Coven activity switch. Quiet hours are switched off. Set the cron to every minute, or reaction and comment pushes can arrive several minutes late. Needs one secret, `FIREBASE_SERVICE_ACCOUNT` (full JSON of a Firebase service-account key). Messages are data-only. The morning spell only sends between 8:00 and 11:59am Pacific and the nudge between 7:00 and 9:59pm Pacific. If the Worker was down for the whole window, that send is skipped, not sent late.
2. Cloudflare Worker, media search proxy (`spellcheck`, at `spellcheck.nnirema.workers.dev`, source in `workers/media/`): `GET /spotify?q=`, `GET /tmdb?q=`, `GET /googlebooks?q=`. Returns the best match for the Currently fields. Needs four secrets: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `TMDB_API_KEY`, `GOOGLE_BOOKS_API_KEY`. The endpoints are public with `Access-Control-Allow-Origin: *`. Deployed the same way, by pasting into the dashboard.
3. Firebase: the Realtime Database and its rules (console), Cloud Messaging, and the service-account key. The app's web config in `index.html` is not a secret.
4. Third-party services the app calls from the browser: the Overpass API (overpass-api.de, with overpass.kumi.systems as a fallback) for nearby places, which is free OpenStreetMap data with no key; BigDataCloud for the city name; Spotify, TMDb, and Google Books through the media Worker; html2canvas (cdnjs) and tesseract.js (jsdelivr), loaded only when used; Google Fonts. If a lookup is down the feature should degrade, for example the place picker falls back to the city or a typed place.
5. Approved copy lives in shared Claude Docs, not the repo: the 31-day prompt review and the forecast text bank. The app's forecast lines and the Worker's `SPECIAL` and `AFFIRMATIONS` were built from them. Do not rewrite copy. Ask Nina.
6. Secrets never go in this public repo. Keep them in Cloudflare Variables and Secrets.
7. Before touching any of these, read the current deployed version first. Do not assume the repo copy matches what is deployed.

## Hard rules (these have broken things before)

1. Do not bump `SCHEDULE_VERSION` mid-challenge. Changing it runs `applyScheduleReset` on everyone's data on their next load. Wave 1 style changes are additive and leave it at 2.
2. Do not change the shape of `r2:recal:<Person>` records without a migration that keeps old records working. Existing data must never be lost. Add fields, do not rename or remove them.
3. Notifications are sent data-only (no `notification` field). iOS Safari does not reliably auto-display the standard Firebase `notification` type, so display is handled by a raw `push` listener in `sw.js`. Do not revert this.
4. The "from Spell Check" line under a notification title is iOS appending the app name. It is not in our code and cannot be removed. Do not try to fix it.
5. After any edit to `index.html`, run `python3 tests/run_all.py`. It includes a `node --check` on every script. This file has broken from small edits before.
6. Visual bugs can be caching. iOS Safari HTTP cache, the GitHub Pages CDN, and the service worker Cache API are three separate layers. Test in a private window before assuming a code bug.
7. Keep these in sync by hand between the app and the push Worker: `CHALLENGE_START` in the Worker with `CHALLENGE_START` in `index.html`; the day numbers in the Worker's `SPECIAL` and `AFFIRMATIONS` with the tagged days in `DAYS`; and the Worker's `FEED_LINES`, `pickLine`, and `lineKey` with the app's feed code, so a push and its feed post read identically.
8. The push Worker reads and writes the database over plain REST with no login. The Google token it requests is scoped to `firebase.messaging` only, and it is used for sending pushes. This only works while `recalData` rules are public. Do not tighten the rules without changing the Worker in the same release (it would need the database scope and a token on every request), or pushes and the app will break together.
9. Every write to shared data must go through `trackSave` or `trackedSet`, which is what drives the "Saving / Saved" pill and the honest failure message. Do not call `storage.set` directly for user-visible saves.
10. Photos must go through `prepareUploadImage` (longest side 1600 px, profile photos 512 px, re-encoded as JPEG). Never store a raw upload. The re-encode drops the location stamp, so the stored copy carries no location. A photo's own GPS, read from the original file, is kept on the device only (`r2-photo-gps:` in localStorage) and must never be written to Firebase.
11. The shape of `recal-reactions:<Person>` is `{eventKey: [glyph, ...]}` and must not change. The push Worker loops over every entry as an array, so any other value type breaks it for everyone. Notes and comments go in `recal-comments:<Person>`.
12. Every text box, text area, and dropdown must stay at 16px or larger. Below 16px, iPhone zooms the whole page when someone taps one. A global rule near the end of the CSS enforces this, so do not override it. Keep `touch-action: manipulation` on tappable elements, which stops double-tap zoom while leaving pinch-to-zoom working. Never add `maximum-scale` or `user-scalable=no` to the viewport tag, because that blocks zooming for people who need it.

## Patterns in index.html (use these, do not reinvent)

- Saving: `savePerson()`, `trackSave(promise)`, `trackedSet(key, value, shared)`, `flashSaved(input)`.
- Text fields: `bindSavedField(input, commit)` saves about 0.7 seconds after typing stops and again on blur, then folds to plain text with a check and an Edit link once the save has landed. It never folds while the person is typing. It builds on `bindAutosave`.
- Location: `buildLocationRow(obj, onSaved, photoKey)` is the place picker (nearest named places, or the city, or a typed place). It shows a pill with a check once chosen. `captureExifGps(file, photoKey)` reads the photo's GPS.
- Icons: `signBadge`, `planetBadge`, `PIN_SVG`, `CHECK_SVG`. Sign badges are colored by element: fire coral, earth green, air aqua, water periwinkle. The Big 3 is a three-column layout directly under the profile name, with each column centred. There are no profile chips. A few symbols are drawn slightly off-centre, so `GLYPH_NUDGE` shifts each one to the true centre of its circle. If you draw a new symbol, check it with `tests/t_big3.py` and add a nudge if it fails. The Big 3's Edit control is a tiny link in the card's top-right corner (`.b3-edit`) with a larger tap area than it looks.
- Reactions and comments: reactions are three symbols (Heart swelling, Spellbound, Calm tides, defined in `REACTION_GLYPHS`) shown without their names, to save space. The one you picked spells out its name, and so does the note box. Tapping one saves it and opens the note box (`feedCompose`). The "Say something" link sits in the same row as the symbols (`appendFeedLink`). Comments use `postComment`, `deleteComment`, `commentsForEvent`, and `appendFeedComments`. Any text box inside the feed must use the class `cmt-input`, because `renderCovenFeed` holds off redrawing while one has focus.
- Name picker: `renderIdentityBanner()` puts "Who's using this?" at the very top of Today for any phone that does not know who is using it. This is every fresh install, because the iPhone Home Screen app starts with blank storage. Keep it first: notifications cannot be set up until she has picked her name, so burying it below the intro stalls the whole setup.
- Notification prompt: `renderNotifPrompt()` shows a card at the top of Today for anyone not set up for pushes (ask, iPhone-not-installed, or blocked), hidden for 3 days after "Not now".
- The Saved pill stays quiet until the first touch, so saves that happen on their own when the app opens do not flash it. Failures always show.
- What we conjured (the coven receipt): each Journey chapter ends with a `.rcpt-block` (`buildReceiptBlock`), collapsed to a stat strip and an Open button. One receipt is open at a time (`openReceipt`). `mountReceiptPanel()` wires it after `renderChapters()`. The quote is anonymous, anyone can edit it, up to 80 characters, saved with `trackedSet('recal-quote:<chapter>', ..., true)`. `renderChapters()` skips its rebuild while the quote box has focus, or typing would be wiped.
- The receipt card is a fixed design size: 340x425 (square) and 300x533 (story). `fitReceiptPreview()` scales it down to the phone for the preview only. The PNG is drawn by `downloadReceipt()` from an unscaled off-screen copy at exactly 1080x1350 or 1080x1920, so it never depends on screen width. Everything on the card must fit inside that size with every optional line on; `tests/t_receipts.py` checks the longest case at three phone widths. If you add a line to the card, shrink something else or that test will fail.
- Round prefix: use `rk()` for any new shared key that belongs to Round 2.

## Testing

- `python3 tests/run_all.py` runs the syntax check, the browser tests, and the Worker test. See `tests/README.md` for setup. It needs Node 18 or newer.
- `tests/worker_test.mjs` runs the push Worker against a fake Firebase and a fake push service. Change a push's wording or rules in the Worker and its test together.
- The tests run Chromium at a phone viewport against an in-memory stand-in for Firebase, with mocked place lookups and a clock pinned to Oct 1, 2026. They never touch the real database.
- Every new feature gets a test. If an intended design change breaks a test, update that test in the same pull request.
- GitHub Pages serves only `main`, so a branch cannot be previewed on a phone, and any live copy points at the real database. That is why the tests matter: they are the check before merging.

## Workflow

- Nina reviews anything creative (copy, tone, wording) or structural (layout, navigation) before it is built. Show the plan or the actual text first. Wait for a go-ahead. Do not implement unapproved changes.
- Work on a branch named `claude/<short-topic>` and open a pull request. Never merge to `main` yourself. Merging deploys to four daily users, so Nina merges.
- After Nina merges, she checks on her phone right away. If something is wrong, revert the merge. Say plainly what to check and where.
- Worker changes: edit the file under `workers/`, tell Nina, and she pastes it into Cloudflare. Say exactly what changed.
- Commit messages: a short summary line, with an optional longer description. Say which file(s) changed.
- Ask one short question at a time.
- If you make a mistake, say so plainly and fix it. Do not get defensive or over-explain.
- When a session ends, give a three-line summary: what changed, what to check on a phone, what is still open.

## Voice for any in-app copy or notification

- Warm and affectionate first, cheeky second. If a line has no real warmth, a joke on top does not fix it.
- Never a fake singular "I" from the app. No "I love you", no "I believe in you". When it needs a voice, it is the group: "we".
- Light, current slang is fine, checked against real usage, never forced into every line. If a joke's key word does not fit how the sentence is used, cut it.
- Every line must parse as a real sentence with real meaning. Watch for dangling metaphors and ambiguous pronouns.
- Astrology references must be factually and thematically correct for that day (which sign, which transit). Cross-check, do not use vague "the sky says" filler.
- No astrology jargon in prose. Trine, square, and sextile belong only in small chip labels.
- No exclamation points as a substitute for warmth.
- For health-adjacent features in a social or leaderboard context, score against personal goals, never raw numbers or direct comparison.
- Never use em dashes. Anywhere. In code comments, copy, commit messages, or notifications.
- Spell and style the artist name as "SAINt JHN" with no exceptions.
- Use inclusive language when discussing the needs of people with disabilities.

## Known open items (verify before acting, then delete when fixed)

- GitHub secret scanning shows a Google API key alert for the Firebase web key in `index.html`, `round1.html`, and `sw.js`. That key is meant to be public in client code, and the alert was closed as "Won't fix" in Oct 2026. Do not rotate, remove, or "fix" it, because the app needs it to register devices for notifications. If a different secret is ever flagged, treat it as urgent.
- The media link previews build their HTML from the saved link's `url` and `image` without escaping them (`renderMediaPreviewHtml`). Because the database allows public writes, someone with the database address could plant a bad link. Verify, then escape or validate those two fields.
- Media Worker endpoints are public with CORS `*`, so anyone who finds the URL (it is in this public repo) can spend the Spotify, TMDb, and Google Books quotas. Consider checking the `Origin` header against ninaprojects.github.io, adding a Cloudflare rate limit, and caching results.
- Timezone mismatch: the app calculates "today" from the device's local time, but the push Worker calculates it in Pacific time. This can disagree near midnight for anyone not in Pacific (Kellye is in Mountain Time). A decision is needed on whether the coven runs on Pacific time.
- No export or backup of journal entries and photos. Receipt PNG download is the only export. A planned "Wrapped" keepsake would cover export. A scheduled backup of `recalData` should exist before the Firebase rules are tightened.
- Firebase rules allow public read and write on `recalData`. Journal entries and photos are readable by anyone with the database URL. Securing this needs the Worker and app changes described in hard rule 8.
- Decisions pending, do not build until Nina decides: a streak grace day; a poke button; per-person custom daily goals; sending pushes on each person's own clock instead of Pacific. Sleep tracking is the strongest fit if health data is ever added. Do not add macro or calorie tracking.
