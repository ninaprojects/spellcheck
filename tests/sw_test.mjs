// Runs the real sw.js against a fake notification system, and checks what a tap on a notification does.
// A tap about a letter must land on the letter. Any other tap just brings the app forward.
// Run:  node tests/sw_test.mjs
import fs from 'fs';
import vm from 'vm';
import path from 'path';
import { fileURLToPath } from 'url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const code = fs.readFileSync(process.env.SPELLCHECK_SW || path.join(HERE, '..', 'sw.js'), 'utf8');
const SCOPE = 'https://ninaprojects.github.io/spellcheck/';

const results = [];
function check(name, ok, detail = '') {
  results.push([name, !!ok]);
  console.log((ok ? 'PASS ' : 'FAIL ') + name + (!ok && detail !== '' ? '  [' + JSON.stringify(detail) + ']' : ''));
}

// A fresh fake world: the windows that are open, and a record of everything the worker does.
function makeWorld(openWindows = [], opts = {}) {
  const handlers = {};
  const calls = { shown: [], opened: [], focused: [], posted: [], closed: 0 };
  const wins = openWindows.map(url => ({
    url,
    focus: async () => { if (opts.focusThrows) throw new Error('refused'); calls.focused.push(url); },
    postMessage: (m) => { calls.posted.push(m); }
  }));
  const clients = {
    matchAll: async () => wins,
    openWindow: async (u) => { calls.opened.push(u); },
    claim: async () => {}
  };
  const self = {
    registration: { scope: SCOPE, showNotification: (title, opts) => { calls.shown.push({ title, opts }); return Promise.resolve(); } },
    addEventListener: (type, fn) => { handlers[type] = fn; },
    skipWaiting: () => {},
    clients
  };
  const sandbox = {
    self, clients, URL, console,
    importScripts: () => {},
    firebase: { initializeApp: () => {}, messaging: () => ({}) },
    caches: { open: async () => ({ addAll: async () => {}, put: async () => {} }), keys: async () => [], delete: async () => {}, match: async () => null },
    fetch: async () => ({ ok: true, clone: () => ({}) })
  };
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox);
  const push = async (payload) => {
    const waits = [];
    handlers.push({ data: { json: () => payload }, waitUntil: (p) => waits.push(p) });
    await Promise.all(waits);
    return calls.shown[calls.shown.length - 1];
  };
  const tap = async (data) => {
    const waits = [];
    handlers.notificationclick({ notification: { data, close: () => { calls.closed++; } }, waitUntil: (p) => waits.push(p) });
    await Promise.all(waits);
  };
  return { handlers, calls, push, tap };
}

const LETTER_URL = SCOPE + 'index.html?push=letters#profile/letters';
const APP_WINDOW = SCOPE + 'index.html';

// ---- which pushes count as letter pushes ----
{
  const w = makeWorld();
  const letterTitles = ["You've got mail, witches \u2726", 'Break the seal \u2726', 'Nina wrote you something \u2726', 'Kellye wrote all of us something \u2726'];
  const otherTitles = ['\u2728 Day 17 of Spells, Witches', 'Today\u2019s brew', 'Lauren\u2019s heart is swelling \u2661', 'The comments are getting rowdy', 'Still time for Day 17', 'Carolina is on a roll \u2726', 'Nina cast her spell \u2726', 'A perfect week \u2726'];
  for (const t of letterTitles) {
    const shown = await w.push({ data: { title: t, body: 'b' } });
    check('letter push is marked as a letter: ' + t, shown && shown.opts.data && shown.opts.data.letters === true, shown && shown.opts);
  }
  for (const t of otherTitles) {
    const shown = await w.push({ data: { title: t, body: 'b' } });
    check('other push is not marked as a letter: ' + t, shown && shown.opts.data && shown.opts.data.letters === false, shown && shown.opts);
  }
  const shown = await w.push({ data: { title: 'Break the seal \u2726', body: 'Hello there' } });
  check('the notification still shows its title, body and icon', shown.title === 'Break the seal \u2726' && shown.opts.body === 'Hello there' && shown.opts.icon === 'icon-192.png', shown);
}

// ---- tapping a letter notification ----
{
  const w = makeWorld([APP_WINDOW]);
  await w.tap({ letters: true });
  check('letter tap, app already open: brings the app forward', w.calls.focused.length === 1 && w.calls.focused[0] === APP_WINDOW, w.calls.focused);
  check('letter tap, app already open: tells it to open the letter', JSON.stringify(w.calls.posted) === JSON.stringify([{ type: 'open-letters' }]), w.calls.posted);
  check('letter tap, app already open: does not open a second window', w.calls.opened.length === 0, w.calls.opened);
  check('letter tap: the notification is dismissed', w.calls.closed === 1);
}
{
  const w = makeWorld([]);
  await w.tap({ letters: true });
  check('letter tap, app closed: opens the app on the Letters page', JSON.stringify(w.calls.opened) === JSON.stringify([LETTER_URL]), w.calls.opened);
  check('letter tap, app closed: sends no message to a window that does not exist', w.calls.posted.length === 0);
}
{
  const w = makeWorld(['https://example.com/', APP_WINDOW]);
  await w.tap({ letters: true });
  check('letter tap: picks the app window, not some other site', w.calls.focused.length === 1 && w.calls.focused[0] === APP_WINDOW && w.calls.posted.length === 1, w.calls);
}
{
  const w = makeWorld(['https://example.com/']);
  await w.tap({ letters: true });
  check('letter tap, only another site open: opens the app', w.calls.opened.length === 1 && w.calls.opened[0] === LETTER_URL, w.calls.opened);
}

