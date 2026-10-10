import os
import sys, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h import *

res = []
def check(name, ok, detail=''):
    res.append((name, bool(ok), detail)); print(('PASS ' if ok else 'FAIL ') + name + (('  [' + str(detail) + ']') if detail and not ok else ''))
def go(pg, h):
    pg.evaluate("location.hash=%s; 0;" % json.dumps(h)); pg.wait_for_timeout(350)
def vis(pg, sel):
    return pg.evaluate("(s)=>{const e=document.querySelector(s); return !!e && !!(e.offsetWidth||e.offsetHeight) && !e.closest('[hidden]');}", sel)

D8 = (2026,10,8,12,0,0)   # before Day 10 (New Moon in Libra)
D10 = (2026,10,10,12,0,0) # Day 10 itself
D26 = (2026,10,26,12,0,0) # after Day 25 (Full Moon in Taurus), before Halloween

with sync_playwright() as pw:
    # ---------- writing a letter ----------
    e = Env(pw, seed_nina(), now=D8); e.open(); pg = e.page
    go(pg, 'profile/letters')
    check('L1 Letters page shows the empty state', 'nothing sealed yet' in pg.inner_text('#lettersWrap').lower())
    pg.click('#writeLetterBtn'); pg.wait_for_selector('#letterSheet')
    check('L2 To options are Me, the other three, and All of us', pg.locator('#letterToSelect option').all_inner_texts() == ['Me','Kellye','Lauren','Carolina','All of us'])
    check('L2 Opens-on only offers days still ahead', pg.locator('#letterDaySelect option').all_inner_texts() == ['Oct 10, New Moon in Libra','Oct 25, Full Moon in Taurus','Oct 31, Halloween'])
    check('L2b idea defaults to the self version for Me + Day 10', "being fair to" in pg.inner_text('#letterIdea').lower())
    pg.select_option('#letterToSelect', 'Kellye')
    check('L2c idea switches to the person version for someone else', "never say with a straight face" in pg.inner_text('#letterIdea').lower())
    pg.select_option('#letterToSelect', 'all')
    check('L2d idea switches to the group version for All of us', 'whole coven' in pg.inner_text('#letterIdea').lower())
    pg.select_option('#letterDaySelect', '25')
    check('L2e idea updates for Day 25 too, still the group version', 'venus' in pg.inner_text('#letterIdea').lower() and 'coven' in pg.inner_text('#letterIdea').lower())
    pg.select_option('#letterToSelect', 'Nina')
    pg.select_option('#letterDaySelect', '10')
    check('L3 Seal it starts disabled', pg.is_disabled('#letterSealBtn'))
    pg.fill('#letterBodyInput', 'x' * 600)
    check('L4 the letter is capped at 500 characters', len(pg.input_value('#letterBodyInput')) <= 500, len(pg.input_value('#letterBodyInput')))
    pg.fill('#letterBodyInput', 'Dear future me, you did the thing.')
    check('L4 Seal it enables once there is text', not pg.is_disabled('#letterSealBtn'))
    pg.select_option('#letterDaySelect', '10')
    pg.click('#letterSealBtn'); pg.wait_for_timeout(400)
    check('L5 sealing closes the sheet', not vis(pg, '#letterSheet'))
    saved = json.loads(pg.evaluate("window.__FB['recalData/r2:recal-letters:Nina']"))
    check('L5 saved under the round key, own record only', len(saved) == 1 and saved[0]['to'] == 'Nina' and saved[0]['body'].startswith('Dear future me'), saved)
    check('L6 the new row reads From you, to you', 'from you, to you' in pg.inner_text('#lettersList').lower())
    check('L6 a locked row shows the days-until count, not the body', 'dear future me' not in pg.inner_text('#lettersList').lower())
    e.close()

    # ---------- a locked letter nudges instead of opening ----------
    fb = seed_nina()
    fb['recalData/r2:recal-letters:Carolina'] = json.dumps([{"id":"Carolina:1","to":"Nina","body":"Secret stuff.","opensDay":25,"writtenAt":"2026-10-05T00:00:00.000Z"}])
    e = Env(pw, fb, now=D8); e.open(); pg = e.page
    go(pg, 'profile/letters')
    check('L7 the row says From Carolina', 'from carolina' in pg.inner_text('#lettersList').lower())
    check('L7 shows days left, not the body', 'secret stuff' not in pg.inner_text('#lettersList').lower() and '17 day' in pg.inner_text('#lettersList').lower(), pg.inner_text('#lettersList'))
    pg.click('.ltr-row[data-locked="1"]'); pg.wait_for_timeout(200)
    check('L8 tapping a locked row shakes and shows a not-yet message, never the letter', 'not yet' in pg.inner_text('#lettersList').lower() and 'secret stuff' not in pg.inner_text('#lettersList').lower())
    check('L8 reading view never opened', not vis(pg, '.ltr-stage'))
    e.close()

    # ---------- breaking the seal on an unlocked letter ----------
    fb = seed_nina()
    fb['recalData/r2:recal-letters:Carolina'] = json.dumps([{"id":"Carolina:1","to":"Nina","body":"You are doing better than you think.","opensDay":10,"writtenAt":"2026-10-05T00:00:00.000Z"}])
    e = Env(pw, fb, now=D10); e.open(); pg = e.page
    go(pg, 'profile/letters')
    check('L9 an unlocked row says tap to break the seal', 'tap to break the seal' in pg.inner_text('#lettersList').lower())
    pg.click('.ltr-row[data-locked="0"]'); pg.wait_for_timeout(200)
    check('L10 the reveal stage opens, sealed', vis(pg, '.ltr-stage') and vis(pg, '#letterSealTap'))
    check('L10 the letter text is not revealed yet', pg.evaluate("!document.querySelector('.ltr-scroll-wrap').classList.contains('show')"))
    pg.click('#letterSealTap'); pg.wait_for_timeout(1000)
    check('L11 the letter reveals after the crack', 'doing better than you think' in pg.inner_text('.ltr-stage').lower())
    check('L11 the sender line shows', 'from carolina' in pg.inner_text('.ltr-stage').lower())
    opened = json.loads(pg.evaluate("window.__FB['recalData/r2:recal-letters-opened:Nina']"))
    check('L12 opening writes to my own opened record, not Carolina’s', 'Carolina:1' in opened, opened)
    carolina_untouched = pg.evaluate("window.__FB['recalData/r2:recal-letters:Carolina']")
    check('L12 Carolina’s own letter record is never written by me', carolina_untouched == fb['recalData/r2:recal-letters:Carolina'])
    pg.click('#letterBackLink'); pg.wait_for_timeout(300)
    check('L13 back to letters moves it under Opened letters', 'opened letters' in pg.inner_text('#lettersWrap').lower() and 'read again' in pg.inner_text('#lettersWrap').lower())
    pg.click('[data-reread]'); pg.wait_for_timeout(300)
    check('L14 Read again shows the letter straight away, no envelope', vis(pg, '.ltr-stage') and not vis(pg, '#letterSealTap') and 'doing better than you think' in pg.inner_text('.ltr-stage').lower())
    check('L14 Replay the seal is offered', vis(pg, '#letterReplayLink'))
    e.close()

    # ---------- a letter to all of us shows for every recipient ----------
    fb = seed_nina()
    fb['recalData/r2:recal-letters:Kellye'] = json.dumps([{"id":"Kellye:1","to":"all","body":"Proud of all of us this month.","opensDay":10,"writtenAt":"2026-10-05T00:00:00.000Z"}])
    e = Env(pw, fb, now=D10); e.open(); pg = e.page
    go(pg, 'profile/letters')
    check('L15 a letter to all of us shows in my inbox', 'from kellye, to all of us' in pg.inner_text('#lettersList').lower())
    e.close()

    # ---------- after the round ends, every letter is unlocked and nothing is left to seal ----------
    fb = seed_nina()
    fb['recalData/r2:recal-letters:Carolina'] = json.dumps([{"id":"Carolina:1","to":"Nina","body":"Last one.","opensDay":31,"writtenAt":"2026-10-05T00:00:00.000Z"}])
    e = Env(pw, fb, now=(2026,11,2,12,0,0)); e.open(); pg = e.page
    go(pg, 'profile/letters')
    check('L16 after the round, a letter for Day 31 reads as unlocked', 'tap to break the seal' in pg.inner_text('#lettersList').lower())
    pg.click('#writeLetterBtn'); pg.wait_for_timeout(200)
    check('L17 with no astro day left, Write a letter says so instead of a broken form', 'no astro day left' in pg.inner_text('#letterSheet').lower(), pg.inner_text('#letterSheet'))
    e.close()

    # ---------- Letters is hidden on someone else's profile ----------
    e = Env(pw, seed_nina(), now=D8); e.open(); pg = e.page
    go(pg, 'profile')
    pg.evaluate("openProfile('Kellye')"); pg.wait_for_timeout(400)
    check('L18 someone else\'s profile has no Letters page', not pg.locator('#subnav .subnav-link[data-page=letters]').count())
    e.close()

    # no sideways scroll at 360
    e = Env(pw, seed_nina(), width=360, now=D8); e.open(); pg = e.page
    go(pg, 'profile/letters')
    check('L19 no sideways overflow at 360px', pg.evaluate("document.documentElement.scrollWidth") <= 360, pg.evaluate("document.documentElement.scrollWidth"))
    e.close()

bad = [r for r in res if not r[1]]
print('%d checks, %d failed' % (len(res), len(bad)))
sys.exit(1 if bad else 0)
