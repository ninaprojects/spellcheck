import os
import sys, io, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h import *
import tempfile
from PIL import Image
SHOTS = os.path.join(tempfile.gettempdir(), 'spellcheck-shots')
os.makedirs(SHOTS, exist_ok=True)

res = []
def check(name, ok, detail=''):
    res.append((name, bool(ok), detail)); print(('PASS ' if ok else 'FAIL ') + name + (('  [' + str(detail) + ']') if detail and not ok else ''))

FAKE_H2C = """
window.__H2C = [];
window.html2canvas = async (el, opts) => {
  const c = document.createElement('canvas');
  c.width = Math.round(el.offsetWidth * opts.scale); c.height = Math.round(el.offsetHeight * opts.scale);
  window.__H2C.push({w: el.offsetWidth, h: el.offsetHeight, id: el.id, transform: el.style.transform, staged: !!el.closest('.receipt-scope')});
  return c;
};
0;
"""

# The longest card we can make: every optional line filled in, big numbers, the longest status, an 80 character quote.
WORST = """
window.chapterAstroCallout = () => ['Nina', 'Kellye', 'Lauren', 'Carolina'];
const o = computeChapterStats;
window.computeChapterStats = (id) => Object.assign(o(id), {journalCount: 128, workoutCount: 42, noSpendCount: 11, articleCount: 17, fullCovenCount: 6, status: 'just getting started'});
0;
"""
QUOTE80 = 'We said we would drink water and then we all did, a miracle of the group c'

