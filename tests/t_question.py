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

def qa(t, at='2026-10-08T15:00:00.000Z'): return {"t": t, "at": at}
D8 = (2026,10,8,12,0,0)

with sync_playwright() as pw:
    # Day 1 to 7: no question
    e = Env(pw, seed_nina()); e.open(); pg = e.page
    check('Q0 no question card before Day 6', not vis(pg, '#questionWrap .qa-card'))
    e.close()

    # Day 6 and 7 have questions now
    for d,frag in ((6,'like more than you did a year ago'),(7,'deep breath')):
        e = Env(pw, seed_nina(), now=(2026,10,d,12,0,0)); e.open(); pg = e.page
        check('Q0 Day %d has a brew' % d, vis(pg, '#questionWrap .qa-card') and frag in pg.inner_text('#questionWrap'), pg.inner_text('#questionWrap')[:100])
        e.close()

    # Day 8, nobody answered yet
    e = Env(pw, seed_nina(), now=D8); e.open(); pg = e.page
    check('Q1 the card shows on Day 8', vis(pg, '#questionWrap .qa-card'))
    check('Q1 it asks the Day 8 question', 'said no to' in pg.inner_text('#questionWrap').lower(), pg.inner_text('#questionWrap')[:120])
    check('Q1 Spill it is disabled when empty', pg.is_disabled('#qaCast'))
    check('Q1 no spoiler note when nobody has answered', 'no spoilers' not in pg.inner_text('#questionWrap').lower())
    pg.fill('#qaInput', 'x' * 200)
    check('Q2 answers are capped at 140', len(pg.input_value('#qaInput')) <= 140, len(pg.input_value('#qaInput')))
    pg.fill('#qaInput', 'A 6am call that could have been an email.')
    check('Q2 Spill it enables once there is text', not pg.is_disabled('#qaCast'))
    pg.click('#qaCast'); pg.wait_for_timeout(600)
    check('Q3 answering folds the card', not vis(pg, '#qaInput') and 'a 6am call' in pg.inner_text('#questionWrap').lower())
    check('Q3 others show Still thinking', pg.inner_text('#questionWrap').lower().count('still thinking') == 3, pg.inner_text('#questionWrap'))
    saved = pg.evaluate("window.__FB['recalData/r2:recal-qa:Nina']")
    check('Q3 saved under the round key, own record only', saved and json.loads(saved)['8']['t'].startswith('A 6am'), saved)
    pg.click('#qaEdit'); pg.wait_for_timeout(250)
    check('Q4 Edit reopens the input with the answer', vis(pg, '#qaInput') and pg.input_value('#qaInput').startswith('A 6am'))
    pg.fill('#qaInput', 'Saying no to a 6am call.'); pg.click('#qaCast'); pg.wait_for_timeout(600)
    d = json.loads(pg.evaluate("window.__FB['recalData/r2:recal-qa:Nina']"))
    check('Q4 edit replaces the text and keeps the first time', d['8']['t'] == 'Saying no to a 6am call.' and d['8']['at'], d)
    e.close()

    # Day 8, Kellye already answered, Nina has not
    fb = seed_nina(); fb['recalData/r2:recal-qa:Kellye'] = json.dumps({"8": qa('Dinner with people I do not like.')})
    e = Env(pw, fb, now=D8); e.open(); pg = e.page
    t = pg.inner_text('#questionWrap').lower()
    check('Q5 unanswered card says who already answered, no answer shown', 'kellye already answered' in t and 'dinner with people' not in t, t)
    go(pg, 'coven'); pg.wait_for_timeout(300)
    feed = pg.inner_text('#covenFeed').lower()
    check('Q6 Tea shows the question post, answers locked', "day 8" in feed and 'dinner with people' not in feed, feed[:300])
    # answer, then everything reveals
    go(pg, 'today'); pg.fill('#qaInput', 'The gym at 5.'); pg.click('#qaCast'); pg.wait_for_timeout(600)
    check('Q7 answering shows the strip with Kellye\'s answer', 'dinner with people' in pg.inner_text('#questionWrap').lower())
    go(pg, 'coven'); pg.wait_for_timeout(300)
    feed = pg.inner_text('#covenFeed').lower()
    check('Q8 Tea reveals answers once you answered', 'dinner with people' in feed and 'the gym at 5' in feed)
    e.close()

    # A past day: revealed to everyone, even a non-answerer
    fb = seed_nina(); fb['recalData/r2:recal-qa:Kellye'] = json.dumps({"8": qa('Old answer from Kellye.')})
    e = Env(pw, fb, now=(2026,10,10,12,0,0)); e.open(); pg = e.page
    go(pg, 'coven'); pg.wait_for_timeout(300)
    check('Q9 past days are open without answering', 'old answer from kellye' in pg.inner_text('#covenFeed').lower(), pg.inner_text('#covenFeed')[:300])
    # reaction on an answer
    n = pg.locator('#covenFeed .qa-ans .react-chip').count()
    check('Q10 an answer has reaction chips', n > 0, n)
    pg.locator('#covenFeed .qa-ans .react-chip').first.click(); pg.wait_for_timeout(600)
    ks = pg.evaluate("Object.keys(window.__FB).filter(k=>k.indexOf('qa%3A')>=0||k.indexOf('qa:Kellye')>=0)")
    check('Q10 reacting saves under the answer id', len(ks) > 0, pg.evaluate("Object.keys(window.__FB)"))
    # Card is on own Today only
    go(pg, 'profile')
    check('Q11 no question card off Today', not vis(pg, '#questionWrap .qa-card'))
    e.close()

    # Snapshot round trip
    fb = seed_nina(); fb['recalData/r2:recal-qa:Kellye'] = json.dumps({"8": qa('Snap answer.')})
    e = Env(pw, fb, now=D8); e.open(); pg = e.page
    snap = pg.evaluate("JSON.parse(localStorage.getItem('recal-snapshot-r2')||'{}').qa")
    check('Q12 snapshot carries answers', snap and snap.get('Kellye', {}).get('8'), snap)
    e.close()

bad = [r for r in res if not r[1]]
print('%d checks, %d failed' % (len(res), len(bad)))
sys.exit(1 if bad else 0)
