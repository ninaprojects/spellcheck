// Tests the push Worker end to end with an in-memory Firebase and a fake notification service.
// Run:  node tests/worker_test.mjs
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = process.env.SPELLCHECK_WORKER || path.join(HERE, '..', 'workers', 'push', 'spellcheck-push-worker.js');
const tmp = path.join(os.tmpdir(), 'spellcheck-push-under-test.mjs');
fs.writeFileSync(tmp, fs.readFileSync(SRC, 'utf8'));
const W = await import(pathToFileURL(tmp).href + '?t=' + Date.now());

const PEOPLE = ['Nina', 'Kellye', 'Lauren', 'Carolina'];
const { privateKey } = crypto.generateKeyPairSync('rsa', { modulusLength: 2048, privateKeyEncoding: { type: 'pkcs8', format: 'pem' }, publicKeyEncoding: { type: 'spki', format: 'pem' } });
const env = { FIREBASE_SERVICE_ACCOUNT: JSON.stringify({ private_key: privateKey, client_email: 'test@example.iam', project_id: 'test-project' }) };

let results = [];
function check(name, ok, detail) { results.push(!!ok); console.log((ok ? 'PASS ' : 'FAIL ') + name + (!ok && detail !== undefined ? '  [' + JSON.stringify(detail) + ']' : '')); }

// ---- fake world ----
let store, pushes;
function resetWorld() {
  store = {}; pushes = [];
  for (const p of PEOPLE) store['recal-fcm-token:' + p] = 'token-' + p;
}
globalThis.fetch = async (url, opts = {}) => {
  url = String(url);
  if (url.startsWith('https://cast-and-check-default-rtdb.firebaseio.com/recalData/')) {
    const key = decodeURIComponent(url.split('/recalData/')[1].replace(/\.json$/, ''));
    if ((opts.method || 'GET') === 'PUT') { store[key] = JSON.parse(opts.body); return new Response('null', { status: 200 }); }
    return new Response(JSON.stringify(key in store ? store[key] : null), { status: 200 });
  }
  if (url.startsWith('https://oauth2.googleapis.com/token')) return new Response(JSON.stringify({ access_token: 'fake-access-token' }), { status: 200 });
  if (url.includes('fcm.googleapis.com')) {
    const m = JSON.parse(opts.body).message;
    pushes.push({ to: m.token.replace('token-', ''), title: m.data.title, body: m.data.body, target: m.data.target });
    return new Response('{}', { status: 200 });
  }
  return new Response('not mocked: ' + url, { status: 500 });
};
const put = (key, obj) => { store[key] = JSON.stringify(obj); };
const putPerson = (p, data) => put('r2:recal:' + p, data);
const cast = (extra = {}) => Object.assign({ journaled: true, noPhone: true, waterOz: 0 }, extra);
const person = (days = {}, weeks = {}) => ({ days, weeks });
const at = (iso) => new Date(iso);
const sentTo = (who) => pushes.filter(x => x.to === who);
async function runAt(iso) { pushes = []; return W.run(env, at(iso)); }
// When several jobs are due in the same minute the Worker spreads them over a few minutes to stay under the
// call limit. This runs the same moment and the next minutes, collecting everything that went out.
async function runSettled(iso, minutes = 4) {
  const all = [];
  for (let i = 0; i < minutes; i++) { await runAt(plus(iso, i * 60)); all.push(...pushes); }
  pushes = all;
}
// The Worker marks what already exists as seen over its first two runs, silently. Do both before changing the data.
async function baseline() { await runAt(D5); await runAt(plus(D5, 5)); pushes = []; }

// 3:30pm Pacific on Mon Oct 5 2026 = Day 5, outside the morning and nudge windows
const D5 = '2026-10-05T22:30:00Z';
const plus = (iso, sec) => new Date(new Date(iso).getTime() + sec * 1000).toISOString();

// ===== exact copy =====
{
  check('reaction copy: heart', W.composeMessage([{ reactor: 'Kellye', glyph: '\u2661', eventKey: 'photo:Nina:5', text: 'your Day 5 photo' }]).title === 'Kellye\u2019s heart is swelling \u2661');
  check('reaction copy: sparkle body', W.composeMessage([{ reactor: 'Kellye', glyph: '\u2726', eventKey: 'photo:Nina:5', text: 'your Day 5 photo' }]).body === 'On your Day 5 photo. A bow is customary. Several bows are encouraged.');
  check('reaction copy: moon title', W.composeMessage([{ reactor: 'Kellye', glyph: '\u263E', eventKey: 'cast:Nina:5', text: 'your Day 5 spell' }]).title === 'Kellye sent you calm tides \u263E');
  const note = W.composeMessage([{ reactor: 'Kellye', glyph: '\u2726', eventKey: 'photo:Nina:5', text: 'your Day 5 photo', note: 'you\u2019ve got this' }]);
  check('reaction copy: note rides along', note.body === '\u201cyou\u2019ve got this\u201d On your Day 5 photo.', note);
  check('reaction copy: bundled', W.composeMessage([{ reactor: 'Kellye', glyph: '\u2661', eventKey: 'photo:Nina:5', text: 'x' }, { reactor: 'Lauren', glyph: '\u2726', eventKey: 'photo:Nina:5', text: 'x' }]).title === 'Kellye and Lauren reacted \u2661 \u2726');
  check('every-time copy rotates by day', W.covenMessage(5, 1).title === 'Day 5 is officially ours \u2726' && W.covenMessage(6, 1).title === 'Day 6, conjured \u2726' && W.covenMessage(7, 1).title === 'All four of us, Day 7 \u2726');
  check('every-time adds the days-running line', W.covenMessage(5, 4).body.endsWith('That\u2019s four days running.'), W.covenMessage(5, 4));
  check('milestone replaces the everyday line', [3, 7, 14, 21, 31].every(n => W.covenMessage(20, n).title === W.COVEN_MILESTONES[n][0]));
  check('roll copy: others and self', W.rollMessage({ type: 'roll', actor: 'Lauren', streak: 20 }).body === 'Twenty days in a row. Somebody get her a cape.' && W.rollMessage({ type: 'rollself', actor: 'Lauren', streak: 20 }).body === 'Twenty days in a row. Your cape is on order and ships whenever we get around to it.');
  check('recap copy: perfect, quiet, strong', W.recapMessage({ perfect: true, spells: 28, possible: 28, photos: 0, reactions: 0 }).title === 'A perfect week \u2726'
    && W.recapMessage({ perfect: false, spells: 11, possible: 28 }).title === 'A softer week'
    && W.recapMessage({ perfect: false, spells: 22, possible: 28, photos: 9, reactions: 31 }).body === 'We cast 22 spells, shared 9 photos, and sent 31 reactions. Come see the damage.');
}

// ===== baseline is silent =====
resetWorld();
for (const p of PEOPLE) putPerson(p, person({ 1: cast() }));
put('r2:recal-comments:Kellye', { 'photo:Nina:1': [{ id: 'c1', t: 'old comment', at: '2026-10-01T18:00:00Z' }] });
await runAt(D5);
check('first run sends nothing', pushes.length === 0, pushes);
await runAt(plus(D5, 60));
check('existing comments are not announced', pushes.length === 0, pushes);

