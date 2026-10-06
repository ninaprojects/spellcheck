import os, sys, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h import *
res = []
def check(n, ok, d=''):
    res.append(bool(ok)); print(('PASS ' if ok else 'FAIL ') + n + ((' [' + str(d) + ']') if not ok and d else ''))
def store(pg, key):
    v = pg.evaluate("window.__FB[%s]" % json.dumps('recalData/' + key)); return json.loads(v) if isinstance(v, str) and v[:1] in '{[' else v
HEART, SPARK, MOON = '\u2661', '\u2726', '\u263E'
ANDROID = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36'
IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1'

def seed():
    fb = seed_nina()
    d = json.loads(fb['recalData/r2:recal:Nina'])
    for who in ['Kellye', 'Lauren']:
        fb['recalData/r2:recal:' + who] = json.dumps(d)
        fb['recalData/r2:recal-daily-photo:' + who + ':1'] = PNG
        fb['recalData/r2:recal-photo:' + who + ':0:0'] = PNG
    return fb
def kellye_photo(pg):
    return pg.locator('#covenFeed > *', has_text='Kellye added a photo').first

with sync_playwright() as pw:
    # ---------- reactions: labels, note, saved ----------
    e = Env(pw, seed()); e.open(); pg = e.page
    pg.click('.tabbar .tab[data-tab=coven]'); pg.wait_for_timeout(700)
    post = kellye_photo(pg)
    post.scroll_into_view_if_needed()
    check('reactions are symbols only until you tap', post.locator('.react-chip .lbl').count() == 0, post.locator('.react-chip').all_inner_texts())
    check('each symbol still carries its name for screen readers and hover', [c.get_attribute('title') for c in post.locator('.react-chip').all()] == ['Heart swelling', 'Spellbound', 'Calm tides'])
    check('"Say something" sits on the same line as the symbols', post.locator('.react-row .cmt-link').count() == 1)
    rowh = post.locator('.react-row').evaluate("el => el.getBoundingClientRect().height")
    check('the whole reaction area is one line when nobody has reacted', rowh < 46, rowh)
    post.locator('.react-chip[aria-label="Spellbound reaction"]').click(); pg.wait_for_timeout(500)
    post = kellye_photo(pg)
    check('the symbol you tapped spells out its name for a moment', post.locator('.react-chip.mine .lbl').text_content() == 'Spellbound', post.locator('.react-chip').all_inner_texts())
    pg.wait_for_timeout(2300)
    post = kellye_photo(pg)
    check('then the word is gone and only the symbol is left', post.locator('.react-chip .lbl').count() == 0 and post.locator('.react-chip.mine .g').inner_text() == '\u2726', post.locator('.react-chip').all_inner_texts())
    check('a reaction chip keeps its name for screen readers after the word fades', post.locator('.react-chip.mine').get_attribute('aria-label') == 'Spellbound reaction')
    check('and the note box names it too', post.locator('.cmt-note-title').inner_text() == '\u2726 Spellbound', post.locator('.cmt-note-title').inner_text() if post.locator('.cmt-note-title').count() else 'none')
    check('the link steps aside while the box is open', post.locator('.react-row .cmt-link').count() == 0)
    check('tapping a reaction opens the note box, focused', post.locator('.cmt-input').count() == 1 and pg.evaluate("document.activeElement && document.activeElement.classList.contains('cmt-input')"))
    check('the note box says what we approved', post.locator('.cmt-input').get_attribute('placeholder') == 'Say something, if you\u2019re feeling chatty', post.locator('.cmt-input').get_attribute('placeholder'))
    r = store(pg, 'r2:recal-reactions:Nina')
    check('the reaction is saved right away', r and any(SPARK in v for v in r.values()), r)
    post.locator('.cmt-input').fill('you\u2019ve got this'); post.get_by_role('button', name='Send').click(); pg.wait_for_timeout(600)
    c = store(pg, 'r2:recal-comments:Nina')
    note = [x for v in (c or {}).values() for x in v]
    check('the note is saved with its symbol', len(note) == 1 and note[0]['g'] == SPARK and note[0]['t'] == 'you\u2019ve got this', c)
    post = kellye_photo(pg)
    check('the note shows under the post', 'Nina' in post.locator('.cmt').inner_text() and SPARK in post.locator('.cmt').inner_text() and 'you\u2019ve got this' in post.locator('.cmt').inner_text(), post.locator('.cmt-list').inner_text() if post.locator('.cmt-list').count() else 'none')
    check('Saved pill appears after a send', 'Saved' in pg.locator('#saveToast').inner_text() or 'Saving' in pg.locator('#saveToast').inner_text())
    pg.screenshot(path=os.path.join(os.environ.get('TMPDIR','/tmp'), 'shot_social_note.png'), full_page=False)
    # skip
    post.locator('.react-chip[aria-label="Heart swelling reaction"]').click(); pg.wait_for_timeout(300)
    post = kellye_photo(pg); post.get_by_text('Skip').click(); pg.wait_for_timeout(300)
    check('Skip closes the box and adds no comment', kellye_photo(pg).locator('.cmt-input').count() == 0 and len([x for v in (store(pg, 'r2:recal-comments:Nina') or {}).values() for x in v]) == 1)
    # untoggle removes the reaction and its note
    post = kellye_photo(pg); post.locator('.react-chip[aria-label="Spellbound reaction"]').click(); pg.wait_for_timeout(500)
    c2 = store(pg, 'r2:recal-comments:Nina')
    check('removing a reaction removes its note too', not [x for v in (c2 or {}).values() for x in v if x.get('g') == SPARK], c2)
    e.close()

    # ---------- comments ----------
    fb = seed()
    fb['recalData/r2:recal-comments:Kellye'] = json.dumps({'photo:Lauren:1': [{'id': 'k1', 't': 'Obsessed with this one', 'at': '2026-10-01T08:00:00.000Z'}]})
    e = Env(pw, fb); e.open(); pg = e.page
    pg.click('.tabbar .tab[data-tab=coven]'); pg.wait_for_timeout(700)
    lauren = pg.locator('#covenFeed > *', has_text='Lauren added a photo').first
    lauren.scroll_into_view_if_needed()
    check("other people's comments show up", 'Kellye' in lauren.locator('.cmt-list').inner_text() and 'Obsessed with this one' in lauren.locator('.cmt-list').inner_text(), lauren.inner_text()[:200])
    check("you cannot delete someone else's comment", lauren.locator('.cmt-del').count() == 0)
    check('the comment link says what we approved', lauren.locator('.cmt-link').inner_text() == 'Say something', lauren.locator('.cmt-link').inner_text())
    lauren.locator('.cmt-link').click(); pg.wait_for_timeout(300)
    lauren = pg.locator('#covenFeed > *', has_text='Lauren added a photo').first
    check('the comment box says what we approved', lauren.locator('.cmt-input').get_attribute('placeholder') == 'Say something nice, or at least funny')
    lauren.locator('.cmt-input').fill('Same, honestly'); lauren.get_by_role('button', name='Post').click(); pg.wait_for_timeout(700)
    mine = [x for v in (store(pg, 'r2:recal-comments:Nina') or {}).values() for x in v]
    check('a comment is saved', len(mine) == 1 and mine[0]['t'] == 'Same, honestly' and 'g' not in mine[0], mine)
    lauren = pg.locator('#covenFeed > *', has_text='Lauren added a photo').first
    texts = lauren.locator('.cmt').all_inner_texts()
    check('comments are oldest first', len(texts) == 2 and 'Kellye' in texts[0] and 'Nina' in texts[1], texts)
    check('you can delete your own', lauren.locator('.cmt-del').count() == 1)
    lauren.locator('.cmt-del').click(); pg.wait_for_timeout(600)
    check('deleting removes it from the database', not [x for v in (store(pg, 'r2:recal-comments:Nina') or {}).values() for x in v])
    # typing is never wiped by a redraw
    lauren = pg.locator('#covenFeed > *', has_text='Lauren added a photo').first
    lauren.locator('.cmt-link').click(); pg.wait_for_timeout(300)
    inp = pg.locator('#covenFeed .cmt-input'); inp.fill('half a thought')
    pg.evaluate("renderCovenFeed(); renderCovenFeed();"); pg.wait_for_timeout(300)
    check('a redraw while typing keeps the text and the cursor', pg.locator('#covenFeed .cmt-input').input_value() == 'half a thought' and pg.evaluate("document.activeElement.classList.contains('cmt-input')"))
    pg.evaluate("document.activeElement.blur()"); pg.wait_for_timeout(500)
    check('no stray errors in the feed', not [x for x in e.errors if 'ServiceWorker' not in x], e.errors)
    e.close()

    # ---------- the notification switch is renamed ----------
    e = Env(pw, seed()); e.open(); pg = e.page
    pg.evaluate("openProfile('Nina')"); pg.wait_for_timeout(600)
    txt = pg.locator('#notifPrefs').inner_text()
    check('the switch is called Reactions and comments', 'Reactions and comments' in txt and 'comments on your stuff' in txt, txt[:200])
    e.close()

    # ---------- notification prompt ----------
    def prompt(**kw):
        fb = kw.pop('fb', None) or seed()
        e = Env(pw, fb, **kw); e.open(); e.page.wait_for_timeout(600); return e
    e = prompt(ua=ANDROID, notif='default'); pg = e.page
    check('opening the app does not flash a Saved pill', 'show' not in (pg.locator('#saveToast').get_attribute('class') or '') if pg.locator('#saveToast').count() else True)
    card = pg.locator('#notifPromptWrap .notif-prompt')
    check('the prompt sits at the very top of Today', pg.evaluate("(()=>{const w=document.getElementById('notifPromptWrap'); const m=document.querySelector('[data-view=today] .masthead'); return !!(w && m && (w.compareDocumentPosition(m) & Node.DOCUMENT_POSITION_FOLLOWING));})()"))
    check('Android, not set up: asks politely', card.count() == 1 and 'Permission to be a little annoying?' in card.inner_text() and 'turn on' in card.inner_text().lower() and 'not now' in card.inner_text().lower(), card.inner_text() if card.count() else 'no card')
    card.get_by_text('Turn on').click(); pg.wait_for_timeout(800)
    check('Turn on asks the phone for permission', pg.evaluate("window.__NREQ") >= 1)
    pg.locator('#notifPromptWrap .notif-prompt').get_by_text('Not now').click() if pg.locator('#notifPromptWrap .notif-prompt').count() else None
    pg.wait_for_timeout(300)
    check('Not now hides it', pg.locator('#notifPromptWrap .notif-prompt').count() == 0)
    pg.reload(); pg.wait_for_timeout(1500)
    check('and it stays hidden for a while', pg.locator('#notifPromptWrap .notif-prompt').count() == 0)
    e.close()
    e = prompt(ua=IPHONE, notif='default'); pg = e.page
    card = pg.locator('#notifPromptWrap .notif-prompt')
    check('iPhone not on the Home Screen: explains the step', card.count() == 1 and 'Tiny chore before the magic' in card.inner_text() and 'Add to Home Screen' in card.inner_text(), card.inner_text() if card.count() else 'no card')
    card.get_by_text('Got it').click(); pg.wait_for_timeout(200)
    check('Got it hides it', pg.locator('#notifPromptWrap .notif-prompt').count() == 0)
    e.close()
    e = prompt(ua=ANDROID, notif='denied'); pg = e.page
    card = pg.locator('#notifPromptWrap .notif-prompt')
    check('blocked: says how to undo it', card.count() == 1 and 'Someone slammed the door on us' in card.inner_text() and 'Settings' in card.inner_text(), card.inner_text() if card.count() else 'no card')
    e.close()
    fb = seed(); fb['recalData/recal-fcm-token:Nina'] = 'some-device-token'
    e = prompt(ua=ANDROID, notif='granted', fb=fb); pg = e.page
    check('already set up: no card', pg.locator('#notifPromptWrap .notif-prompt').count() == 0)
    e.close()
    e = prompt(ua=ANDROID, notif='granted'); pg = e.page
    check('allowed on the phone but never registered: asks again', pg.locator('#notifPromptWrap .notif-prompt').count() == 1)
    errs = [x for x in e.errors if 'ServiceWorker' not in x]
    check('no stray errors from the prompt', not errs, errs)
    e.close()

    # ---------- the name picker is the first thing a fresh install sees ----------
    IPHONE_STANDALONE_JS = "Object.defineProperty(navigator,'standalone',{get:()=>true})"
    e = Env(pw, seed(), who='', ua=IPHONE, notif='default', height=760)
    e.page.add_init_script(IPHONE_STANDALONE_JS)
    e.open(); pg = e.page; pg.wait_for_timeout(600)
    order = pg.evaluate("""() => { const v = document.querySelector('[data-view=today]'); return [...v.children].slice(0, 4).map(c => c.id || c.className); }""")
    check('on a fresh install the name picker comes first on Today', order[0] == 'identityBanner', order)
    top = pg.evaluate("(()=>{const b=document.getElementById('identityBanner').getBoundingClientRect(); const m=document.querySelector('[data-view=today] .masthead').getBoundingClientRect(); return {bannerTop: Math.round(b.top), mastheadTop: Math.round(m.top), screen: window.innerHeight};})()")
    check('it is on the first screen, above the intro, with no scrolling', top['bannerTop'] < top['mastheadTop'] and top['bannerTop'] < top['screen'] * 0.6, top)
    names = pg.locator('#identityGate button').all_inner_texts()
    check('it offers all four names', [n.title() for n in names] == ['Nina', 'Kellye', 'Lauren', 'Carolina'], names)  # buttons are set in all caps
    check('no notification card yet, because we do not know who she is', pg.locator('#notifPromptWrap .notif-prompt').count() == 0)
    pg.locator('#identityGate button', has_text='Kellye').click(); pg.wait_for_timeout(900)
    check('tapping a name hides the picker', pg.locator('#identityGate').count() == 0 and pg.evaluate("document.getElementById('identityBanner').getBoundingClientRect().height") < 2)
    check('her avatar appears in the corner', pg.evaluate("document.getElementById('topbarAvatar').style.display") != 'none')
    check('and the notifications card appears at the top of Today', pg.locator('#notifPromptWrap .notif-prompt').count() == 1 and 'Permission to be a little annoying?' in pg.locator('#notifPromptWrap').inner_text())
    saved = pg.evaluate("localStorage.getItem('recal-whoami')")
    check('the phone remembers her name', saved == 'Kellye', saved)
    e.close()
    # someone already set up sees no picker and no gap
    e = Env(pw, seed(), ua=ANDROID, notif='granted', height=760); e.open(); pg = e.page; pg.wait_for_timeout(500)
    check('someone already set up sees no picker and no empty gap', pg.locator('#identityGate').count() == 0 and pg.evaluate("document.getElementById('identityBanner').getBoundingClientRect().height") < 2)
    e.close()

print('\n%d checks, %d failed' % (len(res), res.count(False)))
