import os
import sys, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h import *

res = []
def check(name, ok, detail=''):
    res.append((name, bool(ok), detail)); print(('PASS ' if ok else 'FAIL ') + name + (('  [' + str(detail) + ']') if detail and not ok else ''))
def go(pg, h):
    pg.evaluate("location.hash=%s; 0;" % json.dumps(h)); pg.wait_for_timeout(350)
def saved_day(e, n='1'):
    d = json.loads(e.page.evaluate("window.__FB['recalData/r2:recal:Nina']"))
    return d['days'].get(n, {})
W = '#todayCardWrap '
def fresh():
    # Day 1 with nothing done yet, so every habit starts at zero
    fb = seed_nina()
    d = json.loads(fb['recalData/r2:recal:Nina'])
    d['days']['1']['journaled'] = False; d['days']['1']['noPhone'] = False; d['days']['1']['waterOz'] = 0
    fb['recalData/r2:recal:Nina'] = json.dumps(d)
    return fb


with sync_playwright() as pw:
    e = Env(pw, fresh()); e.open(); pg = e.page
    go(pg, 'today')
    oz = lambda: int(pg.inner_text(W + '.water-read').split()[0])
    liq = lambda: pg.evaluate("document.querySelector('#todayCardWrap .water-box .liq').style.transform")
    pg.evaluate("localStorage.clear()")
    start = oz()
    # ---- bottle ----
    check('B1 the bottle replaced the drops, marked goal 48 and bonus 64', pg.locator(W + '.bottle').count() == 1 and pg.locator(W + '.water-drop').count() == 0 and 'goal 48' in pg.inner_text(W + '.bottle') and 'bonus 64' in pg.inner_text(W + '.bottle'))
    check('B1 +8 sits above -8', pg.evaluate("(()=>{const p=document.querySelector('#todayCardWrap .water-btn.plus').getBoundingClientRect(), m=document.querySelector('#todayCardWrap .water-btn.minus').getBoundingClientRect(); return p.bottom <= m.top + 1;})()"))
    y0 = liq()
    pg.click(W + '.water-btn.plus'); pg.wait_for_timeout(200); pg.click(W + '.water-btn.plus'); pg.wait_for_timeout(700)
    check('B2 two taps add 16 oz and it is saved', oz() == start + 16 and saved_day(e).get('waterOz') == start + 16, (oz(), saved_day(e)))
    check('B2 the liquid moved up', liq() != y0, (y0, liq()))
    for _ in range(4): pg.click(W + '.water-btn.plus'); pg.wait_for_timeout(120)
    pg.wait_for_timeout(700)
    check('B3 48 oz: goal line, 1 pt, to-bonus readout', oz() == 48 and 'Goal met, 1 pt' in pg.inner_text(W + '.water-box') and 'to bonus' in pg.inner_text(W + '.water-sub'), pg.inner_text(W + '.water-box'))
    for _ in range(2): pg.click(W + '.water-btn.plus'); pg.wait_for_timeout(120)
    pg.wait_for_timeout(700)
    check('B4 64 oz: bonus line, 2 pts', oz() == 64 and 'Bonus hydration, 2 pts' in pg.inner_text(W + '.water-box') and 'bonus reached' in pg.inner_text(W + '.water-sub'), pg.inner_text(W + '.water-box'))
    top64 = liq()
    pg.click(W + '.water-btn.plus'); pg.wait_for_timeout(700)
    check('B4 no upper limit, the bottle stays full', oz() == 72 and liq() == top64 and saved_day(e).get('waterOz') == 72, (oz(), liq(), top64))
    pg.click(W + '.water-btn.minus'); pg.wait_for_timeout(500)
    check('B5 minus takes 8 off', oz() == 64 and saved_day(e).get('waterOz') == 64)
    check('B5 water points are unchanged', pg.evaluate("waterPoints(64)") == 2 and pg.evaluate("waterPoints(48)") == 1 and pg.evaluate("waterPoints(40)") == 0)
    e.close()

    # ---- ring and casting rule ----
    e = Env(pw, fresh()); e.open(); pg = e.page
    go(pg, 'today')
    ring_n = lambda: pg.inner_text(W + '.cring .c b').strip()
    check('R1 the ring starts at 0 of 3 and shows the existing sentence', ring_n() == '0' and "Any two of the three and today" in pg.inner_text(W + '.cring-txt'), pg.inner_text(W + '.cring-wrap'))
    pg.locator(W + '.check-row:has-text("Journaled") .toggle').first.click(); pg.wait_for_timeout(500)
    check('R2 one habit: 1 of 3, still not cast', ring_n() == '1' and pg.locator(W + '.cring.cast').count() == 0 and 'one more' in pg.inner_text(W + '.cring-txt').lower())
    check('R2 the journal row shows its done tag', pg.locator(W + '.check-row.isdone:has-text("Journaled") .done-tag').count() == 1 and 'done' in pg.inner_text(W + '.check-row.isdone .done-tag').lower())
    pg.locator(W + '.check-row:has-text("No phone") .toggle').first.click(); pg.wait_for_timeout(500)
    check('R3 two habits cast the spell: star, CAST, banner still there', pg.locator(W + '.cring.cast').count() == 1 and 'CAST' in pg.inner_text(W + '.cring .c') and pg.locator(W + '.today-cast').count() == 1, pg.inner_text(W + '.cring-wrap'))
    pg.locator(W + '.check-row:has-text("No phone") .toggle').first.click(); pg.wait_for_timeout(500)
    check('R4 undoing one habit takes the cast back off', ring_n() == '1' and pg.locator(W + '.cring.cast').count() == 0 and pg.locator(W + '.today-cast').count() == 0)
    e.close()

    e = Env(pw, fresh()); e.open(); pg = e.page
    go(pg, 'today')
    pg.evaluate("document.querySelector('#todayCardWrap .water-btn.plus')"); 
    for _ in range(6): pg.click(W + '.water-btn.plus'); pg.wait_for_timeout(100)
    pg.wait_for_timeout(500)
    check('R5 water at 48 fills the third segment and counts as one habit', pg.inner_text(W + '.cring .c b').strip() == '1')
    pg.locator(W + '.check-row:has-text("Journaled") .toggle').first.click(); pg.wait_for_timeout(500)
    check('R5 water plus journal casts the spell (the rule is unchanged)', pg.locator(W + '.cring.cast').count() == 1)
    e.close()

    # ---- done animation: runs when marked done, not on a plain page load ----
    e = Env(pw, fresh()); e.open(); pg = e.page
    go(pg, 'today')
    pg.evaluate("window.__sparks = 0; new MutationObserver(m=>m.forEach(r=>r.addedNodes.forEach(n=>{ if(n.classList && (n.classList.contains('spark')||n.classList.contains('conf-layer'))) window.__sparks++; }))).observe(document.body,{childList:true,subtree:true});")
    pg.locator(W + '.check-row:has-text("Journaled") .toggle').first.click(); pg.wait_for_timeout(400)
    check('A1 marking journal done plays sparks and the confetti layer', pg.evaluate("window.__sparks") >= 19, pg.evaluate("window.__sparks"))
    check('A1 the toggle pops and the row gets a pink glow', pg.locator(W + '.check-row:has-text("Journaled") .toggle.pop').count() == 1 and pg.locator(W + '.check-row.glow-pink').count() == 1)
    n0 = pg.evaluate("window.__sparks")
    pg.locator(W + '.check-row:has-text("Journaled") .toggle').first.click(); pg.wait_for_timeout(400)
    check('A2 unchecking plays nothing', pg.evaluate("window.__sparks") == n0, (n0, pg.evaluate("window.__sparks")))
    pg.locator(W + '.check-row:has-text("No phone") .toggle').first.click(); pg.wait_for_timeout(400)
    check('A3 no phone done gets the yellow glow', pg.locator(W + '.check-row.glow-yellow').count() == 1)
    pg.wait_for_timeout(2200)
    check('A4 confetti cleans itself up', pg.locator('.conf-layer').count() == 0 and pg.locator('.spark').count() == 0)
    pg.evaluate('renderAll()'); pg.wait_for_timeout(900)
    check('A5 a plain re-render with them done plays nothing but shows the tags', pg.locator('.spark').count() == 0 and pg.locator(W + '.check-row.isdone').count() == 1)
    check('A6 no sideways overflow on Today', pg.evaluate("document.documentElement.scrollWidth") <= 390, pg.evaluate("document.documentElement.scrollWidth"))
    e.close()

    # ---- reduced motion, small phones ----
    e = Env(pw, fresh(), width=360); e.page.emulate_media(reduced_motion='reduce'); e.open(); pg = e.page
    go(pg, 'today')
    pg.evaluate("window.__sparks = 0; new MutationObserver(m=>m.forEach(r=>r.addedNodes.forEach(n=>{ if(n.classList && (n.classList.contains('spark')||n.classList.contains('conf-layer')||n.classList.contains('bub'))) window.__sparks++; }))).observe(document.body,{childList:true,subtree:true});")
    pg.locator(W + '.check-row:has-text("Journaled") .toggle').first.click(); pg.wait_for_timeout(300)
    pg.click(W + '.water-btn.plus'); pg.wait_for_timeout(300)
    check('M1 reduced motion: no sparks, confetti or bubbles are created', pg.evaluate("window.__sparks") == 0, pg.evaluate("window.__sparks"))
    check('M1 reduced motion: the tag, the ring and the water still update', pg.locator(W + '.check-row.isdone').count() == 1 and pg.inner_text(W + '.water-read').startswith('8 '))
    check('M2 no sideways overflow at 360px', pg.evaluate("document.documentElement.scrollWidth") <= 360, pg.evaluate("document.documentElement.scrollWidth"))
    check('M2 the readout and buttons fit beside the bottle at 360px', pg.evaluate("(()=>{const b=document.querySelector('#todayCardWrap .water-btns').getBoundingClientRect(); const c=document.querySelector('#todayCardWrap .water-box').getBoundingClientRect(); return b.right <= c.right + 1 && b.width >= 60;})()"))
    e.close()

    # ---- haptics: vibrate on Android, quiet no-op when nothing exists ----
    e = Env(pw, fresh()); e.page.add_init_script("window.__vib = []; Object.defineProperty(navigator, 'vibrate', {value: (p)=>{ window.__vib.push(p); return true; }, configurable: true});"); e.open(); pg = e.page
    go(pg, 'today')
    pg.click(W + '.water-btn.plus'); pg.wait_for_timeout(200)
    check('H1 a water tap buzzes briefly', pg.evaluate("window.__vib.length") == 1 and pg.evaluate("window.__vib[0]") == 10, pg.evaluate("window.__vib"))
    for _ in range(5): pg.click(W + '.water-btn.plus'); pg.wait_for_timeout(120)
    check('H2 crossing 48 oz buzzes with a longer pattern', any(isinstance(v, list) and len(v) == 3 for v in pg.evaluate("window.__vib")), pg.evaluate("window.__vib"))
    pg.locator(W + '.check-row:has-text("Journaled") .toggle').first.click(); pg.wait_for_timeout(200)
    check('H3 marking a habit done buzzes', any(isinstance(v, list) and v == [12, 30, 12] for v in pg.evaluate("window.__vib")), pg.evaluate("window.__vib"))
    e.close()
    e = Env(pw, fresh()); e.page.add_init_script("Object.defineProperty(navigator, 'vibrate', {value: undefined, configurable: true});"); e.open(); pg = e.page
    errs = []; pg.on('pageerror', lambda x: errs.append(str(x)))
    go(pg, 'today')
    pg.click(W + '.water-btn.plus'); pg.wait_for_timeout(300)
    check('H4 with no vibrate support (iPhone path) nothing breaks and the tap still counts', errs == [] and pg.inner_text(W + '.water-read').startswith('8 '), errs)
    e.close()

bad = [r for r in res if not r[1]]
print('%d checks, %d failed' % (len(res), len(bad)))
sys.exit(1 if bad else 0)