// ===== reactions: wait a minute, then send with the note =====
resetWorld();
for (const p of PEOPLE) putPerson(p, person({ 5: p === 'Nina' ? { hasPhoto: true } : {} }));
await baseline();
put('r2:recal-reactions:Kellye', { 'photo:Nina:5': ['\u2661'] });
put('r2:recal-reactions:Lauren', { 'photo:Nina:5': ['\u2726'] });
put('r2:recal-comments:Lauren', { 'photo:Nina:5': [{ id: 'n1', t: 'you\u2019ve got this', at: plus(D5, 20), g: '\u2726' }] });
await runAt(plus(D5, 30));
check('reactions wait about a minute (so a note can arrive)', pushes.length === 0, pushes);
await runAt(plus(D5, 120));
{
  const n = sentTo('Nina');
  check('two reactions bundle into one push', n.length === 1 && n[0].title === 'Kellye and Lauren reacted \u2661 \u2726', n);
  await runAt(plus(D5, 300));
  check('and it is not sent twice', pushes.length === 0, pushes);
}
// single reaction with a note
resetWorld();
for (const p of PEOPLE) putPerson(p, person({ 5: p === 'Nina' ? { hasPhoto: true } : {} }));
await baseline();
put('r2:recal-reactions:Lauren', { 'photo:Nina:5': ['\u2726'] });
put('r2:recal-comments:Lauren', { 'photo:Nina:5': [{ id: 'n1', t: 'you\u2019ve got this', at: plus(D5, 20), g: '\u2726' }] });
await runAt(plus(D5, 30)); await runAt(plus(D5, 130));
{
  const n = sentTo('Nina');
  check('a note shows up in the reaction push', n.length === 1 && n[0].title === 'Lauren is spellbound \u2726' && n[0].body === '\u201cyou\u2019ve got this\u201d On your Day 5 photo.', n);
  check('a note does not send its own comment push', pushes.length === 1 || pushes.filter(x => x.title.includes('opinions')).length === 0, pushes);
}

// ===== comments =====
resetWorld();
for (const p of PEOPLE) putPerson(p, person({ 5: p === 'Nina' ? { hasPhoto: true } : {} }));
await baseline();
put('r2:recal-comments:Kellye', { 'photo:Nina:5': [{ id: 'k1', t: 'This is gorgeous, where is this?', at: plus(D5, 10) }] });
await runAt(plus(D5, 30));
check('poster is told about a comment', sentTo('Nina').length === 1 && sentTo('Nina')[0].title === 'Kellye has opinions about your Day 5 photo' && sentTo('Nina')[0].body === 'This is gorgeous, where is this?', sentTo('Nina'));
check('nobody else is pinged by the first comment', pushes.length === 1, pushes);
put('r2:recal-comments:Lauren', { 'photo:Nina:5': [{ id: 'l1', t: 'Seconded.', at: plus(D5, 100) }] });
await runAt(plus(D5, 130));
check('poster hears the next comment too', sentTo('Nina').some(x => x.title === 'Lauren has opinions about your Day 5 photo'), pushes);
{
  const k = sentTo('Kellye');
  check('an earlier commenter hears the reply', k.length === 1 && k[0].title === 'Lauren couldn\u2019t stay out of it' && k[0].body === 'On Nina\u2019s Day 5 photo: Seconded.', k);
}
check('the author is never pinged about her own comment', sentTo('Lauren').length === 0 && sentTo('Carolina').length === 0, pushes);
// two at once
resetWorld();
for (const p of PEOPLE) putPerson(p, person({ 5: p === 'Nina' ? { hasPhoto: true } : {} }));
await baseline();
put('r2:recal-comments:Kellye', { 'photo:Nina:5': [{ id: 'k1', t: 'one', at: plus(D5, 10) }] });
put('r2:recal-comments:Lauren', { 'photo:Nina:5': [{ id: 'l1', t: 'two', at: plus(D5, 12) }] });
await runAt(plus(D5, 30));
check('several comments bundle', sentTo('Nina').length === 1 && sentTo('Nina')[0].title === 'The comments are getting rowdy' && sentTo('Nina')[0].body === '2 new on your Day 5 photo. Go see who said what.', sentTo('Nina'));
// switch off
resetWorld();
for (const p of PEOPLE) putPerson(p, person({ 5: p === 'Nina' ? { hasPhoto: true } : {} }));
put('recal-notif-prefs:Nina', { reactions: false });
await baseline();
put('r2:recal-comments:Kellye', { 'photo:Nina:5': [{ id: 'k1', t: 'hi', at: plus(D5, 10) }] });
await runAt(plus(D5, 30));
check('the Reactions and comments switch is respected', sentTo('Nina').length === 0, pushes);
// old comment
resetWorld();
for (const p of PEOPLE) putPerson(p, person({ 5: {} }));
await baseline();
put('r2:recal-comments:Kellye', { 'photo:Nina:5': [{ id: 'k1', t: 'ancient', at: '2026-10-05T01:00:00Z' }] });
await runAt(plus(D5, 30));
check('a comment from hours ago is never pushed', pushes.length === 0, pushes);

// ===== every time all four cast =====
resetWorld();
for (const p of PEOPLE) putPerson(p, person({}));
await baseline();
for (const p of ['Nina', 'Kellye', 'Lauren']) putPerson(p, person({ 5: cast() }));
await runAt(plus(D5, 30));
check('three of four casting does not trigger the coven push', !pushes.some(x => x.title.includes('officially ours')), pushes);
putPerson('Carolina', person({ 5: cast() }));
await runAt(plus(D5, 90));
{
  const ok = PEOPLE.every(p => sentTo(p).length === 1 && sentTo(p)[0].title === 'Day 5 is officially ours \u2726' && sentTo(p)[0].body === 'All four of us cast. Go be smug about it.');
  check('all four get one push when the fourth casts', ok, pushes);
  await runAt(plus(D5, 200));
  check('and only once', pushes.length === 0, pushes);
}
// streak line and milestone
resetWorld();
for (const p of PEOPLE) putPerson(p, person({ 3: cast(), 4: cast() }));
await baseline();
for (const p of PEOPLE) putPerson(p, person({ 3: cast(), 4: cast(), 5: cast() }));
await runAt(plus(D5, 60));
check('day 3 of the all-four streak uses the milestone line', sentTo('Nina').length === 1 && sentTo('Nina')[0].title === 'Three in a row \u2726', sentTo('Nina'));
resetWorld();
for (const p of PEOPLE) putPerson(p, person({ 1: cast(), 2: cast(), 3: cast(), 4: cast() }));
await baseline();
for (const p of PEOPLE) putPerson(p, person({ 1: cast(), 2: cast(), 3: cast(), 4: cast(), 5: cast() }));
await runAt(plus(D5, 60));
check('a longer streak adds the days-running line', sentTo('Kellye').some(x => x.title === 'Day 5 is officially ours \u2726' && x.body.endsWith('That\u2019s five days running.')), sentTo('Kellye'));
check('when everyone hits a streak at once, the coven push covers it', sentTo('Kellye').length === 2 && sentTo('Kellye').some(x => x.title === 'You\u2019re on a roll \u2726') && !sentTo('Kellye').some(x => x.title === 'Nina is on a roll \u2726'), sentTo('Kellye'));
// backfilling an old day never pings
resetWorld();
for (const p of PEOPLE) putPerson(p, person({}));
await baseline();
for (const p of PEOPLE) putPerson(p, person({ 2: cast() }));
await runAt(plus(D5, 60));
check('casting an old day does not ping anyone', pushes.length === 0, pushes);

