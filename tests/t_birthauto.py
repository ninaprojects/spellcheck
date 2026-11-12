"""Birth details fill in the Big 3: Sun, Moon and Rising worked out from date, time and place. Place lookup is mocked."""
import os, json, datetime
from playwright.sync_api import sync_playwright
APP=os.path.abspath(os.environ.get('SPELLCHECK_HABITS', os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','index.html')))
fails=0;checks=0
def ck(n,ok):
    global fails,checks;checks+=1
    if not ok: fails+=1;print('FAIL',n)
CHI={'results':[{'name':'Chicago','admin1':'Illinois','country':'United States','latitude':41.85,'longitude':-87.65,'timezone':'America/Chicago'}]}
def run(prof,w=390):
    c=b.new_context(viewport={'width':w,'height':900});p=c.new_page();errs=[];p.on('pageerror',lambda e:errs.append(str(e)))
    def h(r):
        u=r.request.url
        if 'geocoding-api.open-meteo.com' in u: return r.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps(CHI))
        return r.abort() if u.startswith('http') else r.continue_()
    p.route('**/*',h);p.clock.install(time=datetime.datetime.fromisoformat('2026-11-08T12:00:00'))
    p.add_init_script("localStorage.setItem('h3-whoami','Nina');localStorage.setItem('h3c-prof-Nina',JSON.stringify(%s))"%json.dumps(prof))
    p.goto('file://'+APP+'#me/settings');p.wait_for_selector('[data-act=birthedit]');p.click('[data-act=birthedit]');p.wait_for_selector('#bd-date');return p,errs
def big(p):return json.loads(p.evaluate("localStorage.getItem('h3c-prof-Nina')")).get('big3',{})
with sync_playwright() as pw:
    b=pw.chromium.launch()
    # 1. Empty Big 3, enter everything: the signs fill themselves
    p,errs=run({'setup':True,'name':'Nina','big3':{}})
    p.fill('#bd-date','1989-08-02');p.wait_for_timeout(300)
    ck('Sun fills from the date alone',big(p).get('sun')=='Leo')
    ck('Moon is not guessed when it could be two signs',not big(p).get('moon'))
    ck('summary offers both Moon signs',('Leo or Virgo' in p.text_content('#bd-calc')) or ('Virgo or Leo' in p.text_content('#bd-calc')))
    p.fill('#bd-time','14:07');p.fill('#bd-place','Chicag');p.wait_for_timeout(700);p.locator('.popt').first.click();p.wait_for_selector('.placepill');p.wait_for_timeout(300)
    g=big(p)
    ck('Kellye fills as Leo, Leo, Scorpio',g.get('sun')=='Leo' and g.get('moon')=='Leo' and g.get('rising')=='Scorpio')
    ck('summary says it matches',p.text_content('#bd-calc').strip().endswith('It matches your big 3.'))
    p.screenshot(path='/tmp/birthauto_filled.png',full_page=True)
    ck('no page errors',errs==[])
    # 2. A wrong saved Moon is offered a fix, never silently changed
    p,errs=run({'setup':True,'name':'Nina','big3':{'sun':'Leo','moon':'Sagittarius','rising':'Scorpio'},'birth':{'date':'1989-08-02','time':'14:07','place':'Chicago, Illinois, United States','placeLat':41.85,'placeLon':-87.65,'placeTz':'America/Chicago'}})
    p.wait_for_timeout(600)
    ck('wrong Moon is not changed on its own',big(p).get('moon')=='Sagittarius')
    ck('offers Use Leo',p.locator('#bd-calc [data-act=b3use]').text_content().strip()=='Use Leo')
    p.screenshot(path='/tmp/birthauto_fix.png',full_page=True)
    p.click('#bd-calc [data-act=b3use]');p.wait_for_timeout(400)
    ck('Use Leo fixes only the Moon',big(p)=={'sun':'Leo','moon':'Leo','rising':'Scorpio'})
    # 3. No birth time: Sun and Moon work when they cannot change, Rising waits
    p,errs=run({'setup':True,'name':'Nina','big3':{},'birth':{'date':'1989-08-02','noTime':True,'place':'Chicago, Illinois, United States','placeLat':41.85,'placeLon':-87.65,'placeTz':'America/Chicago'}})
    p.wait_for_timeout(300)
    g=big(p)
    ck('no time still gives Sun and Moon',g.get('sun')=='Leo' and g.get('moon')=='Leo' and not g.get('rising'))
    ck('says Rising needs a birth time','Rising needs a birth time' in p.text_content('#bd-calc'))
    # 4. Phone widths: no sideways scroll, summary inside the card
    for w in (360,430):
        p,errs=run({'setup':True,'name':'Nina','big3':{'sun':'Leo','moon':'Sagittarius','rising':'Scorpio'},'birth':{'date':'1989-08-02','time':'14:07','placeTz':'America/Chicago','placeLat':41.85,'placeLon':-87.65}},w)
        ck(f'{w}px no sideways scroll',p.evaluate('document.documentElement.scrollWidth<=innerWidth'))
print(f't_birthauto.py: {checks} checks, {fails} failed')
raise SystemExit(1 if fails else 0)
