"""Sky: calm Today card, event colours, Read your sky pop-out (tabs, people, dismiss). Firebase blocked, clock pinned."""
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
    ck('signs tab shows three rows',p.locator('.skybox .srow').count()==3)
    p.click('[data-act=skytab][data-v=chart]')
    ck('chart tab shows chips',p.locator('.skybox .chipx').count()>=1)
    ck('coming up three',p.locator('.skybox .up').count()==3)
    p.click('[data-act=skywho][data-p=Kellye]')
    ck('no-chart person gets add box',p.locator('.addbox').count()==1)
    ck('card not clipped',p.evaluate("(()=>{const c=document.querySelector('.skybox .tc').getBoundingClientRect();const t=document.querySelector('.skybox .tabs').getBoundingClientRect();return t.top>=c.bottom-1})()"))
    p.click('.skyscrim',position={'x':5,'y':5});p.wait_for_timeout(300)
    ck('tap outside closes',p.locator('.skybox').count()==0 and p.url.endswith('#today'))
    p.goto('file://'+APP+'#sky');p.wait_for_selector('.skybox');p.keyboard.press('Escape');p.wait_for_timeout(300)
    ck('escape closes',p.locator('.skybox').count()==0)
    ck('approved headline bank is complete (12 signs x 12 moons x 7)',p.evaluate("Object.keys(SKY_HEAD).length===12&&Object.values(SKY_HEAD).every(m=>Object.keys(m).length===12&&Object.values(m).every(l=>l.length===7))"))
    ck('approved row sentences are complete (18 Sun, 18 Moon, 24 Rising)',p.evaluate("Object.values(SKY_ROWS.Sun).flat().length===18&&Object.values(SKY_ROWS.Moon).flat().length===18&&Object.values(SKY_ROWS.Rising).flat().length===24"))
    ck('no em dashes in the sky copy',p.evaluate("!/\\u2014/.test(JSON.stringify([SKY_HEAD,SKY_ROWS]))"))
    ck('sign relations',p.evaluate("skyRel('Aquarius','Libra')==='element'&&skyRel('Aries','Aries')==='same'&&skyRel('Aries','Libra')==='opposite'&&skyRel('Aries','Cancer')==='tense'&&skyRel('Aries','Gemini')==='friendly'&&skyRel('Aries','Taurus')==='quiet'"))
    ck('today headline comes from the bank for her Sun sign and the Moon sign',p.evaluate("SKY_HEAD.Aquarius.Libra.includes(forecastFor('Nina',todayK()).headline)"))
    p.goto('file://'+APP+'#sky');p.wait_for_selector('.skybox');p.click('[data-act=skywho][data-p=Nina]');p.click('[data-act=skytab][data-v=signs]')
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
        ck(f'{w} tabs one line',q.evaluate("[...document.querySelectorAll('.skybox .tabs button')].every(e=>e.getBoundingClientRect().height<=48)"))
    b.close()
print(f't_sky.py: {checks} checks, {fails} failed');sys.exit(1 if fails else 0)