// ===== on a roll =====
resetWorld();
for (const p of PEOPLE) putPerson(p, person({ 1: cast(), 2: cast(), 3: cast(), 4: cast() }));
for (const p of ['Kellye', 'Lauren', 'Carolina']) putPerson(p, person({}));
await baseline();
putPerson('Nina', person({ 1: cast(), 2: cast(), 3: cast(), 4: cast(), 5: cast() }));
await runAt(plus(D5, 60));
check('others hear that she is on a roll', ['Kellye', 'Lauren', 'Carolina'].every(p => sentTo(p).length === 1 && sentTo(p)[0].title === 'Nina is on a roll \u2726' && sentTo(p)[0].body === 'Five days in a row. Somebody say something nice before it goes to her head.'), pushes);
check('she gets her own private one', sentTo('Nina').length === 1 && sentTo('Nina')[0].title === 'You\u2019re on a roll \u2726', sentTo('Nina'));
check('the plain "cast her spell" push is replaced, not doubled', pushes.length === 4, pushes);

// ===== Sunday recap =====
resetWorld();
const week = {};
for (let n = 5; n <= 11; n++) week[n] = cast();
const SUN = '2026-10-12T01:30:00Z'; // Sun Oct 11, 6:30pm Pacific = Day 11
for (const p of PEOPLE) putPerson(p, person(week));
put('r2:recal-reactions:Kellye', { 'cast:Nina:8': ['\u2661'], 'photo:Nina:9': ['\u2726', '\u263E'] });
await baseline();
await runSettled(SUN);
{
  const rec = PEOPLE.map(p => sentTo(p).find(x => x.title.includes('perfect') || x.title.includes('numbers') || x.title.includes('softer')));
  check('everyone gets the recap on Sunday evening', rec.every(Boolean), pushes);
  check('a week where everyone cast every day is "perfect"', rec.every(r => r && r.title === 'A perfect week \u2726'), rec);
  await runAt(plus(SUN, 120));
  check('the recap goes out once', !pushes.some(x => x.title.includes('perfect')), pushes);
}
resetWorld();
const half = {};
for (let n = 5; n <= 11; n++) half[n] = (n % 2) ? cast() : {};
for (const p of PEOPLE) putPerson(p, person(half));
await baseline();
await runSettled(SUN);
check('a regular week reports the numbers', sentTo('Lauren').some(x => x.title === 'The week, in numbers \u2726' && x.body.startsWith('We cast 16 spells')), sentTo('Lauren'));
resetWorld();
const few = {}; few[8] = cast();
for (const p of PEOPLE) putPerson(p, person(few));
await baseline();
await runSettled(SUN);
check('a quiet week is kind about it', sentTo('Nina').some(x => x.title === 'A softer week' && x.body.includes('Even witches nap')), sentTo('Nina'));
resetWorld();
for (const p of PEOPLE) putPerson(p, person(week));
await runAt('2026-10-11T01:30:00Z'); // Saturday evening
check('no recap on a Saturday', !pushes.some(x => x.title.includes('week')), pushes);
resetWorld();
for (const p of PEOPLE) putPerson(p, person(week));
await runAt('2026-10-05T01:30:00Z'); // Sunday Oct 4, day 4, the short first week
check('no recap in the short first week', !pushes.some(x => x.title.includes('week')), pushes);

// ===== missing device or switch =====
resetWorld();
delete store['recal-fcm-token:Carolina'];
for (const p of PEOPLE) putPerson(p, person({}));
await baseline();
for (const p of PEOPLE) putPerson(p, person({ 5: cast() }));
await runAt(plus(D5, 60));
check('someone without notifications is skipped, the others still hear', sentTo('Carolina').length === 0 && sentTo('Nina').length === 1, pushes);

// ===== the daily brew =====
{
  const D6 = '2026-10-06T19:10:00Z'; // 12:10pm Pacific, Day 6
  const brewTo = (who) => sentTo(who).filter(x => x.title === 'Today\u2019s brew');
  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  await runAt('2026-10-06T18:30:00Z'); // 11:30am Pacific
  check('brew: not before noon Pacific', !pushes.some(x => x.title === 'Today\u2019s brew'), pushes);
  put('recal-notif-prefs:Lauren', { morning: false });
  put('r2:recal-qa:Kellye', { 6: { t: 'My sense of humor.', at: '2026-10-06T16:00:00Z' } });
  await runAt(D6);
  check('brew: Nina gets the Day 6 question', brewTo('Nina').length === 1 && brewTo('Nina')[0].body === W.QUESTIONS[6], brewTo('Nina'));
  check('brew: Day 6 question text', W.QUESTIONS[6] === 'What is something about yourself you like more than you did a year ago?');
  check('brew: someone who already answered is skipped', brewTo('Kellye').length === 0);
  check('brew: the morning switch off means no brew', brewTo('Lauren').length === 0);
  check('brew: Carolina gets it too', brewTo('Carolina').length === 1);
  await runAt(plus(D6, 120));
  check('brew: sent once per person per day', brewTo('Nina').length === 0 && brewTo('Carolina').length === 0, pushes);
  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  await runAt('2026-10-05T22:30:00Z');
  check('brew: no question on a day without one', !pushes.some(x => x.title === 'Today\u2019s brew'), pushes);
}

