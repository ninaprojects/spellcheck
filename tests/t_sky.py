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
    for w in (360,430):
        q=new('2026-11-06',w);q.goto('file://'+APP+'#sky');q.wait_for_selector('.skybox')
        ck(f'{w} no sideways scroll',q.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        ck(f'{w} people row one line',q.evaluate("new Set([...document.querySelectorAll('.skybox .who button,.skybox .sbh .link')].map(e=>Math.round(e.getBoundingClientRect().top))).size===1"))
        ck(f'{w} tabs one line',q.evaluate("[...document.querySelectorAll('.skybox .tabs button')].every(e=>e.getBoundingClientRect().height<=48)"))
    b.close()
print(f't_sky.py: {checks} checks, {fails} failed');sys.exit(1 if fails else 0)
