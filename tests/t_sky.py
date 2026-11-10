"""Sky: calm Today card, event colours, Read your sky pop-out (one scroll, houses in the planet chips, people, dismiss). Firebase blocked, clock pinned."""
import os, sys, datetime
from playwright.sync_api import sync_playwright
APP=os.path.abspath(os.environ.get('SPELLCHECK_HABITS', os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','index.html')))
fails=0;checks=0
def ck(n,ok):
    global fails,checks;checks+=1
    if not ok: fails+=1;print('FAIL',n)
INIT="""localStorage.setItem('h3-whoami','Nina');localStorage.setItem('h3c-prof-Nina',JSON.stringify({setup:true,name:'Nina',big3:{sun:'Aquarius',moon:'Aquarius',rising:'Sagittarius'}}));localStorage.setItem('h3c-prof-Kellye',JSON.stringify({setup:true,name:'Kellye'}));"""
with sync_playwright() as pw:
    b=pw.chromium.launch()
    def new(date,w=390):
        c=b.new_context(viewport={'width':w,'height':800});p=c.new_page()
        p.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
        p.clock.install(time=datetime.datetime.fromisoformat(date+'T12:00:00'));p.add_init_script(INIT);return p
    for date,cls,tag in [('2026-11-06','tc','Moon in Libra'),('2026-11-08','tc new','New Moon in Scorpio'),('2026-11-13','tc retro','Mercury and Venus turn forward'),('2026-11-24','tc full','Full Moon in Gemini')]:
        p=new(date);errs=[];p.on('pageerror',lambda e:errs.append(str(e)))
        p.goto('file://'+APP+'#today');p.wait_for_selector('.tc')
        ck(date+' class',p.get_attribute('.tc','class').strip()==cls)
        ck(date+' tag',tag in p.inner_text('.tc .tag'))
        ck(date+' card shows her personal headline',p.evaluate("document.querySelector('.tc .mood').textContent===forecastFor('Nina',todayK()).headline"))
        ck(date+' no paragraph on card',p.locator('.tc .para').count()==0)
        ck(date+' label above card',p.locator('.skylab:has-text("Your sky today")').count()==1)
        ck(date+' no errors',not errs)
    p=new('2026-11-06');p.goto('file://'+APP+'#today');p.wait_for_selector('.tc')
    p.click('.tlink');p.wait_for_selector('.skybox')
    ck('pop-out opens',p.locator('.skybox').count()==1 and p.locator('.skyscrim').count()==1)
    ck('four people tabs',p.locator('.skybox .who button').count()==4)
    ck('one scroll: no tabs',p.locator('.skybox .tabs').count()==0 and p.locator('[data-act=skytab]').count()==0)
    ck('Sun, Moon, Rising rows then the chart section',p.locator('.skybox .srow').count()>=4 and p.locator('.skybox .skylab:has-text("In your chart today")').count()==1)
    ck('planet chips name the house',p.locator('.skybox .chipx:has-text("house")').count()>=1)
    ck('no old paragraph in the pop-out',p.locator('.skybox .tc .para').count()==0)
    ck('coming up three',p.locator('.skybox .up').count()==3)
    p.click('[data-act=skywho][data-p=Kellye]')
    ck('no-chart person gets add box',p.locator('.addbox').count()==1)
    ck('card not clipped',p.evaluate("(()=>{const c=document.querySelector('.skybox .tc').getBoundingClientRect();const r=document.querySelector('.skybox .srow,.skybox .addbox').getBoundingClientRect();return r.top>=c.bottom-1})()"))
    p.click('.skyscrim',position={'x':5,'y':5});p.wait_for_timeout(300)
    ck('tap outside closes',p.locator('.skybox').count()==0 and p.url.endswith('#today'))
    p.goto('file://'+APP+'#sky');p.wait_for_selector('.skybox');p.keyboard.press('Escape');p.wait_for_timeout(300)
    ck('escape closes',p.locator('.skybox').count()==0)
    ck('approved headline bank is complete (12 signs x 12 moons x 7)',p.evaluate("Object.keys(SKY_HEAD).length===12&&Object.values(SKY_HEAD).every(m=>Object.keys(m).length===12&&Object.values(m).every(l=>l.length===7))"))
    ck('approved row sentences are complete (18 Sun, 18 Moon, 24 Rising)',p.evaluate("Object.values(SKY_ROWS.Sun).flat().length===18&&Object.values(SKY_ROWS.Moon).flat().length===18&&Object.values(SKY_ROWS.Rising).flat().length===24"))
    ck('no em dashes in the sky copy',p.evaluate("!/\\u2014/.test(JSON.stringify([SKY_HEAD,SKY_ROWS]))"))
    ck('sign relations',p.evaluate("skyRel('Aquarius','Libra')==='element'&&skyRel('Aries','Aries')==='same'&&skyRel('Aries','Libra')==='opposite'&&skyRel('Aries','Cancer')==='tense'&&skyRel('Aries','Gemini')==='friendly'&&skyRel('Aries','Taurus')==='quiet'"))
    ck('today headline comes from the bank for her Sun sign and the Moon sign',p.evaluate("SKY_HEAD.Aquarius.Libra.includes(forecastFor('Nina',todayK()).headline)"))
    p.goto('file://'+APP+'#sky');p.wait_for_selector('.skybox');p.click('[data-act=skywho][data-p=Nina]')
    sds=p.evaluate("[...document.querySelectorAll('.skybox .srow .sd')].map(e=>e.textContent)")
    ck('Sun row sentence is from the approved list',sds[0] in p.evaluate("SKY_ROWS.Sun.element"))
    ck('Moon row sentence is from the approved list',sds[1] in p.evaluate("SKY_ROWS.Moon.element"))
    ck('Rising row sentence is from the 11th house list',sds[2] in p.evaluate("SKY_ROWS.Rising['11']"))
    p.screenshot(path='/tmp/sky_rows.png')
    p.keyboard.press('Escape');p.wait_for_timeout(300)
    for w in (360,430):
        q=new('2026-11-06',w);q.goto('file://'+APP+'#sky');q.wait_for_selector('.skybox')
        ck(f'{w} no sideways scroll',q.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        ck(f'{w} people row one line',q.evaluate("new Set([...document.querySelectorAll('.skybox .who button,.skybox .sbh .link')].map(e=>Math.round(e.getBoundingClientRect().top))).size===1"))
        ck(f'{w} badges are drawn at one size',q.evaluate("(()=>{const s=[...document.querySelectorAll('.skybox .srow .sbadge svg')].map(e=>Math.round(e.getBoundingClientRect().width));return s.length>=4&&new Set(s).size===1})()"))
        ck(f'{w} chart section does not overflow',q.evaluate("[...document.querySelectorAll('.skybox .srow')].every(e=>e.getBoundingClientRect().right<=innerWidth)"))
    # houses: data, chips, lines, aspect, event line, no-Rising fallback
    ck('house lines complete (Venus 59, New Moon 33, Sun 37, Mercury 36, Mars 37, Full Moon 38)',p.evaluate("(()=>{const c={Venus:59,'New Moon':33,Sun:37,Mercury:36,Mars:37,'Full Moon':38};return Object.keys(c).every(k=>{const h=HOUSE_LINES[k];return h&&Object.keys(h).length===12&&Object.values(h).flat().length===c[k]&&Object.values(h).every(a=>a.length>=1)})})()"))
    ck('house lines: no em dashes, no exclamation points, under 110 characters',p.evaluate("Object.values(HOUSE_LINES).every(h=>Object.values(h).flat().every(l=>!/[\\u2014\\u2013!]/.test(l)&&l.length<=110)||false)"))
    p.goto('file://'+APP+'#sky');p.wait_for_selector('.skybox')
    rows=p.evaluate("[...document.querySelectorAll('.skybox .srow')].slice(3).map(r=>({chip:(r.querySelector('.chipx')||{}).textContent,sd:(r.querySelector('.sd')||{}).textContent,asp:(r.querySelector('.asp')||{}).textContent}))")
    ck('Nov 6 has up to 3 planet rows',1<=len(rows)<=3)
    ck('every planet row shows its house line from the approved list',all(r['sd'] and any(r['sd'] in v for h in p.evaluate("Object.values(HOUSE_LINES).map(h=>Object.values(h).flat())") for v in [h]) for r in rows))
    ck('chip format is Planet, in your Nth house',all(__import__('re').match(r'^(Venus|Mars|Mercury|Sun|Full Moon|New Moon) . in your \d+(st|nd|rd|th) house$',r['chip'] or '') for r in rows))
    ck('aspect sits in its own small line',all((r['asp'] or '').count('your')==1 for r in rows if r['asp']))
    ck('the house is counted from Rising (Moon sign to house)',p.evaluate("bcHouse('Aquarius','Sagittarius')===3&&bcHouse('Sagittarius','Sagittarius')===1"))
    p.keyboard.press('Escape');p.wait_for_timeout(300)
    # a Full Moon day: the card names the house, and the Moon is the first planet row
    q=new('2026-11-24');q.goto('file://'+APP+'#sky');q.wait_for_selector('.skybox')
    ck('Full Moon day: card has the house line',q.locator('.skybox .tc .rxtag:has-text("Full Moon in your")').count()==1 and 'house' in q.inner_text('.skybox .tc .rxtag').lower())
    ck('Full Moon day: first planet row is the Full Moon',q.locator('.skybox .srow').nth(3).locator('.chipx:has-text("Full Moon")').count()==1)
    ck('Full Moon day: its line is a Full Moon house line',q.evaluate("(()=>{const sd=document.querySelectorAll('.skybox .srow')[3].querySelector('.sd').textContent;return Object.values(HOUSE_LINES['Full Moon']).flat().includes(sd)})()"))
    # a New Moon day
    q=new('2026-11-08');q.goto('file://'+APP+'#sky');q.wait_for_selector('.skybox')
    ck('New Moon day: card has the house line',q.locator('.skybox .tc .rxtag:has-text("New Moon in your")').count()==1)
    # no Rising: chips lose the house and the sentence, the aspect stays
    r=new('2026-11-06');r.add_init_script("localStorage.setItem('h3c-prof-Nina',JSON.stringify({setup:true,name:'Nina',big3:{sun:'Aquarius',moon:'Aquarius'}}));")
    r.goto('file://'+APP+'#sky');r.wait_for_selector('.skybox')
    ck('no Rising: no Rising house text and no house chips',r.locator('.skybox .chipx:has-text("house")').count()==0)
    ck('no Rising: planet rows keep the aspect in the chip',r.locator('.skybox .chipx').count()>=1 and all(' · ' in t for t in r.evaluate("[...document.querySelectorAll('.skybox .chipx')].map(e=>e.textContent)")))
    # badges: signs and planets are drawn, with one stroke width
    p.goto('file://'+APP+'#sky');p.wait_for_selector('.skybox')
    ck('sign and planet badges share one stroke width',p.evaluate("(()=>{const s=new Set([...document.querySelectorAll('.skybox .sbadge svg')].map(e=>e.getAttribute('stroke-width')));return s.size===1&&[...s][0]==='1.6'})()"))
    ck('all 12 signs and 5 planets have a drawing',p.evaluate("['Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces','Sun','Moon','Mercury','Venus','Mars'].every(n=>skyIcon(n).includes('<path')||skyIcon(n).includes('<circle'))"))
    b.close()
print(f't_sky.py: {checks} checks, {fails} failed');sys.exit(1 if fails else 0)