// ===== letters: "you got one" ping =====
{
  const pingTo = (who) => sentTo(who).filter(x => / wrote (you something|all of us something) ✦$/.test(x.title));

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:0', to: 'Nina', body: 'already there', opensDay: 10, writtenAt: '2026-10-01T12:00:00Z' }]);
  await runAt(D5);
  check('letters: first run marks existing letters as seen, sends nothing', pingTo('Nina').length === 0, pushes);

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:1', to: 'Nina', body: 'secret', opensDay: 25, writtenAt: plus(D5, 0) }]);
  await runAt(plus(D5, 60));
  check('letter ping: recipient gets pinged', pingTo('Nina').length === 1, pingTo('Nina'));
  check('letter ping: title names the sender', pingTo('Nina')[0].title === 'Kellye wrote you something ✦', pingTo('Nina'));
  check('letter ping: exact body with the date label', pingTo('Nina')[0].body === 'Kellye sealed a letter with your name on it. It opens Oct 25, Full Moon in Taurus. You\'re the main event, apparently.', pingTo('Nina'));
  check('letter ping: never reveals the letter text', !pingTo('Nina')[0].body.includes('secret'));
  check('letter ping: the sender gets nothing', pingTo('Kellye').length === 0);

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Lauren', [{ id: 'Lauren:1', to: 'all', body: 'group secret', opensDay: 25, writtenAt: plus(D5, 0) }]);
  await runAt(plus(D5, 60));
  check('letter ping: a group letter reaches the other three, never the sender',
    pingTo('Nina').length === 1 && pingTo('Kellye').length === 1 && pingTo('Carolina').length === 1 && pingTo('Lauren').length === 0, pushes);
  check('letter ping: group title and exact body', pingTo('Kellye')[0].title === 'Lauren wrote all of us something ✦'
    && pingTo('Kellye')[0].body === 'Lauren sealed a letter for the whole coven. It opens Oct 25, Full Moon in Taurus. Four of us, one envelope, no peeking.', pingTo('Kellye'));

  // sealed for a date that is already open: says so instead of "making you wait"
  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Carolina', [{ id: 'Carolina:1', to: 'Nina', body: 'late one', opensDay: 10, writtenAt: '2026-10-20T20:00:00Z' }]);
  await runAt('2026-10-20T20:00:00Z'); // Day 20, well after Day 10 already opened
  check('letter ping: already-open date replaces the wait line',
    pingTo('Nina')[0] && pingTo('Nina')[0].body === 'Carolina sealed a letter with your name on it. It\'s open right now, so there\'s no waiting this time. Go on.', pingTo('Nina'));

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Carolina', [{ id: 'Carolina:1', to: 'Carolina', body: 'to future me', opensDay: 31, writtenAt: plus(D5, 0) }]);
  await runAt(plus(D5, 60));
  check('letter ping: a letter to yourself never pings anyone', pingTo('Nina').length === 0 && pingTo('Carolina').length === 0, pushes);

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  put('recal-notif-prefs:Nina', { activity: false });
  await baseline();
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:1', to: 'Nina', body: 'secret', opensDay: 25, writtenAt: plus(D5, 0) }]);
  await runAt(plus(D5, 60));
  check('letter ping: the activity switch off blocks it', pingTo('Nina').length === 0, pushes);

  // a letter discovered more than 6 hours after it was written is old news, no ping
  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:1', to: 'Nina', body: 'secret', opensDay: 25, writtenAt: plus(D5, 0) }]);
  await runAt(plus(D5, 7 * 3600));
  check('letter ping: a letter written more than 6 hours before it is first seen is skipped', pingTo('Nina').length === 0, pushes);
}

// ===== letters: evening nudge (every night, not just the night a letter opens) =====
{
  const O10 = '2026-10-11T03:30:00Z'; // 8:30pm Pacific, Oct 10 (Day 10, New Moon in Libra, inside the window)
  const laterNight = '2026-10-13T03:30:00Z'; // 8:30pm Pacific, Oct 12 (Day 12, two nights after opening, still unopened)
  const nudgeTo = (who) => sentTo(who).filter(x => x.title === 'Break the seal ✦');

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:1', to: 'Nina', body: 'x', opensDay: 25, writtenAt: '2026-10-05T12:00:00Z' }]);
  await runAt(O10);
  check('nudge: nothing before the letter is open', nudgeTo('Nina').length === 0, pushes);

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:1', to: 'Nina', body: 'x', opensDay: 10, writtenAt: '2026-10-05T12:00:00Z' }]);
  await runAt('2026-10-11T02:30:00Z'); // 7:30pm Pacific, Oct 10: open, but before the 8pm window
  check('nudge: nothing before 8pm Pacific even once open', nudgeTo('Nina').length === 0, pushes);
  await runAt(O10);
  check('nudge: the recipient gets nudged the night her letter opens', nudgeTo('Nina').length === 1, nudgeTo('Nina'));
  check('nudge: exact body, night it opens, one letter', nudgeTo('Nina')[0].body === 'Kellye\'s letter is ready and so, we suspect, are you. New Moon in Libra. Break the seal.', nudgeTo('Nina'));
  check('nudge: only the recipient, never the sender', nudgeTo('Kellye').length === 0);
  await runAt(plus(O10, 300));
  check('nudge: sent once per person per day, not every run', nudgeTo('Nina').length === 0, pushes);

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:1', to: 'Nina', body: 'x', opensDay: 10, writtenAt: '2026-10-05T12:00:00Z' }]);
  put('r2:recal-letters-opened:Nina', { 'Kellye:1': '2026-10-10T20:00:00.000Z' });
  await runAt(O10);
  check('nudge: an already-opened letter does not nudge', nudgeTo('Nina').length === 0, pushes);

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:1', to: 'Nina', body: 'x', opensDay: 10, writtenAt: '2026-10-05T12:00:00Z' }]);
  put('r2:recal-letters:Lauren', [{ id: 'Lauren:1', to: 'all', body: 'y', opensDay: 10, writtenAt: '2026-10-05T12:00:00Z' }]);
  await runAt(O10);
  check('nudge: two letters opening the same night pluralize, exact body', nudgeTo('Nina').length === 1
    && nudgeTo('Nina')[0].body === '2 letters are ready for you tonight. Go be adored, one seal at a time.', nudgeTo('Nina'));

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:1', to: 'Nina', body: 'x', opensDay: 10, writtenAt: '2026-10-05T12:00:00Z' }]);
  await runAt(laterNight);
  check('nudge: still nudges on a later night, not just the opening night', nudgeTo('Nina').length === 1, nudgeTo('Nina'));
  check('nudge: later-night single-letter line rotates by day (today % 4)',
    nudgeTo('Nina')[0].body === 'Kellye\'s letter isn\'t going anywhere. Neither are we. Break the seal when you\'re ready.', nudgeTo('Nina'));

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:1', to: 'Nina', body: 'x', opensDay: 10, writtenAt: '2026-10-05T12:00:00Z' }]);
  put('r2:recal-letters:Lauren', [{ id: 'Lauren:1', to: 'Nina', body: 'y', opensDay: 10, writtenAt: '2026-10-05T12:00:00Z' }]);
  await runAt(laterNight);
  check('nudge: later-night several-letter line rotates too (today % 2)',
    nudgeTo('Nina')[0].body === '2 letters are waiting for you, all from people who adore you. Take them in any order.', nudgeTo('Nina'));

  // self-letters: included in the count, but the sender-named single-letter copy isn't approved for them
  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Nina', [{ id: 'Nina:1', to: 'Nina', body: 'x', opensDay: 10, writtenAt: '2026-10-05T12:00:00Z' }]);
  await runAt(O10);
  check('nudge: a letter only to yourself is skipped, not invented copy', nudgeTo('Nina').length === 0, pushes);

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Nina', [{ id: 'Nina:1', to: 'Nina', body: 'x', opensDay: 10, writtenAt: '2026-10-05T12:00:00Z' }]);
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:1', to: 'Nina', body: 'y', opensDay: 10, writtenAt: '2026-10-05T12:00:00Z' }]);
  await runAt(O10);
  check('nudge: a self-letter alongside another still counts toward the plural nudge', nudgeTo('Nina').length === 1
    && nudgeTo('Nina')[0].body === '2 letters are ready for you tonight. Go be adored, one seal at a time.', nudgeTo('Nina'));

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:1', to: 'Nina', body: 'x', opensDay: 10, writtenAt: '2026-10-05T12:00:00Z' }]);
  await runAt('2026-10-09T03:30:00Z'); // 8:30pm Pacific, Oct 8 (Day 8, before the Oct 10-31 window even opens)
  check('nudge: nothing before Day 10, even if (hypothetically) something were open', nudgeTo('Nina').length === 0, pushes);
}

