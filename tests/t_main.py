import os
import sys, io, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h import *
import tempfile
SHOTS = os.path.join(tempfile.gettempdir(), 'spellcheck-shots')
os.makedirs(SHOTS, exist_ok=True)
import piexif
from PIL import Image

res = []
def check(name, ok, detail=''):
    res.append((name, bool(ok), detail)); print(('PASS ' if ok else 'FAIL ') + name + (('  [' + str(detail) + ']') if detail and not ok else ''))

def nina(e): 
    v = e.page.evaluate("window.__FB['recalData/r2:recal:Nina']"); return json.loads(v) if v else None

def jpeg(gps=None):
    im = Image.new('RGB',(64,64),(200,120,160)); b = io.BytesIO()
    if gps:
        lat, lon = gps
        d = lambda x: (int(x), 1)
        def dms(v):
            deg=int(v); m=int((v-deg)*60); s=round(((v-deg)*60-m)*60*100); return ((deg,1),(m,1),(s,100))
        ex = piexif.dump({'GPS':{piexif.GPSIFD.GPSLatitudeRef:b'N' if lat>=0 else b'S', piexif.GPSIFD.GPSLatitude:dms(abs(lat)), piexif.GPSIFD.GPSLongitudeRef:b'E' if lon>=0 else b'W', piexif.GPSIFD.GPSLongitude:dms(abs(lon))}})
        im.save(b,'jpeg',exif=ex)
    else: im.save(b,'jpeg')
    return b.getvalue()

