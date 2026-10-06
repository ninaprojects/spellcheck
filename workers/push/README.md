# Push Worker (spellcheck-push)

This is the Cloudflare Worker that sends every Spell Check notification. It replaced `notify.js` and the two GitHub Actions workflows, which started 3 to 6 hours late.

The file here, `spellcheck-push-worker.js`, is a copy of what is deployed. If the two ever differ, the deployed version is what runs. Check before you edit.

## What it sends

- Morning spell, 8:00am Pacific. Only sent between 8:00 and 11:59am.
- Evening nudge, 7:00pm Pacific. Only sent between 7:00 and 9:59pm.
- Reaction pushes. A reaction waits about a minute so a note typed right after the tap can ride along, then goes out on the next run.
- Comment pushes, to the poster and to anyone who already commented on that post. Never to the person who wrote the comment.
- Every time all four have cast today, a push to all four. It rotates through six lines by day and adds "days running" when the streak is two or more. On streak days 3, 7, 14, 21, and 31 the milestone line replaces it.
- "On a roll" pushes at personal streaks of 5, 10, 15, 20, and 25 days: one to the other three and one private one to her. If everyone hits a streak in the same moment, only the coven push and her private one go out.
- A Sunday recap at 6pm Pacific, from day 7 on, covering the last seven days. It reads "perfect," "the week, in numbers," or "a softer week."
- Coven activity: a spell cast, photos, workout proof, shared links, and Currently updates. Water check-ins stay silent.

If the Worker was down for a whole window, that day's morning or evening push is skipped, not sent late.

Quiet hours are switched off (`QUIET_HOURS_ON = false`). Reactions send any time of day.

Each person has switches in their profile: reactions and comments, activity, morning, nudge. Comments use the reactions switch. The streak, recap, and "on a roll" pushes use the activity switch. Messages are data-only, with no `notification` field, because iOS Safari does not reliably show the standard type. The `push` listener in `sw.js` displays them.

## Where it runs

- Cloudflare dashboard, Workers & Pages, Worker name `spellcheck-push`.
- Cron Trigger: set it to every minute (`* * * * *`) in Settings > Triggers. The code's header still says every 5 minutes. At 5 minutes, reaction and comment pushes can arrive several minutes late, because of the one-minute hold on reactions.
- It is a separate Worker from the media-search one (`spellcheck`).

## Secret

One secret, set in Cloudflare under Settings > Variables and Secrets:

- `FIREBASE_SERVICE_ACCOUNT`: the full JSON of a Firebase service-account key.

Never put this key, or any other secret, in this repo. The repo is public.

## How it talks to Firebase

- Pushes go out through Firebase Cloud Messaging using the service account. The access token it requests has the `firebase.messaging` scope only.
- Reading and writing the database uses plain REST calls with no login. That only works while the `recalData` rules allow public access.
- If the database rules are ever tightened, this Worker has to change in the same release, or every push stops. It would need the database scope added and a token on each request.
- It also reads `recal-comments:<Name>`. The first run after this version deploys marks existing comments as seen, so nothing old is announced.
- It keeps its own state at `recalData/r2:recal-push-state`. Do not edit that by hand unless you mean to reset what it has already seen.

## Keep in sync by hand

These must match `index.html`, or pushes and the app disagree:

- `CHALLENGE_START` here and in `index.html`. Both are Oct 1, 2026 for Round 2.
- The day numbers in `SPECIAL` and `AFFIRMATIONS` with the tagged days in the app's `DAYS` list. Special push messages are for days 1, 3, 10, 23, 24, 25, and 31. Day 16 is tagged "Halfway" in the app but uses a normal affirmation here.
- `FEED_LINES`, `pickLine`, and `lineKey` with the app's feed code, so a push and its feed post read the same.
- `QUESTIONS` here and in `index.html` (Day 6 to 31). The `brew` job sends the day's question at noon to 10pm Pacific, once per person, and skips anyone who already answered or turned the morning switch off.
- Record keys use the `r2:` prefix. Device tokens (`recal-fcm-token:<Name>`) and notification switches (`recal-notif-prefs:<Name>`) are shared between rounds and have no prefix.

Known gap: this Worker works out "today" in Pacific time. The app uses each phone's local time. The two can disagree near midnight for anyone outside Pacific.

## How to change it

1. Edit `spellcheck-push-worker.js` in this repo.
2. In Cloudflare, open the Worker, click Edit code, select everything, paste the new file, and click Deploy.
3. Open the Worker's Logs and wait for the next run to confirm it works.
4. Deploy the app update first, then the Worker. The old Worker ignores comments safely, and the new one needs the new app's data.

Tell Nina before deploying. This Worker sends real notifications to four people.

## Rollback

Paste the previous version of `spellcheck-push-worker.js` from this repo's history into Edit code and click Deploy.