// ===== Oct 11 regression: a failing job must never make earlier pushes repeat =====
// What happened: the letters job pushed a run past Cloudflare's 50 outside calls. The run crashed before it saved
// "already sent", so the same pushes went out again every minute. These tests pin the three guards:
// a call budget, claim-before-send, and one job failing without taking the others down.
{
  const realFetch = globalThis.fetch;
  let calls = 0, failGet = null, failStatePut = false;
  globalThis.fetch = async (url, opts = {}) => {
    calls++;
    const u = String(url);
    if (failGet && u.includes(failGet) && (opts.method || 'GET') === 'GET') return new Response('boom', { status: 500 });
    if (failStatePut && u.includes('recal-push-state') && opts.method === 'PUT') return new Response('boom', { status: 500 });
    return realFetch(url, opts);
  };
  const SUNDAY_630 = '2026-10-12T01:30:00Z'; // Sun Oct 11, 6:30pm Pacific, Day 11
  const dupes = (list) => { const seenK = new Map(); for (const x of list) { const k = x.to + '|' + x.title; seenK.set(k, (seenK.get(k) || 0) + 1); } return [...seenK].filter(([, n]) => n > 1).map(([k]) => k); };
  const sundayWorld = () => {
    resetWorld();
    const wk = {}; for (let n = 5; n <= 11; n++) wk[n] = cast();
    for (const p of PEOPLE) putPerson(p, person(wk));
    put('r2:recal-letters:Kellye', [{ id: 'Kellye:1', to: 'Nina', body: 'x', opensDay: 10, writtenAt: '2026-10-05T12:00:00Z' }]);
    put('r2:recal-letters:Lauren', [{ id: 'Lauren:1', to: 'all', body: 'y', opensDay: 10, writtenAt: '2026-10-05T12:00:00Z' }]);
  };

  // 1. The real evening: 6:30pm to 10pm, every minute, with letters waiting. Nothing repeats, every run stays under 50 calls.
  sundayWorld();
  await baseline();
  let everything = [], maxCalls = 0;
  for (let m = 0; m < 215; m++) {
    calls = 0; pushes = [];
    await W.run(env, at(plus(SUNDAY_630, m * 60)));
    maxCalls = Math.max(maxCalls, calls);
    everything.push(...pushes);
  }
  check('regression: no push ever repeats across an evening of one-minute runs', dupes(everything.filter(x => /perfect|numbers|softer|still yours|Break the seal|brew/i.test(x.title))).length === 0, dupes(everything));
  check('regression: every run stays under the 50 outside-call limit', maxCalls <= 50, maxCalls);
  check('regression: the letters nudge still reached Nina exactly once', everything.filter(x => x.to === 'Nina' && x.title === 'Break the seal ✦').length === 1, everything.filter(x => x.title === 'Break the seal ✦'));
  check('regression: recap and nudge each reached all four once', ['perfect', 'still yours'].every(k => PEOPLE.every(p => everything.filter(x => x.to === p && x.title.toLowerCase().includes(k)).length <= 1)), everything.map(x => x.to + ':' + x.title));

  // 2. One job's data read fails every minute: the others still send, nothing repeats.
  sundayWorld();
  await baseline();
  failGet = 'recal-letters-opened';
  everything = [];
  for (let m = 0; m < 215; m++) { pushes = []; await W.run(env, at(plus(SUNDAY_630, m * 60))); everything.push(...pushes); }
  failGet = null;
  check('failing job: the letters job failing does not stop the recap and nudge', PEOPLE.every(p => everything.some(x => x.to === p && /perfect|numbers|softer/i.test(x.title))), everything.map(x => x.to + ':' + x.title));
  check('failing job: and nothing repeats while it keeps failing', dupes(everything.filter(x => /perfect|numbers|softer|still yours|brew/i.test(x.title))).length === 0, dupes(everything));

  // 3. If the "already sent" state cannot be saved, scheduled pushes are NOT sent (a missed push beats a repeating one).
  sundayWorld();
  await baseline();
  failStatePut = true;
  everything = [];
  for (let m = 0; m < 10; m++) { pushes = []; await W.run(env, at(plus(SUNDAY_630, m * 60))).catch(() => {}); everything.push(...pushes); }
  failStatePut = false;
  check('state cannot be saved: nothing scheduled is sent', everything.filter(x => /perfect|numbers|softer|still yours|brew|Break the seal/i.test(x.title)).length === 0, everything.map(x => x.title));

  // 4. The call counter is exposed and the cache means a key is never fetched twice in one run.
  sundayWorld();
  await baseline();
  const seenGets = [];
  const f2 = globalThis.fetch;
  globalThis.fetch = async (url, opts = {}) => { if ((opts.method || 'GET') === 'GET') seenGets.push(String(url)); return f2(url, opts); };
  await runAt(plus(SUNDAY_630, 90 * 60));
  globalThis.fetch = f2;
  check('one run never reads the same key twice', new Set(seenGets).size === seenGets.length, seenGets.filter((u, i) => seenGets.indexOf(u) !== i));
  check('callsUsed reports a sane number after a run', typeof W.callsUsed() === 'number' && W.callsUsed() > 0 && W.callsUsed() <= 50, W.callsUsed());
  globalThis.fetch = realFetch;
}

