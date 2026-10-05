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
    pushes.push({ to: m.token.replace('token-', ''), title: m.data.title, body: m.data.body });
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
await runAt(SUN);
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
await runAt(SUN);
check('a regular week reports the numbers', sentTo('Lauren').some(x => x.title === 'The week, in numbers \u2726' && x.body.startsWith('We cast 16 spells')), sentTo('Lauren'));
resetWorld();
const few = {}; few[8] = cast();
for (const p of PEOPLE) putPerson(p, person(few));
await baseline();
await runAt(SUN);
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

console.log('\n' + results.length + ' checks, ' + results.filter(x => !x).length + ' failed');
process.exit(results.every(Boolean) ? 0 : 1);
