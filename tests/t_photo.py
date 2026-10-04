import os
import sys, json, re; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h import *
from t_photo_common import *
res=[]
def check(n,ok,d=''):
    res.append(ok); print(('PASS ' if ok else 'FAIL ')+n+((' ['+str(d)+']') if not ok and d else ''))
def nina(e):
    v=e.page.evaluate("window.__FB['recalData/r2:recal:Nina']"); return json.loads(v) if v else None
big = big_jpeg()
with sync_playwright() as pw:
    # daily photo from the library
    e = Env(pw, seed_nina(with_photos=False)); e.open(); pg = e.page
    row = pg.locator('#todayCardWrap .session-row').first
    row.locator('input[type=file]').set_input_files({'name':'IMG_1234.jpg','mimeType':'image/jpeg','buffer':big})
    pg.wait_for_timeout(3500)
    d = nina(e); dd = d['days']['1']
    check('daily: 8.8 MB photo is accepted', dd['hasPhoto'] is True, dd)
    du = pg.evaluate("window.__FB['recalData/r2:recal-daily-photo:Nina:1']")
    raw, im = decode_dataurl(du)
    check('daily: stored copy is small (< 1.5 MB, worst-case noise photo)', len(raw) < 1_500_000, len(raw))
    check('daily: longest side is 1600', max(im.size) == 1600, im.size)
    check('daily: orientation applied (portrait phone photo stays portrait)', im.size[1] > im.size[0], im.size)
    ex = piexif.load(raw) if raw[:2]==b'\xff\xd8' else {}
    check('daily: location stamp not in the stored copy', not (ex.get('GPS') or {}), ex.get('GPS'))
    check('daily: type recorded as jpeg', dd['photoType']=='image/jpeg', dd['photoType'])
    # the picker should still know where the ORIGINAL was taken
    row = pg.locator('#todayCardWrap .session-row').first
    row.get_by_text('Add location').click(); pg.wait_for_selector('#todayCardWrap .loc-item', timeout=8000)
    check('daily: picker still uses the original photo location', 'photo was taken' in row.locator('.loc-sub').inner_text(), row.locator('.loc-sub').inner_text())
    # session photo
    row = pg.locator('#sessionsList .session-row').nth(1)
    row.locator('input[type=file]').set_input_files({'name':'IMG_9.jpg','mimeType':'image/jpeg','buffer':big})
    pg.wait_for_timeout(3500)
    sess = nina(e)['weeks']['0']['sessions'][1]
    check('session: photo accepted and session marked done', sess['hasPhoto'] and sess['done'] and sess['timestamp'], sess)
    raw2, im2 = decode_dataurl(pg.evaluate("window.__FB['recalData/r2:recal-photo:Nina:0:1']"))
    check('session: stored copy is small', len(raw2) < 1_500_000, len(raw2))
    check('no stray page errors', not [x for x in e.errors if 'ServiceWorker' not in x], e.errors)
    e.close()
    # a small ordinary photo still works and shows no stale error
    e = Env(pw, seed_nina(with_photos=False)); e.open(); pg = e.page
    small = big_jpeg(1200, 900, orientation=1, gps=None, quality=80)
    row = pg.locator('#todayCardWrap .session-row').first
    row.locator('input[type=file]').set_input_files({'name':'s.jpg','mimeType':'image/jpeg','buffer':small})
    pg.wait_for_timeout(2500)
    check('small photo: accepted', nina(e)['days']['1']['hasPhoto'] is True)
    e.close()
    # not an image at all
    e = Env(pw, seed_nina(with_photos=False)); e.open(); pg = e.page
    row = pg.locator('#sessionsList .session-row').nth(1)
    row.locator('input[type=file]').set_input_files({'name':'x.jpg','mimeType':'image/jpeg','buffer':b'not really a photo'})
    pg.wait_for_timeout(1500)
    msg = pg.locator('#sessionsList .session-row').nth(1).inner_text()
    check('bad file: says it could not read it', 'read that photo' in msg, msg)
    s1 = nina(e)['weeks']['0']['sessions'][1]
    check('bad file: session NOT marked done', not s1['done'], s1)
    e.close()
    # profile picture
    e = Env(pw, seed_nina(with_photos=False)); e.open(); pg = e.page
    pg.evaluate("openProfile('Nina')"); pg.wait_for_timeout(600)
    pg.locator('#profilePicInput').set_input_files({'name':'me.jpg','mimeType':'image/jpeg','buffer':big})
    pg.wait_for_timeout(3500)
    key = [k for k in pg.evaluate("Object.keys(window.__FB)") if 'profile-pic:Nina' in k]
    check('profile pic: 8.8 MB photo accepted', len(key)==1, key)
    if key:
        raw3, im3 = decode_dataurl(pg.evaluate("window.__FB[%s]" % json.dumps(key[0])))
        check('profile pic: shrunk to 512 max, tiny', max(im3.size)==512 and len(raw3) < 200_000, (im3.size, len(raw3)))
    e.close()
print('\n%d checks, %d failed' % (len(res), res.count(False)))
