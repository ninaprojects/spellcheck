// Spell Check push Worker. Since Nov 2026 it sends the habit tracker pushes (habitsRun, see the README and
// push-copy.json). The Round 2 jobs below ran Oct 1 to 31 and are skipped after that.
// A separate Worker from the media-search one, so that one is never touched.
// Runs on a Cron Trigger every 5 minutes. It has no public endpoints that do
// anything, so nobody can trigger pushes from outside.
//
// Each run:
//   1. Reads everyone's reactions (recal-reactions:<Name>) from Firebase.
//   2. Finds reactions it hasn't seen before.
//   3. Groups them per person into one push, skipping reactions on your own
//      posts and anyone who switched Reactions off in their profile.
//   4. Sends right away, any time of day. (No quiet hours: everyone's
//      phone is on Do Not Disturb at night anyway.)
// It also sends the morning spell (8:00am PT) and the evening nudge (7:00pm
// PT), which used to run on GitHub Actions and arrived hours late.
// It also pushes the coven's big moments to everyone else (switch: Coven
// activity): someone casting today's spell, the full-coven moment, new
// photos (daily or workout proof), shared links, and Currently updates.
// Check-ins like water stay silent.
// Round 2 additions: labeled reactions with optional notes, comments (pushed to the
// poster and anyone who already commented), a push every time all four cast, streak
// milestones, "on a roll" pushes, and a Sunday recap.
// The very first run just marks everything existing as seen, so nobody
// gets a flood of old ones.
//
// Needs ONE secret (Settings > Variables and Secrets):
//   FIREBASE_SERVICE_ACCOUNT  = the full JSON of a Firebase service-account key
// Needs ONE Cron Trigger (Settings > Triggers):  */5 * * * *

const DB = 'https://cast-and-check-default-rtdb.firebaseio.com/recalData/';
const PEOPLE = ['Nina', 'Kellye', 'Lauren', 'Carolina'];
// Round 2 keeps its own records (the app prefixes them with r2:). Device tokens
// and notification switches are shared between rounds, so those keys are unchanged.
const R2 = 'r2:';
const STATE_KEY = R2 + 'recal-push-state';
const VERBS = { reading: 'reading', watching: 'watching', listening: 'listening to' };
// Must match index.html's CHALLENGE_START (and notify.js). Only casts for
// *today* push, so backfilling an old day doesn't ping everyone.
const CHALLENGE_START = '2026-10-01'; // Round 2
// Sealed letters (must match index.html's LETTER_DAYS and DAYS tags).
const LETTER_DAYS = [10, 25, 29, 30, 31]; // New Moon in Libra, Full Moon in Taurus, Gemini Moon, Moon in Cancer, Halloween
const LETTER_NIGHT_NAMES = { 10: 'New Moon in Libra', 25: 'Full Moon in Taurus', 29: 'Gemini Moon', 30: 'Moon in Cancer', 31: 'Halloween' };
const LETTER_DATE_LABELS = { 10: 'Oct 10, New Moon in Libra', 25: 'Oct 25, Full Moon in Taurus', 29: 'Oct 29, Gemini Moon', 30: 'Oct 30, Moon in Cancer', 31: 'Oct 31, Halloween' };
// Nina's one-time intro letter (marked intro:true by the app). This is its push, sent when she seals it
// and resent once, at the time set just below, to everyone but Nina.
const INTRO_PUSH = { title: "You've got mail, witches ✦", body: "Nina wrote all of us a letter and it's open. Drop everything. Okay, finish your sentence first." };
// One-time push about the two new letter nights (Gemini Moon Oct 29, Moon in Cancer Oct 30). Goes to all four,
// on this Day of the challenge, from this Pacific hour. Change these two numbers to move it.
const LETTER_NIGHTS_PUSH = { title: 'Gemini Moon is Thursday \u2726', body: 'Two new letter nights this week, and Gemini goes first. Write yours before the Moon moves on.' };
const LETTER_NIGHTS_SEND = { day: 28, hour: 9 }; // Wed Oct 28, from 9:00am so it never stacks on the 8am spell
// Last call to write, sent the evening before a letter night closes for writing (a night closes when its own day starts).
// Only to people who have not sealed a letter for that night. Keyed by the letter night's day. 8pm Pacific (Nina's call). It shares the hour with the "break the seal" job, so a person with an
// unopened letter who has not written yet gets both. Approved copy, Oct 2026.
const LETTER_LAST_CALL = {
  30: { title: 'Homework due tonight, sorry \u2726', body: 'The only assignment: one letter for Moon in Cancer. It closes tonight. Gold stars for feelings.' },
  31: { title: 'Last call, then go be weird \u2726', body: 'Halloween letters close tonight. Seal one before the party starts.' }
};
const LETTER_LAST_CALL_AT = { hour: 20, minute: 0 };
// When the one-time resend goes out: on this Day of the challenge (Oct N), from this Pacific hour and minute,
// with an hour of grace in case the Worker is a little late. To schedule another one, change these three numbers.
const INTRO_RESEND = { day: 18, hour: 22, minute: 0 }; // Sunday Oct 18, from 10:00pm

