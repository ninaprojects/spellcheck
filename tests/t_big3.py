import os, sys, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h import *
res = []
def check(n, ok, d=''):
    res.append(bool(ok)); print(('PASS ' if ok else 'FAIL ') + n + ((' [' + str(d) + ']') if not ok and d else ''))

def seed(sun='Aquarius', moon='Aquarius', rising='Sagittarius'):
    fb = seed_nina(); d = json.loads(fb['recalData/r2:recal:Nina']); d['placements'] = {'sun': sun, 'moon': moon, 'rising': rising, 'notes': ''}
    fb['recalData/r2:recal:Nina'] = json.dumps(d)
    k = json.loads(json.dumps(d)); fb['recalData/r2:recal:Kellye'] = json.dumps(k)
    return fb

with sync_playwright() as pw:
    e = Env(pw, seed(), height=900); e.open(); pg = e.page
    # every drawn symbol sits at the true centre of its circle
    off = pg.evaluate("""() => {
      const bad = [];
      Object.keys(ICON_PATHS).forEach(n => {
        const holder = document.createElement('div'); holder.style.cssText = 'position:absolute;left:-999px;top:0';
        holder.innerHTML = iconBadge(n, 34, 'tint'); document.body.appendChild(holder);
        const svg = holder.querySelector('svg'); const b = svg.getBBox();
        const dx = b.x + b.width/2 - 12, dy = b.y + b.height/2 - 12; // getBBox already includes the nudge
        if(Math.abs(dx) > 0.12 || Math.abs(dy) > 0.12) bad.push([n, +dx.toFixed(2), +dy.toFixed(2)]);
        holder.remove();
      });
      return bad;
    }""")
    check('all 15 symbols are centred in their circles', not off, off)

    pg.evaluate("openProfile('Nina')"); pg.wait_for_timeout(600)
    cols = pg.evaluate("""() => [...document.querySelectorAll('.b3-col')].map(c => {
      const r = (el) => { const b = el.getBoundingClientRect(); return b.left + b.width/2; };
      const textCentre = (el) => { const rg = document.createRange(); rg.selectNodeContents(el); const b = rg.getBoundingClientRect(); return b.left + b.width/2; };
      const name = c.querySelector('.b3-sign > span:last-child');
      return {badge: r(c.querySelector('.ico-badge')), name: textCentre(name), label: textCentre(c.querySelector('.b3-label'))};
    })""")
    check('there are three columns', len(cols) == 3, cols)
    check('each name is centred under its circle', all(abs(c['name'] - c['badge']) <= 1.2 for c in cols), cols)
    check('each label is centred over its circle', all(abs(c['label'] - c['badge']) <= 1.6 for c in cols), cols)

    info = pg.evaluate("""() => { const b = document.getElementById('placementsEditBtn'); const card = document.getElementById('placementsPanel');
      const br = b.getBoundingClientRect(), cr = card.getBoundingClientRect();
      const hit = document.elementFromPoint(br.right + 9, br.top - 7);
      return {fromRight: Math.round(cr.right - br.right), fromTop: Math.round(br.top - cr.top), w: Math.round(br.width), h: Math.round(br.height), font: parseFloat(getComputedStyle(b).fontSize), border: getComputedStyle(b).borderTopWidth, hitIsButton: hit === b}; }""")
    check('Edit sits in the top-right corner of the card', info['fromRight'] <= 20 and info['fromTop'] <= 16, info)
    check('Edit is tiny: under 30px wide, under 18px tall, 11px text', info['w'] < 30 and info['h'] < 18 and info['font'] <= 11, info)
    check('Edit is a plain link, with no box around it', info['border'] == '0px', info)
    check('the area you can tap is bigger than the link you see', info['hitIsButton'], info)
    pg.locator('#placementsEditBtn').click(); pg.wait_for_timeout(500)
    check('tapping Edit opens the editor', pg.locator('#placementsPanel select').count() >= 3, pg.locator('#placementsPanel').inner_text()[:80])
    # nobody else can edit your Big 3
    pg.evaluate("openProfile('Kellye')"); pg.wait_for_timeout(600)
    check("someone else's Big 3 has no Edit link", pg.locator('#placementsEditBtn').count() == 0)
    # a half-filled Big 3 still lines up
    e.close()
    e = Env(pw, seed(sun='Leo', moon='Scorpio', rising='Capricorn'), height=900); e.open(); pg = e.page
    pg.evaluate("openProfile('Nina')"); pg.wait_for_timeout(600)
    wide = pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    check('long names (Capricorn) do not push the page sideways', wide)
    check('no stray errors', not [x for x in e.errors if 'ServiceWorker' not in x], e.errors)
    e.close()
print('\n%d checks, %d failed' % (len(res), res.count(False)))
