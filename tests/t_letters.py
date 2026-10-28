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
    check('L2 Opens-on only offers days still ahead (plus Nina\'s one-time option, last)', pg.locator('#letterDaySelect option').all_inner_texts() == ['Oct 10, New Moon in Libra','Oct 25, Full Moon in Taurus','Oct 29, Gemini Moon','Oct 30, Moon in Cancer','Oct 31, Halloween','Right now (just this once)'])
    check('L2b idea defaults to the self version for Me + Day 10', "being fair to" in pg.inner_text('#letterIdea').lower())
    pg.select_option('#letterToSelect', 'Kellye')
    check('L2c idea switches to the person version for someone else', "never say with a straight face" in pg.inner_text('#letterIdea').lower())
    pg.select_option('#letterToSelect', 'all')
    check('L2d idea switches to the group version for All of us', 'whole coven' in pg.inner_text('#letterIdea').lower())
    pg.select_option('#letterDaySelect', '25')
    check('L2e idea updates for Day 25 too, still the group version', 'venus' in pg.inner_text('#letterIdea').lower() and 'coven' in pg.inner_text('#letterIdea').lower())
    pg.select_option('#letterDaySelect', '29')
    idea = lambda: pg.inner_text('#letterIdea').strip()
    G29_SOME = ["Gemini Moon, the sign of talking, so let's talk. Tell them one thing you love about the way they show up for you.", "Gemini Moon is chatty by nature, so use it. Tell them the nicest thing you've thought about them and never said.", "Gemini Moon loves a good conversation, and this one is a love letter in disguise. Tell them what makes talking to them the best part of your day."]
    G29_ALL = ["Gemini Moon, the sign of talking. Tell the coven what you love about the way the four of us talk to each other.", "Gemini Moon, the sign of talking, and this group has never run out of things to say. Tell the coven what you love about us.", "Gemini Moon is chatty by nature, and so are we. Tell the coven the group-chat moment that still makes you laugh."]
    G29_ME = ["Gemini Moon, the sign of talking, and your mind has been loud all month. Tell future you what it's been saying, with nothing cleaned up.", "Gemini Moon wants the unfiltered version. Tell future you what you actually think, the part you leave out when you talk to everyone else.", "Gemini Moon, the sign of talking, so say the quiet part. Tell future you the one thing you're finally ready to admit."]
    C30_SOME = ["The Moon moves into Cancer, the sign it rules, right after chatty Gemini. Skip the small talk and tell them what you actually feel about them.", "The Moon is home in Cancer, the sign it rules, and Cancer is all about the people who feel like family. Tell them what they mean to you.", "Cancer is the Moon's home sign, known for tenderness. Tell them the moment you knew they were your person."]
    C30_ALL = ["The Moon moves into Cancer, the sign it rules, right after chatty Gemini. Skip the small talk and tell the coven what this group feels like to come home to.", "Cancer is the Moon's home sign, so let's talk about home. Tell the coven what this group has meant to you this month.", "The Moon is home in Cancer, and so is this group. Tell the coven the moment this month you felt most held by us."]
    C30_ME = ["Cancer is the Moon's home sign, and home is where the truth gets quiet. Tell future you what you're still carrying that you wish you could set down.", "The Moon is home in Cancer, so be honest about what home means to you right now. Tell future you what you need more of and what you've outgrown.", "Cancer is the Moon's home sign, known for feeling everything. Tell future you what you've felt this month that you haven't said to anyone."]
    pg.select_option('#letterDaySelect', '29')
    check('L2f Day 29, group: one of the three approved lines', idea() in G29_ALL, idea())
    first29 = idea()
    pg.select_option('#letterToSelect', 'Kellye')
    check('L2g Day 29, person: one of the three approved lines', idea() in G29_SOME, idea())
    pg.select_option('#letterToSelect', 'Nina')
    check('L2g2 Day 29, self: one of the three approved lines', idea() in G29_ME, idea())
    pg.select_option('#letterDaySelect', '30')
    check('L2h Day 30, self: one of the three approved lines', idea() in C30_ME, idea())
    pg.select_option('#letterToSelect', 'Kellye')
    check('L2h2 Day 30, person: one of the three approved lines', idea() in C30_SOME, idea())
    pg.select_option('#letterToSelect', 'all')
    check('L2i Day 30, group: one of the three approved lines', idea() in C30_ALL, idea())
    first30 = idea()
    pg.select_option('#letterDaySelect', '29'); pg.select_option('#letterToSelect', 'all')
    check('L2k the line is steady while the sheet stays open (back to Day 29 + All of us gives the same one)', idea() == first29, (idea(), first29))
    pg.select_option('#letterDaySelect', '30')
    check('L2l same for Day 30 + All of us', idea() == first30, (idea(), first30))
    seen = set()
    for _ in range(14):
        pg.click('#letterCancelBtn'); pg.wait_for_timeout(60)
        pg.click('#writeLetterBtn'); pg.wait_for_selector('#letterSheet')
        pg.select_option('#letterDaySelect', '29'); pg.select_option('#letterToSelect', 'all')
        seen.add(idea())
    check('L2m reopening the sheet rotates through the approved lines (more than one seen, all approved)', len(seen) > 1 and seen <= set(G29_ALL), seen)
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
    check('L23 once sealed, the option is gone for good', pg.locator('#letterDaySelect option').all_inner_texts() == ['Oct 25, Full Moon in Taurus','Oct 29, Gemini Moon','Oct 30, Moon in Cancer','Oct 31, Halloween'], pg.locator('#letterDaySelect option').all_inner_texts())
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
    check('L25 Kellye is not offered Right now', pg.locator('#letterDaySelect option').all_inner_texts() == ['Oct 25, Full Moon in Taurus','Oct 29, Gemini Moon','Oct 30, Moon in Cancer','Oct 31, Halloween'], pg.locator('#letterDaySelect option').all_inner_texts())
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


    # ====================== Letters, part 2: typing, scenes, pill, hint card, dots ======================
    D31 = (2026,10,31,12,0,0)
    BODY = "Dear Witches,\nI made us a mailbox. Write as many as you like, to any of us, all of us, or future you. Seal them for the Full Moon, for Halloween, or for both.\nHugs and hexes,"
    def letters_fb(items, opened_for=None, who_opened=None):
        fb = seed_nina()
        fb['recalData/r2:recal-letters:Nina'] = json.dumps(items)
        if opened_for:
            fb['recalData/r2:recal-letters-opened:' + opened_for] = json.dumps({i['id']: "2026-10-09T20:00:00.000Z" for i in items})
        return fb
    def L(id, day, body=BODY): return {"id": id, "to": "all", "body": body, "opensDay": day, "writtenAt": "2026-10-09T18:00:00.000Z"}

    # --- the letter types itself in, and a tap finishes it ---
    e = Env(pw, letters_fb([L('Nina:1', 10)]), who='Kellye', now=D10); e.open(); pg = e.page
    go(pg, 'profile/letters'); pg.click('.ltr-row'); pg.wait_for_selector('#letterSealTap')
    check('L40 before opening, the From and Plain text controls are not on yet', not pg.evaluate("document.querySelector('.ltr-float-ctl').classList.contains('on')"))
    pg.click('#letterSealTap')
    pg.wait_for_function("document.querySelector('.ltr-scroll-wrap.show')", timeout=6000)
    check('L40 the Plain text pill appears once the letter is open', pg.evaluate("document.querySelector('.ltr-float-ctl').classList.contains('on')"))
    pg.wait_for_timeout(1200)
    check('L41 typing has not started while the scroll is still unrolling', pg.evaluate("document.getElementById('letterTyped').textContent") == '', pg.evaluate("document.getElementById('letterTyped').textContent"))
    check('L41 the full text is already there, invisible, so nothing jumps', pg.evaluate("document.getElementById('letterUntyped').textContent") == BODY)
    pg.wait_for_timeout(2600)
    typed = pg.evaluate("document.getElementById('letterTyped').textContent")
    check('L41 the letter is typing in, one character at a time', 0 < len(typed) < len(BODY) and BODY.startswith(typed), (len(typed), len(BODY)))
    check('L41 the sender line waits until the typing is done', not pg.evaluate("document.querySelector('.ltr-sender-line').classList.contains('ltr-late-on')"))
    pg.click('.ltr-letter-card')
    check('L42 tapping the letter finishes it at once, with the line breaks', pg.evaluate("document.getElementById('letterTyped').textContent") == BODY and pg.evaluate("document.getElementById('letterUntyped').textContent") == '')
    check('L42 then the sender line appears', pg.evaluate("document.querySelector('.ltr-sender-line').classList.contains('ltr-late-on')"))
    e.close()

    # --- Reduce Motion: no typing, the letter simply appears ---
    e = Env(pw, letters_fb([L('Nina:2', 10)]), who='Kellye', now=D10); e.open(); pg = e.page
    pg.emulate_media(reduced_motion='reduce')
    go(pg, 'profile/letters'); pg.click('.ltr-row'); pg.wait_for_selector('#letterSealTap'); pg.click('#letterSealTap')
    pg.wait_for_function("document.querySelector('.ltr-scroll-wrap.show')", timeout=6000); pg.wait_for_timeout(300)
    check('L43 with Reduce Motion on, there is no typing', pg.locator('#letterTyped').count() == 0)
    check('L43 the whole letter and the sender line show straight away', pg.inner_text('.ltr-body-text').strip() == BODY and pg.evaluate("document.querySelector('.ltr-sender-line').classList.contains('ltr-late-on')"))
    e.close()

    # --- the three looks: standard, Full Moon (Oct 25), Halloween (Oct 31) ---
    e = Env(pw, letters_fb([L('Nina:10', 10), L('Nina:25', 25), L('Nina:31', 31)], opened_for='Kellye'), who='Kellye', now=D31); e.open(); pg = e.page
    go(pg, 'profile/letters')
    def scene_of(id):
        pg.evaluate("openLetter(%s)" % json.dumps(id)); pg.wait_for_selector('.ltr-stage'); pg.wait_for_timeout(300)
        r = pg.evaluate("(()=>{const d=(s)=>getComputedStyle(document.querySelector(s)).display; return {cls: document.querySelector('.ltr-stage').className, moon:d('.ltr-moon'), bats:d('.ltr-bat-w'), glow:d('.ltr-hglow'), embers: document.querySelectorAll('.ltr-em').length};})()")
        pg.evaluate("closeLetterReading()"); pg.wait_for_timeout(150)
        return r
    r10, r25, r31 = scene_of('Nina:10'), scene_of('Nina:25'), scene_of('Nina:31')
    check('L44 an ordinary letter keeps the standard look', 'scene-std' in r10['cls'] and r10['moon'] == 'none' and r10['bats'] == 'none', r10)
    check('L44 the Oct 25 letter gets the Full Moon scene', 'scene-moon' in r25['cls'] and r25['moon'] == 'block' and r25['bats'] == 'none', r25)
    check('L44 the Oct 31 letter gets the Halloween scene with bats', 'scene-hallo' in r31['cls'] and r31['bats'] == 'block' and r31['glow'] == 'block' and r31['moon'] == 'none', r31)
    check('L44 every look has embers', r10['embers'] == r25['embers'] == r31['embers'] == 12, (r10['embers'], r25['embers'], r31['embers']))

    # --- the Plain text pill ---
    pg.evaluate("openLetter('Nina:31')"); pg.wait_for_selector('.ltr-stage'); pg.wait_for_timeout(1900)
    font = lambda: pg.evaluate("getComputedStyle(document.querySelector('.ltr-body-text')).fontFamily").lower()
    check('L45 the pill is showing on an open letter', pg.evaluate("document.querySelector('.ltr-float-ctl').classList.contains('on')") and pg.inner_text('#letterPlainLink').strip().lower() == 'plain text')
    check('L45 the letter starts in handwriting', 'zeyada' in font(), font())
    pg.click('#letterPlainLink'); pg.wait_for_timeout(200)
    check('L45 tapping it switches to the regular font and says Handwriting', 'inter' in font() and 'zeyada' not in font() and pg.inner_text('#letterPlainLink').strip().lower() == 'handwriting', font())
    check('L45 the choice is remembered', pg.evaluate("localStorage.getItem('r2-letters-plain')") == '1')
    pg.evaluate("closeLetterReading()"); pg.evaluate("openLetter('Nina:25')"); pg.wait_for_selector('.ltr-stage'); pg.wait_for_timeout(300)
    check('L45 and it carries over to the next letter you open', 'plain' in pg.get_attribute('.ltr-stage', 'class') and 'inter' in font())
    pg.click('#letterPlainLink'); pg.wait_for_timeout(200)
    check('L45 tapping again goes back to handwriting', 'zeyada' in font() and pg.evaluate("localStorage.getItem('r2-letters-plain')") == '0')
    e.close()

    # --- the Halloween bats must never make the page scroll sideways on a small phone ---
    e = Env(pw, letters_fb([L('Nina:31', 31)], opened_for='Kellye'), who='Kellye', now=D31, width=360); e.open(); pg = e.page
    go(pg, 'profile/letters'); pg.evaluate("openLetter('Nina:31')"); pg.wait_for_selector('.ltr-stage'); pg.wait_for_timeout(4000)
    check('L46 no sideways scrolling at 360px with the bats flying', pg.evaluate("document.documentElement.scrollWidth") <= 360, pg.evaluate("document.documentElement.scrollWidth"))
    e.close()

    # --- the one-time "where to find letters" card on Today ---
    e = Env(pw, seed_nina(), now=D8); e.open(); pg = e.page; pg.wait_for_timeout(400)
    txt = pg.inner_text('#lettersHintWrap')
    check('L47 a new person sees the letters card on Today', 'New: sealed letters' in txt and 'tab, then Letters' in txt and 'got it' in txt.lower(), txt)
    pg.click('#lettersHintGot'); pg.wait_for_timeout(200)
    check('L47 Got it makes it go away', pg.inner_text('#lettersHintWrap').strip() == '')
    pg.reload(); pg.wait_for_timeout(1500)
    check('L47 and it stays gone after a reload', pg.inner_text('#lettersHintWrap').strip() == '')
    e.close()
    e = Env(pw, seed_nina(), now=D8); e.open(); pg = e.page; pg.wait_for_timeout(300)
    pg.click('#people button:has-text("Kellye")'); pg.wait_for_timeout(300)
    check("L47 the card never shows on somebody else's page", pg.inner_text('#lettersHintWrap').strip() == '')
    pg.click('#people button:has-text("Nina")'); pg.wait_for_timeout(300)
    check('L47 it is back on your own page', 'New: sealed letters' in pg.inner_text('#lettersHintWrap'))
    e.close()

    # --- the dot on Me while an open letter is waiting ---
    e = Env(pw, letters_fb([L('Nina:3', 10)]), who='Kellye', now=D10); e.open(); pg = e.page; pg.wait_for_timeout(500)
    check('L48 a pink dot sits on the Me tab while a letter is waiting', pg.evaluate("!document.querySelector('.tab-dot').hidden"))
    check('L48 and the Me tab says so to screen readers', 'letter' in (pg.get_attribute('.tabbar .tab[data-tab=profile]', 'aria-label') or '').lower())
    go(pg, 'profile/letters')
    check('L48 the Letters sub-tab has a dot too', pg.locator('#subnav .subnav-link[data-page=letters] .sub-dot').count() == 1)
    pg.click('.ltr-row'); pg.wait_for_selector('#letterSealTap'); pg.click('#letterSealTap')
    pg.wait_for_function("document.querySelector('.ltr-scroll-wrap.show')", timeout=6000); pg.wait_for_timeout(300)
    check('L48 opening the letter clears both dots', pg.evaluate("document.querySelector('.tab-dot').hidden") and pg.locator('#subnav .subnav-link[data-page=letters] .sub-dot').count() == 0)
    e.close()
    e = Env(pw, letters_fb([L('Nina:4', 25)]), who='Kellye', now=D10); e.open(); pg = e.page; pg.wait_for_timeout(500)
    check('L48 a letter that is still locked does not light the dot', pg.evaluate("document.querySelector('.tab-dot').hidden"))
    e.close()

    # --- casting a spell never changes anyone's notification settings ---
    fb = seed_nina()
    fb['recalData/recal-notif-prefs:Nina'] = json.dumps({"reactions": True, "activity": True, "morning": True, "nudge": True})
    fb['recalData/recal-fcm-token:Nina'] = "token-nina-1"
    e = Env(pw, fb, now=D8); e.open(); pg = e.page; pg.wait_for_timeout(500)
    before = pg.evaluate("[window.__FB['recalData/recal-notif-prefs:Nina'], window.__FB['recalData/recal-fcm-token:Nina']]")
    pg.locator('.check-row:has-text("Journaled") .toggle').first.click(); pg.wait_for_timeout(250)
    pg.locator('.check-row:has-text("No phone") .toggle').first.click(); pg.wait_for_timeout(600)
    cast = json.loads(pg.evaluate("window.__FB['recalData/r2:recal:Nina']"))['days']['8']
    after = pg.evaluate("[window.__FB['recalData/recal-notif-prefs:Nina'], window.__FB['recalData/recal-fcm-token:Nina']]")
    check('L49 the spell really was cast (journaled and no phone)', cast.get('journaled') is True and cast.get('noPhone') is True, cast)
    check('L49 casting left her notification switches and phone address untouched', before == after and after[1] == 'token-nina-1', (before, after))
    e.close()


    # ====================== Tapping a letter notification ======================
    SW_STUB = "(()=>{ const sw = new EventTarget(); sw.register = ()=>Promise.resolve({}); sw.ready = Promise.resolve({}); Object.defineProperty(navigator,'serviceWorker',{value:sw,configurable:true}); window.__swStub = sw; })();"
    def two_letters(): return [L('Nina:p2', 10), L('Nina:p3', 10)]
    def on_letters(pg): return pg.evaluate("!!document.querySelector('#subnav .subnav-link.active[data-page=letters]')") and vis(pg, '#lettersWrap')

    # --- the app was closed: the notification opens a link that carries ?push=letters ---
    e = Env(pw, letters_fb([L('Nina:p1', 10)]), who='Kellye', now=D10); e.open(); pg = e.page
    pg.goto('file://' + APP + '?push=letters#profile/letters'); pg.wait_for_timeout(2500)
    check('P1 closed app: the link lands on your Letters page', on_letters(pg))
    check('P1 closed app: with one letter waiting, its envelope is ready to break', vis(pg, '#letterSealTap'))
    check('P1 closed app: the link is tidied up so a refresh does not repeat it', pg.evaluate("location.search") == '')
    e.close()
    e = Env(pw, letters_fb(two_letters()), who='Kellye', now=D10); e.open(); pg = e.page
    pg.goto('file://' + APP + '?push=letters#profile/letters'); pg.wait_for_timeout(2500)
    check('P2 closed app: with two letters waiting it shows the list, not one envelope', on_letters(pg) and pg.locator('.ltr-row').count() == 2 and not vis(pg, '#letterSealTap'), pg.locator('.ltr-row').count())
    e.close()
    e = Env(pw, letters_fb([L('Nina:p4', 25)]), who='Kellye', now=D10); e.open(); pg = e.page
    pg.goto('file://' + APP + '?push=letters#profile/letters'); pg.wait_for_timeout(2500)
    check('P3 closed app: a letter that is still locked is never opened for you', on_letters(pg) and not vis(pg, '#letterSealTap'))
    e.close()
    e = Env(pw, letters_fb([L('Nina:p5', 10)], opened_for='Kellye'), who='Kellye', now=D10); e.open(); pg = e.page
    pg.goto('file://' + APP + '?push=letters#profile/letters'); pg.wait_for_timeout(2500)
    check('P3 closed app: a letter you already opened is not opened again', on_letters(pg) and not vis(pg, '#letterSealTap') and not vis(pg, '.ltr-stage'))
    e.close()
    e = Env(pw, letters_fb([]), who='Kellye', now=D10); e.open(); pg = e.page
    pg.goto('file://' + APP + '?push=letters#profile/letters'); pg.wait_for_timeout(2500)
    check('P3 closed app: with no letters at all it still lands on Letters, no error', on_letters(pg))
    e.close()

    # --- the app was open: the service worker sends the page a message ---
    e = Env(pw, letters_fb([L('Nina:p6', 10)]), who='Kellye', now=D10)
    e.page.add_init_script(SW_STUB); e.open(); pg = e.page; pg.wait_for_timeout(500)
    check('P4 open app: starts on Today, not on Letters', not on_letters(pg))
    pg.evaluate("window.__swStub.dispatchEvent(new MessageEvent('message', {data:{type:'open-letters'}}))"); pg.wait_for_timeout(700)
    check('P4 open app: the message takes you to Letters', on_letters(pg))
    check('P4 open app: with one letter waiting, its envelope is ready', vis(pg, '#letterSealTap'))
    e.close()
    e = Env(pw, letters_fb([L('Nina:p7', 10)]), who='Kellye', now=D10)
    e.page.add_init_script(SW_STUB); e.open(); pg = e.page; pg.wait_for_timeout(500)
    pg.click('#people button:has-text("Nina")'); pg.wait_for_timeout(300)
    pg.evaluate("window.__swStub.dispatchEvent(new MessageEvent('message', {data:{type:'open-letters'}}))"); pg.wait_for_timeout(700)
    check('P5 open app, looking at someone else: it brings you back to your own letters', on_letters(pg) and vis(pg, '#letterSealTap'))
    e.close()
    e = Env(pw, letters_fb(two_letters()), who='Kellye', now=D10)
    e.page.add_init_script(SW_STUB); e.open(); pg = e.page; pg.wait_for_timeout(500)
    pg.evaluate("window.__swStub.dispatchEvent(new MessageEvent('message', {data:{type:'open-letters'}}))"); pg.wait_for_timeout(700)
    check('P6 open app, two letters waiting: shows the list', on_letters(pg) and pg.locator('.ltr-row').count() == 2 and not vis(pg, '#letterSealTap'))
    e.close()
    e = Env(pw, letters_fb([L('Nina:p8', 10)]), who='Kellye', now=D10)
    e.page.add_init_script(SW_STUB); e.open(); pg = e.page; pg.wait_for_timeout(500)
    pg.evaluate("window.__swStub.dispatchEvent(new MessageEvent('message', {data:{type:'something-else'}}))"); pg.wait_for_timeout(500)
    check('P7 open app: a message that is not about letters does nothing', not on_letters(pg))
    e.close()
    e = Env(pw, letters_fb([L('Nina:p9', 10)]), who='Kellye', now=D10)
    e.page.add_init_script(SW_STUB); e.open(); pg = e.page; pg.wait_for_timeout(500)
    pg.evaluate("window.__swStub.dispatchEvent(new MessageEvent('message', {data:{type:'open-letters'}}))"); pg.wait_for_timeout(500)
    pg.click('#letterSealTap')
    pg.wait_for_function("document.querySelector('.ltr-scroll-wrap.show')", timeout=6000)
    check('P8 the envelope you land on really opens the letter', pg.evaluate("document.querySelector('.ltr-scroll-wrap').classList.contains('show')"))
    e.close()


    # ====================== Tapping a notification about a post ======================
    def on_tea(pg): return pg.evaluate("!!document.querySelector('#subnav .subnav-link.active[data-page=tea]')") and vis(pg, '#covenFeed')
    def pulsing(pg): return pg.evaluate("(()=>{const el=document.querySelector('#covenFeed .feed-item.pulse'); return el ? el.dataset.key : null;})()")
    def tea_message(pg, key):
        pg.evaluate("(k)=>window.__swStub.dispatchEvent(new MessageEvent('message', {data:{type:'open-post', key:k}}))", key); pg.wait_for_timeout(700)

    e = Env(pw, seed_nina(), now=D8); e.open(); pg = e.page; pg.wait_for_timeout(500)
    keys = pg.evaluate("Array.from(document.querySelectorAll('#covenFeed .feed-item')).map(x=>x.dataset.key)")
    check('E1 every post in The Tea carries its own key', keys == ['cast:Nina:1', 'photo:Nina:1', 'session:Nina:0:0'], keys)
    e.close()

    # --- the app was closed: the notification opens a link with ?push=tea&post=... ---
    e = Env(pw, seed_nina(), now=D8); e.open(); pg = e.page
    errors = []; pg.on('pageerror', lambda x: errors.append(str(x)))
    pg.goto('file://' + APP + '?push=tea&post=photo%3ANina%3A1#coven/tea')
    pg.wait_for_function("document.querySelector('#covenFeed .feed-item.pulse')", timeout=8000)
    check('E2 closed app: the link lands on The Tea', on_tea(pg))
    check('E2 closed app: the right post is highlighted', pulsing(pg) == 'photo:Nina:1', pulsing(pg))
    check('E2 closed app: that post is scrolled into view', pg.evaluate("(()=>{const el=document.querySelector('#covenFeed .feed-item.pulse'); const r=el.getBoundingClientRect(); return r.bottom>0 && r.top<window.innerHeight;})()"))
    check('E2 closed app: the link is tidied so a refresh does not repeat it', pg.evaluate("location.search") == '' and pg.evaluate("location.hash") == '#coven/tea')
    pg.wait_for_timeout(3400)
    check('E2 closed app: the highlight fades away by itself', pulsing(pg) is None)
    check('E2 closed app: no errors on the way', errors == [], errors)
    e.close()
    e = Env(pw, seed_nina(), now=D8); e.open(); pg = e.page
    pg.goto('file://' + APP + '?push=tea#coven/tea'); pg.wait_for_timeout(2500)
    check('E3 closed app: a link with no post just opens The Tea, nothing highlighted', on_tea(pg) and pulsing(pg) is None)
    e.close()
    e = Env(pw, seed_nina(), now=D8); e.open(); pg = e.page
    errors = []; pg.on('pageerror', lambda x: errors.append(str(x)))
    pg.goto('file://' + APP + '?push=tea&post=cast%3ANobody%3A99#coven/tea'); pg.wait_for_timeout(2500)
    check('E4 closed app: a post that no longer exists lands on The Tea without breaking', on_tea(pg) and pulsing(pg) is None and errors == [], errors)
    e.close()

    # --- the app was open: the service worker sends the page a message ---
    e = Env(pw, seed_nina(), now=D8)
    e.page.add_init_script(SW_STUB); e.open(); pg = e.page; pg.wait_for_timeout(500)
    check('E5 open app: starts on Today, not The Tea', not on_tea(pg))
    tea_message(pg, 'cast:Nina:1')
    check('E5 open app: the message takes you to The Tea', on_tea(pg))
    check('E5 open app: and highlights that post', pulsing(pg) == 'cast:Nina:1', pulsing(pg))
    e.close()
    e = Env(pw, seed_nina(), now=D8)
    e.page.add_init_script(SW_STUB); e.open(); pg = e.page; pg.wait_for_timeout(500)
    pg.evaluate("feedShowCount = 1; renderCovenFeed();")
    check('E6 a long feed starts short (only one post showing)', pg.locator('#covenFeed .feed-item').count() == 1)
    tea_message(pg, 'session:Nina:0:0')
    check('E6 open app: a post further down is brought into the list', pg.locator('#covenFeed .feed-item').count() == 3 and pulsing(pg) == 'session:Nina:0:0', (pg.locator('#covenFeed .feed-item').count(), pulsing(pg)))
    e.close()
    e = Env(pw, seed_nina(), now=D8)
    e.page.add_init_script(SW_STUB); e.open(); pg = e.page; pg.wait_for_timeout(500)
    tea_message(pg, None)
    check('E7 open app: a message with no post just opens The Tea', on_tea(pg) and pulsing(pg) is None)
    e.close()
    e = Env(pw, seed_nina(), now=D8)
    e.page.add_init_script(SW_STUB); e.open(); pg = e.page; pg.wait_for_timeout(500)
    errors = []; pg.on('pageerror', lambda x: errors.append(str(x)))
    tea_message(pg, 'photo:Kellye:99')
    check('E8 open app: an unknown post lands on The Tea without breaking', on_tea(pg) and pulsing(pg) is None and errors == [], errors)
    e.close()


    # ---------- Letters waiting cards on Today ----------
    D28 = (2026,10,28,12,0,0)
    D29 = (2026,10,29,12,0,0)
    D31 = (2026,10,31,12,0,0)
    A_BODY = ["It's open and it's waiting, and we are not going to be normal about this until you've read it.", "Someone sat down and got sentimental about you. Go see how sweet it is.", "Feelings were put in writing and the seal is ready. Open it before we do."]
    B_BODY = ["Everyone is writing something. Don't be the one who shows up empty-handed.", "Three people could be sealing a letter to you right now. Write yours and find out who's feeling brave.", "Write yours today, because a letter you didn't send can't make anyone cry."]
    C_PAIRS = [("One letter. One condition.", "Cast today's spell and the seal breaks itself. We don't make the rules, we just enforce them."), ("Not so fast.", "The letter is right there. Cast today's spell first, then we'll let you in."), ("Pay to play.", "The price is one spell. Cast today's, then read what they wrote."), ("Your letter is being held hostage.", "The ransom is today's spell. Cast it and we'll release it.")]
    def letter_fb(opens=25, frm='Carolina'):
        fb = seed_nina()
        fb['recalData/r2:recal-letters:' + frm] = json.dumps([{"id": frm + ":1", "to": "Nina", "body": "Hi.", "opensDay": opens, "writtenAt": "2026-10-05T00:00:00.000Z"}])
        return fb
    txt = lambda pg, sel: pg.inner_text(sel).strip()

    e = Env(pw, letter_fb(25), now=D8); e.open(); pg = e.page; go(pg, 'today')
    check('W1 locked letter: no Letters-waiting card A, only the countdown', pg.locator('#lettersWaitingWrap .lw-card').count() == 1 and 'next letter night' in txt(pg, '#lettersWaitingWrap').lower(), txt(pg, '#lettersWaitingWrap'))
    check('W1 card B title names the next night and the weekday', txt(pg, '#lettersWaitingWrap .lw-title') == 'New Moon in Libra, Saturday.', txt(pg, '#lettersWaitingWrap .lw-title'))
    check('W1 card B body is one of the three approved lines', txt(pg, '#lettersWaitingWrap .lw-body') in B_BODY, txt(pg, '#lettersWaitingWrap .lw-body'))
    before = txt(pg, '#lettersWaitingWrap')
    pg.evaluate("renderLettersWaiting(); renderLettersWaiting();"); 
    check('W2 re-rendering does not change the words', txt(pg, '#lettersWaitingWrap') == before)
    pg.click('#lwWriteBtn'); pg.wait_for_selector('#letterSheet')
    check('W3 card B link opens the write-a-letter sheet', vis(pg, '#letterSheet'))
    e.close()

    e = Env(pw, letter_fb(10), now=D10); e.open(); pg = e.page; go(pg, 'today')
    cards_txt = pg.locator('#lettersWaitingWrap .lw-card').all_inner_texts()
    check('W4 open letter: card A first, then card B', len(cards_txt) == 2 and 'sealed for you' in cards_txt[0].lower() and 'next letter night' in cards_txt[1].lower(), cards_txt)
    check('W4 card A names the sender and uses an approved body', txt(pg, '#lettersWaitingWrap .lw-card:first-child .lw-title') == 'Carolina wrote you something.' and txt(pg, '#lettersWaitingWrap .lw-card:first-child .lw-body') in A_BODY, txt(pg, '#lettersWaitingWrap'))
    check('W4 card A is not the dark gated card on Day 10', pg.locator('#lettersWaitingWrap .lw-gate').count() == 0)
    pg.click('#lwOpenBtn'); pg.wait_for_timeout(300)
    check('W5 Break the seal goes to the Letters page', 'profile/letters' in pg.evaluate('location.hash'), pg.evaluate('location.hash'))
    e.close()

    fb = letter_fb(10, 'Kellye'); 
    fb['recalData/r2:recal-letters:Lauren'] = json.dumps([{"id":"Lauren:1","to":"all","body":"Hi all.","opensDay":10,"writtenAt":"2026-10-05T00:00:00.000Z"}])
    e = Env(pw, fb, now=D10); e.open(); pg = e.page; go(pg, 'today')
    check('W6 two open letters: the title says how many', txt(pg, '#lettersWaitingWrap .lw-card:first-child .lw-title') == 'Two letters are waiting for you.', txt(pg, '#lettersWaitingWrap .lw-card:first-child .lw-title'))
    e.close()

    e = Env(pw, letter_fb(25), now=D28); e.open(); pg = e.page; go(pg, 'today')
    check('W7 Oct 28: an open letter is card A, the gate does not start until Oct 29', pg.locator('#lettersWaitingWrap .lw-gate').count() == 0 and pg.locator('#lwOpenBtn').count() == 1)
    check('W7 card B counts down to Gemini Moon, Thursday', txt(pg, '#lettersWaitingWrap .lw-card:last-child .lw-title') == 'Gemini Moon, Thursday.', txt(pg, '#lettersWaitingWrap'))
    e.close()

    e = Env(pw, letter_fb(25), now=D29, width=360); e.open(); pg = e.page; go(pg, 'today')
    ct = (txt(pg, '#lettersWaitingWrap .lw-gate .lw-title'), txt(pg, '#lettersWaitingWrap .lw-gate .lw-body'))
    check('W8 Oct 29, spell not cast: the dark gated card C shows, one approved pair', pg.locator('#lettersWaitingWrap .lw-gate').count() == 1 and ct in C_PAIRS, ct)
    check('W8 card C has Cast today\u2019s spell and no Break the seal', 'cast today' in txt(pg, '#lwCastBtn').lower() and pg.locator('#lwOpenBtn').count() == 0)
    check('W8 card B shows Moon in Cancer, Friday', txt(pg, '#lettersWaitingWrap .lw-card:last-child .lw-title') == 'Moon in Cancer, Friday.', txt(pg, '#lettersWaitingWrap'))
    check('W8 no sideways overflow at 360px', pg.evaluate("document.documentElement.scrollWidth") <= 360, pg.evaluate("document.documentElement.scrollWidth"))
    pg.evaluate("(()=>{const d=dayData('Nina',29); d.journaled=true; d.noPhone=true; renderLettersWaiting();})()")
    check('W9 once today\u2019s spell is cast, card C flips to card A', pg.locator('#lettersWaitingWrap .lw-gate').count() == 0 and pg.locator('#lwOpenBtn').count() == 1 and txt(pg, '#lettersWaitingWrap .lw-card:first-child .lw-title') == 'Carolina wrote you something.', txt(pg, '#lettersWaitingWrap'))
    pg.evaluate("(()=>{const d=dayData('Nina',29); d.journaled=false; d.noPhone=false; renderLettersWaiting();})()")
    go(pg, 'profile/letters')
    check('W10 the gate is a nudge only: the Letters page still opens the letter', 'tap to break the seal' in pg.inner_text('#lettersList').lower())
    e.close()

    e = Env(pw, letter_fb(25), now=D31); e.open(); pg = e.page; go(pg, 'today')
    check('W11 Oct 31, spell not cast: card C still applies, and no card B (no letter night left)', pg.locator('#lettersWaitingWrap .lw-gate').count() == 1 and 'next letter night' not in txt(pg, '#lettersWaitingWrap').lower(), txt(pg, '#lettersWaitingWrap'))
    e.close()

    e = Env(pw, seed_nina(), now=D26); e.open(); pg = e.page; go(pg, 'today')
    check('W12 no letters and Oct 26: only card B, for Gemini Moon', pg.locator('#lettersWaitingWrap .lw-card').count() == 1 and txt(pg, '#lettersWaitingWrap .lw-title') == 'Gemini Moon, Thursday.', txt(pg, '#lettersWaitingWrap'))
    e.close()


bad = [r for r in res if not r[1]]
print('%d checks, %d failed' % (len(res), len(bad)))
sys.exit(1 if bad else 0)
