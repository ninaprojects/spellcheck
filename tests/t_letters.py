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
    check('L2 Opens-on only offers days still ahead (plus Nina\'s one-time option, last)', pg.locator('#letterDaySelect option').all_inner_texts() == ['Oct 10, New Moon in Libra','Oct 25, Full Moon in Taurus','Oct 31, Halloween','Right now (just this once)'])
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
    check('L4 the letter is capped at 600 characters', len(pg.input_value('#letterBodyInput')) <= 600, len(pg.input_value('#letterBodyInput')))
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
    pg.click('#letterSealTap'); pg.wait_for_timeout(1600)
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

    # ---------- Nina's one-time intro letter ("Right now") ----------
    D10b = (2026,10,10,12,0,0)
    e = Env(pw, seed_nina(), now=D10b); e.open(); pg = e.page
    go(pg, 'profile/letters')
    pg.click('#writeLetterBtn'); pg.wait_for_selector('#letterSheet')
    check('L20 Right now is the last option, so it is never the default', pg.locator('#letterDaySelect option').last.inner_text() == 'Right now (just this once)' and pg.input_value('#letterDaySelect') == '25', pg.input_value('#letterDaySelect'))
    pg.select_option('#letterDaySelect', 'now')
    check('L21 Right now locks To to All of us', pg.input_value('#letterToSelect') == 'all' and pg.is_disabled('#letterToSelect'))
    check('L21 Right now shows no idea prompt', pg.inner_text('#letterIdea').strip() == '', pg.inner_text('#letterIdea'))
    pg.select_option('#letterDaySelect', '25')
    check('L21 picking a normal day again frees To and brings the idea back', not pg.is_disabled('#letterToSelect') and 'venus' in pg.inner_text('#letterIdea').lower())
    pg.select_option('#letterDaySelect', 'now')
    pg.fill('#letterBodyInput', 'Dear witches, I made us a mailbox.')
    pg.click('#letterSealBtn'); pg.wait_for_timeout(400)
    saved = json.loads(pg.evaluate("window.__FB['recalData/r2:recal-letters:Nina']"))
    check('L22 it saves to All of us, open today, marked intro, own record only', len(saved) == 1 and saved[0]['to'] == 'all' and saved[0]['opensDay'] == 10 and saved[0].get('intro') is True and saved[0]['body'].startswith('Dear witches'), saved)
    check('L22 the intro mark is never shown in the app', 'intro' not in pg.inner_text('#lettersWrap').lower())
    check('L22 it shows as open right away: from Nina, to all of us, tap to break the seal', 'from nina, to all of us' in pg.inner_text('#lettersList').lower() and 'tap to break the seal' in pg.inner_text('#lettersList').lower(), pg.inner_text('#lettersList'))
    pg.click('#writeLetterBtn'); pg.wait_for_selector('#letterSheet')
    check('L23 once sealed, the option is gone for good', pg.locator('#letterDaySelect option').all_inner_texts() == ['Oct 25, Full Moon in Taurus','Oct 31, Halloween'], pg.locator('#letterDaySelect option').all_inner_texts())
    check('L23 a second intro letter is refused', pg.evaluate("sealLetter('all', 0, 'again', {intro:true})") is False and len(json.loads(pg.evaluate("window.__FB['recalData/r2:recal-letters:Nina']"))) == 1)
    e.close()

    # the intro letter opens like any other, from another phone
    fb = seed_nina()
    fb['recalData/r2:recal-letters:Nina'] = json.dumps([{"id":"Nina:9","to":"all","body":"Dear witches, I made us a mailbox.","opensDay":10,"writtenAt":"2026-10-10T18:00:00.000Z","intro":True}])
    e = Env(pw, fb, who='Kellye', now=D10b); e.open(); pg = e.page
    go(pg, 'profile/letters')
    check('L24 Kellye sees it as from Nina, to all of us, open', 'from nina, to all of us' in pg.inner_text('#lettersList').lower() and 'tap to break the seal' in pg.inner_text('#lettersList').lower(), pg.inner_text('#lettersList'))
    pg.click('.ltr-row'); pg.wait_for_selector('#letterSealTap'); pg.click('#letterSealTap'); pg.wait_for_timeout(1700)
    check('L24 the letter reads after the seal breaks', 'made us a mailbox' in pg.inner_text('.ltr-stage').lower() and 'from nina' in pg.inner_text('.ltr-stage').lower(), pg.inner_text('.ltr-stage'))
    e.close()

    # nobody else is ever offered it, and cannot make one
    e = Env(pw, seed_nina(), who='Kellye', now=D10b); e.open(); pg = e.page
    go(pg, 'profile/letters')
    pg.click('#writeLetterBtn'); pg.wait_for_selector('#letterSheet')
    check('L25 Kellye is not offered Right now', pg.locator('#letterDaySelect option').all_inner_texts() == ['Oct 25, Full Moon in Taurus','Oct 31, Halloween'], pg.locator('#letterDaySelect option').all_inner_texts())
    check('L25 Kellye cannot make an intro letter by calling it directly', pg.evaluate("sealLetter('all', 0, 'sneaky', {intro:true})") is False and not pg.evaluate("window.__FB['recalData/r2:recal-letters:Kellye']"))
    e.close()

    # the round is over: no intro letter either
    e = Env(pw, seed_nina(), now=(2026,11,2,12,0,0)); e.open(); pg = e.page
    go(pg, 'profile/letters')
    check('L26 after the round, the intro letter is not available', pg.evaluate("letterIntroAvailable()") is False)
    e.close()

    # fits at 360 with Right now picked
    e = Env(pw, seed_nina(), width=360, now=D10b); e.open(); pg = e.page
    go(pg, 'profile/letters')
    pg.click('#writeLetterBtn'); pg.wait_for_selector('#letterSheet'); pg.select_option('#letterDaySelect', 'now')
    check('L27 no sideways overflow at 360px with Right now picked', pg.evaluate("document.documentElement.scrollWidth") <= 360, pg.evaluate("document.documentElement.scrollWidth"))
    e.close()


    # ---------- the envelope stays put, whatever the letter length ----------
    LONG_BODY = "Dear Witches, I made us a mailbox. Under the Me tab, tap Letters and write as many as you like, to any of us, all of us, or future you. Seal them for the Full Moon on Oct 25, for Halloween, or for both. Once a letter is sealed it can't be unsent, so say the thing you never say out loud. Say the sweet thing, the silly thing, the thing you'd only say after two drinks. This one's open now. The rest will make us wait. Frankly, we love a tease. Hugs and hexes,"
    seen = {}
    for label, body in (('short', 'See you at the full moon.'), ('long', LONG_BODY)):
        fb = seed_nina()
        fb['recalData/r2:recal-letters:Nina'] = json.dumps([{"id":"Nina:9","to":"all","body":body,"opensDay":10,"writtenAt":"2026-10-10T18:00:00.000Z"}])
        e = Env(pw, fb, who='Kellye', now=D10); e.open(); pg = e.page
        pg.set_viewport_size({'width':390,'height':844})
        go(pg, 'profile/letters'); pg.click('.ltr-row'); pg.wait_for_selector('#letterSealTap'); pg.wait_for_timeout(400)
        b = pg.locator('.ltr-envelope').bounding_box()
        seen[label] = (round(b['y']), round(b['width']), round(b['height']))
        check('L28 %s letter: the sealed envelope is fully on the first screen' % label, b['y'] > 0 and b['y'] + b['height'] <= 844, b)
        pg.click('#letterSealTap'); pg.wait_for_timeout(4800)
        gap = pg.evaluate("(()=>{const st=document.querySelector('.ltr-stage').getBoundingClientRect(), sc=document.querySelector('.ltr-scroll-wrap').getBoundingClientRect(); return Math.round(st.bottom - sc.bottom);})()")
        check('L29 %s letter: no big empty gap under the opened scroll' % label, gap <= 150, gap)
        if label == 'long':
            check('L29 long letter: the scroll starts near the top of the stage', pg.evaluate("(()=>{const st=document.querySelector('.ltr-stage').getBoundingClientRect(), sc=document.querySelector('.ltr-scroll-wrap').getBoundingClientRect(); return Math.round(sc.top - st.top);})()") <= 140)
        else:
            check('L29 short letter: the whole scroll fits on the first screen, centered', pg.evaluate("(()=>{const sc=document.querySelector('.ltr-scroll-wrap').getBoundingClientRect(); return sc.top > 0 && sc.bottom <= 844;})()"), pg.evaluate("(()=>{const sc=document.querySelector('.ltr-scroll-wrap').getBoundingClientRect(); return [Math.round(sc.top), Math.round(sc.bottom)];})()"))
        e.close()
    check('L28 the envelope is the same place and size for short and long letters', seen['short'] == seen['long'], seen)


    # ---------- Launch bundle: line breaks, 600 limit, script From, deeper pink ----------
    e = Env(pw, seed_nina(), now=D8); e.open(); pg = e.page
    go(pg, 'profile/letters')
    pg.click('#writeLetterBtn'); pg.wait_for_selector('#letterSheet')
    check('L30 the counter starts at 600', pg.inner_text('#letterCharCount').strip() == '600 left', pg.inner_text('#letterCharCount'))
    check('L30 the text box allows 600', pg.get_attribute('#letterBodyInput', 'maxlength') == '600')
    pg.fill('#letterBodyInput', 'x' * 700)
    check('L30 a long letter stops at 600', len(pg.input_value('#letterBodyInput')) == 600 and pg.inner_text('#letterCharCount').strip() == '0 left')
    pg.fill('#letterBodyInput', 'Dear Witches,\nI made us a mailbox.   Spaces   collapse.\n\n\n\nHugs and hexes,')
    pg.click('#letterSealBtn'); pg.wait_for_timeout(400)
    sealed = json.loads(pg.evaluate("window.__FB['recalData/r2:recal-letters:Nina']"))
    check('L31 sealing keeps the line breaks you typed', sealed[-1]['body'] == 'Dear Witches,\nI made us a mailbox. Spaces collapse.\n\nHugs and hexes,', sealed[-1]['body'])
    e.close()

    fb = seed_nina()
    fb['recalData/r2:recal-letters:Nina'] = json.dumps([{"id":"Nina:3","to":"all","body":"Dear Witches,\nI made us a mailbox.\nHugs and hexes,","opensDay":10,"writtenAt":"2026-10-10T18:00:00.000Z"}])
    e = Env(pw, fb, who='Kellye', now=D10); e.open(); pg = e.page
    go(pg, 'profile/letters'); pg.click('.ltr-row'); pg.wait_for_selector('#letterSealTap')
    check('L32 the envelope From line is in the handwriting font', 'zeyada' in pg.evaluate("getComputedStyle(document.querySelector('.ltr-tap-hint')).fontFamily").lower())
    pg.click('#letterSealTap'); pg.wait_for_timeout(4800)
    lines = [l for l in pg.inner_text('.ltr-body-text').split('\n') if l.strip()]
    check('L32 the opened letter shows each line on its own line', lines == ['Dear Witches,', 'I made us a mailbox.', 'Hugs and hexes,'], lines)
    check('L32 the sender line in the letter is in the handwriting font', 'zeyada' in pg.evaluate("getComputedStyle(document.querySelector('.ltr-sender-line')).fontFamily").lower())
    pg.click('#letterBackLink'); pg.wait_for_selector('#writeLetterBtn')
    enabled = pg.evaluate("getComputedStyle(document.getElementById('writeLetterBtn')).backgroundColor")
    check('L33 main buttons use the deeper pink', enabled == 'rgb(255, 194, 220)', enabled)
    pg.click('#writeLetterBtn'); pg.wait_for_selector('#letterSheet')
    disabled = pg.evaluate("getComputedStyle(document.getElementById('letterSealBtn')).backgroundColor")
    check('L33 a disabled button stays grey, clearly different', pg.is_disabled('#letterSealBtn') and disabled == 'rgb(247, 242, 244)', disabled)
    e.close()


    # ---------- The opening: bigger envelope, slower, the scroll unrolls, replay works ----------
    fb = seed_nina()
    fb['recalData/r2:recal-letters:Nina'] = json.dumps([{"id":"Nina:5","to":"all","body":"Dear Witches,\nHugs and hexes,","opensDay":10,"writtenAt":"2026-10-10T18:00:00.000Z"}])
    e = Env(pw, fb, who='Kellye', now=D10); e.open(); pg = e.page
    go(pg, 'profile/letters'); pg.click('.ltr-row'); pg.wait_for_selector('#letterSealTap'); pg.wait_for_timeout(300)
    check('L34 the envelope is bigger: 240px tall', round(pg.locator('.ltr-envelope').bounding_box()['height']) == 240, pg.locator('.ltr-envelope').bounding_box())
    pg.click('#letterSealTap'); pg.wait_for_timeout(450)
    check('L35 the seal takes its time: still cracking just after the tap', not pg.evaluate("document.querySelector('.ltr-scroll-wrap').classList.contains('show')") and pg.evaluate("!!document.querySelector('.ltr-envelope.cracked')"))
    pg.wait_for_function("document.querySelector('.ltr-scroll-wrap.show')", timeout=6000)
    pg.wait_for_timeout(1000)   # the scroll has begun to unroll
    h1 = pg.locator('.ltr-unroll').bounding_box()['height']
    pg.wait_for_timeout(3200)
    h2 = pg.locator('.ltr-unroll').bounding_box()['height']
    check('L35 the scroll unrolls: it grows downward as it opens', h2 > h1 + 40, (round(h1), round(h2)))
    check('L35 the unroll ends fully open', pg.evaluate("document.querySelector('.ltr-unroll').classList.contains('unrolled')"))
    # replay: the envelope comes back, and breaking it again opens the letter again
    pg.click('#letterBackLink'); pg.wait_for_selector('[data-reread]')
    pg.click('[data-reread]'); pg.wait_for_selector('#letterReplayLink')
    check('L36 an opened letter shows no envelope until you replay', pg.locator('.ltr-envelope').count() == 0)
    pg.click('#letterReplayLink'); pg.wait_for_timeout(500)
    check('L36 Replay the seal brings the envelope back', pg.locator('.ltr-envelope').count() == 1 and vis(pg, '#letterSealTap'))
    pg.click('#letterSealTap')
    pg.wait_for_function("document.querySelector('.ltr-scroll-wrap.show')", timeout=6000)
    check('L36 breaking it again opens the letter again', True)
    e.close()

    # reduced motion: no animation time on the opening pieces
    fb = seed_nina()
    fb['recalData/r2:recal-letters:Nina'] = json.dumps([{"id":"Nina:6","to":"all","body":"Hi.","opensDay":10,"writtenAt":"2026-10-10T18:00:00.000Z"}])
    e = Env(pw, fb, who='Kellye', now=D10); e.open(); pg = e.page
    pg.emulate_media(reduced_motion='reduce')
    go(pg, 'profile/letters'); pg.click('.ltr-row'); pg.wait_for_selector('#letterSealTap')
    dur = pg.evaluate("[getComputedStyle(document.querySelector('.ltr-unroll')).transitionDuration, getComputedStyle(document.querySelector('.ltr-env-flap')).transitionDuration, getComputedStyle(document.querySelector('.ltr-scroll-wrap')).transitionDuration]")
    check('L37 with Reduce Motion on, the opening has no animation time', all(float(x.split(',')[0].replace('s','')) == 0 for x in dur), dur)
    e.close()


bad = [r for r in res if not r[1]]
print('%d checks, %d failed' % (len(res), len(bad)))
sys.exit(1 if bad else 0)
