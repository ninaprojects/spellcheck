"""Birth place: search-as-you-type dropdown that saves an exact city (name, lat, lon, timezone). Lookup is mocked."""
import os, json, datetime
from playwright.sync_api import sync_playwright
APP=os.path.abspath(os.environ.get('SPELLCHECK_HABITS', os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','index.html')))
fails=0;checks=0
def ck(n,ok):
    global fails,checks;checks+=1
    if not ok: fails+=1;print('FAIL',n)
INIT="""localStorage.setItem('h3-whoami','Nina');localStorage.setItem('h3c-prof-Nina',JSON.stringify({setup:true,name:'Nina',big3:{sun:'Aquarius',moon:'Aquarius',rising:'Sagittarius'},birth:{date:'1991-02-14'}}))"""
RES={'results':[{'name':'Bujumbura','admin1':'Bujumbura Mairie','country':'Burundi','latitude':-3.3822,'longitude':29.3644,'timezone':'Africa/Bujumbura'},{'name':'Bujumbura','admin1':'Bujumbura Rural','country':'Burundi','latitude':-3.4,'longitude':29.4,'timezone':'Africa/Bujumbura'}]}
def run(mode,w=390):
    c=b.new_context(viewport={'width':w,'height':820});p=c.new_page();errs=[];p.on('pageerror',lambda e:errs.append(str(e)))
    def h(r):
        u=r.request.url
        if 'geocoding-api.open-meteo.com' in u:
            if mode=='down': return r.abort()
            if mode=='none': return r.fulfill(status=200,content_type='application/json',body='{}')
            return r.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps(RES))
        return r.abort() if u.startswith('http') else r.continue_()
    p.route('**/*',h);p.clock.install(time=datetime.datetime.fromisoformat('2026-11-08T12:00:00'));p.add_init_script(INIT)
    p.goto('file://'+APP+'#me');p.wait_for_selector('[data-act=birthedit]');p.click('[data-act=birthedit]');p.wait_for_selector('#bd-place')
    return p,errs
with sync_playwright() as pw:
    b=pw.chromium.launch()
    p,errs=run('ok')
    ck('label says Place of birth',p.locator('label[for=bd-place]').inner_text().strip()=='Place of birth')
    ck('input is 16px or larger',float(p.eval_on_selector('#bd-place','e=>parseFloat(getComputedStyle(e).fontSize)'))>=16)
    p.fill('#bd-place','B');p.wait_for_timeout(500)
    ck('no search for one letter',p.locator('.popt').count()==0)
    p.fill('#bd-place','Bujum');p.wait_for_timeout(700)
    ck('dropdown lists the matches',p.locator('.popt').count()==2)
    ck('option shows city, region, country',p.locator('.popt').first.inner_text().strip()=='Bujumbura, Bujumbura Mairie, Burundi')
    ck('options are at least 44px tall',p.locator('.popt').first.bounding_box()['height']>=44)
    p.locator('.popt').first.click();p.wait_for_selector('.placepill')
    ck('picked place shows as a pill',p.locator('.placepill span').inner_text().strip()=='Bujumbura, Bujumbura Mairie, Burundi')
    ck('input is gone once picked',p.locator('#bd-place').count()==0)
    saved=json.loads(p.evaluate("localStorage.getItem('h3c-prof-Nina')"))['birth']
    ck('saved place name',saved.get('place')=='Bujumbura, Bujumbura Mairie, Burundi')
    ck('saved coordinates and timezone',saved.get('placeLat')==-3.38 and saved.get('placeLon')==29.36 and saved.get('placeTz')=='Africa/Bujumbura')
    ck('date was kept',saved.get('date')=='1991-02-14')
    p.click('[data-act=placechange]');p.wait_for_selector('#bd-place')
    saved=json.loads(p.evaluate("localStorage.getItem('h3c-prof-Nina')"))['birth']
    ck('change clears coordinates',saved.get('placeLat') is None and saved.get('date')=='1991-02-14')
    ck('no errors',not errs)
    p,errs=run('none');p.fill('#bd-place','Zzzzq');p.wait_for_timeout(700)
    ck('no match message',p.locator('.pnone:has-text("No match")').count()==1)
    p,errs=run('down');p.fill('#bd-place','Bujumbura');p.wait_for_timeout(700)
    ck('lookup down: says so and keeps what was typed',p.locator('.pnone:has-text("not available")').count()==1)
    saved=json.loads(p.evaluate("localStorage.getItem('h3c-prof-Nina')"))['birth']
    ck('lookup down: typed place is saved',saved.get('place')=='Bujumbura')
    for w in (360,430):
        p,errs=run('ok',w);p.fill('#bd-place','Bujum');p.wait_for_timeout(700)
        ck(f'{w}px no sideways scroll',p.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    b.close()
print(f't_birthplace.py: {checks} checks, {fails} failed')
raise SystemExit(1 if fails else 0)