with sync_playwright() as pw:
    # ---------- T1 layout with a saved location ----------
    e = Env(pw, seed_nina(session_loc='Equinox Santa Monica, Santa Monica', daily_loc='Tongva Park, Santa Monica')); e.open(); pg = e.page
    row = pg.locator('#sessionsList .session-row').nth(0)
    row.scroll_into_view_if_needed()
    cap = row.locator('input.gratitude-input')
    w = cap.evaluate("el=>el.getBoundingClientRect().width")
    check('T1 caption box is full width on a phone', w > 250, w)
    check('T1 no sideways scroll', pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
    check('T1 label stays on one line', row.locator('.session-label').evaluate("el=>el.getBoundingClientRect().height") < 24)
    check('T1 location line fits', row.locator('.loc-pill').evaluate("el=>{const r=el.getBoundingClientRect(); return r.right <= window.innerWidth}"))
    row.screenshot(path=os.path.join(SHOTS, 's_t1_session.png'))
    pg.locator('#todayCardWrap .session-row').first.screenshot(path=os.path.join(SHOTS, 's_t1_daily.png'))
    e.close()

    # ---------- T2 place picker (device location) ----------
    e = Env(pw, seed_nina()); e.open(); pg = e.page
    row = pg.locator('#sessionsList .session-row').nth(0); row.scroll_into_view_if_needed()
    row.get_by_text('Add location').click()
    pg.wait_for_selector('#sessionsList .loc-item', timeout=8000)
    names = row.locator('.loc-name').all_inner_texts()
    check('T2 nearest place first', names[0] == 'Equinox Santa Monica', names)
    check('T2 duplicate names shown once', names.count('Equinox Santa Monica') == 1, names)
    check('T2 unnamed places skipped', len(names) == 5 and 'Just the city' in names, names)
    check('T2 says it is near where you are', 'where you are right now' in row.locator('.loc-sub').inner_text())
    body = [r[1] for r in e.reqs if r[0]=='overpass'][0]
    check('T2 lookup used the device coordinates', '34.01950' in body and '-118.49120' in body, body[:200])
    row.screenshot(path=os.path.join(SHOTS, 's_t2_picker.png'))
    row.locator('.loc-item', has_text='Tongva Park').click()
    pg.wait_for_timeout(600)
    check('T2 pick shows the pin line', 'Tongva Park, Santa Monica' in row.locator('.loc-pill').inner_text())
    d = nina(e)
    check('T2 pick saved to the database', d and d['weeks']['0']['sessions'][0]['photoLocation'] == 'Tongva Park, Santa Monica', d and d['weeks']['0']['sessions'][0])
    pg.click('.tabbar .tab[data-tab=coven]'); pg.wait_for_timeout(700)
    feed_locs = pg.locator('.feed-loc').all_inner_texts()
    check('T2 coven feed shows the place', any('Tongva Park' in t for t in feed_locs), feed_locs)
    pg.locator('.feed-loc').first.scroll_into_view_if_needed()
    pg.screenshot(path=os.path.join(SHOTS, 's_t2_feed.png'))
    # just the city + change flow
    pg.click('.tabbar .tab[data-tab=today]'); pg.wait_for_timeout(500)
    row = pg.locator('#sessionsList .session-row').nth(0); row.scroll_into_view_if_needed()
    row.get_by_text('change').click(); pg.wait_for_selector('#sessionsList .loc-item')
    row.locator('.loc-item', has_text='Just the city').click(); pg.wait_for_timeout(500)
    check('T2 "just the city" works', 'Santa Monica, California' in row.locator('.loc-pill').inner_text(), row.locator('.loc-pill').inner_text())
    row.get_by_text('remove').click(); pg.wait_for_timeout(400)
    check('T2 remove brings back Add location', row.get_by_text('Add location').count() == 1)
    # typed place
    row.get_by_text('Add location').click(); pg.wait_for_selector('#sessionsList .loc-item')
    row.locator('.loc-type input').fill("Kellye's backyard"); row.get_by_text('Use this').click(); pg.wait_for_timeout(400)
    check('T2 typed place works', "Kellye's backyard" in row.locator('.loc-pill').inner_text())
    e.close()

    # ---------- T3 daily photo uses the same picker + photo GPS ----------
    e = Env(pw, seed_nina(with_photos=False)); e.open(); pg = e.page
    log_move(pg)  # slot 2 only shows once a move is logged; then a photo is added to it
    row2 = pg.locator('#sessionsList .session-row').nth(1); row2.scroll_into_view_if_needed()
    row2.locator('input[type=file]').set_input_files({'name':'a.jpg','mimeType':'image/jpeg','buffer':jpeg((40.7580,-73.9855))})
    pg.wait_for_timeout(1200)
    gps = pg.evaluate("localStorage.getItem('r2-photo-gps:recal-photo:Nina:0:1')")
    check('T3 photo GPS read from the file', gps and abs(json.loads(gps)['lat']-40.7580) < 0.001 and abs(json.loads(gps)['lon']+73.9855) < 0.001, gps)
    check('T3 photo GPS never sent to the shared database', not any('gps' in k for k in pg.evaluate("Object.keys(window.__FB)")))
    row2 = pg.locator('#sessionsList .session-row').nth(1)
    row2.get_by_text('Add location').click(); pg.wait_for_selector('#sessionsList .loc-item', timeout=8000)
    body = [r[1] for r in e.reqs if r[0]=='overpass'][-1]
    check('T3 lookup used the PHOTO coordinates, not the phone', '40.75800' in body and '-73.98550' in body, body[:160])
    check('T3 says near where the photo was taken', 'photo was taken' in row2.locator('.loc-sub').inner_text(), row2.locator('.loc-sub').inner_text())
    # daily photo row (Today card) also offers the picker
    daily = pg.locator('#todayCardWrap .session-row').first
    daily.locator('input[type=file]').set_input_files({'name':'b.jpg','mimeType':'image/jpeg','buffer':jpeg()})
    pg.wait_for_timeout(1200)
    daily = pg.locator('#todayCardWrap .session-row').first
    check('T3 daily photo row offers Add location', daily.get_by_text('Add location').count() == 1)
    daily.get_by_text('Add location').click(); pg.wait_for_selector('#todayCardWrap .loc-item', timeout=8000)
    check('T3 no photo GPS falls back to the phone and says so', 'where you are right now' in daily.locator('.loc-sub').inner_text(), daily.locator('.loc-sub').inner_text())
    daily.locator('.loc-item').first.click(); pg.wait_for_timeout(500)
    dd = nina(e)['days'][str(pg.evaluate('todayInfo().dayNum'))] if nina(e) else {}
    check('T3 daily pick saved', dd.get('photoLocation','').endswith('Santa Monica') and dd.get('photoLocation','') != '', dd.get('photoLocation'))
    e.close()

    # ---------- T4 no location available / lookup down ----------
    e = Env(pw, seed_nina(), geo=None, overpass='down'); e.open(); pg = e.page
    row = pg.locator('#sessionsList .session-row').nth(0); row.scroll_into_view_if_needed()
    row.get_by_text('Add location').click(); pg.wait_for_timeout(1500)
    check('T4 no location: still can type a place', 'type a place' in row.locator('.loc-sub').inner_text() or row.locator('.loc-type input').count()==1, row.locator('.loc-sub').inner_text())
    row.locator('.loc-type input').fill('Home gym'); row.get_by_text('Use this').click(); pg.wait_for_timeout(400)
    check('T4 typed place saved without a lookup', 'Home gym' in row.locator('.loc-pill').inner_text())
    e.close()
    e = Env(pw, seed_nina(), overpass='down'); e.open(); pg = e.page
    row = pg.locator('#sessionsList .session-row').nth(0); row.scroll_into_view_if_needed()
    row.get_by_text('Add location').click(); pg.wait_for_selector('#sessionsList .loc-item', timeout=15000)
    check('T4 lookup down: says so, still offers the city', 'right now' in row.locator('.loc-sub').inner_text() or "Couldn" in row.locator('.loc-sub').inner_text(), row.locator('.loc-sub').inner_text())
    check('T4 lookup down: city option present', row.locator('.loc-name').all_inner_texts() == ['Just the city'], row.locator('.loc-name').all_inner_texts())
    e.close()

    # ---------- T5 saving feedback ----------
    e = Env(pw, seed_nina(), set_delay=1300); e.open(); pg = e.page
    row = pg.locator('#sessionsList .session-row').nth(0); row.scroll_into_view_if_needed()
    cap = row.locator('input.gratitude-input'); before = pg.evaluate("(window.__SETS||[]).length")
    cap.click(); cap.press_sequentially('Pilates with Kellye', delay=20)
    pg.wait_for_timeout(1000)
    toast = pg.locator('#saveToast').inner_text(); flash = row.locator('.save-flash').inner_text()
    check('T5 shows Saving while it is in flight', 'Saving' in toast and 'Saving' in flash, (toast, flash))
    pg.screenshot(path=os.path.join(SHOTS, 's_t5_saving.png'))
    pg.wait_for_timeout(1800)
    toast = pg.locator('#saveToast').inner_text(); flash = row.locator('.save-flash').inner_text()
    check('T5 ends on Saved (toast + under the field)', 'Saved' in toast and 'Saved' in flash, (toast, flash))
    pg.screenshot(path=os.path.join(SHOTS, 's_t5_saved.png'))
    check('T5 caption actually in the database', nina(e)['weeks']['0']['sessions'][0]['photoCaption'] == 'Pilates with Kellye', nina(e)['weeks']['0']['sessions'][0]['photoCaption'])
    n1 = pg.evaluate("(window.__SETS||[]).length") - before
    cap.blur(); pg.wait_for_timeout(500)
    n2 = pg.evaluate("(window.__SETS||[]).length") - before
    check('T5 blur does not save the same text twice', n1 == n2, (n1, n2))
    pg.wait_for_timeout(2300)
    check('T5 toast tidies itself away', 'show' not in (pg.locator('#saveToast').get_attribute('class') or ''))
    # toggles also confirm
    pg.locator('.acc-head[aria-controls=accMoveBody]').scroll_into_view_if_needed()
    pg.click('#logMoveBtn'); pg.wait_for_selector('#moveSheet'); pg.click('#moveSheetSave'); pg.wait_for_timeout(250)
    check('T5 a toggle shows Saving', 'Saving' in pg.locator('#saveToast').inner_text())
    pg.wait_for_timeout(1900)
    check('T5 a toggle ends on Saved', 'Saved' in pg.locator('#saveToast').inner_text())
    e.close()
    e = Env(pw, seed_nina(), fail_sets=True); e.open(); pg = e.page
    row = pg.locator('#sessionsList .session-row').nth(0); row.scroll_into_view_if_needed()
    cap = row.locator('input.gratitude-input'); cap.click(); cap.press_sequentially('will not save', delay=10); cap.blur(); pg.wait_for_timeout(1200)
    toast = pg.locator('#saveToast').inner_text(); flash = row.locator('.save-flash').inner_text()
    check('T5 failure is honest, not "Saved"', 'save' in toast.lower() and 'Saved' not in toast.replace("Couldn","") and 'Couldn' in flash, (toast, flash))
    pg.screenshot(path=os.path.join(SHOTS, 's_t5_fail.png'))
    e.close()

    # ---------- T6 icons ----------
    e = Env(pw, seed_nina()); e.open(); pg = e.page
    pg.evaluate("openProfile('Nina')"); pg.wait_for_timeout(600)
    check('T6 chips are gone (no duplicate Big 3)', pg.locator('.profile-chip').count() == 0)
    order = pg.evaluate("[...document.querySelectorAll('[data-view=profile] .page[data-page=profile] > *')].map(x=>x.id||x.className).slice(0,4)")
    check('T6 Big 3 sits right under the name on the Profile page', order.index('placementsPanel') > order.index('profilePicSection') and order.index('profilePicSection') < order.index('nav-placements'), order)
    check('T6 Notifications live on the Settings page, not Profile', pg.evaluate("!!document.querySelector('.page[data-page=settings] #notifSection') && !document.querySelector('.page[data-page=profile] #notifSection')"))
    b3 = pg.locator('.big3-compact-line .ico-badge').count()
    check('T6 Big 3 shows 3 sign badges and the 3 labels', b3 == 3 and [x.lower() for x in pg.locator('.b3-label').all_inner_texts()] == ['sun','moon','rising'], (b3, pg.locator('.b3-label').all_inner_texts()))
    check('T6 no emoji glyphs left in Big 3', not any(ch in pg.locator('.big3-compact-line').inner_text() for ch in '\u2652\u2650\u2609\u263d'))
    pg.locator('[data-view=profile]').screenshot(path=os.path.join(SHOTS, 's_t6_profile.png'))
    e.close()

    # ---------- T7 water scoring: 1 pt at 48 oz, 2 pts at 64 oz ----------
    e = Env(pw, seed_nina()); e.open(); pg = e.page
    wp = pg.evaluate("[0, 40, 47, 48, 56, 64, 80].map(waterPoints)")
    check('T7 water points are 0,0,0,1,1,2,2', wp == [0,0,0,1,1,2,2], wp)
    pg.evaluate("location.hash='coven/standings'; 0;"); pg.wait_for_timeout(300)
    note = pg.evaluate("document.querySelector('#nav-leaderboard').nextElementSibling.textContent")
    check('T7 leaderboard note says 1 at 48oz, 2 at 64oz', 'water (1 at 48oz, 2 at 64oz)' in note, note)
    e.close()

bad = [r for r in res if not r[1]]
print('\n%d checks, %d failed' % (len(res), len(bad)))
