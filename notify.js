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
const CHALLENGE_START_STR = '2026-09-18'; // must match index.html's CHALLENGE_START

// The four big astro days get their own message instead of an affirmation,
// naming the real event. Keep these day numbers in sync with index.html's
// DAYS array if the day numbers ever change again.
const SPECIAL = {
  5:  "Happy Equinox, witches \u2600\ufe0f Sun's in Libra now, day and night dead equal, balance made visible. Libra can't do that alone though, she needs a mirror. Get on a real call tonight, texting doesn't count and you know it.",
  9:  "Full moon in Aries tonight \ud83c\udf15 She did not pull up for your feelings, she pulled up for action. Go do the thing before you talk yourself out of it again.",
  16: "Venus just went retrograde, so love and money are about to get messy on purpose. Notice who you become around someone you don't trust, she's been dying to make an appearance.",
  23: "New moon in Libra tonight \ud83c\udf11\u2728 Say what you want like it's already yours, hesitation isn't a good look on you."
};

// One line per day, matching that day's actual prompt in the app.
// Used on every day that isn't one of the four SPECIAL days above.
const AFFIRMATIONS = {
  1:  "You get to actually pay attention to your own life today. Wild that you needed permission, but here it is.",
  2:  "Whatever you keep circling back to, name it today, and notice the pattern while you're at it. It's been sitting there in plain sight long enough.",
  3:  "Talk to yourself like your own hype girl today. Your inner critic's had the mic long enough.",
  4:  "Done explaining yourself today. Took you long enough, and we mean that with love.",
  6:  "Notice the lopsided thing in your life today. Diplomacy's had a whole career, let her retire.",
  7:  "Send the message today. Whatever happens next isn't your problem anymore, it's theirs.",
  8:  "Do the beautiful thing today just because. You don't owe anyone a reason, especially not a good one.",
  10: "However you let go last night, gently or in a full unhinged spiral, it counts. We don't need the details, just the receipts.",
  11: "Go back to whatever felt lopsided earlier this week. Notice if it actually moved, or just looks different today.",
  12: "Your definition of balance wins today. Everyone else can take their opinion elsewhere.",
  13: "Rank your values today, no ties. Pretending you can't choose is just avoidance in a cute outfit.",
  14: "Pick honesty over harmony today. Harmony's had a good run, she can sit down now.",
  15: "Say the unspoken thing out loud today, even just to yourself. It's been taking up way too much real estate in your head.",
  17: "Rest today, actually rest. No performance today, not even for yourself.",
  18: "Still mad about that compromise? Good. Say it out loud today, stop letting it live rent free.",
  19: "Four days till the New Moon reset. Get honest now, before the sky does it for you, publicly, in front of everyone.",
  20: "Say the money thing out loud today. Silence isn't saving you money, it's just costing you sleep.",
  21: "You've outgrown more than you're saying. We noticed. Say it anyway.",
  22: "Clear one loose end today. The new moon doesn't do clutter, and neither should you.",
  24: "Get specific about the balance you want with someone you love. Vague wishes are just polite avoidance.",
  25: "Compare today to Day 1. Honestly? Kind of a glow-up, and you should say so.",
  26: "Tell each of the other three witches something you've noticed shifting in them. Real, not just nice.",
  27: "Say the thing you're proud of that nobody would think to ask about. We're asking. Don't make us beg.",
  28: "Pick the commitment that's actually you today, not the one that sounds good at brunch and dies by Tuesday.",
  29: "Tie up one loose end today, before Mercury shows up and drags it into the group chat.",
  30: "Notice your mornings today. Past-you would not recognize this level of together.",
  31: "Last quiet moment for a while, witches. Write future-you a letter tonight, then share it. Mercury's about to ruin everyone's peace, enjoy this while it lasts."
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

  const title = `\u2728 Day ${day} of Spells, Witches`;
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
