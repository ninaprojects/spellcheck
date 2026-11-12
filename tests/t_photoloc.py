"""Photo location (index.html): pick a nearby place, the city, or type one. Only the place name is saved.
Clock pinned Nov 11 2026. Place and city lookups mocked. Never touches the real database."""
import os, json, datetime, tempfile
from playwright.sync_api import sync_playwright
from PIL import Image
HERE=os.path.dirname(os.path.abspath(__file__))
APP=os.environ.get('SPELLCHECK_HABITS', os.path.join(HERE,'..','index.html'))
fails=0; checks=0
def ck(name,ok):
    global fails,checks
    checks+=1
    if not ok: fails+=1; print('FAIL',name)
tmp=tempfile.mkdtemp()
plain=os.path.join(tmp,'plain.jpg'); Image.new('RGB',(800,600),(90,120,200)).save(plain)
gps=os.path.join(tmp,'gps.jpg'); im=Image.new('RGB',(800,600),(200,120,90))
ex=Image.Exif(); ex[0x8825]={1:'N',2:(34.0,0.0,0.0),3:'W',4:(118.0,30.0,0.0)}; im.save(gps,exif=ex)
H={'o':{'id':'o','name':'OOTD','type':'yesno','days':[1]*7,'shared':True,'created':1,'createdDay':'2026-11-01','preset':'ootd'}}
INIT=f"""localStorage.setItem('h3-whoami','Nina');
localStorage.setItem('h3c-prof-Nina',JSON.stringify({{setup:true,big3:{{sun:'Libra',moon:'Pisces',rising:'Leo'}}}}));
localStorage.setItem('h3c-habits-Nina',JSON.stringify({json.dumps(H)}));"""
OVER={'elements':[{'type':'node','lat':34.0001,'lon':-118.5,'tags':{'name':'Venice Cafe','amenity':'cafe'}},{'type':'node','lat':34.0005,'lon':-118.5,'tags':{'name':'Rose Park','leisure':'park'}}]}
CITY={'city':'Santa Monica','principalSubdivision':'California'}
def setup(b,w,geo=True,over_ok=True):
    ctx=b.new_context(viewport={'width':w,'height':800},permissions=['geolocation'] if geo else [],geolocation={'latitude':34.01,'longitude':-118.49} if geo else None)
    page=ctx.new_page(); page.clock.install(time=datetime.datetime(2026,11,11,12,0,0))
    seen=[]
    def route(r):
        u=r.request.url
        if 'overpass' in u:
            seen.append(r.request.post_data or '')
            return r.fulfill(json=OVER) if over_ok else r.abort()
        if 'bigdatacloud' in u: return r.fulfill(json=CITY)
        if u.startswith('http'): return r.abort()
        r.continue_()
    page.route('**/*',route); page.add_init_script(INIT)
    errs=[]; page.on('pageerror',lambda e: errs.append(str(e)))
    page.goto('file://'+os.path.abspath(APP)+'#photos'); page.wait_for_selector('.pill[data-act=picadd]')
    return ctx,page,seen,errs
