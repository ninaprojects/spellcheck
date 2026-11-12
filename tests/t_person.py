"""Other people's profiles (index.html): avatars open a read-only profile with Big 3, shared habits and a sky button.
Clock pinned to Wed Nov 11 2026. Firebase blocked. Never touches the real database."""
import os, json, datetime
from playwright.sync_api import sync_playwright
HERE=os.path.dirname(os.path.abspath(__file__))
APP=os.environ.get('SPELLCHECK_HABITS', os.path.join(HERE,'..','index.html'))
fails=0; checks=0
def ck(name,ok):
    global fails,checks
    checks+=1
    if not ok: fails+=1; print('FAIL',name)
def T(page,sel): return (page.locator(sel).first.text_content() or '').strip()
log={}
for d in range(1,12): log.setdefault(f'2026-11-{d:02d}',{})['k1']=1
KH={'k1':{'id':'k1','name':'Read 20 min','type':'yesno','days':[1]*7,'shared':True,'created':1,'createdDay':'2026-11-01','preset':'read'},
    'k2':{'id':'k2','name':'Secret thing','type':'yesno','days':[1]*7,'shared':False,'created':2,'createdDay':'2026-11-01'}}
def init(extra=''):
    return f"""
      localStorage.setItem('h3-whoami','Nina');
      localStorage.setItem('h3c-prof-Nina',JSON.stringify({{setup:true,big3:{{sun:'Libra',moon:'Pisces',rising:'Leo'}}}}));
      localStorage.setItem('h3c-prof-Kellye',JSON.stringify({{setup:true,big3:{{sun:'Aries',moon:'Cancer',rising:''}},birth:{{date:'1990-04-02',place:'Denver'}}}}));
      localStorage.setItem('h3c-habits-Kellye',JSON.stringify({json.dumps(KH)}));
      localStorage.setItem('h3c-log-Kellye',JSON.stringify({json.dumps(log)}));
      {extra}
    """
with sync_playwright() as pw:
    b=pw.chromium.launch()
    for w in (360,390,430):
        ctx=b.new_context(viewport={'width':w,'height':800},device_scale_factor=1)
        page=ctx.new_page()
        page.clock.install(time=datetime.datetime(2026,11,11,12,0,0))
        page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
        page.add_init_script(init())
        errs=[]
        page.on('pageerror',lambda e: errs.append(str(e)))
        page.goto('file://'+os.path.abspath(APP)+'#today'); page.wait_for_selector('.strip')
        ck(f'{w} strip has four profile links',page.locator('.strip a.av').count()==4)
        page.click('.strip a.av[href="#person/Kellye"]'); page.wait_for_selector('.mehead')
        ck(f'{w} lands on Kellye profile',page.evaluate('location.hash')=='#person/Kellye' and T(page,'.mehead .h1')=='Kellye')
        body=page.locator('#app').text_content()
        ck(f'{w} shows Big 3',('Aries' in body) and ('Cancer' in body))
        ck(f'{w} shows the shared habit',('Read 20 min' in body))
        ck(f'{w} hides the private habit',('Secret thing' not in body))
        ck(f'{w} hides birth details',('Denver' not in body) and ('1990' not in body))
        ck(f'{w} no edit or photo change',page.locator('input[type=file]').count()==0 and 'Change photo' not in body)
        tops=page.evaluate("(()=>{const f=t=>{const e=[...document.querySelectorAll('#app .label')].find(x=>x.textContent.trim()===t);return e?e.getBoundingClientRect().top:-1;};return {b3:document.querySelector('.b3').getBoundingClientRect().top,sky:document.querySelector('[data-act=personsky]').getBoundingClientRect().top,habits:f('Shared habits'),cur:f('Currently'),reads:f('Shared reads')};})()")
        ck(f'{w} order: Big 3, sky, habits, Currently, reads',0<tops['b3']<tops['sky']<tops['habits']<tops['cur']<tops['reads'])
        ck(f'{w} habit name is not a link',page.locator('.hcard button.name').count()==0)
        ck(f'{w} no sideways scroll',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.click('[data-act=personsky]'); page.wait_for_selector('.skybox')
        ck(f'{w} sky opens on Kellye',page.locator('.skybox .who button.on').first.text_content().strip()=='Kellye')
        page.click('.skybox [data-act=skyclose]'); page.wait_for_selector('.mehead')
        ck(f'{w} closing the sky returns to her profile',page.evaluate('location.hash')=='#person/Kellye')
        page.click('.top a.link'); page.wait_for_selector('.strip')
        ck(f'{w} Back returns to Today',page.evaluate('location.hash')=='#today')
        # own avatar goes to Me
        page.click('.strip a.av[href="#me"]'); page.wait_for_selector('.mehead')
        ck(f'{w} own avatar goes to Me',page.evaluate('location.hash')=='#me' and page.locator('input[type=file]').count()>0)
        # Me has two tabs
        page.click('.seg button:has-text("Settings")'); page.wait_for_selector('[data-act=birthedit]')
        ck(f'{w} Settings tab: setup rows, no Big 3 or photo',page.locator('#cf').count()==1 and page.locator('.mrow:has-text("Notifications")').count()==1 and page.locator('.b3').count()==0 and page.locator('#pf').count()==0)
        page.click('.seg button:has-text("Profile")'); page.wait_for_selector('#pf',state='attached')
        ck(f'{w} Profile tab: photo, Big 3, no setup rows',page.locator('.b3').count()==1 and page.locator('#cf').count()==0 and page.locator('[data-act=birthedit]').count()==0)
        ck(f'{w} Profile tab lists shared habits section','Shared habits' in (page.locator('#app').text_content() or ''))
        # direct link to self or a stranger falls back to Me
        page.goto('file://'+os.path.abspath(APP)+'#person/Nina'); page.wait_for_selector('.mehead')
        ck(f'{w} own #person link shows Me',page.locator('#pf').count()==1)
        page.goto('file://'+os.path.abspath(APP)+'#person/Nobody'); page.wait_for_selector('.mehead')
        ck(f'{w} unknown name shows Me',page.locator('#pf').count()==1)
        # standings rows
        page.goto('file://'+os.path.abspath(APP)+'#standings'); page.wait_for_selector('.rank')
        page.click('.rank a.av[href="#person/Kellye"]'); page.wait_for_selector('.mehead')
        ck(f'{w} standings avatar opens profile',T(page,'.mehead .h1')=='Kellye')
        page.click('.top a.link'); page.wait_for_selector('.rank')
        ck(f'{w} Back returns to Standings',page.evaluate('location.hash')=='#standings')
        ck(f'{w} no page errors',not errs)
        if w==390:
            page.goto('file://'+os.path.abspath(APP)+'#person/Kellye'); page.wait_for_selector('.mehead')
            page.wait_for_timeout(1200); page.screenshot(path='/tmp/shots/person390.png',full_page=True)
        ctx.close()
    # empty state
    ctx=b.new_context(viewport={'width':390,'height':800}); page=ctx.new_page()
    page.clock.install(time=datetime.datetime(2026,11,11,12,0,0))
    page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
    page.add_init_script(init().replace("h3c-habits-Kellye","x-unused"))
    page.goto('file://'+os.path.abspath(APP)+'#person/Kellye'); page.wait_for_selector('.mehead')
    ck('empty state when nothing shared','has not shared any habits yet' in page.locator('#app').text_content())
    b.close()
print(f'{checks-fails}/{checks} checks passed'); raise SystemExit(1 if fails else 0)
