"""Easy birth details: pop-out button opens the form, one-time Today card, no-birth-time tick."""
import os, json, datetime
from playwright.sync_api import sync_playwright
APP=os.path.abspath(os.environ.get('SPELLCHECK_HABITS', os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','index.html')))
fails=0;checks=0
def ck(n,ok):
    global fails,checks;checks+=1
    if not ok: fails+=1;print('FAIL',n)
def prof(birth,big=True):
    d={'setup':True,'name':'Nina'}
    if big: d['big3']={'sun':'Leo','moon':'Sagittarius','rising':'Scorpio'}
    if birth: d['birth']=birth
    return json.dumps(d)
def mk(b,birth,w=390,hash='#today',big=True):
    c=b.new_context(viewport={'width':w,'height':820});p=c.new_page();errs=[];p.on('pageerror',lambda e:errs.append(str(e)))
    p.route('**/*',lambda r:r.abort() if r.request.url.startswith('http') else r.continue_())
    p.clock.install(time=datetime.datetime.fromisoformat('2026-11-08T12:00:00'))
    p.add_init_script("localStorage.setItem('h3-whoami','Nina');localStorage.setItem('h3c-prof-Nina',JSON.stringify(%s))"%prof(birth,big))
    p.goto('file://'+APP+hash);p.wait_for_timeout(400);return p,errs
with sync_playwright() as pw:
    b=pw.chromium.launch()
    p,errs=mk(b,None)
    ck('card shows with Big 3 and no birth date',p.locator('#birthhint').count()==1)
    p.click('#birthhint [data-act=birthgo]');p.wait_for_selector('#bd-date')
    ck('card button lands on Me with the form open',p.evaluate('location.hash')=='#me/settings' and p.locator('#bd-date').count()==1)
    p,errs=mk(b,None);p.click('#birthhint [data-act=birthhide]');p.wait_for_timeout(200)
    ck('Not now hides it',p.locator('#birthhint').count()==0)
    p.reload();p.wait_for_timeout(300)
    ck('stays hidden after reload',p.locator('#birthhint').count()==0)
    p,errs=mk(b,{'date':'1991-02-14'})
    ck('no card once date is added',p.locator('#birthhint').count()==0)
    p,errs=mk(b,None,hash='#sky',big=False);p.wait_for_selector('.skybox .addbox [data-act=birthgo]')
    ck('pop-out has the button',True)
    p.click('.skybox .addbox [data-act=birthgo]');p.wait_for_selector('#bd-date')
    ck('pop-out button opens the form directly',p.evaluate('location.hash')=='#me/settings' and p.locator('#bd-date').count()==1)
    p.click('#bd-notime');p.wait_for_timeout(200)
    ck('tick hides the time field',p.locator('#bd-time').count()==0)
    saved=json.loads(p.evaluate("localStorage.getItem('h3c-prof-Nina')"))
    ck('tick saved',saved['birth'].get('noTime') is True)
    p.click('#bd-notime');p.wait_for_timeout(200)
    ck('untick brings the time field back',p.locator('#bd-time').count()==1)
    ck('no errors',not errs)
    for w in (360,430):
        p,errs=mk(b,None,w,'#me/settings');p.click('[data-act=birthedit]');p.wait_for_selector('#bd-notime')
        ck(f'{w}px no sideways scroll',p.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        ck(f'{w}px tick is 44px tall',p.locator('#bd-notime').bounding_box()['height']>=44)
    b.close()
print(f't_birtheasy.py: {checks} checks, {fails} failed')
raise SystemExit(1 if fails else 0)