with sync_playwright() as pw:
    # ---------- tabs and old links ----------
    e = Env(pw, seed_nina()); e.open(); pg = e.page
    labels = pg.locator('.tabbar .tab span').all_inner_texts()
    check('R1 tabs are Today, Coven, Journey, Me', labels == ['Today', 'Coven', 'Journey', 'Me'], labels)
    check('R1 no Receipts tab and no Receipts screen', pg.locator('.tabbar .tab[data-tab=receipts]').count() == 0 and pg.locator('[data-view=receipts]').count() == 0)
    pg.evaluate("location.hash = 'receipts'"); pg.wait_for_timeout(400)
    check('R2 an old #receipts link lands on Journey', pg.evaluate("!document.querySelector('[data-view=journey]').hidden && activeView === 'journey'"))

    # ---------- a receipt at the bottom of every chapter ----------
    blocks = pg.evaluate("[...document.querySelectorAll('#chapters .chapter-body')].map(b => { const k = b.lastElementChild; return {last: k.classList.contains('rcpt-block'), label: (k.querySelector('.rcpt-label')||{}).textContent, btn: (k.querySelector('.rcpt-btn')||{}).textContent, count: b.querySelectorAll('.rcpt-block').length}; })")
    check('R3 all five chapters end with a "What we conjured" receipt and an Open button', len(blocks) == 5 and all(b['last'] and b['count'] == 1 and b['label'] == 'What we conjured' and b['btn'] == 'Open' for b in blocks), blocks)

    # ---------- open one, then another ----------
    pg.locator('.chapter-body.open .rcpt-btn').click(); pg.wait_for_timeout(500)
    check('R4 Open shows the card, and the button becomes Close', pg.locator('#receiptCardEl').count() == 1 and pg.locator('.chapter-body.open .rcpt-btn').text_content() == 'Close')
    pg.locator('.chapter-head').nth(1).click(); pg.wait_for_timeout(300)
    pg.locator('.chapter-body.open .rcpt-btn').click(); pg.wait_for_timeout(500)
    check('R4 only one receipt is open at a time', pg.locator('#receiptCardEl').count() == 1 and pg.evaluate("receiptChapterId") == 2 and pg.locator('.rcpt-block[data-ch="1"] #receiptCardEl').count() == 0)

    # ---------- the quote ----------
    q = pg.locator('#receiptQuoteInput')
    check('R5 quote box allows 80 characters', q.get_attribute('maxlength') == '80')
    q.fill('x' * 120)
    check('R5 a 120 character paste is held to 80', len(q.input_value()) == 80, len(q.input_value()))
    q.fill('Water is a personality trait now'); q.blur(); pg.wait_for_timeout(600)
    saved = pg.evaluate("Object.entries(window.__FB).filter(([k]) => k.includes('recal-quote:2')).map(([k, v]) => v)")
    check('R5 the quote saves to the shared record for that chapter', saved and 'Water is a personality trait now' in saved[0], saved)
    check('R5 the quote shows on the card', 'Water is a personality trait now' in pg.locator('#receiptCardEl').inner_text())
    check('R5 the quote box is 16px or larger', pg.evaluate("parseFloat(getComputedStyle(document.getElementById('receiptQuoteInput')).fontSize)") >= 16)
    # typing is never wiped by a redraw
    q.click(); q.press('End'); q.type('abc'); pg.evaluate("renderAll()"); pg.wait_for_timeout(300)
    check('R6 a redraw while typing keeps the box and what was typed', pg.locator('#receiptQuoteInput').input_value().endswith('abc') and pg.evaluate("document.activeElement.id") == 'receiptQuoteInput')
    pg.evaluate("document.activeElement.blur()")
    pg.locator('.chapter-body.open .rcpt-btn').click(); pg.wait_for_timeout(300)
    check('R4 Close collapses it again', pg.locator('#receiptCardEl').count() == 0 and pg.locator('.chapter-body.open .rcpt-btn').text_content() == 'Open')
    e.close()

    # ---------- the card fits, at every phone width, in both shapes ----------
    for width in (360, 390, 430):
        e = Env(pw, seed_nina(), width=width); e.open(); pg = e.page
        pg.click('.tabbar .tab[data-tab=journey]'); pg.wait_for_timeout(400)
        pg.evaluate(WORST); pg.evaluate("trackedSet('recal-quote:1', %s, true)" % json.dumps(QUOTE80)); pg.wait_for_timeout(500)
        pg.locator('.chapter-body.open .rcpt-btn').click(); pg.wait_for_timeout(500)
        for fmt, btn, want in (('square', '#formatCardBtn', (340, 425)), ('story', '#formatStoryBtn', (300, 533))):
            pg.locator(btn).click(); pg.wait_for_timeout(400)
            m = pg.evaluate("(() => { const c = document.getElementById('receiptCardEl'); const k = c.getBoundingClientRect().width / c.offsetWidth; const r = c.getBoundingClientRect(); const f = c.querySelector('.footer-row').getBoundingClientRect(); const fit = document.getElementById('receiptFit').getBoundingClientRect(); const sc = c.closest('.receipt-scope').getBoundingClientRect(); return {w: c.offsetWidth, h: c.offsetHeight, content: c.scrollHeight, footer: (f.bottom - r.top) / k, boxes: ['.divider', '.callouts', '.quote', '.footer-row'].map(s => c.querySelector(s) ? c.querySelector(s).getBoundingClientRect().height : -1), inside: r.left >= sc.left - 1 && r.right <= sc.right + 1}; })()")
            check(f'R7 {fmt} card at {width}px is its full design size', (m['w'], m['h']) == want, m)
            check(f'R7 {fmt} card at {width}px has room for everything, with every optional line on', m['content'] <= m['h'] + 1 and m['footer'] <= m['h'] and all(b > 0 for b in m['boxes']), m)
            check(f'R7 {fmt} card at {width}px sits inside the screen', m['inside'] and pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), m)
            if width == 390: pg.locator('#receiptCardEl').screenshot(path=os.path.join(SHOTS, f's_r7_{fmt}.png'))
        e.close()

    # ---------- the download is the same size on every phone ----------
    for width in (360, 430):
        e = Env(pw, seed_nina(), width=width); e.open(); pg = e.page
        pg.click('.tabbar .tab[data-tab=journey]'); pg.wait_for_timeout(400)
        pg.evaluate(FAKE_H2C)
        pg.locator('.chapter-body.open .rcpt-btn').click(); pg.wait_for_timeout(500)
        for fmt, btn, size, design in (('square', '#formatCardBtn', (1080, 1350), 340), ('story', '#formatStoryBtn', (1080, 1920), 300)):
            pg.locator(btn).click(); pg.wait_for_timeout(300)
            with pg.expect_download(timeout=15000) as d:
                pg.locator('#downloadReceiptBtn').click()
            path = os.path.join(tempfile.gettempdir(), f'r8_{fmt}_{width}.png'); d.value.save_as(path)
            got = Image.open(path).size
            call = pg.evaluate("window.__H2C[window.__H2C.length - 1]")
            check(f'R8 {fmt} download at {width}px is exactly {size[0]}x{size[1]}', got == size, got)
            check(f'R8 {fmt} download at {width}px is drawn from an unscaled copy', call['w'] == design and call['transform'] == 'none' and call['id'] == '' and call['staged'], call)
            check(f'R8 {fmt} download leaves no stray copy on the page', pg.evaluate("document.querySelectorAll('.receipt-scope').length") == 1)
        e.close()

    # ---------- Me ----------
    e = Env(pw, seed_nina()); e.open(); pg = e.page
    pg.evaluate("openProfile('Kellye')"); pg.wait_for_timeout(500)
    check('R9 another person\'s profile still opens', pg.evaluate("currentPerson") == 'Kellye' and pg.evaluate("activeView") == 'profile')
    pg.click('.tabbar .tab[data-tab=profile]'); pg.wait_for_timeout(500)
    check('R9 the Me tab shows your own profile', pg.evaluate("currentPerson") == 'Nina' and pg.evaluate("activeView") == 'profile')
    check('R9 Me is the highlighted tab', pg.locator('.tabbar .tab.active').inner_text().strip() == 'Me')
    pg.click('.tabbar .tab[data-tab=today]'); pg.wait_for_timeout(300)
    pg.click('#topbarAvatar'); pg.wait_for_timeout(500)
    check('R9 your avatar in the top bar still opens it', pg.evaluate("activeView") == 'profile' and pg.evaluate("currentPerson") == 'Nina')
    check('R9 no stray errors', not [x for x in e.errors if 'ServiceWorker' not in x], e.errors)
    e.close()

bad = [r for r in res if not r[1]]
print('\n%d checks, %d failed' % (len(res), len(bad)))
