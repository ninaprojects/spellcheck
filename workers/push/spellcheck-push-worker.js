// Spell Check reaction pushes.
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
  if (item.type === 'rollself') return { title: 'You\u2019re on a roll \u2726', body: ROLL_SELF[item.streak] };
  return { title: `${item.actor} is on a roll \u2726`, body: ROLL_OTHERS[item.streak] };
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
export function composeComments(items) {
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

export function composeActivity(items, castTodayCount) {
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
    ctx.waitUntil(run(env, new Date()).catch(e => console.error('run failed', e && e.stack || e)));
  },
  async fetch() {
    return new Response('Spell Check push worker. Nothing to see here.', { status: 200 });
  }
};

// ---------- Firebase REST (values are stored as JSON strings) ----------
async function readKey(key) {
  const r = await fetch(DB + key + '.json');
  if (!r.ok) throw new Error('read ' + key + ' ' + r.status);
  const v = await r.json();
  if (typeof v !== 'string') return null;
  try { return JSON.parse(v); } catch (e) { return null; }
}
async function writeKey(key, obj) {
  const r = await fetch(DB + key + '.json', { method: 'PUT', body: JSON.stringify(JSON.stringify(obj)) });
  if (!r.ok) throw new Error('write ' + key + ' ' + r.status);
}
async function readRaw(key) {
  const r = await fetch(DB + key + '.json');
  if (!r.ok) return null;
  const v = await r.json();
  return typeof v === 'string' ? v : null;
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

function pacificHour(now) {
  return Number(new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', hour: 'numeric', hourCycle: 'h23' }).format(now));
}
// Quiet hours are off. To bring them back, e.g. midnight to 7am Pacific:
//   return h >= 0 && h < 7;
const QUIET_HOURS_ON = false;
function isQuiet(now) { if (!QUIET_HOURS_ON) return false; const h = pacificHour(now); return h >= 22 || h < 8; }

export function composeMessage(items) {
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

export async function run(env, now) {
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
      const targets = e.type === 'rollself' ? [e.actor] : PEOPLE.filter(r => r !== e.actor);
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

  const sent = [];
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
      const rest = items.filter(i => !isRoll(i) && !(i.type === 'cast' && rollActors.has(i.actor)));
      const batches = rollItems.slice(0, 2).map(i => ({ items: [i], msg: rollMessage(i) }));
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
    }
  }

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
      } catch (e) {
        console.error('Comment send failed for', r, e && e.message);
        items.forEach(i => { i.tries = (i.tries || 0) + 1; });
        pendingComments[r] = items.filter(i => i.tries < 5);
        if (!pendingComments[r].length) delete pendingComments[r];
        changed = true;
      }
    }
  }

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
    }
  }

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
    for (const job of ['morning', 'nudge', 'recap']) {
      const inWindow = job === 'morning' ? (ptHour >= 8 && ptHour < 12)
        : job === 'nudge' ? (ptHour >= 19 && ptHour < 22)
        : (isSunday && today >= 7 && ptHour >= 18 && ptHour < 22); // Sunday recap, from 6pm
      if (!inWindow) continue;
      let rec = state.sched[job];
      if (!rec || rec.day !== today) { rec = state.sched[job] = { day: today, done: [], tries: {} }; changed = true; }
      for (const person of PEOPLE) {
        if (rec.done.includes(person)) continue;
        const finish = () => { rec.done.push(person); changed = true; };
        if (!(await prefsFor(person))[job === 'recap' ? 'activity' : job]) { console.log(person, 'turned', job, 'off, skipping.'); finish(); continue; }
        let msg;
        if (job === 'morning') {
          msg = { title: `\u2728 Day ${today} of Spells, Witches`, body: SPECIAL[today] || AFFIRMATIONS[today] || `Day ${today} is live. Go check in.` };
        } else if (job === 'recap') {
          msg = recapMessage(weekStats(data, reactions, today));
        } else {
          const dd = data[person] && data[person].days ? data[person].days[today] : null;
          if (isCast(dd)) { console.log(person, 'already cast Day', today, ', no nudge.'); finish(); continue; }
          const othersCast = PEOPLE.filter(p => p !== person && castOn(p, today)).length;
          msg = nudgeMessage(today, 2 - castCount(dd), othersCast, streak);
        }
        const token = await readRaw('recal-fcm-token:' + person);
        if (!token) { console.log('No device token for', person, ', skipping', job); finish(); continue; }
        try {
          if (!schedToken) schedToken = await getAccessToken(env);
          await sendPush(env, schedToken, token, msg);
          sent.push({ owner: person, job, ...msg });
          console.log(job, 'to', person, '|', msg.title);
          finish();
        } catch (e) {
          rec.tries[person] = (rec.tries[person] || 0) + 1;
          console.error(job, 'send failed for', person, '(try', rec.tries[person] + '):', e && e.message);
          if (rec.tries[person] >= 5) finish(); else changed = true;
        }
      }
    }
  }

  if (changed) {
    // Keep "seen" from growing forever: only ids that still exist matter.
    const trimmed = Array.from(seen).filter(id => live.has(id));
    await writeKey(STATE_KEY, { initialized: true, seen: trimmed, pending, activityInit: !!state.activityInit, activityV: state.activityV || 1, activitySeen: state.activitySeen || [], pendingActivity, commentsInit: !!state.commentsInit, commentsSeen: state.commentsSeen || [], pendingComments, sched: state.sched || {} });
  }
  return { sent, quiet };
}

// ---------- Google auth + FCM (data-only, same as the morning push) ----------
function b64url(bytes) {
  let s = typeof bytes === 'string' ? btoa(bytes) : btoa(String.fromCharCode(...new Uint8Array(bytes)));
  return s.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
async function getAccessToken(env) {
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
  const r = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST', headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: 'grant_type=' + encodeURIComponent('urn:ietf:params:oauth:grant-type:jwt-bearer') + '&assertion=' + jwt
  });
  if (!r.ok) throw new Error('token ' + r.status + ' ' + (await r.text()).slice(0, 200));
  return (await r.json()).access_token;
}
async function sendPush(env, accessToken, deviceToken, msg) {
  const sa = JSON.parse(env.FIREBASE_SERVICE_ACCOUNT);
  const r = await fetch(`https://fcm.googleapis.com/v1/projects/${sa.project_id}/messages:send`, {
    method: 'POST',
    headers: { 'authorization': 'Bearer ' + accessToken, 'content-type': 'application/json' },
    body: JSON.stringify({ message: { token: deviceToken, data: { title: msg.title, body: msg.body } } })
  });
  if (!r.ok) throw new Error('fcm ' + r.status + ' ' + (await r.text()).slice(0, 200));
}
