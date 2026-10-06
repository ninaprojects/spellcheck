import os, sys, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h import *
res = []
def check(n, ok, d=''):
    res.append(bool(ok)); print(('PASS ' if ok else 'FAIL ') + n + ((' [' + str(d) + ']') if not ok and d else ''))

SIZES = """() => {
  const out = [];
  document.querySelectorAll('input:not([type=file]):not([type=checkbox]):not([type=hidden]), textarea, select').forEach(el => {
    if(!el.offsetParent && getComputedStyle(el).position !== 'fixed') return; // hidden boxes do not count
    out.push([parseFloat(getComputedStyle(el).fontSize), (el.className || el.id || el.tagName).toString().slice(0, 40)]);
  });
  return out;
}"""
def seed():
    fb = seed_nina(); d = json.loads(fb['recalData/r2:recal:Nina'])
    for who in ['Kellye']:
        fb['recalData/r2:recal:' + who] = json.dumps(d); fb['recalData/r2:recal-daily-photo:' + who + ':1'] = PNG
    return fb

with sync_playwright() as pw:
    e = Env(pw, seed(), height=900); e.open(); pg = e.page
    small = {}
    def scan(where):
        for fs, name in pg.evaluate(SIZES):
            if fs < 16: small[(name, fs)] = where
    scan('today')
    # unfold the saved fields so their real boxes count too
    pg.evaluate("document.querySelectorAll('input.gratitude-input').forEach(el=>{ el.style.display=''; })")
    scan('today (open fields)')
    # location picker's typed place box
    pg.locator('#sessionsList .session-row').nth(0).get_by_text('Add location').click(); pg.wait_for_timeout(600); scan('place picker')
    # coven: comment box and note box
    pg.click('.tabbar .tab[data-tab=coven]'); pg.wait_for_timeout(700)
    post = pg.locator('#covenFeed > *', has_text='Kellye added a photo').first
    post.scroll_into_view_if_needed(); post.locator('.cmt-link').click(); pg.wait_for_timeout(300); scan('comment box')
    pg.evaluate("document.activeElement && document.activeElement.blur()"); pg.wait_for_timeout(300)
    for t in ['journey', 'receipts']:
        pg.click(f'.tabbar .tab[data-tab={t}]'); pg.wait_for_timeout(500); scan(t)
    pg.evaluate("openProfile('Nina')"); pg.wait_for_timeout(600); scan('profile')
    check('every text box is at least 16px, so iPhone never zooms in on one', not small, sorted([(k[0], k[1], v) for k, v in small.items()]))

    # taps: double-tap zoom is off, pinch still allowed
    ta = pg.evaluate("""() => { const q = (s) => { const el = document.querySelector(s); return el ? getComputedStyle(el).touchAction : null; }; return {html: q('html'), body: q('body'), button: q('button'), link: q('a'), tab: q('.tab')}; }""")
    check('double-tap zoom is switched off on the page and on buttons, links, and tabs', all(v == 'manipulation' for v in ta.values() if v is not None) and ta['html'] == 'manipulation', ta)

    # nothing slid sideways because the text got bigger
    wide = []
    for v in ['today', 'coven', 'journey', 'receipts']:
        pg.evaluate("document.querySelectorAll('.view').forEach(s=>{ s.hidden = s.dataset.view !== %s; })" % json.dumps(v)); pg.wait_for_timeout(200)
        if not pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"): wide.append(v)
    pg.evaluate("openProfile('Nina')"); pg.wait_for_timeout(300)
    if not pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"): wide.append('profile')
    check('no screen scrolls sideways at 16px', not wide, wide)
    check('no stray errors', not [x for x in e.errors if 'ServiceWorker' not in x], e.errors)
    e.close()
print('\n%d checks, %d failed' % (len(res), res.count(False)))