// Same swap the app uses for feed post ids, so a push can point at the exact post.
const safeKey = (id) => String(id).replace(/[.#$\[\]\/]/g, '_');

function castCount(dd) {
  if (!dd) return 0;
  return (dd.journaled ? 1 : 0) + (dd.noPhone ? 1 : 0) + ((dd.waterOz || 0) >= 48 ? 1 : 0);
}
const isCast = (dd) => castCount(dd) >= 2;

function pacificDayNumber(now) {
  const ymd = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Los_Angeles', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now);
  return Math.round((Date.parse(ymd + 'T00:00:00Z') - Date.parse(CHALLENGE_START + 'T00:00:00Z')) / 86400000) + 1;
}

function sharesOf(wd) {
  if (!wd) return [];
  if (Array.isArray(wd.shares)) return wd.shares.filter(x => x && x.url && String(x.url).trim());
  if (wd.article && wd.article.url && String(wd.article.url).trim()) {
    return [{ id: 'a0', url: String(wd.article.url).trim(), label: wd.article.label || '', timestamp: wd.article.timestamp || null }];
  }
  return [];
}
function domainOf(u) {
  try { return new URL(/^https?:\/\//i.test(u) ? u : 'https://' + u).hostname.replace(/^www\./, ''); } catch (e) { return ''; }
}
const NOW_VERB = { reading: 'reading', watching: 'watching', listening: 'listening to' };

// ---------- Round 2 social copy (reviewed and approved by Nina) ----------
const REACTION_COPY = {
  '\u2661': { title: (who) => `${who}\u2019s heart is swelling \u2661`, body: (t) => `On ${t}. We\u2019d ask you to stay humble, but we\u2019ve met you.` },
  '\u2726': { title: (who) => `${who} is spellbound \u2726`, body: (t) => `On ${t}. A bow is customary. Several bows are encouraged.` },
  '\u263E': { title: (who) => `${who} sent you calm tides \u263E`, body: (t) => `On ${t}. Unclench your shoulders, the coven\u2019s got this.` }
};

// Every time all four have cast today. Rotates by day so it never repeats day after day.
const EVERY_TIME = [
  ['Day {N}, conjured \u2726', 'All four spells cast. The coven is unstoppable and slightly smug.'],
  ['All four of us, Day {N} \u2726', 'Every spell cast, nobody left behind. Frankly, we\u2019re glowing.'],
  ['Full coven, Day {N} \u2726', 'Four for four. Somebody tell the sky.'],
  ['Day {N}: the whole coven showed up \u2726', 'All four spells cast. Take the victory lap.'],
  ['Four spells, Day {N} \u2726', 'Everyone\u2019s in. The cauldron is bubbling.'],
  ['Day {N} is officially ours \u2726', 'All four of us cast. Go be smug about it.']
];
// On these streak lengths the milestone line replaces the everyday one, so nobody gets two pushes.
export const COVEN_MILESTONES = {
  3: ['Three in a row \u2726', 'All four of us, three days running. Okay, who invited the overachievers?'],
  7: ['A full week, all four \u2726', 'Seven days where every one of us cast. We are, frankly, a lot to be around right now.'],
  14: ['Fourteen days. All four of us \u2726', 'Two weeks of everyone casting. The group chat is about to be unbearable, and we\u2019re here for it.'],
  21: ['Twenty-one days \u2726', 'Three full weeks, all four of us. This stopped being a habit and became a personality.'],
  31: ['All 31 days. All four of us \u2726', 'Not one day missed, start to finish. Happy Halloween, witches. Go be insufferable about it.']
};
export function covenMessage(day, streak) {
  const m = COVEN_MILESTONES[streak];
  if (m) return { title: m[0], body: m[1] };
  const [t, b] = EVERY_TIME[day % EVERY_TIME.length];
  return { title: t.replace('{N}', day), body: b + (streak >= 2 ? ` That\u2019s ${numWord(streak)} days running.` : '') };
}

// A personal streak of this many days in a row. One push to the other three, one private one to her.
export const ROLL_STEPS = [5, 10, 15, 20, 25];
const ROLL_OTHERS = {
  5: 'Five days in a row. Somebody say something nice before it goes to her head.',
  10: 'Ten days in a row. The applause is due, and we\u2019ll wait.',
  15: 'Fifteen days in a row and not even a little tired. Suspicious.',
  20: 'Twenty days in a row. Somebody get her a cape.',
  25: 'Twenty-five days in a row. The finish line is nervous, and it should be.'
};
const ROLL_SELF = {
  5: 'Five days in a row. We noticed, and we\u2019re acting very normal about it.',
  10: 'Ten days in a row. We\u2019re proud, and we\u2019re being weird about it.',
  15: 'Fifteen days running. All you, cape optional, ego encouraged.',
  20: 'Twenty days in a row. Your cape is on order and ships whenever we get around to it.',
  25: 'Twenty-five days in a row. Don\u2019t look down, just keep going.'
};
export function rollMessage(item) {
  if (item.type === 'rollself') return { title: 'You\u2019re on a roll \u2726', body: ROLL_SELF[item.streak], target: 'tea' };
  return { title: `${item.actor} is on a roll \u2726`, body: ROLL_OTHERS[item.streak], target: 'tea' };
}

// Third movement session of a Mon to Sun week. One push to the other three, one private one to her.
// Each has three approved versions. The pick is a hash of who and which week, so the same event always
// reads the same way if it is ever composed twice.
export const MOVES_OTHERS = [
  { title: '{who} is making the rest of us look bad \u2726', body: 'Three moves this week. Go see for yourself and give her the applause she\u2019s earned.' },
  { title: 'Somebody is glowing \u2726', body: 'It\u2019s {who}. Three moves this week. Open the app and tell her how loud we\u2019re allowed to be about it.' },
  { title: '{who} just hit three moves \u2726', body: 'The receipts are in The Tea. Go look, then say something nice before it goes to her head.' }
];
export const MOVES_SELF = [
  { title: 'Go off, queen \u2726', body: 'Three moves this week. The glow is showing, and we\u2019re taking full credit.' },
  { title: 'Okay, we see you \u2726', body: 'Three moves this week. Open the app and see who has already left you applause.' },
  { title: 'You, but make it iconic \u2726', body: 'Three moves this week and the whole coven knows it. Go see what they\u2019re saying.' }
];
export function movesMessage(item) {
  const key = `${item.type}:${item.actor}:${item.week}`;
  const v = pickLine(item.type === 'moves3self' ? MOVES_SELF : MOVES_OTHERS, key);
  return { title: v.title.replace('{who}', item.actor), body: v.body.replace('{who}', item.actor), target: 'tea' };
}

// Sunday recap.
function oxford(a) {
  if (a.length <= 1) return a.join('');
  if (a.length === 2) return `${a[0]} and ${a[1]}`;
  return `${a.slice(0, -1).join(', ')}, and ${a[a.length - 1]}`;
}
export function recapMessage(stats) {
  if (stats.perfect) return { title: 'A perfect week \u2726', body: 'Every one of us cast, every day. Come admire us, we\u2019ll wait.' };
  if (stats.spells * 2 < stats.possible) {
    return { title: 'A softer week', body: `We cast ${stats.spells} ${stats.spells === 1 ? 'spell' : 'spells'}. Even witches nap. A fresh week starts tomorrow, and we\u2019re all in it.` };
  }
  const parts = [`cast ${stats.spells} spells`];
  if (stats.photos) parts.push(`shared ${stats.photos} ${stats.photos === 1 ? 'photo' : 'photos'}`);
  if (stats.reactions) parts.push(`sent ${stats.reactions} ${stats.reactions === 1 ? 'reaction' : 'reactions'}`);
  return { title: 'The week, in numbers \u2726', body: `We ${oxford(parts)}. Come see the damage.` };
}
function eventDayNumber(key, data) {
  const parts = key.split(':');
  const type = parts[0];
  if (type === 'cast' || type === 'photo') { const n = Number(parts[2]); return Number.isFinite(n) ? n : null; }
  if (type === 'session') {
    const list = (((data[parts[1]] || {}).weeks || {})[parts[2]] || {}).sessions;
    const x = list && list[Number(parts[3])];
    return x && x.timestamp ? pacificDayNumber(new Date(x.timestamp)) : null;
  }
  if (type === 'cur') {
    const t = new Date(parts.slice(3).join(':').replace(/_/g, '.'));
    return isNaN(t) ? null : pacificDayNumber(t);
  }
  if (type === 'article') {
    const wd = ((data[parts[1]] || {}).weeks || {})[parts[2]];
    const sh = sharesOf(wd).find(x => (x.id || 'a0') === (parts[3] || 'a0'));
    return sh && sh.timestamp ? pacificDayNumber(new Date(sh.timestamp)) : null;
  }
  return null;
}
// The seven days ending today (or fewer, early in the round).
export function weekStats(data, reactions, today) {
  const start = Math.max(1, today - 6), end = today;
  const inRange = (d) => d !== null && d >= start && d <= end;
  let spells = 0, photos = 0, reactionCount = 0, perfect = true;
  for (let n = start; n <= end; n++) {
    let all = true;
    for (const p of PEOPLE) {
      const d = data[p] && data[p].days ? data[p].days[n] : null;
      if (isCast(d)) spells++; else all = false;
      if (d && d.hasPhoto) photos++;
    }
    if (!all) perfect = false;
  }
  for (const p of PEOPLE) {
    const pd = data[p];
    if (!pd) continue;
    for (const wd of Object.values(pd.weeks || {})) {
      for (const s of ((wd && wd.sessions) || [])) {
        if (s && s.done && s.hasPhoto && s.timestamp && inRange(pacificDayNumber(new Date(s.timestamp)))) photos++;
      }
    }
  }
  for (const reactor of PEOPLE) {
    for (const [key, glyphs] of Object.entries(reactions[reactor] || {})) {
      if (inRange(eventDayNumber(key, data))) reactionCount += (glyphs || []).length;
    }
  }
  return { spells, photos, reactions: reactionCount, possible: PEOPLE.length * (end - start + 1), perfect };
}

// Comments: who is it about, and what is it called.
function describePost(eventKey) {
  const parts = eventKey.split(':');
  const type = parts[0];
  if (type === 'coven') return { owner: null, noun: `Day ${parts[1]} full-coven moment` };
  const owner = PEOPLE.includes(parts[1]) ? parts[1] : null;
  const noun = type === 'cast' ? `Day ${parts[2]} spell`
    : type === 'photo' ? `Day ${parts[2]} photo`
    : type === 'session' ? 'movement session'
    : type === 'article' ? 'shared link'
    : type === 'cur' ? 'Currently update'
    : 'post';
  return { owner, noun };
}
// Every comment push says which post it is about, so a tap can open that post. Several posts means the feed.
export function composeComments(items) {
  const events = uniq(items.map(i => i.eventKey));
  return { ...composeCommentsText(items), target: events.length === 1 ? 'post:' + events[0] : 'tea' };
}
function composeCommentsText(items) {
  const events = uniq(items.map(i => i.eventKey));
  if (items.length === 1) {
    const it = items[0];
    if (it.role === 'owner') return { title: `${it.author} has opinions about your ${it.noun}`, body: trunc(it.t, 90) };
    const whose = it.owner ? `${it.owner}\u2019s` : 'the';
    return { title: `${it.author} couldn\u2019t stay out of it`, body: `On ${whose} ${it.noun}: ${trunc(it.t, 90)}` };
  }
  const where = events.length === 1 && items.every(i => i.role === 'owner') ? `your ${items[0].noun}` : 'the coven feed';
  return { title: 'The comments are getting rowdy', body: `${items.length} new on ${where}. Go see who said what.` };
}
// A note is a comment that carries a reaction symbol. It rides along in that reaction's push.
function noteFor(comments, reactor, eventKey, glyph) {
  const list = ((comments[reactor] || {})[eventKey]) || [];
  for (let i = list.length - 1; i >= 0; i--) if (list[i] && list[i].g === glyph && list[i].t) return list[i].t;
  return '';
}
const trunc = (t, n = 90) => { t = String(t || '').trim(); return t.length > n ? t.slice(0, n - 1).trimEnd() + '\u2026' : t; };

// ---------- scheduled copy (moved here from notify.js, unchanged) ----------
// The morning spell and evening nudge used to run on GitHub Actions, which
// started them 3 to 6 hours late. Cloudflare's cron is punctual, so they live
// here now. Copy is identical to notify.js.
// Round 2 morning messages (Oct 1 to 31), the same lines as the in-app prompts' pushes in the review doc.
// Daily brew questions. Keep in sync with QUESTIONS in index.html.
export const QUESTIONS = {
  6:'What is something about yourself you like more than you did a year ago?',
  7:'What is a place that feels like a deep breath to you?',
  8:'What is the last thing you said no to that felt amazing?',
  9:'What is the lowest-effort thing that made you happy today?',
  10:'What is one intention you are planting this month, in five words or fewer?',
  11:'What is something on your calendar this week that you are actually looking forward to?',
  12:'What is one thing you have been pretending not to want?',
  13:'What song has been on repeat, and what does it say about you right now?',
  14:'What is a tiny adventure you could have before Friday?',
  15:'What is the best thing you have eaten this week?',
  16:'What have you done this month that Day 1 you would not have believed?',
  17:'What is one habit you would bet on yourself keeping?',
  18:'What is something you do just because it makes you feel put together?',
  19:'What is something one of the other three said lately that stuck with you?',
  20:'What is a small luxury you will not give up, whatever the budget?',
  21:'What is a feeling you had today that you did not expect?',
  22:'What did you choose this month just for you, and not to keep the peace?',
  23:'Scorpio season is here. What is something you want to get to the bottom of?',
  24:'What is one text you are glad you did not send?',
  25:'What is one thing you can point to that grew this month?',
  26:'What did your body ask for most this month, and did you listen?',
  27:'What did you do this month that you would do again in a heartbeat?',
  28:'What is the funniest thing that happened this month?',
  29:'What is the smallest version of your keeper habit that you could do on your worst day?',
  30:'What is a photo from this month that you keep going back to?',
  31:'What did this month give you that you did not know you needed?'
};

export const SPECIAL = {
  1: "Day 1, witches. Round 2 starts now, with no catching up and no guilt. Say your intention out loud to someone today, then cast one small spell.",
  3: "Venus went retrograde overnight \ud83d\udd2e so love, money and values are up for review. No dramatic decisions, just an honest audit of where your time and money go versus what you say matters.",
  10: "New Moon in Libra this morning \ud83c\udf11 Say what you want like it's already on its way, then say it to the group too. Intentions stick better with witnesses.",
  23: "The Sun just moved into Scorpio \ud83e\udd82 Welcome to the deep end, where small talk goes to die. Ask one real question today, of someone else or of yourself.",
  24: "Mercury went retrograde just after midnight. Reread before you send, back up your phone, and close one loose end before it closes you.",
  25: "Full moon in Taurus tonight \ud83c\udf15 It's the receipts moon, so gather what actually grew this month. Three things, photos count, then celebrate a little.",
  31: "Happy Halloween, witches \ud83c\udf83 Last day. Write a short letter to future you, share the good part with the group, then go be spooky. We did a whole month together."
};

export const AFFIRMATIONS = {
  2: "Three words for how you want this month to feel. Not goals, feelings. Pick them today and let them do the steering.",
  4: "Someone's been on your mind, witch. Text them today. Venus retrograde is famous for bringing people back around, and the worst case is a nice reply.",
  5: "Look at what you spent this week. Keep what made you happy, side-eye the rest, and pick your no-spend day if you haven't yet.",
  6: "Still annoyed about that compromise? Good, that's information. Write down what you actually wanted, then decide what to do with it.",
  7: "The Moon's in Virgo, so it's a good day to fix one tiny annoying thing. Ten minutes, one drawer or inbox, then feel smug about it.",
  8: "The Moon is nearly dark, which is the sky's way of saying put something down. Pick one thing to drop before the New Moon, and really drop it.",
  9: "Dark moon today, so the assignment is gentle: take your phone-free hour and do nothing impressive. Tomorrow the New Moon shows up, and she likes a clean slate.",
  11: "You set an intention yesterday, so what's the smallest possible step? Tiny counts. Do it today and let the small win do its job.",
  12: "The Moon's in Scorpio, so honesty is trending. Write the unfiltered version of one thing you keep saying \"I'm fine\" about.",
  13: "Send the coven something today: a link, a song, a weird fact. We're all just here to be a little more interesting to each other.",
  14: "The Moon's in Sagittarius, so today runs on curiosity. Do the thing you keep putting off, then tell us how it went.",
  15: "One free hour, zero obligations: what do you do with it? Go do a small version of that today, and call it whatever you want.",
  16: "Halfway, witches! Reread your Day 1 entry today and notice what's different. Then send the group one thing you're proud of so far.",
  17: "The Moon's in Capricorn, so let's be realistic. Pick the habit you want to keep and picture it on a busy Tuesday, not a perfect Saturday.",
  18: "Which daily spell feels easy and which one feels like homework? Notice why. That's data, not a character flaw.",
  19: "The Moon's in Aquarius, which makes it a very group-chat kind of day. Tell one of the witches something you appreciate about her.",
  20: "What do you believe now that you didn't a year ago? Write it down. Growth is usually a little embarrassing in hindsight, which is how you know it worked.",
  21: "The Moon's in Pisces, so feelings are loud today. Give the one you've been avoiding fifteen minutes. It's probably smaller than it looks.",
  22: "Libra season ends in the early hours tomorrow. Before it does, decide what balance means to you, not to a wellness poster.",
  26: "The Moon's still in Taurus, so today is for comfort. Eat something good, sit down to do it, and count it as a spell, because it is one.",
  27: "What are you proud of from this month that nobody would think to ask about? Tell the group. Showing off is allowed.",
  28: "The Moon's in Gemini, which makes it a talking day. Voice-note one of the witches your favorite moment of this challenge.",
  29: "Pick the one habit that comes with you past Halloween. Make it smaller than feels impressive, then tell the group so someone's watching.",
  30: "The Moon's in Cancer, so let's be sentimental. Scroll back through this month, pick a favorite photo, and send it to the group."
};

const NUMBER_WORDS = ['zero','one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve'];
const numWord = (n) => NUMBER_WORDS[n] || String(n);

export function nudgeMessage(day, need, othersCast, streak) {
  if (streak >= 1) {
    const needLine = need === 1 ? 'Just one more and your spell\u2019s cast.' : 'Any two of the three and your spell\u2019s cast.';
    if (day % 2 === 0) {
      return {
        title: 'The streak\u2019s holding the door',
        body: `${streak} full-coven day${streak === 1 ? '' : 's'} and counting. ${needLine} No guilt, we just want you on the board.`
      };
    }
    return {
      title: `Day ${streak + 1} of the streak is right there`,
      body: `${needLine} Let\u2019s make it ${numWord(streak + 1)}.`
    };
  }
  const threeIn = othersCast === 3 ? ' Three of us are in, come make it four.' : '';
  const v = day % 3;
  if (v === 0) {
    return {
      title: `Day ${day}\u2019s spell isn\u2019t cast yet`,
      body: (need === 1 ? 'Just one more and it\u2019s done.' : 'Any two of the three and it\u2019s done.') + threeIn
    };
  }
  if (v === 1) {
    return {
      title: `Still time for Day ${day}`,
      body: (need === 1 ? 'Just one more and it\u2019s done.' : 'Any two of the three and it\u2019s done.') +
        (othersCast === 3 ? threeIn : ' The coven\u2019s still casting too, you\u2019re in good company.')
    };
  }
  return {
    title: 'The day\u2019s still yours',
    body: (need === 1 ? 'Just one more and today\u2019s spell is cast.' : 'Any two of the three and today\u2019s spell is cast.') + threeIn
  };
}

// Every activity moment currently true in the data, keyed by a stable id.
function activityEvents(data, today) {
  const ev = new Map();
  for (const p of PEOPLE) {
    const pd = data[p];
    if (!pd) continue;
    for (const [k, d] of Object.entries(pd.days || {})) {
      const n = Number(k);
      if (!d) continue;
      if (n === today && isCast(d)) ev.set(`cast:${p}:${n}`, { type: 'cast', actor: p, day: n });
      if (d.hasPhoto) ev.set(`photo:${p}:${n}`, { type: 'photo', actor: p, day: n });
    }
    for (const [wi, wd] of Object.entries(pd.weeks || {})) {
      ((wd && wd.sessions) || []).forEach((s, i) => {
        if (s && s.done && s.hasPhoto) ev.set(`session:${p}:${wi}:${i}`, { type: 'workout', actor: p });
      });
      // Third move of the week: once per person per week. `at` is the latest logged time, so an old week is never news.
      const doneS = ((wd && wd.sessions) || []).filter(s => s && s.done);
      if (doneS.length >= 3) {
        const at = doneS.map(s => s.timestamp || '').sort().pop() || '';
        ev.set(`moves3:${p}:${wi}`, { type: 'moves3', actor: p, week: wi, at });
        ev.set(`moves3self:${p}:${wi}`, { type: 'moves3self', actor: p, week: wi, at });
      }
    }
  }
  // shared links (many a week; the old single article counts as the first one)
  for (const p of PEOPLE) {
    const pd = data[p];
    if (!pd) continue;
    for (const [wi, wd] of Object.entries(pd.weeks || {})) {
      sharesOf(wd).forEach(sh => {
        if (sh.timestamp) ev.set(`share:${p}:${wi}:${sh.id || 'a0'}`, { id: `share:${p}:${wi}:${sh.id || 'a0'}`, type: 'share', actor: p, at: sh.timestamp, label: sh.label || '', url: sh.url });
      });
    }
    // Currently updates (reading / watching / listening)
    for (const h of (pd.currentlyHistory || [])) {
      if (h && h.timestamp && h.value) ev.set(`cur:${p}:${h.field}:${h.timestamp}`, { id: `cur:${p}:${h.field}:${h.timestamp}`, type: 'currently', actor: p, at: h.timestamp, field: h.field, value: h.value });
    }
  }
  if (today >= 1 && today <= 31 && PEOPLE.every(p => data[p] && data[p].days && isCast(data[p].days[today]))) {
    let streak = 0;
    for (let n = today; n >= 1 && PEOPLE.every(p => data[p] && data[p].days && isCast(data[p].days[n])); n--) streak++;
    ev.set(`coven:${today}`, { type: 'coven', actor: null, day: today, streak });
  }
  // Personal streaks: a push to the other three and a private one to her.
  for (const p of PEOPLE) {
    const pd = data[p];
    if (!pd || !pd.days || !isCast(pd.days[today])) continue;
    let streak = 0;
    for (let n = today; n >= 1 && isCast(pd.days[n]); n--) streak++;
    if (ROLL_STEPS.includes(streak)) {
      ev.set(`roll:${p}:${today}:${streak}`, { type: 'roll', actor: p, streak, day: today });
      ev.set(`rollself:${p}:${today}:${streak}`, { type: 'rollself', actor: p, streak, day: today });
    }
  }
  return ev;
}

const ACTION = { cast: 'cast her spell', photo: 'added a photo', workout: 'posted workout proof', share: 'passed on a little magic', currently: 'updated her Currently' };

// Same lines and same picking as the feed in index.html, so a push and its
// feed post read identically. Keep FEED_LINES and pickLine in sync with it.
export const FEED_LINES = {
  share: ['{who} read this and thought of us', '{who} left something on the altar', '{who} passed on a little magic'],
  reading: ['{who} opened a new chapter', '{who} turned a new page', '{who} is deep in a new one'],
  watching: ['{who} hit play on something new', '{who} is on the couch with a new one', '{who} queued up something new'],
  listening: ['{who}\u2019s soundtrack just changed', '{who} has a new one on repeat', '{who} is setting the mood']
};
export function lineKey(id) { return String(id).split(':').slice(1).join(':'); }
export function pickLine(list, key) {
  let h = 0;
  for (const c of String(key)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return list[h % list.length];
}
const line = (kind, id, who) => pickLine(FEED_LINES[kind], lineKey(id)).replace('{who}', who);

function headline(who, type, its, castCount) {
  if (type === 'cast') return { title: `${who} cast her spell \u2726`, body: `${castCount} of 4 spells cast today.` };
  if (type === 'photo') return { title: `${who} added a photo`, body: 'Come take a look.' };
  if (type === 'workout') return { title: `${who} posted workout proof`, body: 'Come take a look.' };
  if (type === 'share') {
    if (its.length > 1) return { title: `${who} left ${its.length} things on the altar`, body: 'Come take a look.' };
    const it = its[0];
    const site = domainOf(it.url);
    return { title: line('share', it.id, who), body: trunc(it.label) || (site ? `From ${site}.` : 'Come take a look.') };
  }
  if (type === 'currently') {
    if (its.length > 1) return { title: `${who}\u2019s Currently just got a refresh`, body: its.slice(0, 2).map(i => `${NOW_VERB[i.field] || 'into'} ${trunc(i.value, 40)}`).join(', ') };
    const it = its[0];
    return { title: FEED_LINES[it.field] ? line(it.field, it.id, who) : `${who} is now ${NOW_VERB[it.field] || 'into'}`, body: trunc(it.value) };
  }
  return { title: who, body: 'Come take a look.' };
}

// Activity pushes point at the one post they are about (the full-coven moment included), else at the feed.
export function composeActivity(items, castTodayCount) {
  const msg = composeActivityText(items, castTodayCount);
  const coven = items.find(i => i.type === 'coven');
  const target = coven ? 'post:' + safeKey(coven.id || ('coven:' + coven.day)) : (items.length === 1 && items[0].id ? 'post:' + safeKey(items[0].id) : 'tea');
  return { ...msg, target };
}
function composeActivityText(items, castTodayCount) {
  const coven = items.find(i => i.type === 'coven');
  if (coven) return covenMessage(coven.day, coven.streak || 1);
  const actors = uniq(items.map(i => i.actor));
  if (actors.length === 1) {
    const who = actors[0];
    const acts = uniq(items.map(i => i.type));
    const head = headline(who, acts[0], items.filter(i => i.type === acts[0]), castTodayCount);
    if (acts.length === 1) return head;
    return { title: head.title, body: `She also ${joinNames(acts.slice(1).map(t => ACTION[t]))}. Come take a look.` };
  }
  const phrases = actors.map(a => `${a} ${joinNames(uniq(items.filter(i => i.actor === a).map(i => ACTION[i.type])))}`);
  return { title: 'The coven\u2019s been busy', body: phrases.slice(0, 3).join(', ') + (phrases.length > 3 ? ', and more' : '') + '.' };
}


export default {
  async scheduled(event, env, ctx) {
    // Round 2 (old-app.html) ran Oct 1 to 31, 2026. After that its jobs have nothing to send, so it is skipped
    // and the whole call budget goes to the habit tracker.
    const now = new Date();
    const round2 = pacificDayNumber(now) <= 31;
    ctx.waitUntil(
      (round2 ? run(env, now).catch(e => console.error('run failed', e && e.stack || e)) : Promise.resolve(resetRun()))
        .then(() => habitsRun(env, new Date()))
        .catch(e => console.error('habits run failed', e && e.stack || e))
    );
  },
  async fetch() {
    return new Response('Spell Check push worker. Nothing to see here.', { status: 200 });
  }
};

// ---------- Firebase REST (values are stored as JSON strings) ----------
// Cloudflare's free plan allows 50 outside calls (subrequests) per run. A run that goes over
// crashes, and a crash before the "already sent" state is saved means the same pushes go out
// again every minute (this happened on Oct 11). Three guards keep that from recurring:
//  1. Every read is cached for the length of one run, so the same key is never fetched twice.
//  2. Every outside call is counted. Normal work stops at CALL_LIMIT, which leaves room to
//     save state; only the state save may use the reserve up to CALL_HARD.
//  3. Scheduled sends are claimed (saved as done) BEFORE they go out. See run().
const CALL_LIMIT = 46;
const CALL_HARD = 49;
let _calls = 0;
let _readCache = new Map();
let _rawCache = new Map();
let _tokenP = null;
function resetRun() { _calls = 0; _readCache = new Map(); _rawCache = new Map(); _tokenP = null; _copyP = null; }
export function callsUsed() { return _calls; }
function bfetch(url, opts, reserved) {
  if (_calls >= (reserved ? CALL_HARD : CALL_LIMIT)) throw new Error('subrequest budget reached (' + _calls + ' calls)');
  _calls++;
  return fetch(url, opts);
}
async function readKey(key) {
  if (_readCache.has(key)) return _readCache.get(key);
  const r = await bfetch(DB + key + '.json');
  if (!r.ok) throw new Error('read ' + key + ' ' + r.status);
  const v = await r.json();
  let out = null;
  if (typeof v === 'string') { try { out = JSON.parse(v); } catch (e) { out = null; } }
  _readCache.set(key, out);
  return out;
}
async function writeKey(key, obj, reserved) {
  const r = await bfetch(DB + key + '.json', { method: 'PUT', body: JSON.stringify(JSON.stringify(obj)) }, reserved);
  if (!r.ok) throw new Error('write ' + key + ' ' + r.status);
  _readCache.delete(key);
}
async function readRaw(key) {
  if (_rawCache.has(key)) return _rawCache.get(key);
  const r = await bfetch(DB + key + '.json');
  let out = null;
  if (r.ok) { const v = await r.json(); out = typeof v === 'string' ? v : null; }
  _rawCache.set(key, out);
  return out;
}

// ---------- who owns a feed item ----------
// Event keys match index.html's feed ids (with . # $ [ ] / swapped for _).
function describe(eventKey) {
  const parts = eventKey.split(':');
  const type = parts[0];
  if (type === 'coven') return null; // group posts have no single owner
  const owner = parts[1];
  if (!PEOPLE.includes(owner)) return null;
  if (type === 'cast') return { owner, text: `your Day ${parts[2]} spell` };
  if (type === 'photo') return { owner, text: `your Day ${parts[2]} photo` };
  if (type === 'session') return { owner, text: 'your movement session' };
  if (type === 'article') return { owner, text: 'your shared link' };
  if (type === 'cur') return { owner, text: `what you\u2019re ${VERBS[parts[2]] || 'into'}` };
  return null;
}

function joinNames(a) {
  if (a.length <= 1) return a.join('');
  return a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1];
}
function uniq(a) { return Array.from(new Set(a)); }

function pacificMinute(now) {
  return Number(new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', minute: 'numeric' }).format(now));
}
function pacificHour(now) {
  return Number(new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', hour: 'numeric', hourCycle: 'h23' }).format(now));
}
// Quiet hours are off. To bring them back, e.g. midnight to 7am Pacific:
//   return h >= 0 && h < 7;
const QUIET_HOURS_ON = false;
function isQuiet(now) { if (!QUIET_HOURS_ON) return false; const h = pacificHour(now); return h >= 22 || h < 8; }

// Same for reactions: a tap opens the post that was reacted to, or the feed when there are several.
export function composeMessage(items) {
  const events = uniq(items.map(i => i.eventKey));
  return { ...composeMessageText(items), target: events.length === 1 ? 'post:' + events[0] : 'tea' };
}
function composeMessageText(items) {
  const reactors = uniq(items.map(i => i.reactor));
  const glyphs = uniq(items.map(i => i.glyph));
  const events = uniq(items.map(i => i.eventKey));
  const target = events.length === 1 ? items[0].text : `${events.length} of your posts`;
  const heldOvernight = items.some(i => i.heldOvernight);
  if (heldOvernight) {
    return { title: 'While you were asleep', body: `${joinNames(reactors)} reacted to ${target} ${glyphs.join(' ')}` };
  }
  if (items.length === 1) {
    const it = items[0];
    const copy = REACTION_COPY[it.glyph];
    if (copy) {
      const note = String(it.note || '').trim();
      return { title: copy.title(it.reactor), body: note ? `\u201c${trunc(note, 90)}\u201d On ${target}.` : copy.body(target) };
    }
    return { title: `${reactors[0]} sent you a ${glyphs[0]}`, body: `On ${target}.` };
  }
  return { title: `${joinNames(reactors)} reacted ${glyphs.join(' ')}`, body: `On ${target}. The coven sees you, and it\u2019s being weird about how good you are.` };
}

// Runs one part of the Worker so a failure in it is logged and skipped instead of taking down the
// whole run (and with it the state save).
async function guard(name, fn) {
  try { await fn(); } catch (e) { console.error(name + ' failed', e && e.message); }
}

export async function run(env, now) {
  resetRun();
  const reactions = {};
  for (const p of PEOPLE) reactions[p] = (await readKey(R2 + 'recal-reactions:' + p)) || {};

  // Every live reaction as a "reactor|eventKey|glyph" id.
  const live = new Map();
  for (const reactor of PEOPLE) {
    for (const [eventKey, glyphs] of Object.entries(reactions[reactor])) {
      for (const glyph of (glyphs || [])) live.set(`${reactor}|${eventKey}|${glyph}`, { reactor, eventKey, glyph });
    }
  }

  const state = (await readKey(STATE_KEY)) || null;
  if (!state || !state.initialized) {
    await writeKey(STATE_KEY, { initialized: true, seen: Array.from(live.keys()), pending: {} });
    console.log('First run: marked', live.size, 'existing reactions as seen, sent nothing.');
    return { sent: [], baseline: live.size };
  }

  const seen = new Set(state.seen || []);
  const pending = state.pending || {};
  let changed = false;
  const quiet = isQuiet(now);
  const prefsCache = {};
  const prefsFor = async (p) => {
    if (!(p in prefsCache)) prefsCache[p] = Object.assign({ reactions: true, activity: true, morning: true, nudge: true }, (await readKey('recal-notif-prefs:' + p)) || {});
    return prefsCache[p];
  };

  for (const [id, r] of live) {
    if (seen.has(id)) continue;
    seen.add(id); changed = true;
    const d = describe(r.eventKey);
    if (!d || d.owner === r.reactor) continue;
    if (!(await prefsFor(d.owner)).reactions) continue;
    (pending[d.owner] = pending[d.owner] || []).push({ id, reactor: r.reactor, glyph: r.glyph, eventKey: r.eventKey, text: d.text, heldOvernight: quiet, holdUntil: now.getTime() + 60 * 1000 });
  }

  // Drop anything un-reacted before it went out.
  for (const owner of Object.keys(pending)) {
    const before = pending[owner].length;
    pending[owner] = pending[owner].filter(i => live.has(i.id));
    if (pending[owner].length !== before) changed = true;
    if (!pending[owner].length) delete pending[owner];
  }

  // ---- coven activity ----
  const data = {};
  for (const p of PEOPLE) data[p] = await readKey(R2 + 'recal:' + p);
  const today = pacificDayNumber(now);
  const liveActivity = activityEvents(data, today);
  const pendingActivity = state.pendingActivity || {};
  if (!state.activityInit) {
    state.activitySeen = Array.from(liveActivity.keys());
    state.activityInit = true;
    state.activityV = 2;
    changed = true;
    console.log('Activity baseline: marked', liveActivity.size, 'existing moments as seen.');
  } else {
    const aSeen = new Set(state.activitySeen || []);
    if ((state.activityV || 1) < 2) {
      // Links and Currently updates are new here: mark what already exists as
      // seen, silently, so nobody gets a flood the moment this version deploys.
      for (const [id, e] of liveActivity) if (e.type === 'share' || e.type === 'currently') aSeen.add(id);
      state.activityV = 2;
      changed = true;
      console.log('Activity v2 baseline: existing links and Currently updates marked as seen.');
    }
    for (const [id, e] of liveActivity) {
      if (aSeen.has(id)) continue;
      if (e.type === 'moves3' || e.type === 'moves3self') {
        // Only fresh news: a third move logged in the last 6 hours. Anything older, or with no time, is marked seen silently.
        const ageM = now.getTime() - new Date(e.at).getTime();
        if (!(ageM >= 0 && ageM <= 6 * 3600 * 1000)) { aSeen.add(id); changed = true; continue; }
      }
      if (e.type === 'share' || e.type === 'currently') {
        const age = now.getTime() - new Date(e.at).getTime();
        // Old news (Worker was off, clock skew): never push it.
        if (age > 6 * 3600 * 1000) { aSeen.add(id); changed = true; continue; }
        if (e.type === 'currently') {
          // A quick correction is one update: a newer one for the same field
          // within 10 minutes supersedes this one silently.
          let superseded = false;
          for (const [, o] of liveActivity) {
            if (o !== e && o.type === 'currently' && o.actor === e.actor && o.field === e.field) {
              const d = new Date(o.at).getTime() - new Date(e.at).getTime();
              if (d > 0 && d < 10 * 60 * 1000) { superseded = true; break; }
            }
          }
          if (superseded) { aSeen.add(id); changed = true; continue; }
          // Let it settle for 90 seconds in case she is still fixing the title.
          if (age < 90 * 1000) continue;
        }
      }
      aSeen.add(id); changed = true;
      // A private streak push goes only to her. Everything else is never about your own activity.
      const targets = (e.type === 'rollself' || e.type === 'moves3self') ? [e.actor] : PEOPLE.filter(r => r !== e.actor);
      for (const r of targets) {
        if (!(await prefsFor(r)).activity) continue;
        (pendingActivity[r] = pendingActivity[r] || []).push({ id, ...e });
      }
    }
    state.activitySeen = Array.from(aSeen).filter(id => liveActivity.has(id));
  }
  const castTodayCount = PEOPLE.filter(p => data[p] && data[p].days && isCast(data[p].days[today])).length;

  // ---- comments ----
  const comments = {};
  for (const p of PEOPLE) comments[p] = (await readKey(R2 + 'recal-comments:' + p)) || {};
  const liveComments = new Map();
  for (const author of PEOPLE) {
    for (const [eventKey, list] of Object.entries(comments[author])) {
      for (const c of (list || [])) {
        if (c && c.id && c.t) liveComments.set(`${author}|${eventKey}|${c.id}`, { author, eventKey, id: c.id, t: c.t, at: c.at, g: c.g });
      }
    }
  }
  const pendingComments = state.pendingComments || {};
  if (!state.commentsInit) {
    // First run with comments: mark whatever exists as seen, silently.
    state.commentsSeen = Array.from(liveComments.keys());
    state.commentsInit = true;
    changed = true;
    console.log('Comments baseline: marked', liveComments.size, 'existing comments as seen.');
  } else {
    const cSeen = new Set(state.commentsSeen || []);
    for (const [uid, c] of liveComments) {
      if (cSeen.has(uid)) continue;
      cSeen.add(uid); changed = true;
      if (c.g) continue; // a note rides along with its reaction push
      if (now.getTime() - new Date(c.at).getTime() > 6 * 3600 * 1000) continue; // old news
      const info = describePost(c.eventKey);
      const recipients = new Set();
      if (info.owner && info.owner !== c.author) recipients.add(info.owner);
      for (const o of liveComments.values()) {
        if (o.eventKey === c.eventKey && !o.g && o.author !== c.author && String(o.at) < String(c.at)) recipients.add(o.author);
      }
      for (const r of recipients) {
        if (!(await prefsFor(r)).reactions) continue;
        (pendingComments[r] = pendingComments[r] || []).push({ uid, author: c.author, eventKey: c.eventKey, t: c.t, owner: info.owner, noun: info.noun, role: r === info.owner ? 'owner' : 'also' });
      }
    }
    state.commentsSeen = Array.from(cSeen).filter(u => liveComments.has(u));
  }

  // ---- letters: "you got one" ping, fires when a letter is sealed to you ----
  // Letters are append-only (never edited or unsent), so this is a plain seen-set
  // diff like reactions, with no need to handle removal.
  const lettersByIdNow = new Map(); // id -> {sender, to, opensDay, writtenAt}
  for (const sender of PEOPLE) {
    const list = (await readKey(R2 + 'recal-letters:' + sender)) || [];
    for (const l of list) if (l && l.id) lettersByIdNow.set(l.id, { sender, to: l.to, opensDay: l.opensDay, writtenAt: l.writtenAt, intro: l.intro === true && sender === 'Nina' && l.to === 'all' });
  }
  const pendingLetters = state.pendingLetters || {};
  if (!state.lettersInit) {
    state.lettersSeen = Array.from(lettersByIdNow.keys());
    state.lettersInit = true;
    changed = true;
    console.log('Letters baseline: marked', lettersByIdNow.size, 'existing letters as seen.');
  } else {
    const lSeen = new Set(state.lettersSeen || []);
    for (const [id, l] of lettersByIdNow) {
      if (lSeen.has(id)) continue;
      lSeen.add(id); changed = true;
      if (l.writtenAt && now.getTime() - new Date(l.writtenAt).getTime() > 6 * 3600 * 1000) continue; // old news
      if (l.to === l.sender) continue; // letter to yourself: no ping, you already know
      const recipients = l.to === 'all' ? PEOPLE.filter(p => p !== l.sender) : (PEOPLE.includes(l.to) ? [l.to] : []);
      for (const r of recipients) {
        if (!(await prefsFor(r)).activity) continue;
        (pendingLetters[r] = pendingLetters[r] || []).push({ id, sender: l.sender, to: l.to, opensDay: l.opensDay, intro: l.intro === true });
      }
    }
    state.lettersSeen = Array.from(lSeen).filter(id => lettersByIdNow.has(id));
  }

  // One place that saves the Worker's state. Called right after sends so a later problem can never
  // make an earlier push go out again, and once more at the end for everything else.
  const persist = async (reserved) => {
    const trimmed = Array.from(seen).filter(id => live.has(id)); // only ids that still exist matter
    await writeKey(STATE_KEY, { initialized: true, seen: trimmed, pending, activityInit: !!state.activityInit, activityV: state.activityV || 1, activitySeen: state.activitySeen || [], pendingActivity, commentsInit: !!state.commentsInit, commentsSeen: state.commentsSeen || [], pendingComments, lettersInit: !!state.lettersInit, lettersSeen: state.lettersSeen || [], pendingLetters, sched: state.sched || {} }, reserved);
    changed = false;
  };

  const sent = [];
  await guard('activity pushes', async () => {
  if (!quiet && Object.keys(pendingActivity).length) {
    let accessTokenA = null;
    const isRoll = (i) => i.type === 'roll' || i.type === 'rollself';
    for (const r of Object.keys(pendingActivity)) {
      const items = pendingActivity[r].filter(i => liveActivity.has(i.id)); // undone before it went out? skip it
      if (!items.length) { delete pendingActivity[r]; changed = true; continue; }
      const token = await readRaw('recal-fcm-token:' + r);
      if (!token) { delete pendingActivity[r]; changed = true; continue; }
      // A streak push replaces that person's plain "cast her spell" push, so nobody gets two for one moment.
      // When the whole coven is celebrated in this same moment, that push already covers everyone's streaks.
      // Only her own private streak push still goes out.
      const covenNow = items.some(i => i.type === 'coven');
      const rollItems = items.filter(i => isRoll(i) && !(covenNow && i.type === 'roll'));
      const rollActors = new Set(items.filter(isRoll).map(i => i.actor));
      const isMoves = (i) => i.type === 'moves3' || i.type === 'moves3self';
      const movesItems = items.filter(isMoves);
      const rest = items.filter(i => !isRoll(i) && !isMoves(i) && !(i.type === 'cast' && rollActors.has(i.actor)));
      const batches = rollItems.slice(0, 2).map(i => ({ items: [i], msg: rollMessage(i) }));
      movesItems.slice(0, 2).forEach(i => batches.push({ items: [i], msg: movesMessage(i) }));
      if (rest.length) batches.push({ items: rest, msg: composeActivity(rest, castTodayCount) });
      let failed = false;
      const left = [];
      for (const b of batches) {
        if (failed) { left.push(...b.items); continue; }
        try {
          if (!accessTokenA) accessTokenA = await getAccessToken(env);
          await sendPush(env, accessTokenA, token, b.msg);
          sent.push({ owner: r, ...b.msg });
          console.log('Activity to', r, '|', b.msg.title, '|', b.msg.body);
        } catch (e) {
          failed = true;
          console.error('Activity send failed for', r, e && e.message);
          b.items.forEach(i => { i.tries = (i.tries || 0) + 1; });
          left.push(...b.items);
        }
      }
      const kept = left.filter(i => (i.tries || 0) < 5);
      if (kept.length) pendingActivity[r] = kept; else delete pendingActivity[r];
      changed = true;
      await persist();
    }
  }
  });

  await guard('comment pushes', async () => {
  if (!quiet && Object.keys(pendingComments).length) {
    let accessTokenC = null;
    for (const r of Object.keys(pendingComments)) {
      const items = pendingComments[r].filter(i => liveComments.has(i.uid)); // deleted before it went out? skip it
      if (!items.length) { delete pendingComments[r]; changed = true; continue; }
      if (!(await prefsFor(r)).reactions) { delete pendingComments[r]; changed = true; continue; }
      const token = await readRaw('recal-fcm-token:' + r);
      if (!token) { delete pendingComments[r]; changed = true; continue; }
      const msg = composeComments(items);
      try {
        if (!accessTokenC) accessTokenC = await getAccessToken(env);
        await sendPush(env, accessTokenC, token, msg);
        sent.push({ owner: r, ...msg });
        console.log('Comments to', r, '|', msg.title, '|', msg.body);
        delete pendingComments[r]; changed = true;
        await persist();
      } catch (e) {
        console.error('Comment send failed for', r, e && e.message);
        items.forEach(i => { i.tries = (i.tries || 0) + 1; });
        pendingComments[r] = items.filter(i => i.tries < 5);
        if (!pendingComments[r].length) delete pendingComments[r];
        changed = true;
      }
    }
  }
  });

  await guard('letter pings', async () => {
  if (!quiet && Object.keys(pendingLetters).length) {
    let accessTokenL = null;
    for (const r of Object.keys(pendingLetters)) {
      const items = pendingLetters[r].filter(i => lettersByIdNow.has(i.id)); // can't happen (letters aren't deletable), kept for symmetry
      if (!items.length) { delete pendingLetters[r]; changed = true; continue; }
      const token = await readRaw('recal-fcm-token:' + r);
      if (!token) { delete pendingLetters[r]; changed = true; continue; }
      for (const l of items) {
        const alreadyOpen = l.opensDay <= today;
        const dateLabel = LETTER_DATE_LABELS[l.opensDay] || ('Oct ' + l.opensDay);
        // Nina's one-time intro letter (marked intro:true by the app) gets its own announcement.
        const msg = l.intro
          ? { ...INTRO_PUSH }
          : l.to === 'all'
          ? { title: `${l.sender} wrote all of us something ✦`,
              body: alreadyOpen
                ? `${l.sender} sealed a letter for the whole coven. It's open right now, so there's no waiting this time. Go on.`
                : `${l.sender} sealed a letter for the whole coven. It opens ${dateLabel}. Four of us, one envelope, no peeking.` }
          : { title: `${l.sender} wrote you something ✦`,
              body: alreadyOpen
                ? `${l.sender} sealed a letter with your name on it. It's open right now, so there's no waiting this time. Go on.`
                : `${l.sender} sealed a letter with your name on it. It opens ${dateLabel}. You're the main event, apparently.` };
        msg.target = 'letters';
        try {
          if (!accessTokenL) accessTokenL = await getAccessToken(env);
          await sendPush(env, accessTokenL, token, msg);
          sent.push({ owner: r, ...msg });
          l.sent = true; // sent: never keep it queued, even if an earlier try failed
          console.log('Letter ping to', r, '|', msg.title, '|', msg.body);
        } catch (e) {
          console.error('Letter ping send failed for', r, e && e.message);
          l.tries = (l.tries || 0) + 1;
        }
      }
      // Sent items are done; a failed item (tries set, still under 5) stays queued and retries next run.
      pendingLetters[r] = items.filter(i => !i.sent && (i.tries || 0) > 0 && i.tries < 5);
      if (!pendingLetters[r].length) delete pendingLetters[r];
      changed = true;
      await persist();
    }
  }
  });

  await guard('reaction pushes', async () => {
  if (!quiet && Object.keys(pending).length) {
    let accessToken = null;
    for (const owner of Object.keys(pending)) {
      const items = pending[owner];
      const prefs = await prefsFor(owner);
      if (!prefs.reactions) { delete pending[owner]; changed = true; continue; }
      // Give a note typed right after the tap a moment to arrive, so it rides along.
      const ready = items.filter(i => !i.holdUntil || i.holdUntil <= now.getTime());
      if (!ready.length) continue;
      const token = await readRaw('recal-fcm-token:' + owner);
      if (!token) { console.log('No device token for', owner, ', dropping', items.length); delete pending[owner]; changed = true; continue; }
      ready.forEach(i => { i.note = noteFor(comments, i.reactor, i.eventKey, i.glyph); });
      const msg = composeMessage(ready);
      try {
        if (!accessToken) accessToken = await getAccessToken(env);
        await sendPush(env, accessToken, token, msg);
        sent.push({ owner, ...msg });
        console.log('Sent to', owner, '|', msg.title, '|', msg.body);
      } catch (e) {
        // Stays pending and retries next run, but gives up after 5 tries so a
        // dead device token can't retry forever.
        console.error('Send failed for', owner, e && e.message);
        ready.forEach(i => { i.tries = (i.tries || 0) + 1; });
        if (ready.some(i => i.tries >= 5)) pending[owner] = items.filter(i => !ready.includes(i)); 
        if (pending[owner] && !pending[owner].length) delete pending[owner];
        changed = true;
        continue;
      }
      pending[owner] = items.filter(i => !ready.includes(i));
      if (!pending[owner].length) delete pending[owner];
      changed = true;
      await persist();
    }
  }
  });

  let schedToken = null;
  // ---- scheduled: morning spell (8:00am PT) and evening nudge (7:00pm PT) ----
  // Each job has a window so it can never go out at a silly hour: the morning
  // spell only between 8:00 and 11:59am Pacific, the nudge only between 7:00
  // and 9:59pm. If the Worker was down for the whole window, that day's send
  // is skipped rather than sent late. Sent-status is tracked per person, so a
  // failed send retries next minute (up to 5 times) without double-sending.
  const ptHour = pacificHour(now);
  const isSunday = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', weekday: 'short' }).format(now) === 'Sun';
  if (today >= 1 && today <= 31) {
    state.sched = state.sched || {};
    const castOn = (p, n) => !!(data[p] && data[p].days && isCast(data[p].days[n]));
    let streak = 0;
    for (let n = today - 1; n >= 1 && PEOPLE.every(p => castOn(p, n)); n--) streak++;
    for (const job of ['morning', 'brew', 'nudge', 'recap', 'letters', 'introResend', 'letterNights', 'lastCall']) {
      const inWindow = job === 'morning' ? (ptHour >= 8 && ptHour < 12)
        : job === 'brew' ? (ptHour >= 12 && ptHour < 22 && !!QUESTIONS[today])
        : job === 'nudge' ? (ptHour >= 19 && ptHour < 22)
        : job === 'letters' ? (ptHour >= 20 && ptHour < 22 && today >= 10 && today <= 31) // starts at 8pm so it never collides with the 7pm nudge
        : job === 'lastCall' ? (!!LETTER_LAST_CALL[today + 1] && ((ptHour === LETTER_LAST_CALL_AT.hour && pacificMinute(now) >= LETTER_LAST_CALL_AT.minute) || (ptHour > LETTER_LAST_CALL_AT.hour && ptHour < 22))) // from 8pm, skipped once the window shuts at 10pm
        : job === 'letterNights' ? (today === LETTER_NIGHTS_SEND.day && ptHour >= LETTER_NIGHTS_SEND.hour && ptHour < 12) // once, from 9am, skipped if the Worker was down all morning
        : job === 'introResend' ? (today === INTRO_RESEND.day && ((ptHour === INTRO_RESEND.hour && pacificMinute(now) >= INTRO_RESEND.minute) || ptHour === INTRO_RESEND.hour + 1)) // once, at the time set above, with an hour of grace
        : (isSunday && today >= 7 && ptHour >= 18 && ptHour < 22); // Sunday recap, from 6pm
      if (!inWindow) continue;
      await guard('scheduled job ' + job, async () => {
      let rec = state.sched[job];
      if (!rec || rec.day !== today) { rec = state.sched[job] = { day: today, done: [], tries: {} }; changed = true; }
      const outbox = [];
      for (const person of PEOPLE) {
        if (rec.done.includes(person)) continue;
        const finish = () => { rec.done.push(person); changed = true; };
        if (job === 'introResend' && person === 'Nina') { finish(); continue; } // it is her own letter
        const prefKey = (job === 'recap' || job === 'letters' || job === 'introResend' || job === 'letterNights' || job === 'lastCall') ? 'activity' : job === 'brew' ? 'morning' : job;
        if (!(await prefsFor(person))[prefKey]) { console.log(person, 'turned', job, 'off, skipping.'); finish(); continue; }
        let msg;
        if (job === 'morning') {
          msg = { title: `\u2728 Day ${today} of Spells, Witches`, body: SPECIAL[today] || AFFIRMATIONS[today] || `Day ${today} is live. Go check in.` };
        } else if (job === 'brew') {
          const qa = await readKey(R2 + 'recal-qa:' + person);
          if (qa && qa[today]) { console.log(person, 'already answered the Day', today, 'brew, no push.'); finish(); continue; }
          msg = { title: `Today\u2019s brew`, body: QUESTIONS[today] };
        } else if (job === 'introResend') {
          // The same push, once more, for everyone but Nina, whether or not they have opened the letter.
          // A skip is only for a switched-off setting or a missing phone address, and each says why.
          const intro = Array.from(lettersByIdNow.entries()).find(([, l]) => l.intro);
          if (!intro) { console.log('No intro letter found, nothing to resend.'); finish(); continue; }
          msg = { ...INTRO_PUSH };
        } else if (job === 'letterNights') {
          msg = { ...LETTER_NIGHTS_PUSH };
        } else if (job === 'lastCall') {
          // Skip anyone who has already sealed a letter for tomorrow's night (to anyone, herself included).
          const mine = (await readKey(R2 + 'recal-letters:' + person)) || [];
          if (mine.some(l => l && l.opensDay === today + 1)) { console.log(person, 'already wrote for night', today + 1, ', no last call.'); finish(); continue; }
          msg = { ...LETTER_LAST_CALL[today + 1] };
        } else if (job === 'recap') {
          msg = recapMessage(weekStats(data, reactions, today));
        } else if (job === 'letters') {
          // Nudges every evening (not just the night a letter opens) for any letter that's
          // open (opensDay <= today, per the app's letterIsUnlocked) and not yet opened by
          // this person. Unlike the landed ping, this includes letters she sealed to herself.
          const opened = (await readKey(R2 + 'recal-letters-opened:' + person)) || {};
          const unopened = [];
          for (const sender of PEOPLE) {
            const list = (await readKey(R2 + 'recal-letters:' + sender)) || [];
            for (const l of list) {
              if (l.opensDay > today) continue; // not open yet
              if (l.to !== person && l.to !== 'all') continue;
              if (opened[l.id]) continue;
              unopened.push({ id: l.id, sender, opensDay: l.opensDay });
            }
          }
          if (!unopened.length) { console.log(person, 'has nothing unopened to nudge about.'); finish(); continue; }
          if (unopened.length === 1 && unopened[0].sender === person) {
            // Self-letter nudge copy isn't approved yet (only derived, unconfirmed lines exist).
            // Skip rather than invent wording; flagged to Nina separately.
            console.log(person, 'only has an unopened letter to herself, nudge copy not approved, skipping.');
            finish(); continue;
          }
          const count = unopened.length;
          const openedToday = unopened.some(l => l.opensDay === today);
          if (openedToday) {
            const night = LETTER_NIGHT_NAMES[today]; // none on days with no sky tag
            msg = count === 1
              ? { title: 'Break the seal ✦', body: `${unopened[0].sender}'s letter is ready and so, we suspect, are you. ${night ? night + '. ' : ''}Break the seal.` }
              : { title: 'Break the seal ✦', body: `${count} letters are ready for you tonight. Go be adored, one seal at a time.` };
          } else if (count === 1) {
            const lines = [
              `${unopened[0].sender}'s letter isn't going anywhere. Neither are we. Break the seal when you're ready.`,
              `Still sealed, still from ${unopened[0].sender}, still very patient. Break the seal whenever you like.`,
              `${unopened[0].sender}'s letter is still sealed and still ready. Some things are worth taking your time over. Break the seal when you do.`,
              `${unopened[0].sender} wrote you something and it's still here, waiting for the right moment. Make your entrance whenever you like.`,
            ];
            msg = { title: 'Break the seal ✦', body: lines[today % lines.length] };
          } else {
            const lines = [
              `${count} letters are waiting for you, all from people who adore you. Take them in any order.`,
              `${count} letters, all yours, all waiting politely. Take them in any order.`,
            ];
            msg = { title: 'Break the seal ✦', body: lines[today % lines.length] };
          }
        } else {
          const dd = data[person] && data[person].days ? data[person].days[today] : null;
          if (isCast(dd)) { console.log(person, 'already cast Day', today, ', no nudge.'); finish(); continue; }
          const othersCast = PEOPLE.filter(p => p !== person && castOn(p, today)).length;
          msg = nudgeMessage(today, 2 - castCount(dd), othersCast, streak);
        }
        if (job === 'letters' || job === 'introResend' || job === 'letterNights') msg.target = 'letters';
        const token = await readRaw('recal-fcm-token:' + person);
        if (!token) { console.log('No device token for', person, ', skipping', job); finish(); continue; }
        // Claim first: she is marked done and saved BEFORE any push goes out (below). Sends happen after the loop.
        finish();
        outbox.push({ person, msg, token });
      }
      if (outbox.length) {
        try { await persist(); } catch (e) {
          for (const o of outbox) rec.done = rec.done.filter(x => x !== o.person);
          console.error(job, 'could not save state, not sending:', e && e.message);
          return;
        }
        for (const { person, msg, token } of outbox) {
          try {
            if (!schedToken) schedToken = await getAccessToken(env);
            await sendPush(env, schedToken, token, msg);
            sent.push({ owner: person, job, ...msg });
            console.log(job, 'to', person, '|', msg.title);
          } catch (e) {
            const overBudget = /subrequest budget/.test(e && e.message);
            if (!overBudget) rec.tries[person] = (rec.tries[person] || 0) + 1; // running out of calls is not her device's fault
            console.error(job, 'send failed for', person, '(try', (rec.tries[person] || 0) + '):', e && e.message);
            if (overBudget || rec.tries[person] < 5) rec.done = rec.done.filter(x => x !== person); // retry next minute
            changed = true;
          }
        }
      }
      });
    }
  }

  if (changed) await persist(true);
  return { sent, quiet };
}

// ---------- new habit tracker pushes (index.html, data under recalData/h3-*) ----------
// Everything for the habit tracker, kept apart from the Round 2 jobs above. Own state key (h3-push-state).
// Scheduled sends are claimed (saved as done) BEFORE they go out, like Round 2.
//   h3sky     8am to 11:59am Pacific on her sky days (New and Full Moons, the app's SKY_DAYS, every Wednesday).
//   h3morning 8am to 11:59am Pacific (9am on her sky days, so the two never land together): one approved line
//             per person (see weekPlan). A and J lines only when a habit is open today. After two days with nothing
//             done, the comeback line goes out instead.
//   h3brew    noon to 9:59pm Pacific: today's brew question, skipped once she has answered.
//   h3nudge   7pm to 9:59pm Pacific: a habit due today is not done. When one of those habits has a streak of 3 or
//             more, the streak line goes out instead of the nudge.
//   h3vote    Sunday 6pm to 9:59pm Pacific: next week's coven habit vote is still open for her.
//   h3result  Monday 8am to 11:59am Pacific: the coven habit for this week, if anyone voted.
//   social    every run: friend showed up, all four showed up, milestones, reactions, brew answers, shared reads,
//             Currently, new group habits.
// All wording lives in push-copy.json. The brew question and the sky headline come from the app itself
// (h3-sched-<Person>, written by index.html), so the Worker never holds its own copy of them.
const H3_STATE_KEY = 'h3-push-state';
export const H3_JOBS_ON = { vote: true, result: true };
export const H3_VOTE_NAMES = { phone: 'Phone-free hour', walk: '10 minute walk outside', tidy: 'Tidy 10 minutes', water: 'Drink a full glass first thing' };
export const SEASON_START = '2026-11-05'; // must match index.html
// ---------- push copy lives in the repo (push-copy.json), not in this file ----------
// Approved wording is fetched from GitHub Pages once per run, so a wording change is a pull request and
// never a Cloudflare paste. It counts as one outside call. If the fetch fails or a line is invalid, the
// small built-in set below is used so a push is never lost. The database is not used for copy because
// its rules allow public writes.
export const COPY_URL = 'https://ninaprojects.github.io/spellcheck/push-copy.json';
export const H3_FALLBACK = {
  A: [{ id: 'A1', title: 'Rise and tap ✦', body: 'Today’s habits. The effort? Tiny. The cheering section? ENORMOUS.' }, { id: 'A2', title: 'Good morning, {name} ✦', body: 'Today’s habits are ready when you are.' }],
  J: [{ id: 'J5', title: 'A way with words ✦', body: 'Putting what you feel into sentences is a real skill, and we love watching you use it, {name}.' }],
  C: [{ id: 'C6', title: 'Daily highlight ✦', body: 'Choose one moment to look forward to and say it out loud. A reason to smile, already booked.' }],
  E: [{ id: 'E2', title: 'Tap before the credits ✦', body: 'Whatever is still open from today is waiting, and the day deserves a proper finale, {name}.' }],
  BT: [{ id: 'BT1', title: 'The coven wants to know ✦', body: '{q}' }],
  V: [{ id: 'V1', title: 'Last call to vote ✦', body: 'Next week\'s coven habit is still open. Pick one before the night is over, or we run it back.' }],
  R: [{ id: 'R1', title: 'The people have spoken ✦', body: '{habit} it is. Everyone is in, whether they know it yet or not.' }],
  B: [{ id: 'B14', title: 'Psst, gossip for you ✦', body: '{sky}' }],
  IN: [{ id: 'IN8', title: '{who} is in ✦', body: '{who} did {habit}. Girl get yours.' }],
  ALL: [{ id: 'ALL1', title: 'All four showed up ✦', body: 'Everyone did something today. The coven is undefeated.' }],
  RX: [{ id: 'RXh1', title: '{who}\'s heart is swelling ♡', body: 'On your {post}. We\'d ask you to stay humble, but we\'ve met you.', tags: ['heart'] },
    { id: 'RXs1', title: '{who} is spellbound ✦', body: 'On your {post}. A bow is customary. Several bows are encouraged.', tags: ['spell'] },
    { id: 'RXm1', title: '{who} sent you calm tides ☾', body: 'On your {post}. Unclench your shoulders, the coven\'s got this.', tags: ['moon'] }],
  QA: [{ id: 'QA1', title: '{who} spilled ✦', body: '{answer}' }],
  SR: [{ id: 'SR1', title: '{who} read this and thought of us ✦', body: '{label}' }],
  CU: [{ id: 'CUr1', title: '{who} opened a new chapter ✦', body: '{value}', tags: ['reading'] }, { id: 'CUw1', title: '{who} hit play on something new ✦', body: '{value}', tags: ['watching'] }, { id: 'CUl1', title: '{who}\'s soundtrack just changed ✦', body: '{value}', tags: ['listening'] }],
  GH: [{ id: 'GH1', title: 'New club just dropped ✦', body: '{who} started {habit}. Peer pressure, but make it healthy.' }],
  CM: [{ id: 'CM7_1', title: 'Milestone alert ✦', body: '{who} hit 7 days on {habit}. Nobody panic.', tags: ['d7'] }, { id: 'CM14_1', title: 'Milestone alert ✦', body: 'Two weeks of {habit} for {who}. The rest of us are taking notes.', tags: ['d14'] }, { id: 'CM30_1', title: 'Milestone alert ✦', body: '{who} just hit 30 days on {habit}. We are not worthy.', tags: ['d30'] }],
  MP: [{ id: 'MP7a', title: 'Seven days of {habit} ✦', body: 'A whole week. The coven is losing it.', tags: ['d7'] }, { id: 'MP14a', title: 'Two weeks of {habit} ✦', body: 'Fourteen days straight. Honestly, ENERGY.', tags: ['d14'] }, { id: 'MP30a', title: 'Thirty days of {habit} ✦', body: 'A full month. Iconic behavior, truly.', tags: ['d30'] }],
  ST: [{ id: 'ST1', title: 'Your streak is glowing ✦', body: '{n} days and counting. One small thing makes it {n1}.' }],
  CB: [{ id: 'CB1', title: 'Welcome back ✦', body: 'The coven kept your seat warm. One small thing and you are back.' }]
};
// Groups where a line must match its own tag (a reaction, a field, a milestone). If the copy file loses every line
// for one tag, the built-in lines for that tag fill in.
const TAGGED = { RX: ['heart', 'spell', 'moon'], CU: ['reading', 'watching', 'listening'], CM: ['d7', 'd14', 'd30'], MP: ['d7', 'd14', 'd30'] };
const okTitle = t => typeof t === 'string' && t.length > 0 && t.length <= 40 && /[✦♡☾]$/.test(t);
// Keeps only well-formed lines: a short id, titles ending in the star (or a reaction symbol), bodies under 130
// characters, no links, no em or en dashes. Anything else is dropped. A group left empty falls back to the built-in lines.
export function cleanCopy(raw, fallback = H3_FALLBACK) {
  const out = {};
  for (const g of Object.keys(fallback)) {
    const list = raw && Array.isArray(raw[g]) ? raw[g] : [];
    const ok = list.filter(l => {
      if (!l || typeof l.id !== 'string' || !/^[A-Za-z0-9_-]{1,16}$/.test(l.id)) return false;
      const titles = Array.isArray(l.titles) && l.titles.length ? l.titles : [l.title];
      if (!titles.every(okTitle)) return false;
      if (typeof l.body !== 'string' || !l.body.length || l.body.length > 130) return false;
      const all = titles.join(' ') + ' ' + l.body;
      return !/https?:|www\./i.test(all) && !/[–—]/.test(all);
    });
    const seen = new Set();
    out[g] = ok.filter(l => !seen.has(l.id) && seen.add(l.id)).map(l => {
      const o = { id: l.id, titles: Array.isArray(l.titles) && l.titles.length ? l.titles.slice() : [l.title], title: Array.isArray(l.titles) && l.titles.length ? l.titles[0] : l.title, body: l.body };
      if (Array.isArray(l.tags)) o.tags = l.tags.filter(t => typeof t === 'string' && /^[a-z0-9]{1,16}$/.test(t)).slice(0, 4);
      if (typeof l.set === 'string' && /^[a-z0-9]{1,16}$/.test(l.set)) o.set = l.set;
      if (Number.isInteger(l.rare) && l.rare >= 2 && l.rare <= 50) o.rare = l.rare;
      if (typeof l.only === 'string' && /^[a-z]{2,16}$/.test(l.only)) o.only = l.only;
      return o;
    });
    if (!out[g].length) out[g] = cleanCopy.norm(fallback[g]);
    for (const tag of (TAGGED[g] || [])) if (!out[g].some(l => (l.tags || []).includes(tag))) out[g] = out[g].concat(cleanCopy.norm(fallback[g].filter(l => (l.tags || []).includes(tag))));
  }
  return out;
}
cleanCopy.norm = list => list.map(l => ({ ...l, titles: l.titles || [l.title] }));
let _copyP = null;
async function loadCopy() {
  if (!_copyP) _copyP = (async () => {
    try {
      const r = await bfetch(COPY_URL, { cf: { cacheTtl: 300 } });
      if (!r.ok) throw new Error('copy ' + r.status);
      return cleanCopy(await r.json());
    } catch (e) { console.error('push copy not loaded, using the built-in lines:', e && e.message); return cleanCopy({}); }
  })();
  return _copyP;
}
// Picks a line that was not used among the last (pool size minus 1) sends to this person, so a line only comes back
// after the whole pool has been used. Stable for the same person, day and group. Lines that share a set with a line
// sent in the last 28 days are passed over while anything else is available (best effort when the pool is small).
// A line marked rare: N is only picked about 1 in N times.
export function pickFresh(pool, recent, seed, setLast, date) {
  const rareRoll = h3Hash(seed + 'r');
  let base = pool.filter(l => !l.rare || rareRoll % l.rare === 0);
  if (pool.some(l => l.rare) && base.some(l => l.rare)) base = base.filter(l => l.rare); // the rare one won the roll
  if (!base.length) base = pool;
  const skip = new Set((recent || []).slice(-(base.length - 1)));
  let list = base.filter(l => !skip.has(l.id));
  if (!list.length) list = base;
  if (setLast && date) {
    const clear = list.filter(l => !l.set || !setLast[l.set] || h3DaysBetween(setLast[l.set], date) >= 28);
    if (clear.length) list = clear;
    else { const age = l => (l.set && setLast[l.set]) ? h3DaysBetween(setLast[l.set], date) : 999; const best = Math.max(...list.map(age)); list = list.filter(l => age(l) === best); }
  }
  return list[h3Hash(seed) % list.length];
}
export function h3Fill(line, vars, seed) {
  const titles = line.titles || [line.title];
  const t = titles[h3Hash((seed || '') + 't') % titles.length];
  const f = s => s.replace(/\{(\w+)\}/g, (m, k) => vars[k] != null ? String(vars[k]) : m);
  return { title: f(t), body: f(line.body) };
}
// Morning pushes: a shuffled mix, different for each person. Each week (Monday to Sunday) every person gets 2 ritual days (C),
// plus 2 journaling days (J) if she tracks the Journal habit. The days are picked by a seeded shuffle, so they are stable for a person
// and a week but differ between people, and the same kind never lands on back-to-back days (a ritual next to a journaling day can happen for people who journal). Every other day
// is a habits line (A). A and J lines are skipped when nothing is open today.
// A stronger string hash than h3Hash (which must match the app), so shuffles do not follow the last character.
function h3Mix(str) { let h = 2166136261; for (const c of String(str)) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } h ^= h >>> 15; h = Math.imul(h, 2246822507); h ^= h >>> 13; h = Math.imul(h, 3266489909); h ^= h >>> 16; return h >>> 0; }
export function weekPlan(weekStart, person, hasJournal) {
  const kinds = hasJournal ? ['C', 'J', 'C', 'J'] : ['C', 'C'];
  let best = null, bestScore = Infinity;
  for (let attempt = 0; attempt < 40; attempt++) {
    const days = [0, 1, 2, 3, 4, 5, 6].map(d => [h3Mix(d + ':' + attempt + weekStart + person), d]).sort((x, y) => x[0] - y[0]).slice(0, kinds.length).map(x => x[1]).sort((x, y) => x - y);
    const ks = kinds.map((k, i) => [h3Mix(i + 'k' + attempt + weekStart + person), k]).sort((x, y) => x[0] - y[0]).map(x => x[1]);
    let score = 0; // same kind on back-to-back days is worst, any special days back to back is next
    for (let i = 1; i < days.length; i++) if (days[i] - days[i - 1] === 1) score += ks[i] === ks[i - 1] ? 10 : 1;
    if (score < bestScore) { bestScore = score; best = { days, ks }; }
    if (score === 0) break;
  }
  const plan = {};
  best.days.forEach((d, i) => { plan[d] = best.ks[i]; });
  return plan;
}
export function morningKind(date, person, hasJournal) {
  const wd = h3Wd(date);
  return weekPlan(h3Add(date, -wd), person, hasJournal)[wd] || 'A';
}
const isJournal = h => !!h && (h.preset === 'journal' || /journal/i.test(String(h.name || '')));
// Habit tags used by the ritual lines. A habit counts by its preset id, or by its name for custom habits.
const H3_TAG_RE = { move: /move|workout|exercise|run|walk|gym|yoga|lift/i, stretch: /stretch|mobility/i, outside: /outside|outdoor|sun|nature|walk/i,
  call: /call|phone a|friend/i, ootd: /ootd|outfit/i, cook: /cook|meal prep/i, tidy: /tidy|clean|declutter/i, meditate: /meditat|breath/i,
  journal: /journal/i, sleep: /sleep|bed\b|bedtime/i, noscroll: /scroll|phone/i, show: /morning show/i };
export function habitTags(habits) {
  const t = new Set();
  for (const h of habits) {
    if (h.preset && H3_TAG_RE[h.preset]) t.add(h.preset);
    for (const k of Object.keys(H3_TAG_RE)) if (H3_TAG_RE[k].test(String(h.name || ''))) t.add(k);
  }
  return t;
}
// About 2 of every 3 ritual lines match a habit she tracks (when she has a match). No line repeats within her last 8 rituals
// (about 4 weeks), unless the pool runs out. A line marked only: <tag> goes only to people who track that habit.
export function pickRitual(pool, recent, seed, tags) {
  pool = pool.filter(l => !l.only || tags.has(l.only));
  const skip = new Set((recent || []).slice(-Math.min(8, pool.length - 1)));
  const fresh = pool.filter(l => !skip.has(l.id));
  const base = fresh.length ? fresh : pool;
  const match = base.filter(l => (l.tags || []).some(t => tags.has(t)));
  const other = base.filter(l => !match.includes(l));
  const wantMatch = h3Hash(seed + 't') % 3 !== 0;
  const list = wantMatch && match.length ? match : (other.length ? other : base);
  return list[h3Hash(seed) % list.length];
}
function h3Date(now) { return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Los_Angeles', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now); }
function h3Add(k, n) { const d = new Date(k + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }
function h3Wd(k) { return (new Date(k + 'T12:00:00Z').getUTCDay() + 6) % 7; } // Monday is 0
function h3DaysBetween(a, b) { return Math.round((Date.parse(b + 'T12:00:00Z') - Date.parse(a + 'T12:00:00Z')) / 86400000); }
function h3Hash(s) { let h = 0; for (const c of String(s)) { h = (h * 31 + c.charCodeAt(0)) | 0; } return Math.abs(h); } // same as the app
function h3Pick(arr, seed) { return arr[h3Hash(seed) % arr.length]; } // same as the app's pick()
function h3Val(log, k, id) { return (log[k] && log[k][id]) || 0; }
function h3Done(h, log, k) { const v = h3Val(log, k, h.id); return h.type === 'number' ? v >= (h.target || 1) : v >= 1; }
const h3Counts = (h, k) => !!(h.days && h.days[h3Wd(k)]);
export function h3Due(h, log, date) {
  if (!h || h.archived) return false;
  if (h.paused && h.pausedAt && date >= h.pausedAt) return false;
  if (h3Done(h, log, date)) return false;
  const wd = h3Wd(date);
  if (h.perWeek) {
    const ws = h3Add(date, -wd);
    let c = 0;
    for (let i = 0; i <= wd; i++) if (h3Done(h, log, h3Add(ws, i))) c++;
    if (c >= h.perWeek) return false;
    return (h.perWeek - c) >= (7 - wd); // only nag when every remaining day is needed
  }
  return !!(h.days && h.days[wd]);
}
// Daily streak ending on day k, the same count as the app's streakAt() for daily habits.
export function h3StreakAt(h, log, k) {
  let n = 0, x = k, g = 0;
  while (g++ < 800) {
    if (h.createdDay && x < h.createdDay) break;
    if (!h3Counts(h, x)) { x = h3Add(x, -1); continue; }
    if (h3Done(h, log, x)) n++; else break;
    x = h3Add(x, -1);
  }
  return n;
}
export function h3Winner(votes, weekKey) {
  const t = {};
  for (const v of Object.values(votes)) t[v] = (t[v] || 0) + 1;
  const ids = Object.keys(t);
  if (!ids.length) return null;
  const max = Math.max(...ids.map(i => t[i]));
  const tied = ids.filter(i => t[i] === max).sort();
  return tied[h3Hash(weekKey) % tied.length];
}
// The coven habit running in a week: last week's winner, else the one before, else the first option (same as the app).
function h3CovenHabit(votesBy, wk) {
  for (let w = wk, g = 0; g < 60; g++, w = h3Add(w, -7)) {
    const v = {}; for (const p of PEOPLE) { const x = (votesBy[p] || {})[w]; if (x) v[p] = x; }
    const win = h3Winner(v, w); if (win) return win;
    if (w <= h3Add(SEASON_START, -h3Wd(SEASON_START))) break;
  }
  return 'phone';
}
// What a person finished today that the coven can see: a shared habit, the coven habit or the moon spell. Private habits never count.
export function h3Showed(habits, log, k, votesBy) {
  const l = log[k] || {};
  for (const h of habits) if (h.shared && !h.archived && h3Done(h, log, k)) return h.name;
  for (const id of Object.keys(l)) {
    if (!l[id]) continue;
    if (id.startsWith('_coven_')) return H3_VOTE_NAMES[h3CovenHabit(votesBy, id.slice(7))] || 'the coven habit';
    if (id.startsWith('_spell_')) return 'the moon spell';
  }
  return null;
}
function anyDone(log, k) { const l = log[k] || {}; return Object.keys(l).some(id => !!l[id]); }

// Reads every h3 record in two calls (the photos and avatars are skipped: they are big and never needed here) and
// fills the per-run cache, so the jobs below never read inside a per-person loop. Returns false if it failed, and the
// social job then sits the run out rather than spending the call budget on single reads.
async function prefetchH3() {
  try {
    for (const [a, b] of [['h3-', 'h3-pha'], ['h3-pr', 'h3-~']]) {
      const url = DB.replace(/\/$/, '') + '.json?orderBy=%22%24key%22&startAt=' + encodeURIComponent(JSON.stringify(a)) + '&endAt=' + encodeURIComponent(JSON.stringify(b));
      const r = await bfetch(url);
      if (!r.ok) throw new Error('prefetch ' + r.status);
      const all = (await r.json()) || {};
      for (const [k, v] of Object.entries(all)) {
        let out = null;
        if (typeof v === 'string') { try { out = JSON.parse(v); } catch (e) { out = null; } }
        _readCache.set(k, out);
      }
    }
    for (const p of PEOPLE) for (const kind of ['habits', 'log', 'prof', 'qa', 'rx', 'cur', 'shr', 'vote', 'sched']) if (!_readCache.has('h3-' + kind + '-' + p)) _readCache.set('h3-' + kind + '-' + p, null);
    return true;
  } catch (e) { console.error('h3 prefetch failed', e && e.message); return false; }
}

// Who a Tea post belongs to, and what to call it in a reaction push. Ids are the app's feed ids (buildFeed).
export function h3PostInfo(id, habitsBy) {
  const s = String(id), parts = s.split(':');
  const own = p => PEOPLE.includes(p) ? p : null;
  if (parts[0] === 'f') { const p = own(parts[1]); const h = p && (habitsBy[p] || {})[parts[2]]; return p ? { owner: p, noun: h && h.name ? h.name : 'habit' } : null; }
  if (parts[0] === 'sh') return own(parts[1]) ? { owner: parts[1], noun: 'shared read' } : null;
  if (parts[0] === 'pic') return own(parts[1]) ? { owner: parts[1], noun: 'photo' } : null;
  if (parts[0] === 'cur') return own(parts[1]) ? { owner: parts[1], noun: 'Currently update' } : null;
  if (parts[0] === 'sp') { const p = PEOPLE.find(x => s.startsWith('sp:' + x)); return p ? { owner: p, noun: 'moon spell' } : null; }
  return null; // the brew, the vote and group habits have no single owner
}
const RX_GLYPH = { heart: '♡', spell: '✦', moon: '☾' };

export async function habitsRun(env, now, opts = {}) {
  if (opts.fresh) resetRun(); // tests only. In production it shares the call counter of the run() just before it.
  const date = h3Date(now);
  const ptHour = pacificHour(now);
  const dow = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', weekday: 'short' }).format(now);
  const sent = [];
  const fetched = await prefetchH3();
  let st;
  try { st = (await readKey(H3_STATE_KEY)) || {}; } catch (e) { console.error('h3 state read failed, sending nothing:', e && e.message); return { sent }; }
  st.sched = st.sched || {};
  let changed = false;
  let token = null;
  const prefsOf = async p => Object.assign({ activity: true, nudge: true, morning: true }, (await readKey('recal-notif-prefs:' + p)) || {});
  const habitsOf = async p => Object.values((await readKey('h3-habits-' + p)) || {}).filter(h => h && !h.archived);
  const logOf = async p => (await readKey('h3-log-' + p)) || {};
  const schedOf = async p => (await readKey('h3-sched-' + p)) || {};
  const skyDay = async p => { const s = await schedOf(p); return s.sky && s.sky[date] ? s.sky[date] : null; };
  const send = async (list) => { // list of {person, msg, tok}
    for (const { person, msg, tok, job } of list) {
      try {
        if (!token) token = await getAccessToken(env);
        await sendPush(env, token, tok, msg);
        sent.push({ owner: person, job, ...msg });
      } catch (e) { console.error(job, 'send failed for', person, e && e.message); }
    }
  };
  const saveState = async () => { await writeKey(H3_STATE_KEY, st, true); changed = false; };
  const setLastOf = p => { st.setLast = st.setLast || {}; return st.setLast[p] = st.setLast[p] || {}; };
  const noteSet = (p, line) => { if (line.set) setLastOf(p)[line.set] = date; };

  const jobs = [];
  if (ptHour >= 8 && ptHour < 12) jobs.push('h3sky', 'h3morning');
  if (ptHour >= 12 && ptHour < 22) jobs.push('h3brew');
  if (ptHour >= 19 && ptHour < 22) jobs.push('h3nudge');
  if (H3_JOBS_ON.vote && dow === 'Sun' && ptHour >= 18 && ptHour < 22) jobs.push('h3vote');
  if (H3_JOBS_ON.result && dow === 'Mon' && ptHour >= 8 && ptHour < 12) jobs.push('h3result');
  for (const job of jobs) {
    await guard(job, async () => {
      let rec = st.sched[job];
      if (!rec || rec.date !== date) { rec = st.sched[job] = { date, done: [] }; changed = true; }
      if (PEOPLE.every(p => rec.done.includes(p))) return;
      const outbox = [];
      let winner = null;
      if (job === 'h3result') {
        const votes = {};
        for (const p of PEOPLE) { const v = (await readKey('h3-vote-' + p)) || {}; if (v[date]) votes[p] = v[date]; }
        winner = h3Winner(votes, date);
        if (!winner) { console.log('Nobody voted for the week of', date, ', no result push.'); return; }
      }
      let brewQ = null;
      if (job === 'h3brew') {
        for (const p of PEOPLE) { const s = await schedOf(p); if (s.brew && s.brew[date]) { brewQ = s.brew[date]; break; } }
        if (!brewQ) { console.log('No brew question known for', date, ', no brew push.'); return; }
      }
      for (const person of PEOPLE) {
        if (rec.done.includes(person)) continue;
        const finish = () => { rec.done.push(person); changed = true; };
        const prefs = await prefsOf(person);
        const prefOn = job === 'h3nudge' ? prefs.nudge : (job === 'h3morning' || job === 'h3brew' || job === 'h3sky') ? prefs.morning : prefs.activity;
        if (!prefOn) { finish(); continue; }
        const habits = await habitsOf(person);
        if (!habits.length) { finish(); continue; } // not using the new app
        const log = await logOf(person);
        const copy = await loadCopy();
        st.morn = st.morn || {};
        const mem = st.morn[person] = st.morn[person] || {};
        const take = (g, line) => { mem[g] = (mem[g] || []).concat(line.id).slice(-40); noteSet(person, line); changed = true; };
        let msg;
        if (job === 'h3sky') {
          const sky = await skyDay(person);
          if (!sky || !sky.h) { finish(); continue; }
          const line = pickFresh(copy.B, mem.B, date + person + 'B', setLastOf(person), date);
          take('B', line);
          msg = h3Fill(line, { name: person, sky: trunc(sky.h, 128) }, date + person);
        } else if (job === 'h3morning') {
          if (ptHour < 9 && await skyDay(person)) continue; // her sky push goes at 8, this one waits until 9
          // Comeback: nothing done yesterday or the day before, she has done something before, and no comeback since.
          const y1 = h3Add(date, -1), y2 = h3Add(date, -2);
          const lastDone = Object.keys(log).filter(k => k < date && anyDone(log, k)).sort().pop();
          st.come = st.come || {};
          if (lastDone && lastDone < y2 && !anyDone(log, y1) && !anyDone(log, y2) && !anyDone(log, date) && !(st.come[person] && st.come[person] > lastDone)) {
            const line = pickFresh(copy.CB, mem.CB, date + person + 'CB');
            take('CB', line);
            st.come[person] = date;
            msg = h3Fill(line, { name: person }, date + person);
          } else {
            const anyOpen = habits.some(h => h3Due(h, log, date));
            const kind = morningKind(date, person, habits.some(isJournal));
            if (kind !== 'C' && !anyOpen) { finish(); continue; } // A and J lines need something still open
            const pool = copy[kind];
            const line = kind === 'C' ? pickRitual(pool, mem[kind], date + person + kind, habitTags(habits)) : pickFresh(pool, mem[kind], date + person + kind, setLastOf(person), date);
            take(kind, line);
            msg = h3Fill(line, { name: person }, date + person);
          }
        } else if (job === 'h3brew') {
          const qa = (await readKey('h3-qa-' + person)) || {};
          if (qa[date]) { finish(); continue; }
          msg = h3Fill(copy.BT[h3Hash(date) % copy.BT.length], { name: person, q: brewQ }, date + person);
        } else if (job === 'h3nudge') {
          const due = habits.filter(h => h3Due(h, log, date));
          if (!due.length) { finish(); continue; }
          const n = Math.max(0, ...due.filter(h => !h.perWeek).map(h => h3StreakAt(h, log, h3Add(date, -1))));
          st.eve = st.eve || {};
          if (n >= 3) {
            const line = pickFresh(copy.ST, mem.ST, date + person + 'ST');
            take('ST', line);
            msg = h3Fill(line, { name: person, n, n1: n + 1 }, date + person);
          } else {
            const recent = st.eve[person] || [];
            const line = pickFresh(copy.E, recent, date + person, setLastOf(person), date);
            st.eve[person] = recent.concat(line.id).slice(-40);
            noteSet(person, line);
            changed = true;
            msg = h3Fill(line, { name: person }, date + person);
          }
        } else if (job === 'h3vote') {
          const nextWeek = h3Add(date, 7 - h3Wd(date));
          const v = (await readKey('h3-vote-' + person)) || {};
          if (v[nextWeek]) { finish(); continue; }
          const line = pickFresh(copy.V, mem.V, date + person + 'V');
          take('V', line);
          msg = h3Fill(line, { name: person }, date + person);
        } else {
          const line = pickFresh(copy.R, mem.R, date + 'R');
          take('R', line);
          msg = h3Fill(line, { name: person, habit: H3_VOTE_NAMES[winner] || winner }, date);
        }
        const tok = await readRaw('recal-fcm-token:' + person);
        if (!tok) { finish(); continue; }
        finish();
        outbox.push({ person, msg, tok, job });
      }
      if (!outbox.length) return;
      try { await saveState(); } catch (e) {
        for (const o of outbox) rec.done = rec.done.filter(x => x !== o.person);
        console.error(job, 'could not save state, not sending:', e && e.message);
        return;
      }
      await send(outbox);
    });
  }

  if (fetched) await guard('h3social', async () => {
    const r = await socialEvents(st, date, now, prefsOf);
    if (r.changedOnly) { changed = true; return; }
    if (!r.outbox.length) { if (r.changed) changed = true; return; }
    try { await saveState(); } catch (e) { console.error('social could not save state, not sending:', e && e.message); r.rollback(); return; }
    await send(r.outbox);
  });

  if (changed) { try { await saveState(); } catch (e) { console.error('h3 state save failed', e && e.message); } }
  return { sent };
}

// Finds what happened since the last run and builds the pushes. State lives in st.soc. The very first run only
// records what already exists, so nobody gets a flood of old news.
async function socialEvents(st, date, now, prefsOf) {
  const copy = await loadCopy();
  const habitsBy = {}, logBy = {}, votesBy = {}, rxBy = {}, qaBy = {}, curBy = {}, shrBy = {};
  for (const p of PEOPLE) {
    habitsBy[p] = (await readKey('h3-habits-' + p)) || {};
    logBy[p] = (await readKey('h3-log-' + p)) || {};
    votesBy[p] = (await readKey('h3-vote-' + p)) || {};
    rxBy[p] = (await readKey('h3-rx-' + p)) || {};
    qaBy[p] = (await readKey('h3-qa-' + p)) || {};
    curBy[p] = (await readKey('h3-cur-' + p)) || {};
    shrBy[p] = (await readKey('h3-shr-' + p));
    if (!Array.isArray(shrBy[p])) shrBy[p] = [];
  }
  const active = p => Object.values(habitsBy[p]).some(h => h && !h.archived);
  const list = p => Object.values(habitsBy[p]).filter(h => h && !h.archived);
  const before = JSON.stringify(st.soc || null);
  const soc = st.soc = st.soc || {};
  const first = !soc.init;
  // Live reactions as reactor|post|kind.
  const liveRx = new Set();
  for (const r of PEOPLE) for (const [post, ks] of Object.entries(rxBy[r] || {})) for (const [k, on] of Object.entries(ks || {})) if (on && RX_GLYPH[k]) liveRx.add(r + '|' + post + '|' + k);
  const latestAt = arr => arr.reduce((m, x) => (x && x.at && String(x.at) > m ? String(x.at) : m), '');
  const groupIds = () => { const s = []; for (const p of PEOPLE) for (const h of list(p)) if (h.shared && h.groupOwner === p && h.groupId === h.id) s.push(h.id); return s; };
  if (first) {
    soc.init = true;
    soc.rxSeen = Array.from(liveRx);
    soc.rxPend = {};
    soc.qa = { date, done: PEOPLE.filter(p => qaBy[p][date]) };
    soc.day = { date, in: PEOPLE.filter(p => h3Showed(list(p), logBy[p], date, votesBy)), all: PEOPLE.every(p => h3Showed(list(p), logBy[p], date, votesBy)) };
    soc.mile = { date, done: [] };
    for (const p of PEOPLE) for (const h of list(p)) if (!h.perWeek && h3Done(h, logBy[p], date)) soc.mile.done.push(p + '|' + h.id);
    soc.curAt = {}; soc.shrAt = {};
    for (const p of PEOPLE) { soc.curAt[p] = latestAt(curBy[p].hist || []); soc.shrAt[p] = latestAt(shrBy[p]); }
    soc.grp = groupIds();
    console.log('h3 social: first run, marked what exists as seen.');
    return { outbox: [], changedOnly: true };
  }
  const events = []; // {to: [people], msg, key}
  const others = p => PEOPLE.filter(x => x !== p && active(x));
  const mem = st.socMem = st.socMem || {};
  const pickG = (g, seed, filter) => { const pool = filter ? copy[g].filter(filter) : copy[g]; const line = pickFresh(pool.length ? pool : copy[g], mem[g], seed); mem[g] = (mem[g] || []).concat(line.id).slice(-40); return line; };

  // Day rollover for the per-day records.
  if (!soc.day || soc.day.date !== date) soc.day = { date, in: [], all: false };
  if (!soc.qa || soc.qa.date !== date) soc.qa = { date, done: [] };
  if (!soc.mile || soc.mile.date !== date) soc.mile = { date, done: [] };

  // Friend showed up, and all four showed up.
  const showedNow = {};
  for (const p of PEOPLE) showedNow[p] = h3Showed(list(p), logBy[p], date, votesBy);
  const allNow = PEOPLE.every(p => showedNow[p]);
  if (allNow && !soc.day.all) {
    soc.day.all = true;
    const line = pickG('ALL', date + 'ALL');
    events.push({ to: PEOPLE.filter(active), msg: h3Fill(line, {}, date), job: 'all' });
  }
  for (const p of PEOPLE) {
    if (!showedNow[p] || soc.day.in.includes(p)) continue;
    soc.day.in.push(p);
    if (allNow && events.some(e => e.job === 'all')) continue; // the all-four push covers the last one in
    const line = pickG('IN', date + p + 'IN');
    events.push({ to: others(p), msg: h3Fill(line, { who: p, habit: showedNow[p] }, date + p), job: 'in', activity: true });
  }

  // Milestones: private to her for any daily habit, plus the coven for shared ones (same line as the Tea post).
  for (const p of PEOPLE) for (const h of list(p)) {
    if (h.perWeek || !h3Done(h, logBy[p], date)) continue;
    const key = p + '|' + h.id;
    if (soc.mile.done.includes(key)) continue;
    soc.mile.done.push(key);
    const n = h3StreakAt(h, logBy[p], date);
    if (![7, 14, 30].includes(n)) continue;
    const mp = pickG('MP', date + key, l => (l.tags || []).includes('d' + n));
    events.push({ to: [p], msg: h3Fill(mp, { name: p, habit: h.name, n }, date + key), job: 'mile' });
    if (h.shared) {
      const cm = copy.CM.filter(l => (l.tags || []).includes('d' + n));
      const line = h3Pick(cm, p + h.id + n); // same pick as the app's feed
      events.push({ to: others(p), msg: h3Fill(line, { who: p, habit: h.name, n }, date + key), job: 'covenmile', activity: true, target: 'post:' + safeKey('f:' + p + ':' + h.id + ':' + date) });
    }
  }

  // Brew answers: to everyone who answered earlier today.
  for (const p of PEOPLE) {
    const a = qaBy[p][date];
    if (!a || soc.qa.done.includes(p)) continue;
    const earlier = soc.qa.done.filter(x => x !== p && active(x));
    soc.qa.done.push(p);
    if (!earlier.length) continue;
    const line = pickG('QA', date + p + 'QA');
    events.push({ to: earlier, msg: h3Fill(line, { who: p, answer: trunc(a.t, 120) }, date + p), job: 'brewanswer', activity: true });
  }

  // Shared reads and Currently.
  soc.shrAt = soc.shrAt || {}; soc.curAt = soc.curAt || {};
  for (const p of PEOPLE) {
    const fresh = shrBy[p].filter(s => s && s.at && String(s.at) > (soc.shrAt[p] || ''));
    if (fresh.length) {
      soc.shrAt[p] = latestAt(fresh.concat([{ at: soc.shrAt[p] }]));
      const s = fresh.sort((a, b) => String(a.at).localeCompare(String(b.at)))[fresh.length - 1];
      const site = domainOf(String(s.u || ''));
      const label = trunc(s.l, 120) || (site ? `From ${site}.` : 'Come take a look.');
      const line = pickG('SR', p + s.id);
      events.push({ to: others(p), msg: h3Fill(line, { who: p, label }, p + s.id), job: 'share', activity: true, target: 'post:' + safeKey('sh:' + p + ':' + s.id) });
    }
    const hist = (curBy[p].hist || []).filter(h => h && h.at && String(h.at) > (soc.curAt[p] || ''));
    if (hist.length) {
      soc.curAt[p] = latestAt(hist.concat([{ at: soc.curAt[p] }]));
      const h = hist.sort((a, b) => String(a.at).localeCompare(String(b.at)))[hist.length - 1];
      const pool = copy.CU.filter(l => (l.tags || []).includes(h.f));
      if (pool.length && h.t) {
        const id = 'cur:' + p + ':' + h.at;
        const line = h3Pick(pool, id); // same pick as the app's feed
        events.push({ to: others(p), msg: h3Fill(line, { who: p, value: trunc(h.t, 120) }, id), job: 'currently', activity: true, target: 'post:' + safeKey(id) });
      }
    }
  }

  // New group habits.
  soc.grp = soc.grp || [];
  for (const p of PEOPLE) for (const h of list(p)) {
    if (!(h.shared && h.groupOwner === p && h.groupId === h.id) || soc.grp.includes(h.id)) continue;
    soc.grp.push(h.id);
    const line = h3Pick(copy.GH, h.id); // same pick as the app's feed
    events.push({ to: others(p), msg: h3Fill(line, { who: p, habit: h.name }, h.id), job: 'group', activity: true });
  }

  // Reactions: held about a minute (a quick tap and untap never sends), then one push per post owner.
  const seen = new Set(soc.rxSeen || []);
  soc.rxPend = soc.rxPend || {};
  for (const id of Object.keys(soc.rxPend)) if (!liveRx.has(id)) delete soc.rxPend[id];
  const nowMs = now.getTime();
  const ready = [];
  for (const id of liveRx) {
    if (seen.has(id)) continue;
    if (!soc.rxPend[id]) { soc.rxPend[id] = nowMs; continue; }
    if (nowMs - soc.rxPend[id] >= 55000) ready.push(id);
  }
  const byOwner = {};
  for (const id of ready) {
    delete soc.rxPend[id]; seen.add(id);
    const [reactor, post, k] = [id.split('|')[0], id.split('|').slice(1, -1).join('|'), id.split('|').slice(-1)[0]];
    const info = h3PostInfo(post, habitsBy);
    if (!info || info.owner === reactor || !active(info.owner)) continue;
    (byOwner[info.owner] = byOwner[info.owner] || []).push({ reactor, post, k, noun: info.noun });
  }
  soc.rxSeen = Array.from(seen).filter(id => liveRx.has(id));
  for (const [owner, items] of Object.entries(byOwner)) {
    const posts = uniq(items.map(i => i.post));
    const target = posts.length === 1 ? 'post:' + safeKey(posts[0]) : 'tea';
    let msg;
    if (items.length === 1) {
      const it = items[0];
      const line = pickG('RX', date + owner + it.post + it.k, l => (l.tags || []).includes(it.k));
      msg = h3Fill(line, { who: it.reactor, post: it.noun }, it.post + it.k);
    } else { // Round 2 wording for several at once
      const what = posts.length === 1 ? 'your ' + items[0].noun : `${posts.length} of your posts`;
      msg = { title: `${joinNames(uniq(items.map(i => i.reactor)))} reacted ${uniq(items.map(i => RX_GLYPH[i.k])).join(' ')}`, body: `On ${what}. The coven sees you, and it’s being weird about how good you are.` };
    }
    events.push({ to: [owner], msg, job: 'reaction', activity: true, target });
  }

  // Build the outbox: one push per person per event, respecting her Coven activity switch and the call budget.
  const outbox = [];
  for (const e of events) for (const person of uniq(e.to)) {
    if (!active(person)) continue;
    if (e.activity && !(await prefsOf(person)).activity) continue;
    const tok = await readRaw('recal-fcm-token:' + person);
    if (!tok) continue;
    outbox.push({ person, tok, job: 'h3' + e.job, msg: e.target ? { ...e.msg, target: e.target } : e.msg });
  }
  const room = CALL_LIMIT - _calls - 3; // token, state save, a little spare
  if (outbox.length > room) { console.error('h3 social: too many pushes for one run, sending', Math.max(0, room), 'of', outbox.length); outbox.length = Math.max(0, room); }
  const snapshot = before;
  return { outbox, changed: JSON.stringify(st.soc) !== before, rollback: () => { st.soc = snapshot === 'null' ? undefined : JSON.parse(snapshot); } };
}

// ---------- Google auth + FCM (data-only, same as the morning push) ----------
function b64url(bytes) {
  let s = typeof bytes === 'string' ? btoa(bytes) : btoa(String.fromCharCode(...new Uint8Array(bytes)));
  return s.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
async function getAccessToken(env) {
  if (!_tokenP) _tokenP = fetchAccessToken(env).catch(e => { _tokenP = null; throw e; });
  return _tokenP;
}
async function fetchAccessToken(env) {
  const sa = JSON.parse(env.FIREBASE_SERVICE_ACCOUNT);
  const pem = sa.private_key.replace(/-----[^-]+-----/g, '').replace(/\s+/g, '');
  const der = Uint8Array.from(atob(pem), c => c.charCodeAt(0));
  const key = await crypto.subtle.importKey('pkcs8', der, { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['sign']);
  const iat = Math.floor(Date.now() / 1000);
  const header = b64url(JSON.stringify({ alg: 'RS256', typ: 'JWT' }));
  const claims = b64url(JSON.stringify({
    iss: sa.client_email, scope: 'https://www.googleapis.com/auth/firebase.messaging',
    aud: 'https://oauth2.googleapis.com/token', iat, exp: iat + 3600
  }));
  const sig = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', key, new TextEncoder().encode(header + '.' + claims));
  const jwt = header + '.' + claims + '.' + b64url(sig);
  const r = await bfetch('https://oauth2.googleapis.com/token', {
    method: 'POST', headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: 'grant_type=' + encodeURIComponent('urn:ietf:params:oauth:grant-type:jwt-bearer') + '&assertion=' + jwt
  });
  if (!r.ok) throw new Error('token ' + r.status + ' ' + (await r.text()).slice(0, 200));
  return (await r.json()).access_token;
}
async function sendPush(env, accessToken, deviceToken, msg) {
  const sa = JSON.parse(env.FIREBASE_SERVICE_ACCOUNT);
  const r = await bfetch(`https://fcm.googleapis.com/v1/projects/${sa.project_id}/messages:send`, {
    method: 'POST',
    headers: { 'authorization': 'Bearer ' + accessToken, 'content-type': 'application/json' },
    body: JSON.stringify({ message: { token: deviceToken, data: { title: msg.title, body: msg.body, ...(msg.target ? { target: String(msg.target) } : {}) } } })
  });
  if (!r.ok) throw new Error('fcm ' + r.status + ' ' + (await r.text()).slice(0, 200));
}
