import os
import sys, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h import *
import tempfile
SHOTS = os.path.join(tempfile.gettempdir(), 'spellcheck-shots')
os.makedirs(SHOTS, exist_ok=True)

res = []
def check(name, ok, detail=''):
    res.append((name, bool(ok), detail)); print(('PASS ' if ok else 'FAIL ') + name + (('  [' + str(detail) + ']') if detail and not ok else ''))

def go(pg, h):
    pg.evaluate("location.hash=%s; 0;" % json.dumps(h)); pg.wait_for_timeout(350)
def links(pg):
    return pg.locator('#subnav .subnav-link').all_inner_texts() if pg.locator('#subnav:not([hidden])').count() else []
def vis(pg, sel):
    return pg.evaluate("(s)=>{const e=document.querySelector(s); return !!e && !!(e.offsetWidth||e.offsetHeight) && !e.closest('[hidden]');}", sel)

with sync_playwright() as pw:
    # ---------- pages inside the tabs ----------
    e = Env(pw, seed_nina()); e.open(); pg = e.page
    check('G1 Today is one page, no page row', links(pg) == [], links(pg))
    go(pg, 'coven')
    check('G1 Coven pages are The Tea and Standings', [x.lower() for x in links(pg)] == ['the tea', 'standings'], links(pg))
    check('G2 The Tea shows the feed, Standings is hidden', vis(pg, '#covenFeed') and not vis(pg, '#leaderboardPanel'))
    pg.locator('#subnav .subnav-link[data-page=standings]').click(); pg.wait_for_timeout(300)
    check('G2 tapping Standings shows the leaderboard and moves the hash', vis(pg, '#leaderboardPanel') and not vis(pg, '#covenFeed') and pg.evaluate("location.hash") == '#coven/standings', pg.evaluate("location.hash"))
    check('G2 the active page link is marked', pg.evaluate("document.querySelector('#subnav .subnav-link.active').dataset.page") == 'standings')
    go(pg, 'today'); go(pg, 'coven')
    check('G3 a tab remembers the page you were on', vis(pg, '#leaderboardPanel'))
    check('G3 last page is kept on the device', pg.evaluate("JSON.parse(localStorage.getItem('r2-last-pages')).coven") == 'standings')
    go(pg, 'journey')
    check('G1 Journey pages are The 31 days and Photos', [x.lower() for x in links(pg)] == ['the 31 days', 'photos'], links(pg))
    check('G2 The 31 days shows chapters, not photos', vis(pg, '#chapters') and not vis(pg, '#photoGallery'))
    go(pg, 'journey/photos')
    check('G2 #journey/photos opens the photo journal', vis(pg, '#photoGallery') and not vis(pg, '#chapters'))
    go(pg, 'receipts')
    check('G4 an old #receipts link opens The 31 days', pg.evaluate("activeView==='journey'") and vis(pg, '#chapters'))
    go(pg, 'profile')
    check('G1 Me pages are Profile and Settings', [x.lower() for x in links(pg)] == ['profile', 'settings'], links(pg))
    check('G2 Profile shows the big 3, Settings is hidden', vis(pg, '#placementsPanel') and not vis(pg, '#notifPrefs'))
    pg.locator('#subnav .subnav-link[data-page=settings]').click(); pg.wait_for_timeout(300)
    check('G2 Settings shows notifications', vis(pg, '#notifPrefs') and not vis(pg, '#placementsPanel'))
    check('G2 Settings has no row of names, it is about you', not vis(pg, '#people'))
    pg.evaluate("openProfile('Kellye')"); pg.wait_for_timeout(500)
    check('G5 someone else\'s profile has no Settings page', links(pg) == [] and vis(pg, '#placementsPanel'), links(pg))
    pg.evaluate("openProfile('Nina')"); pg.wait_for_timeout(500)
    check('G5 your own profile brings the page row back', len(links(pg)) == 2, links(pg))
    pg.evaluate("openProfile('Nina')")
    check('G5 opening a profile lands on its Profile page, not Settings', vis(pg, '#placementsPanel'))
    go(pg, 'coven'); go(pg, 'coven/standings'); go(pg, 'coven/tea')
    peek = pg.locator('.standings-peek').inner_text() if pg.locator('.standings-peek').count() else ''
    check('G6 The Tea opens with a one-line standings peek', 'on the board' in peek or 'in the lead' in peek, peek)
    pg.locator('.standings-peek a').click(); pg.wait_for_timeout(300)
    check('G6 the peek link opens Standings', vis(pg, '#leaderboardPanel'))
    e.close()

    # ---------- the subnav at phone widths ----------
    for w in (360, 390, 430):
        e = Env(pw, seed_nina(), width=w); e.open(); pg = e.page
        for h in ('coven', 'journey', 'profile'):
            go(pg, h)
            fit = pg.evaluate("(()=>{const n=document.getElementById('subnav'); const r=n.getBoundingClientRect(); return {w:r.width, sw:n.scrollWidth, cw:n.clientWidth, h:r.height, doc:document.documentElement.scrollWidth, vw:innerWidth};})()")
            check(f'G7 page row fits at {w}px on {h}', fit['sw'] <= fit['cw'] + 1 and fit['doc'] <= fit['vw'] and fit['h'] >= 40, fit)
        e.close()

    # ---------- Also this week ----------
    e = Env(pw, seed_nina()); e.open(); pg = e.page
    pg.evaluate("document.querySelectorAll('.acc-head[aria-controls]').forEach(h=>{ if(h.getAttribute('aria-expanded')==='true') h.click(); }); 0;"); pg.wait_for_timeout(100)
    check('W1 the three rows start closed', pg.evaluate("[...document.querySelectorAll('.acc-body')].every(b=>b.hidden)"))
    check('W1 Move row shows its count and dots', pg.locator('#moveCount').inner_text().endswith('of 3') and pg.locator('#moveDots i').count() == 3)
    pg.locator('.acc-head[aria-controls=accMoveBody]').click(); pg.wait_for_timeout(150)
    check('W2 tapping Move opens it', vis(pg, '#sessionsList') and pg.get_attribute('.acc-head[aria-controls=accMoveBody]', 'aria-expanded') == 'true')
    pg.locator('.acc-head[aria-controls=accShareBody]').click(); pg.wait_for_timeout(150)
    check('W2 only one row is open at a time', vis(pg, '#shareBtn') and not vis(pg, '#sessionsList'))
    pg.locator('.acc-head[aria-controls=accShareBody]').click(); pg.wait_for_timeout(150)
    check('W2 tapping an open row closes it', not vis(pg, '#shareBtn'))
    before = pg.evaluate("weekData('Nina', currentWeekIdx).noSpend.done")
    pg.locator('#noSpendToggle').click(); pg.wait_for_timeout(300)
    check('W3 No-spend is a switch that needs no opening', pg.evaluate("weekData('Nina', currentWeekIdx).noSpend.done") != before)
    pg.locator('.acc-head[aria-controls=accShareBody]').click(); pg.wait_for_timeout(150)
    pg.fill('#articleUrlInput', 'https://example.com/a'); pg.click('#shareBtn'); pg.wait_for_timeout(400)
    check('W4 sharing from the row works and the row says so', pg.locator('#shareCount').inner_text() == '1 shared', pg.locator('#shareCount').inner_text())
    pg.evaluate("currentWeekIdx = 1; renderWeekPanel(); 0;"); pg.wait_for_timeout(150)
    wk0 = pg.evaluate("currentWeekIdx"); t0 = pg.locator('#weekTitle').inner_text()
    check('W5 week buttons start tucked away', not vis(pg, '#weekPrev'))
    pg.locator('#earlierWeeks').click(); pg.wait_for_timeout(150)
    check('W5 Earlier weeks reveals the week buttons', vis(pg, '#weekPrev') and vis(pg, '#weekNext'))
    if wk0 > 0:
        pg.locator('#weekPrev').click(); pg.wait_for_timeout(200)
        check('W5 Earlier steps back a week', pg.locator('#weekTitle').inner_text() != t0 and pg.evaluate("currentWeekIdx") == wk0 - 1)
    e.close()

    # ---------- Log a move ----------
    PNGB = base64.b64decode(PNG.split(',')[1])
    e = Env(pw, seed_nina(with_photos=False)); e.open(); pg = e.page
    pg.evaluate("currentWeekIdx = 1; renderWeekPanel(); 0;"); pg.wait_for_timeout(200)
    n0 = pg.evaluate("weekData('Nina',1).sessions.filter(s=>s.done).length")
    check('M0 week 2 starts with no moves in this test', n0 == 0, n0)
    check('M0 with nothing logged, no move rows and no switches, just a quiet line', pg.locator('#sessionsList .session-row').count() == 0 and pg.locator('#sessionsList .toggle').count() == 0 and 'Nothing logged' in pg.locator('#sessionsList').inner_text())
    pg.click('#logMoveBtn'); pg.wait_for_selector('#moveSheet', timeout=3000)
    check('M1 the sheet opens with a time stamp line', 'stamped' in pg.locator('#moveSheet .sheet-sub').inner_text())
    box = pg.evaluate("(()=>{const r=document.getElementById('moveSheetSave').getBoundingClientRect(); return {b:r.bottom, h:r.height, vh:innerHeight};})()")
    check('M1 Save is on screen and big enough to tap', box['b'] <= box['vh'] and box['h'] >= 44, box)
    pg.click('#moveSheetCancel'); pg.wait_for_timeout(200)
    check('M2 Cancel closes the sheet and logs nothing', pg.locator('#moveSheet').count() == 0 and pg.evaluate("weekData('Nina',1).sessions.filter(s=>s.done).length") == 0)
    pg.click('#logMoveBtn'); pg.wait_for_selector('#moveSheet'); pg.keyboard.press('Escape'); pg.wait_for_timeout(200)
    check('M2 Escape closes the sheet', pg.locator('#moveSheet').count() == 0)
    pg.click('#logMoveBtn'); pg.wait_for_selector('#moveSheet'); pg.click('#moveSheetSave'); pg.wait_for_timeout(500)
    s0 = pg.evaluate("weekData('Nina',1).sessions[0]")
    check('M3 one tap on Save logs a move with a time stamp, no photo needed', s0['done'] and s0['timestamp'] and not s0['hasPhoto'], s0)
    check('M3 the row now reads 1 of 3', pg.locator('#moveCount').inner_text() == '1 of 3' and pg.locator('#moveDots i.on').count() == 1)
    check('M3 the sheet closed after saving', pg.locator('#moveSheet').count() == 0)
    # photo + place
    pg.click('#logMoveBtn'); pg.wait_for_selector('#moveSheet')
    pg.set_input_files('#moveSheetFile', {'name':'run.png','mimeType':'image/png','buffer':PNGB}); pg.wait_for_timeout(700)
    check('M4 a picked photo shows as a thumbnail and the link says Change', pg.evaluate("!!document.querySelector('#moveSheetPhoto img.has')") and pg.locator('#moveSheetPhotoBtn').inner_text().lower() == 'change photo')
    pg.locator('#moveSheet .loc-row').get_by_text('Add location').click(); pg.wait_for_selector('#moveSheet .loc-type input')
    pg.fill('#moveSheet .loc-type input', 'Cherry Creek Trail'); pg.locator('#moveSheet .loc-type').get_by_text('Use this').click(); pg.wait_for_timeout(300)
    check('M4 a chosen place shows as a pill with a check, inside the sheet', pg.locator('#moveSheet .loc-pill').count() == 1 and 'Cherry Creek Trail' in pg.locator('#moveSheet .loc-pill').inner_text())
    check('M4 the sheet is still open after choosing a place', pg.locator('#moveSheet').count() == 1)
    pg.click('#moveSheetSave'); pg.wait_for_timeout(700)
    s1 = pg.evaluate("weekData('Nina',1).sessions[1]")
    check('M5 the move keeps its photo flag and its place', s1['done'] and s1['hasPhoto'] and s1['photoLocation'] == 'Cherry Creek Trail', s1)
    stored = pg.evaluate("window.__FB['recalData/r2:recal-photo:Nina:1:1']")
    check('M5 the photo is stored under its own key as a JPEG', bool(stored) and str(stored).startswith('data:image/jpeg'), str(stored)[:40])
    # third move, then full
    pg.click('#logMoveBtn'); pg.wait_for_selector('#moveSheet'); pg.click('#moveSheetSave'); pg.wait_for_timeout(500)
    check('M6 three moves read 3 of 3 with all dots filled', pg.locator('#moveCount').inner_text() == '3 of 3' and pg.locator('#moveDots i.on').count() == 3)
    check('M6 the button says all three are logged and is disabled', pg.locator('#logMoveBtn').is_disabled() and 'all three' in pg.locator('#logMoveBtn').inner_text().lower())
    check('M7 logged moves have no on/off switch, only Undo', pg.locator('#sessionsList .toggle').count() == 0 and pg.locator('#sessionsList .move-remove').count() == 3)
    pg.on('dialog', lambda d: d.accept())
    pg.locator('#sessionsList .move-remove').nth(2).click(); pg.wait_for_timeout(500)
    check('M7 Undo takes a move back: 2 of 3 and Log a move is available again', pg.locator('#moveCount').inner_text() == '2 of 3' and pg.locator('#logMoveBtn').is_enabled() and pg.evaluate("!weekData('Nina',1).sessions[2].done"))
    log_move(pg)
    check('M7 after logging again the list shows all three', pg.locator('#sessionsList .session-row').count() == 3 and pg.locator('#sessionsList .session-row').nth(0).get_by_text('Move 1').count() == 1)
    pg.screenshot(path=os.path.join(SHOTS, 's_move_done.png'))
    e.close()

    # sheet at small phones
    for w, hh in ((360, 640), (390, 844), (430, 932)):
        e = Env(pw, seed_nina(with_photos=False), width=w, height=hh); e.open(); pg = e.page
        pg.evaluate("currentWeekIdx = 1; renderWeekPanel(); 0;"); pg.click('#logMoveBtn'); pg.wait_for_selector('#moveSheet')
        pg.set_input_files('#moveSheetFile', {'name':'run.png','mimeType':'image/png','buffer':PNGB}); pg.wait_for_timeout(600)
        m = pg.evaluate("(()=>{const r=document.getElementById('moveSheet').getBoundingClientRect(); const b=document.getElementById('moveSheetSave').getBoundingClientRect(); return {top:r.top,bottom:r.bottom,w:r.width,vw:innerWidth,vh:innerHeight,sb:b.bottom,doc:document.documentElement.scrollWidth};})()")
        check(f'M8 sheet fits at {w}x{hh}', m['w'] <= m['vw'] and m['bottom'] <= m['vh'] + 1 and m['top'] >= 0 and m['doc'] <= m['vw'], m)
        pg.screenshot(path=os.path.join(SHOTS, f's_move_sheet_{w}.png'))
        e.close()

bad = [r for r in res if not r[1]]
print('\n%d checks, %d failed' % (len(res), len(bad)))
sys.exit(1 if bad else 0)