// ===== Nina's one-time intro letter, and a letter ping that fails once must never repeat =====
{
  const realFetch = globalThis.fetch;
  let failLanded = 0; // how many upcoming letter-ping sends to fail
  globalThis.fetch = async (url, opts = {}) => {
    if (failLanded > 0 && String(url).includes('fcm.googleapis.com')) {
      const m = JSON.parse(opts.body).message;
      if (/ wrote (you something|all of us something) ✦$/.test(m.data.title)) { failLanded--; return new Response('boom', { status: 500 }); }
    }
    return realFetch(url, opts);
  };
  const landed = (who) => sentTo(who).filter(x => / wrote (you something|all of us something) ✦$/.test(x.title));
  const introPush = (who) => sentTo(who).filter(x => x.title === "You've got mail, witches ✦");
  const INTRO_BODY = "Nina wrote all of us a letter and it's open. Drop everything. Okay, finish your sentence first.";
  const world = async () => { resetWorld(); for (const p of PEOPLE) putPerson(p, person({})); await baseline(); };
  const fresh = (extra) => Object.assign({ id: 'Nina:9', to: 'all', body: 'private words', opensDay: 5, writtenAt: plus(D5, 0) }, extra);

  await world();
  put('r2:recal-letters:Nina', [fresh({ intro: true })]);
  await runAt(plus(D5, 60));
  check('intro letter: the other three each get the special push, exact copy', ['Kellye', 'Lauren', 'Carolina'].every(p => introPush(p).length === 1 && introPush(p)[0].body === INTRO_BODY), pushes);
  check('intro letter: Nina does not get her own announcement', introPush('Nina').length === 0 && landed('Nina').length === 0, pushes);
  check('intro letter: it replaces the standard ping instead of adding to it', ['Kellye', 'Lauren', 'Carolina'].every(p => landed(p).length === 0), pushes);
  check('intro letter: the push never carries the letter text', !pushes.some(x => (x.title + x.body).includes('private words')), pushes);
  await runAt(plus(D5, 120));
  check('intro letter: not sent twice', pushes.length === 0, pushes);

  await world();
  put('r2:recal-letters:Kellye', [fresh({ id: 'Kellye:9', intro: true })]);
  await runAt(plus(D5, 60));
  check('intro mark from anyone but Nina is ignored, standard ping instead', introPush('Nina').length === 0 && landed('Nina').length === 1 && landed('Nina')[0].title === 'Kellye wrote all of us something ✦', pushes);

  await world();
  put('r2:recal-letters:Nina', [fresh({ to: 'Lauren', intro: true })]);
  await runAt(plus(D5, 60));
  check('intro mark on a letter that is not to All of us is ignored', introPush('Lauren').length === 0 && landed('Lauren').length === 1 && landed('Lauren')[0].title === 'Nina wrote you something ✦', pushes);

  await world();
  put('r2:recal-letters:Nina', [fresh({})]);
  await runAt(plus(D5, 60));
  check('an ordinary letter from Nina to everyone still gets the standard open-now ping', introPush('Kellye').length === 0 && landed('Kellye').length === 1 && landed('Kellye')[0].body === 'Nina sealed a letter for the whole coven. It\'s open right now, so there\'s no waiting this time. Go on.', pushes);

  // retry fix: one failed send, then success, must send exactly once in total
  await world();
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:2', to: 'Nina', body: 'x', opensDay: 25, writtenAt: plus(D5, 0) }]);
  failLanded = 1;
  let perRun = [];
  for (let i = 1; i <= 5; i++) { await runAt(plus(D5, i * 60)); perRun.push(landed('Nina').length); }
  check('retry: a ping that fails once is sent exactly once on the retry, then never again', JSON.stringify(perRun) === '[0,1,0,0,0]', perRun);
  check('retry: nothing is left queued after it went out', !JSON.parse(store['r2:recal-push-state']).pendingLetters || Object.keys(JSON.parse(store['r2:recal-push-state']).pendingLetters).length === 0, store['r2:recal-push-state']);

  // a ping that keeps failing gives up after 5 tries and stops
  await world();
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:3', to: 'Nina', body: 'x', opensDay: 25, writtenAt: plus(D5, 0) }]);
  failLanded = 99;
  perRun = [];
  for (let i = 1; i <= 8; i++) { await runAt(plus(D5, i * 60)); perRun.push(landed('Nina').length); }
  failLanded = 0;
  check('retry: a ping that always fails sends nothing and stops after 5 tries', perRun.every(n => n === 0), perRun);
  const stuck = JSON.parse(store['r2:recal-push-state']).pendingLetters;
  check('retry: the failed ping is dropped from the queue, not kept forever', !stuck || Object.keys(stuck).length === 0, stuck);

  // evening nudge on a day with no sky tag: no "Day N."
  await world();
  put('r2:recal-letters:Nina', [{ id: 'Nina:7', to: 'all', body: 'x', opensDay: 16, writtenAt: '2026-10-05T12:00:00Z' }]);
  await runSettled('2026-10-17T03:30:00Z'); // 8:30pm Pacific, Oct 16 (Day 16, no sky tag); jobs due together spread over a few minutes
  const n16 = sentTo('Lauren').filter(x => x.title === 'Break the seal ✦');
  check('nudge: on a day with no sky tag the line drops the night name', n16.length === 1 && n16[0].body === 'Nina\'s letter is ready and so, we suspect, are you. Break the seal.', n16);
  check('nudge: no stray "Day N" in it', n16.length === 1 && !/Day \d/.test(n16[0].body), n16);

  globalThis.fetch = realFetch;
}


// ===== casting a spell must never cost anyone a notification (only the 7pm "not cast yet" nudge stops) =====
{
  resetWorld();
  for (const p of PEOPLE) putPerson(p, person(p === 'Kellye' ? { 10: cast() } : {}));
  await baseline();
  put('r2:recal-letters:Nina', [{ id: 'Nina:cast1', to: 'all', body: 'x', opensDay: 10, writtenAt: '2026-10-10T15:20:00Z' }]);
  put('r2:recal-reactions:Lauren', { 'cast:Kellye:10': ['\u2661'] });
  await runSettled('2026-10-10T15:30:00Z');   // 8:30am Pacific, Day 10
  const morning = sentTo('Kellye');
  check('cast her spell and still gets the letter push', morning.some(x => x.title === 'Nina wrote all of us something \u2726'), morning.map(x => x.title));
  check('cast her spell and still gets the morning spell', morning.some(x => /Day 10 of Spells/.test(x.title)), morning.map(x => x.title));
  check('cast her spell and still gets reactions to that spell', morning.some(x => /heart is swelling/.test(x.title)), morning.map(x => x.title));
  await runSettled('2026-10-10T20:30:00Z');   // 1:30pm Pacific
  check('cast her spell and still gets the daily question', sentTo('Kellye').some(x => x.title === 'Today\u2019s brew'), sentTo('Kellye').map(x => x.title));
  await runSettled('2026-10-11T02:30:00Z');   // 7:30pm Pacific
  const NUDGE = /Still time for Day|spell isn\u2019t cast|still yours|streak/i;
  check('the 7pm not-cast-yet nudge skips her, because she has cast', !sentTo('Kellye').some(x => NUDGE.test(x.title)), sentTo('Kellye').map(x => x.title));
  check('and it still goes to people who have not cast', sentTo('Lauren').some(x => NUDGE.test(x.title)), sentTo('Lauren').map(x => x.title));
  await runSettled('2026-10-11T03:30:00Z');   // 8:30pm Pacific
  check('cast her spell and still gets the evening letters nudge', sentTo('Kellye').some(x => x.title === 'Break the seal \u2726'), sentTo('Kellye').map(x => x.title));
}


