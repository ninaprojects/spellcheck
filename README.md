# Spell Check — standalone version

This is the same tracker, but it runs entirely on your own free accounts
instead of Claude. Two things to set up once, then it's done: Firebase
(holds the shared data) and GitHub Pages (hosts the site). About 15 minutes
total, no coding required beyond copy-paste.

## 1. Create a Firebase project (free)

1. Go to https://console.firebase.google.com and sign in with any Google
   account.
2. Click **Add project**. Name it anything (e.g. "recalibration"). You can
   turn off Google Analytics for this project, you don't need it.
3. Once it's created, click the **</> (Web)** icon on the project overview
   page to register a web app. Name it anything, you don't need Firebase
   Hosting in that step, skip it.
4. Firebase shows you a `firebaseConfig` object, it looks like:

   ```js
   const firebaseConfig = {
     apiKey: "AIzaSy...",
     authDomain: "recalibration-xxxx.firebaseapp.com",
     databaseURL: "https://recalibration-xxxx-default-rtdb.firebaseio.com",
     projectId: "recalibration-xxxx",
     ...
   };
   ```

   Copy this whole thing.

5. In `index.html`, find the block near the top of the `<script>` tag that
   says `STEP 1: paste your own Firebase project config here` and replace
   the placeholder object with what you just copied.

   This config is safe to have in a public GitHub repo. It's not a secret,
   Firebase's actual security comes from the rules in step 3 below, not
   from hiding this object.

## 2. Turn on the Realtime Database

1. In the Firebase console sidebar, go to **Build > Realtime Database**.
2. Click **Create Database**. Pick any region. Start in **locked mode**.
3. Go to the **Rules** tab and replace whatever's there with the contents
   of `firebase-rules.json` in this folder. Click **Publish**.

   Worth knowing plainly: these rules let anyone who has your Firebase
   config read and write to this database. There's no login system here,
   the same trust model as before, just you and three friends. Don't put
   anything in this app you wouldn't want a stranger to stumble onto if
   they somehow found the URL. If that's not an acceptable tradeoff, this
   app would need real user accounts added, a bigger project than this.

## 3. Put it on GitHub Pages

1. Create a new repository on GitHub (public or private, either works for
   Pages on a personal account).
2. Upload `index.html` (with your Firebase config already pasted in) to
   the repo. Drag-and-drop through the GitHub web UI works fine, no git
   command line needed.
3. Go to the repo's **Settings > Pages**.
4. Under **Source**, pick the branch (usually `main`) and `/ (root)`, then
   save.
5. GitHub gives you a URL like `https://yourusername.github.io/repo-name/`
   within a minute or two. That's the link to send Kellye, Lauren, and
   Carolina.

## What's different from the Claude version

- **Chart screenshot reader**: now runs on Tesseract.js, a free OCR
  library, entirely in the browser. It reads raw text off the image and
  guesses Sun/Moon/Rising from it. It does not understand chart layouts
  or icons the way the Claude version did, so it'll miss more. The raw
  scanned text gets pasted into the notes field so people can manually
  check what it missed.
- **Shared data**: now lives in Firebase's Realtime Database instead of
  Claude's storage. Same shape, same behavior, just a different free
  service underneath.
- **"Who's using this" lock**: now remembered via this browser's local
  storage instead of your Claude account. It'll ask again on a different
  device or a different browser.
- Everything else, layout, prompts, the leaderboard, the photo journal,
  is unchanged.

## Costs

Firebase's free (Spark) tier and GitHub Pages are both free for this
scale of use, four people, one month, a modest number of photos. Nothing
here should cost you anything.
