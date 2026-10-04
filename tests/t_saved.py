import os
import sys, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h import *
import tempfile
SHOTS = os.path.join(tempfile.gettempdir(), 'spellcheck-shots')
os.makedirs(SHOTS, exist_ok=True)
res=[]
def check(n,ok,d=''):
    res.append(bool(ok)); print(('PASS ' if ok else 'FAIL ')+n+((' ['+str(d)+']') if not ok and d else ''))
def nina(e):
    v=e.page.evaluate("window.__FB['recalData/r2:recal:Nina']"); return json.loads(v) if v else None
def seed(caption='Pilates with Kellye', grat='grateful for movement and slow pace', loc='Tongva Park, Santa Monica'):
    fb = seed_nina(session_loc=loc, daily_loc=loc)
    d = json.loads(fb['recalData/r2:recal:Nina'])
    d['days']['1']['gratitude'] = grat; d['days']['1']['photoCaption'] = caption
    d['weeks']['0']['sessions'][0]['photoCaption'] = caption
    d['kickoffIntention'] = 'Show up for myself'; d['closingToast'] = 'To the coven'
    fb['recalData/r2:recal:Nina'] = json.dumps(d)
    k = json.loads(json.dumps(d)); fb['recalData/r2:recal:Kellye'] = json.dumps(k)
    return fb