// ---- tapping any other notification ----
{
  const w = makeWorld([APP_WINDOW]);
  await w.tap({ letters: false });
  check('other tap, app open: brings the app forward and sends no letter message', w.calls.focused.length === 1 && w.calls.posted.length === 0 && w.calls.opened.length === 0, w.calls);
}
{
  const w = makeWorld([]);
  await w.tap({ letters: false });
  check('other tap, app closed: opens the app on its home page', JSON.stringify(w.calls.opened) === JSON.stringify([SCOPE]), w.calls.opened);
}
{
  const w = makeWorld([]);
  await w.tap(undefined);
  check('an old notification with no data still opens the app, and does not crash', JSON.stringify(w.calls.opened) === JSON.stringify([SCOPE]), w.calls.opened);
}

// ---- robustness ----
{
  const w = makeWorld([APP_WINDOW], { focusThrows: true });
  await w.tap({ letters: true });
  check('if the window will not focus, the letter message is still sent', JSON.stringify(w.calls.posted) === JSON.stringify([{ type: 'open-letters' }]), w.calls.posted);
}


// ---- pushes about a post: a tap opens that post ----
{
  const w = makeWorld([APP_WINDOW]);
  const shown = await w.push({ data: { title: 'Kellye has opinions about your Day 5 spell', body: 'hi', target: 'post:cast:Nina:5' } });
  check('the push target is kept on the notification', shown.opts.data.target === 'post:cast:Nina:5' && shown.opts.data.letters === false, shown.opts.data);
  await w.tap({ letters: false, target: 'post:cast:Nina:5' });
  check('post tap, app open: tells it which post to open', JSON.stringify(w.calls.posted) === JSON.stringify([{ type: 'open-post', key: 'cast:Nina:5' }]) && w.calls.focused.length === 1, w.calls);
}
{
  const w = makeWorld([]);
  await w.tap({ letters: false, target: 'post:cast:Nina:5' });
  check('post tap, app closed: opens The Tea with that post in the link', JSON.stringify(w.calls.opened) === JSON.stringify([SCOPE + 'index.html?push=tea&post=cast%3ANina%3A5#coven/tea']), w.calls.opened);
}
{
  const w = makeWorld([]);
  await w.tap({ letters: false, target: 'post:cur:Kellye:reading:2026-10-10T18:00:00_123Z' });
  check('post tap: ids with colons and dates are safely encoded in the link', w.calls.opened[0] === SCOPE + 'index.html?push=tea&post=' + encodeURIComponent('cur:Kellye:reading:2026-10-10T18:00:00_123Z') + '#coven/tea', w.calls.opened);
}
{
  const w = makeWorld([APP_WINDOW]);
  await w.tap({ letters: false, target: 'tea' });
  check('feed tap, app open: opens The Tea, no particular post', JSON.stringify(w.calls.posted) === JSON.stringify([{ type: 'open-post', key: null }]), w.calls.posted);
}
{
  const w = makeWorld([]);
  await w.tap({ letters: false, target: 'tea' });
  check('feed tap, app closed: opens The Tea', JSON.stringify(w.calls.opened) === JSON.stringify([SCOPE + 'index.html?push=tea#coven/tea']), w.calls.opened);
}
{
  const w = makeWorld([APP_WINDOW]);
  const shown = await w.push({ data: { title: 'Something with a letters target', body: 'b', target: 'letters' } });
  check('a push whose target is "letters" counts as a letter push', shown.opts.data.letters === true, shown.opts.data);
}
{
  const w = makeWorld([]);
  await w.tap({ letters: false, target: 'something-unknown' });
  check('an unknown target just opens the app', JSON.stringify(w.calls.opened) === JSON.stringify([SCOPE]), w.calls.opened);
}
{
  const w = makeWorld([APP_WINDOW]);
  await w.tap({ letters: true, target: 'post:cast:Nina:5' });
  check('a letter push always wins over a post target', JSON.stringify(w.calls.posted) === JSON.stringify([{ type: 'open-letters' }]), w.calls.posted);
}

const bad = results.filter(r => !r[1]).length;
console.log('\n' + results.length + ' checks, ' + bad + ' failed');
process.exit(bad ? 1 : 0);