// ===== the one-time resend of Nina's intro push: Oct 18, 10pm Pacific, to everyone but Nina =====
{
  const INTRO = { id: 'Nina:intro', to: 'all', body: 'x', opensDay: 16, writtenAt: '2026-10-16T22:00:00Z', intro: true };
  const TITLE = "You've got mail, witches \u2726";
  const BODY = "Nina wrote all of us a letter and it's open. Drop everything. Okay, finish your sentence first.";
  const intro = (who) => sentTo(who).filter(x => x.title === TITLE && x.body === BODY);
  const world = async (letters, setup) => {
    resetWorld();
    for (const p of PEOPLE) putPerson(p, person({}));
    if (setup) setup();
    put('r2:recal-letters:Nina', letters);
    await baseline();
  };

  await world([INTRO]);
  await runSettled('2026-10-19T04:40:00Z');   // 9:40pm Pacific, too early
  check('one-time resend: nothing goes out before 10pm', PEOPLE.every(p => intro(p).length === 0), pushes.map(x => x.to + ': ' + x.title));
  await runSettled('2026-10-19T05:05:00Z');   // 10:05pm Pacific
  check('one-time resend: at 10pm the other three get the original push, same words', ['Kellye', 'Lauren', 'Carolina'].every(p => intro(p).length === 1), pushes.map(x => x.to + ': ' + x.title));
  check('one-time resend: Nina does not get her own letter push', intro('Nina').length === 0);
  await runSettled('2026-10-19T05:20:00Z');
  check('one-time resend: and it does not send again later that morning', PEOPLE.every(p => intro(p).length === 0), pushes.map(x => x.to + ': ' + x.title));
  await runSettled('2026-10-19T07:05:00Z');   // 12:05am, a new day
  check('one-time resend: nor after midnight', PEOPLE.every(p => intro(p).length === 0));

  await world([INTRO]);
  await runSettled('2026-10-20T05:05:00Z');   // the next night
  check('one-time resend: it never fires on another day', PEOPLE.every(p => intro(p).length === 0));

  await world([INTRO], () => put('r2:recal-letters-opened:Lauren', { 'Nina:intro': '2026-10-17T05:00:00Z' }));
  await runSettled('2026-10-19T05:05:00Z');
  check('one-time resend: everyone gets it, even someone who already opened the letter', ['Kellye', 'Lauren', 'Carolina'].every(p => intro(p).length === 1), pushes.map(x => x.to + ': ' + x.title));

  await world([INTRO], () => put('recal-notif-prefs:Carolina', { activity: false }));
  await runSettled('2026-10-19T05:05:00Z');
  check('one-time resend: it respects the Coven activity switch', intro('Carolina').length === 0 && intro('Kellye').length === 1 && intro('Lauren').length === 1);

  await world([{ id: 'Nina:plain', to: 'all', body: 'x', opensDay: 16, writtenAt: '2026-10-16T22:00:00Z' }]);
  await runSettled('2026-10-19T05:05:00Z');
  check('one-time resend: an ordinary letter without the intro mark is never resent', PEOPLE.every(p => intro(p).length === 0));

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:fake', to: 'all', body: 'x', opensDay: 16, writtenAt: '2026-10-16T22:00:00Z', intro: true }]);
  await baseline();
  await runSettled('2026-10-19T05:05:00Z');
  check('one-time resend: the intro mark only counts on a letter from Nina', PEOPLE.every(p => intro(p).length === 0));
}


// ===== pushes say which post they are about, so a tap can open that post =====
{
  const cm = (author, eventKey, role = 'owner') => ({ author, eventKey, t: 'hi', owner: 'Nina', noun: 'Day 5 spell', role });
  check('comment push: one post means that post', W.composeComments([cm('Kellye', 'cast:Nina:5')]).target === 'post:cast:Nina:5', W.composeComments([cm('Kellye', 'cast:Nina:5')]));
  check('comment push: several comments on the same post still mean that post', W.composeComments([cm('Kellye', 'cast:Nina:5'), cm('Lauren', 'cast:Nina:5')]).target === 'post:cast:Nina:5');
  check('comment push: several posts mean the feed', W.composeComments([cm('Kellye', 'cast:Nina:5'), cm('Lauren', 'photo:Nina:5')]).target === 'tea');
  check('comment push: the wording is unchanged', W.composeComments([cm('Kellye', 'cast:Nina:5')]).title === 'Kellye has opinions about your Day 5 spell');
  const rx = (reactor, eventKey) => ({ reactor, glyph: '\u2661', eventKey, text: 'your Day 5 spell' });
  check('reaction push: one post means that post', W.composeMessage([rx('Kellye', 'cast:Nina:5')]).target === 'post:cast:Nina:5');
  check('reaction push: several posts mean the feed', W.composeMessage([rx('Kellye', 'cast:Nina:5'), rx('Lauren', 'photo:Nina:5')]).target === 'tea');
  check('reaction push: held overnight still carries it', W.composeMessage([{ ...rx('Kellye', 'cast:Nina:5'), heldOvernight: true }]).target === 'post:cast:Nina:5');
  check('activity push: one spell means that post', W.composeActivity([{ id: 'cast:Kellye:10', type: 'cast', actor: 'Kellye', day: 10 }], 2).target === 'post:cast:Kellye:10');
  check('activity push: the post id uses the same swap the app does', W.composeActivity([{ id: 'cur:Kellye:reading:2026-10-10T18:00:00.123Z', type: 'currently', actor: 'Kellye', field: 'reading', value: 'x', at: '2026-10-10T18:00:00.123Z' }], 2).target === 'post:cur:Kellye:reading:2026-10-10T18:00:00_123Z');
  check('activity push: the full-coven moment means its post', W.composeActivity([{ id: 'coven:10', type: 'coven', day: 10, streak: 2 }], 4).target === 'post:coven:10');
  check('activity push: several things at once mean the feed', W.composeActivity([{ id: 'cast:Kellye:10', type: 'cast', actor: 'Kellye' }, { id: 'photo:Kellye:10', type: 'photo', actor: 'Kellye' }], 2).target === 'tea');
  check('streak pushes mean the feed', W.rollMessage({ type: 'roll', actor: 'Kellye', streak: 5 }).target === 'tea' && W.rollMessage({ type: 'rollself', actor: 'Kellye', streak: 5 }).target === 'tea');
}
{
  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  put('r2:recal-letters:Nina', [{ id: 'Nina:intro', to: 'all', body: 'x', opensDay: 16, writtenAt: '2026-10-16T22:00:00Z', intro: true }]);
  await baseline();
  await runSettled('2026-10-19T05:05:00Z');   // 10:05pm Pacific, the resend and the morning spell
  const resend = sentTo('Kellye').find(x => x.title === "You've got mail, witches \u2726");
  check('the letter resend says it is about letters, in the push itself', resend && resend.target === 'letters', resend);
  await runSettled('2026-10-18T15:35:00Z');   // the next morning, 8:35am Pacific: the morning spell
  const morning = sentTo('Kellye').find(x => /Day 18 of Spells/.test(x.title));
  check('the morning spell carries no target, so a tap just opens the app', morning && morning.target === undefined, morning);
  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Nina', [{ id: 'Nina:x', to: 'Kellye', body: 'x', opensDay: 25, writtenAt: '2026-10-19T05:00:00Z' }]);
  await runSettled('2026-10-19T05:05:00Z');
  const landed = sentTo('Kellye').find(x => / wrote you something/.test(x.title));
  check('a "letter landed" push says it is about letters', landed && landed.target === 'letters', landed);
}