with sync_playwright() as pw:
    b=pw.chromium.launch()
    for w in (360,390):
        ctx,page,seen,errs=setup(b,w)
        page.click('.pill[data-act=picadd]'); page.set_input_files('#ps-lib',gps); page.wait_for_selector('#picsheet .prev')
        ck(f'{w} Add location offered after a photo is chosen',page.locator('#picsheet [data-act=locopen]').count()==1)
        page.click('#picsheet [data-act=locopen]'); page.wait_for_selector('#picsheet .loc-item')
        ck(f'{w} photo with GPS searches where it was taken','where this photo was taken' in page.locator('#picsheet .loc-sub').text_content())
        ck(f'{w} lookup used the photo coordinates (34.0, -118.5), not the device',any('34.00000%2C-118.50000' in s for s in seen))
        names=page.locator('#picsheet .loc-name').all_text_contents()
        ck(f'{w} lists nearest place first and the city last',names[0]=='Venice Cafe' and names[-1]=='Just the city')
        page.click('#picsheet .loc-item >> nth=0'); 
        ck(f'{w} choosing shows the pill with city appended',page.locator('#picsheet .loc-text').text_content()=='Venice Cafe, Santa Monica')
        page.click('#picsheet [data-act=locremove]'); ck(f'{w} remove clears it',page.locator('#picsheet .loc-pill').count()==0)
        page.click('#picsheet [data-act=locopen]'); page.wait_for_selector('#picsheet .loc-item'); page.click('#picsheet [data-act=loccancel]')
        ck(f'{w} cancel closes the panel',page.locator('#picsheet .loc-panel').count()==0 and page.locator('#picsheet [data-act=locopen]').count()==1)
        page.click('#picsheet [data-act=locopen]'); page.wait_for_selector('#picsheet .loc-item')
        small=page.evaluate("[...document.querySelectorAll('#picsheet input')].filter(i=>i.type!=='file'&&parseFloat(getComputedStyle(i).fontSize)<16).length")
        ck(f'{w} typed place box is 16px',small==0)
        page.fill('#loc-typed','Grandma\'s porch'); page.click('#picsheet [data-act=locuse]')
        ck(f'{w} typed place used',page.locator('#picsheet .loc-text').text_content()=="Grandma's porch")
        page.click('[data-act=pssave]'); page.wait_for_selector('#picsheet[hidden]',state='attached')
        ix=json.loads(page.evaluate("localStorage.getItem('h3c-pic-Nina')")); pid=list(ix.keys())[0]; e=ix[pid]
        ck(f'{w} index stores only the place name',e.get('loc')=="Grandma's porch")
        blob=json.dumps(ix)+page.evaluate("JSON.stringify(Object.assign({},localStorage))")
        ck(f'{w} no coordinates stored anywhere','34.0' not in blob.replace('34.01','') and '118.5' not in blob and 'r2-photo-gps' not in blob)
        # viewer
        page.goto('file://'+os.path.abspath(APP)+'#photo/Nina.'+pid); page.wait_for_selector('.pview')
        ck(f'{w} viewer shows the place',"Grandma's porch" in page.locator('#app .loc-text').text_content())
        page.click('#app [data-act=locopen]'); page.wait_for_selector('#app .loc-item')
        ck(f'{w} viewer change uses where you are now','where you are right now' in page.locator('#app .loc-sub').text_content())
        page.click('#app .loc-item >> nth=0')
        e=json.loads(page.evaluate("localStorage.getItem('h3c-pic-Nina')"))[pid]
        ck(f'{w} viewer change saved',e.get('loc')=='Rose Park, Santa Monica')
        page.click('#app [data-act=locremove]'); e=json.loads(page.evaluate("localStorage.getItem('h3c-pic-Nina')"))[pid]
        ck(f'{w} viewer remove deletes the field','loc' not in e)
        # tea feed
        page.click('#app [data-act=locopen]'); page.wait_for_selector('#app .loc-item'); page.click('#app .loc-item >> nth=0')
        page.goto('file://'+os.path.abspath(APP)+'#coven'); page.wait_for_selector('.feed')
        ck(f'{w} Tea post shows the place','Rose Park, Santa Monica' in page.locator('#app').text_content())
        ck(f'{w} no sideways scroll',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        ck(f'{w} no page errors',not errs)
        ctx.close()
    # no GPS in photo: uses the device
    ctx,page,seen,errs=setup(b,390)
    page.click('.pill[data-act=picadd]'); page.set_input_files('#ps-lib',plain); page.wait_for_selector('#picsheet .prev')
    page.click('#picsheet [data-act=locopen]'); page.wait_for_selector('#picsheet .loc-item')
    ck('plain photo falls back to where you are','where you are right now' in page.locator('#picsheet .loc-sub').text_content() and any('34.01000%2C-118.49000' in s for s in seen))
    ctx.close()
    # lookups down: still can type
    ctx,page,seen,errs=setup(b,390,over_ok=False)
    page.click('.pill[data-act=picadd]'); page.set_input_files('#ps-lib',plain); page.wait_for_selector('#picsheet .prev')
    page.click('#picsheet [data-act=locopen]'); page.wait_for_function("document.querySelector('#picsheet .loc-sub').textContent.includes('Couldn')")
    ck('places down says so and offers the city','Just the city' in page.locator('#picsheet').text_content())
    page.fill('#loc-typed','Home'); page.click('#picsheet [data-act=locuse]')
    ck('places down: typing still works',page.locator('#picsheet .loc-text').text_content()=='Home')
    ctx.close()
    # no device location, no GPS
    ctx,page,seen,errs=setup(b,390,geo=False)
    page.click('.pill[data-act=picadd]'); page.set_input_files('#ps-lib',plain); page.wait_for_selector('#picsheet .prev')
    page.click('#picsheet [data-act=locopen]'); page.wait_for_function("document.querySelector('#picsheet .loc-sub').textContent.includes('type a place')",timeout=15000)
    ck('no location at all: type a place offered',page.locator('#loc-typed').count()==1)
    page.keyboard.press('Escape'); ck('Escape closes the panel first',page.locator('#picsheet .loc-panel').count()==0 and page.locator('#picsheet:not([hidden])').count()==1)
    ctx.close(); b.close()
print(f'{checks-fails}/{checks} checks passed'); raise SystemExit(1 if fails else 0)