vis = lambda loc: loc.evaluate("el=>getComputedStyle(el).display!=='none'")
with sync_playwright() as pw:
    # ---- saved items start folded ----
    e = Env(pw, seed()); e.open(); pg = e.page
    row = pg.locator('#sessionsList .session-row').nth(0); row.scroll_into_view_if_needed()
    check('caption starts folded: text + check + Edit', vis(row.locator('.saved-view')) and 'Pilates with Kellye' in row.locator('.saved-view').inner_text() and not vis(row.locator('input.gratitude-input')))
    check('caption fold has a check icon', row.locator('.saved-view .chk-ico').count()==1)
    check('location shows as a pill with check', row.locator('.loc-pill .chk-ico').count()==1 and 'Tongva Park' in row.locator('.loc-pill').inner_text())
    check('location has no raw input box', row.locator('.loc-type input').count()==0)
    check('location still has change + remove', row.locator('.loc-actions .loc-link').all_inner_texts()==['change','remove'])
    row.screenshot(path=os.path.join(SHOTS, 's_sv_session.png'))
    # ---- Edit opens, typing does not fold, blur folds ----
    row.locator('.saved-edit').click(); pg.wait_for_timeout(200)
    cap = row.locator('input.gratitude-input')
    check('Edit opens the box with the value', vis(cap) and cap.input_value()=='Pilates with Kellye' and not vis(row.locator('.saved-view')))
    check('Edit puts the cursor in the box', pg.evaluate("document.activeElement===document.querySelector('#sessionsList .session-row input.gratitude-input')"))
    cap.press_sequentially(' and Lauren', delay=15); pg.wait_for_timeout(1400)
    check('autosaved while typing but stays open', nina(e)['weeks']['0']['sessions'][0]['photoCaption']=='Pilates with Kellye and Lauren' and vis(cap))
    cap.blur(); pg.wait_for_timeout(800)
    check('blur folds with the new text', vis(row.locator('.saved-view')) and 'and Lauren' in row.locator('.saved-view').inner_text() and not vis(cap))
    check('folded state hides the Saved line under it', not row.locator('.save-flash').count() or not vis(row.locator('.save-flash')))
    # tap the text itself
    row.locator('.saved-text').click(); pg.wait_for_timeout(200)
    check('tapping the text also opens it', vis(cap))
    cap.press('Enter'); pg.wait_for_timeout(800)
    check('Enter folds it', vis(row.locator('.saved-view')) and not vis(cap))
    # clearing leaves an empty box, not an empty fold
    row.locator('.saved-edit').click(); cap.fill(''); cap.blur(); pg.wait_for_timeout(900)
    check('cleared text stays an empty box', vis(cap) and not vis(row.locator('.saved-view')) and nina(e)['weeks']['0']['sessions'][0]['photoCaption']=='')
    # ---- location pill: change + remove ----
    row = pg.locator('#sessionsList .session-row').nth(0)
    row.get_by_text('change').click(); pg.wait_for_selector('#sessionsList .loc-item')
    row.locator('.loc-item', has_text='Blue Bottle').click(); pg.wait_for_timeout(500)
    check('changing the place updates the pill', 'Blue Bottle Coffee' in row.locator('.loc-pill').inner_text())
    row.get_by_text('remove').click(); pg.wait_for_timeout(400)
    check('remove goes back to Add location', row.get_by_text('Add location').count()==1 and row.locator('.loc-pill').count()==0)
    e.close()
    # ---- gratitude, Day 1 intention (Today card) ----
    e = Env(pw, seed()); e.open(); pg = e.page
    g = pg.locator('#todayCardWrap .saved-view')
    n = g.count()
    texts = [g.nth(i).inner_text().replace('\n',' ') for i in range(n)]
    check('gratitude + intention + daily caption all folded on Today', any('grateful for movement' in t for t in texts) and any('Show up for myself' in t for t in texts) and any('Pilates' in t for t in texts), texts)
    grat = [i for i,t in enumerate(texts) if 'grateful' in t][0]
    g.nth(grat).locator('.saved-edit').click(); pg.wait_for_timeout(200)
    gi = pg.locator('#todayCardWrap input.gratitude-input:visible').first
    gi.fill('grateful for a slow morning'); gi.blur(); pg.wait_for_timeout(900)
    check('gratitude edit saved + folds', nina(e)['days']['1']['gratitude']=='grateful for a slow morning' and any('slow morning' in pg.locator('#todayCardWrap .saved-view').nth(i).inner_text() for i in range(pg.locator('#todayCardWrap .saved-view').count())))
    pg.screenshot(path=os.path.join(SHOTS, 's_sv_today.png'))
    # ---- profile intention + toast ----
    pg.evaluate("openProfile('Nina')"); pg.wait_for_timeout(600)
    pb = pg.locator('#profileBookends')
    check('profile intention + toast folded', pb.locator('.saved-view').count()==2 and not pb.locator('input:visible').count())
    pb.locator('.saved-edit').nth(1).click(); pg.wait_for_timeout(200)
    t = pb.locator('input:visible'); t.fill('To four witches'); t.press('Enter'); pg.wait_for_timeout(900)
    check('toast edit saved + folds', json.loads(pg.evaluate("window.__FB['recalData/r2:recal:Nina']"))['closingToast']=='To four witches' and 'four witches' in pb.locator('.saved-view').nth(1).inner_text())
    pb.scroll_into_view_if_needed(); pb.screenshot(path=os.path.join(SHOTS, 's_sv_profile.png'))
    e.close()
    # ---- someone else's tab: folded, read-only ----
    e = Env(pw, seed()); e.open(); pg = e.page
    pg.evaluate("currentPerson='Kellye'; renderAll();"); pg.wait_for_timeout(700)
    pg.evaluate("openProfile('Kellye')"); pg.wait_for_timeout(500)
    pb = pg.locator('#profileBookends')
    check("other person's text shows folded with no Edit", pb.locator('.saved-view').count()==2 and pb.locator('.saved-edit').count()==0)
    e.close()
    # ---- failure keeps the box open and says so ----
    e = Env(pw, seed(caption=''), fail_sets=True); e.open(); pg = e.page
    row = pg.locator('#sessionsList .session-row').nth(0); row.scroll_into_view_if_needed()
    cap = row.locator('input.gratitude-input'); cap.click(); cap.press_sequentially('will not save', delay=10); cap.blur(); pg.wait_for_timeout(1500)
    check('failed save does NOT fold, shows the error', vis(cap) and not vis(row.locator('.saved-view')) and 'Couldn' in row.locator('.save-flash').inner_text(), row.locator('.save-flash').inner_text())
    e.close()
    # ---- first-time caption on a fresh photo: box, then fold ----
    e = Env(pw, seed(caption='', grat='')); e.open(); pg = e.page
    row = pg.locator('#sessionsList .session-row').nth(0); row.scroll_into_view_if_needed()
    cap = row.locator('input.gratitude-input')
    check('empty caption shows the normal box', vis(cap) and not vis(row.locator('.saved-view')))
    cap.click(); cap.press_sequentially('first caption', delay=10); cap.blur(); pg.wait_for_timeout(900)
    check('first caption folds after saving', vis(row.locator('.saved-view')) and 'first caption' in row.locator('.saved-view').inner_text())
    errs=[x for x in e.errors if 'ServiceWorker' not in x]
    check('no stray errors', not errs, errs)
    e.close()
print('\n%d checks, %d failed' % (len(res), res.count(False)))