// ===== letters: the Gemini Moon (Day 29) and Moon in Cancer (Day 30) nights =====
{
  const O29 = '2026-10-30T03:30:00Z'; // 8:30pm Pacific, Oct 29 (Day 29)
  const O30 = '2026-10-31T03:30:00Z'; // 8:30pm Pacific, Oct 30 (Day 30)
  const nudgeTo = (who) => sentTo(who).filter(x => x.title === 'Break the seal ✦');
  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:29', to: 'Nina', body: 'x', opensDay: 29, writtenAt: '2026-10-28T20:00:00Z' }]);
  await runAt(O29);
  check('Day 29 nudge names the Gemini Moon', nudgeTo('Nina').length === 1 && nudgeTo('Nina')[0].body === 'Kellye\'s letter is ready and so, we suspect, are you. Gemini Moon. Break the seal.', nudgeTo('Nina'));
  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Kellye', [{ id: 'Kellye:30', to: 'Nina', body: 'x', opensDay: 30, writtenAt: '2026-10-28T20:00:00Z' }]);
  await runAt(O29);
  check('Day 30 letter is not nudged the night before it opens', nudgeTo('Nina').length === 0, pushes);
  await runAt(O30);
  check('Day 30 nudge names the Moon in Cancer', nudgeTo('Nina').length === 1 && nudgeTo('Nina')[0].body === 'Kellye\'s letter is ready and so, we suspect, are you. Moon in Cancer. Break the seal.', nudgeTo('Nina'));
  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  put('r2:recal-letters:Lauren', [{ id: 'Lauren:30', to: 'Nina', body: 'x', opensDay: 30, writtenAt: plus('2026-10-28T20:05:00Z', 0) }]);
  await runAt('2026-10-28T20:06:00Z');
  const ping30 = sentTo('Nina').find(x => / wrote you something/.test(x.title));
  check('a Day 30 letter ping carries the Cancer date label', ping30 && ping30.body === 'Lauren sealed a letter with your name on it. It opens Oct 30, Moon in Cancer. You\'re the main event, apparently.', ping30);
}

// ===== three moves in a week =====
{
  const NOW = '2026-10-05T22:31:00Z'; // just after D5
  const fresh = '2026-10-05T21:00:00Z'; // 2pm Pacific, same day
  const old = '2026-10-02T21:00:00Z';
  const wk = (...ts) => ({ 1: { sessions: [0, 1, 2].map(i => ts[i] ? { done: true, timestamp: ts[i] } : { done: false, timestamp: null }) } });
  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  putPerson('Nina', person({}, wk(old, old)));
  await runAt(NOW);
  check('two moves send nothing', pushes.length === 0, pushes);
  putPerson('Nina', person({}, wk(old, old, fresh)));
  await runAt(plus(NOW, 60));
  const OTHERS = [
    ['Nina is making the rest of us look bad ✦', 'Three moves this week. Go see for yourself and give her the applause she’s earned.'],
    ['Somebody is glowing ✦', 'It’s Nina. Three moves this week. Open the app and tell her how loud we’re allowed to be about it.'],
    ['Nina just hit three moves ✦', 'The receipts are in The Tea. Go look, then say something nice before it goes to her head.']
  ];
  const SELF = [
    ['Go off, queen ✦', 'Three moves this week. The glow is showing, and we’re taking full credit.'],
    ['Okay, we see you ✦', 'Three moves this week. Open the app and see who has already left you applause.'],
    ['You, but make it iconic ✦', 'Three moves this week and the whole coven knows it. Go see what they’re saying.']
  ];
  const isOne = (m, set) => set.some(([t, b]) => m.title === t && m.body === b);
  check('third move: others each get one push, one of the three approved versions', ['Kellye', 'Lauren', 'Carolina'].every(p => sentTo(p).length === 1 && isOne(sentTo(p)[0], OTHERS)), pushes);
  check('third move: all three others get the same version', new Set(['Kellye', 'Lauren', 'Carolina'].map(p => sentTo(p)[0].title)).size === 1, pushes);
  check('third move: she gets her own, one of the three approved versions', sentTo('Nina').length === 1 && isOne(sentTo('Nina')[0], SELF), sentTo('Nina'));
  check('third move: nobody gets the retired wording', !pushes.some(x => /showing off/.test(x.title)), pushes);
  await runAt(plus(NOW, 300));
  await runAt(plus(NOW, 600));
  check('third move: once only, not every run', pushes.length === 0, pushes);

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  putPerson('Kellye', person({}, wk(old, old, old)));
  await runAt(NOW);
  check('a third move logged days ago is never news', pushes.length === 0, pushes);

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  put('recal-notif-prefs:Lauren', { activity: false });
  await baseline();
  putPerson('Carolina', person({}, wk(old, old, fresh)));
  await runAt(NOW);
  check('the activity switch is respected', sentTo('Lauren').length === 0 && sentTo('Nina').length === 1 && sentTo('Kellye').length === 1, pushes);

  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  putPerson('Nina', person({}, wk(old, old, fresh)));
  await runAt(NOW);
  check('three moves does not replace or double any other push', pushes.length === 4, pushes);
}


// ---------- three moves: the wording rotates, and is stable for the same event ----------
{
  const movesMessage = W.movesMessage;
  const seenO = new Set(), seenS = new Set();
  for (const a of ['Nina', 'Kellye', 'Lauren', 'Carolina']) for (let wk = 0; wk < 6; wk++) {
    seenO.add(movesMessage({ type: 'moves3', actor: a, week: wk }).title.replace(a, '{who}'));
    seenS.add(movesMessage({ type: 'moves3self', actor: a, week: wk }).title);
  }
  check('moves wording: all three versions come up across people and weeks', seenO.size === 3 && seenS.size === 3, [...seenO, ...seenS]);
  check('moves wording: the same event always reads the same', JSON.stringify(movesMessage({ type: 'moves3', actor: 'Lauren', week: 3 })) === JSON.stringify(movesMessage({ type: 'moves3', actor: 'Lauren', week: 3 })));
  check('moves wording: no em dashes anywhere', ![...Array.from({ length: 12 }, (_, i) => movesMessage({ type: i % 2 ? 'moves3' : 'moves3self', actor: 'Nina', week: i }))].some(m => /\u2014/.test(m.title + m.body)));
}

// ---------- one-time letter-nights push ----------
{
  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  const D28_8AM = '2026-10-28T15:05:00Z'; // 8:05am Pacific
  const D28_9AM = '2026-10-28T16:05:00Z'; // 9:05am Pacific
  await runSettled(D28_8AM);
  check('letter nights: nothing before 9am on Oct 28', !pushes.some(x => x.title === 'Gemini Moon is Thursday ✦'), pushes);
  await runSettled(D28_9AM);
  check('letter nights: all four get it, exact copy', PEOPLE.every(p => sentTo(p).filter(x => x.title === 'Gemini Moon is Thursday ✦' && x.body === 'Two new letter nights this week, and Gemini goes first. Write yours before the Moon moves on.').length === 1), pushes);
  await runSettled(plus(D28_9AM, 600));
  const again = pushes.filter(x => x.title === 'Gemini Moon is Thursday ✦').length;
  await runSettled(plus(D28_9AM, 3600));
  check('letter nights: once only', again === 0 && pushes.filter(x => x.title === 'Gemini Moon is Thursday ✦').length === 0, pushes);
  resetWorld();
  for (const p of PEOPLE) putPerson(p, person({}));
  await baseline();
  await runSettled('2026-10-29T16:05:00Z');
  check('letter nights: not sent on any other day', !pushes.some(x => x.title === 'Gemini Moon is Thursday ✦'), pushes);
}

console.log('\n' + results.length + ' checks, ' + results.filter(x => !x).length + ' failed');
process.exit(results.every(Boolean) ? 0 : 1);
