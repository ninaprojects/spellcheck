// Sends the daily Spell Check push notification. Runs on a schedule via
// GitHub Actions (see daily-notify.yml), not inside Firebase, so it
// never needs the paid Blaze plan.
const admin = require('firebase-admin');

const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
  databaseURL: "https://cast-and-check-default-rtdb.firebaseio.com"
});

const db = admin.database();
const PEOPLE = ["Nina", "Kellye", "Lauren", "Carolina"];
const CHALLENGE_START_STR = '2026-09-16'; // must match index.html's CHALLENGE_START

// The four big astro days get their own message instead of an affirmation,
// naming the real event. Keep these in sync with index.html's DAYS array
// if the day numbers ever change.
const SPECIAL = {
  7:  "Equinox today, Sun enters Libra. Get everyone on a call tonight, that's the Day 7 assignment.",
  11: "Full Harvest Moon in Aries tonight. Do the thing you've been circling, don't just journal about it.",
  17: "Venus stations retrograde today. Love, money, and values get a little weird for the next few weeks.",
  24: "New Moon in Libra tonight. Set your intention for after this challenge ends."
};

// One affirmation per day, matching that day's actual prompt in the app.
// Used on every day that isn't one of the four SPECIAL days above.
const AFFIRMATIONS = {
  1:  "You're allowed to actually pay attention today.",
  2:  "Notice what's draining you before it decides for you.",
  3:  "Talk to yourself like someone you actually respect.",
  4:  "Move because it feels good. Nobody's watching, nobody has to be.",
  5:  "Patterns only have power when you don't name them.",
  6:  "You're done explaining yourself. Say it like you mean it.",
  8:  "Name the imbalance today. Skip the diplomacy.",
  9:  "Send the message. Softened or not.",
  10: "Beauty doesn't need an audience to count.",
  12: "Letting go doesn't have to look graceful.",
  13: "Balance, defined by you, not the dictionary.",
  14: "Know your values in order. No ties allowed.",
  15: "Honesty first. Harmony can wait its turn.",
  16: "Say the unspoken rule out loud, even just to yourself.",
  18: "No audience today. Not even yourself.",
  19: "The compromise you're still mad about deserves a second look.",
  20: "Four days to the reset. Get honest about what's not true yet.",
  21: "Say the money thing out loud.",
  22: "You've outgrown more than you've admitted.",
  23: "Clear one loose end before the new moon.",
  25: "Balance with someone specific, not balance in general.",
  26: "Compare today to Day 1. Notice what actually moved.",
  27: "Be proud of the thing nobody else would think to ask about.",
  28: "Pick one commitment worth keeping well past the last day.",
  29: "Close the loop before Mercury gets messy.",
  30: "Notice your mornings. They're not the same as September 16th.",
  31: "Last clean signal for a while. Make it count."
};

function getDayNumber() {
  // "Today" as a plain date in Pacific Time, regardless of what time
  // zone the GitHub Actions runner itself is in (it's UTC).
  const now = new Date();
  const pacificDateStr = now.toLocaleDateString('en-US', { timeZone: 'America/Los_Angeles' });
  const pacific = new Date(pacificDateStr);
  const start = new Date(CHALLENGE_START_STR);
  const diffDays = Math.round((pacific - start) / 86400000) + 1;
  return diffDays;
}

async function main() {
  const day = getDayNumber();
  console.log('Computed day number:', day);
  if (day < 1 || day > 31) {
    console.log('Outside the challenge range, nothing to send today.');
    return;
  }

  const title = `Spell Check \u00b7 Day ${day}`;
  const body = SPECIAL[day] || AFFIRMATIONS[day] || `Day ${day} is live. Go check in.`;

  for (const person of PEOPLE) {
    try {
      const snap = await db.ref('recalData/recal-fcm-token:' + person).once('value');
      const token = snap.val();
      if (!token) {
        console.log('No token on file yet for', person, ', skipping.');
        continue;
      }
      // Sent as a data-only message on purpose. A "notification" message
      // relies on the browser auto-displaying it, which iOS Safari doesn't
      // reliably do. Data-only forces it through our own service worker
      // code (see sw.js), which we fully control.
      await admin.messaging().send({ token, data: { title, body } });
      console.log('Sent to', person);
    } catch (e) {
      console.error('Failed for', person, ':', e.message);
    }
  }
}

main()
  .then(() => process.exit(0))
  .catch((e) => { console.error(e); process.exit(1); });
