"""Full chart card on Me: planets from the birth date, houses from Rising, Show more planets, no time, phone widths."""
import os, json, datetime
from playwright.sync_api import sync_playwright
APP=os.path.abspath(os.environ.get('SPELLCHECK_HABITS', os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','index.html')))
fails=0;checks=0
def ck(n,ok):
    global fails,checks;checks+=1
    if not ok: fails+=1;print('FAIL',n)
K={'setup':True,'name':'Nina','big3':{'sun':'Leo','moon':'Leo','rising':'Scorpio'},'birth':{'date':'1989-08-02','time':'14:07','place':'Chicago, Illinois, United States','placeLat':41.85,'placeLon':-87.65,'placeTz':'America/Chicago'}}
def page(b,prof,w=390,scheme='light'):
    c=b.new_context(viewport={'width':w,'height':900},color_scheme=scheme);p=c.new_page();errs=[];p.on('pageerror',lambda e:errs.append(str(e)))
    p.route('**/*',lambda r:r.abort() if r.request.url.startswith('http') else r.continue_())
    p.clock.install(time=datetime.datetime.fromisoformat('2026-11-09T09:00:00'))
    p.add_init_script("localStorage.setItem('h3-whoami','Nina');localStorage.setItem('h3c-prof-Nina',%s)"%json.dumps(json.dumps(prof)))
    p.goto('file://'+APP+'#me');p.wait_for_selector('.b3');p.wait_for_timeout(300);return p,errs
def cells(p):return [ (c.locator('.label').text_content().strip(),c.locator('.b3n').text_content().strip(),(c.locator('.b3h').text_content().strip() if c.locator('.b3h').count() else '')) for c in p.locator('.b3c').all()]
with sync_playwright() as pw:
    b=pw.chromium.launch()
    p,errs=page(b,K);c=cells(p)
    ck('Big 3 shows houses from Rising',c[0]==('Sun','Leo','10th house') and c[1]==('Moon','Leo','10th house') and c[2]==('Rising','Scorpio','1st house'))
    ck('Mercury Venus Mars show by default',[x[0] for x in c[3:]]==['Mercury','Venus','Mars'] and c[4]==('Venus','Virgo','11th house'))
    ck('outer planets hidden until asked',p.locator('[data-act=moreplanets]').text_content().strip().lower()=='show more planets' and len(c)==6)
    p.click('[data-act=moreplanets]');p.wait_for_timeout(150);c=cells(p)
    ck('Show more planets adds Jupiter to Pluto with houses',[x[0] for x in c[6:]]==['Jupiter','Saturn','Uranus','Neptune','Pluto'] and c[6]==('Jupiter','Cancer','9th house') and c[10]==('Pluto','Scorpio','1st house'))
    ck('Show fewer collapses again',(p.click('[data-act=moreplanets]'),p.wait_for_timeout(100),len(cells(p)))[2]==6)
    ck('the Edit your big 3 link is still there',p.locator('.b3links [data-act=b3edit]').count()==1)
    ck('badges are hairline circles with a halo, not solid fills',p.evaluate("(()=>{const e=document.querySelector('.sbadge.fire');const s=getComputedStyle(e);return s.backgroundColor==='rgba(0, 0, 0, 0)'&&s.boxShadow!=='none'&&parseFloat(s.borderTopWidth)>0})()"))
    ck('no page errors',errs==[])
    # no time: planets fill, no Rising and no house lines
    p,errs=page(b,{'setup':True,'name':'Nina','big3':{'sun':'Leo','moon':'Leo'},'birth':{'date':'1989-08-02','noTime':True,'placeTz':'America/Chicago','placeLat':41.85,'placeLon':-87.65}});c=cells(p)
    ck('no time: no house lines anywhere',all(x[2]=='' for x in c))
    ck('no time: Venus still fills',('Venus','Virgo','') in c)
    # no birth date: no planet grid, no show-more link
    p,errs=page(b,{'setup':True,'name':'Nina','big3':{'sun':'Leo','moon':'Leo','rising':'Scorpio'},'birth':{}})
    ck('no birth date: no planets and no show-more link',len(cells(p))==3 and p.locator('[data-act=moreplanets]').count()==0)
    # dark mode and phone widths
    p,errs=page(b,K,scheme='dark');p.click('[data-act=moreplanets]')
    ck('dark mode: symbols are light enough to read',p.evaluate("(()=>{const e=document.querySelector('.sbadge.earth');const m=getComputedStyle(e).color.match(/\\d+/g).map(Number);return (m[0]+m[1]+m[2])/3>110})()"))
    for w in (360,430):
        p,errs=page(b,K,w);p.click('[data-act=moreplanets]');p.wait_for_timeout(100)
        ck(f'{w}px no sideways scroll',p.evaluate('document.documentElement.scrollWidth<=innerWidth'))
print(f't_fullchart.py: {checks} checks, {fails} failed')
raise SystemExit(1 if fails else 0)
