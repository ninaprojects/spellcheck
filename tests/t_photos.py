"""Photos (index.html): add from the OOTD row or the Photos page, view in Coven, show in The Tea, delete.
Clock pinned to Wed Nov 11 2026. Firebase blocked. Never touches the real database."""
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
big=os.path.join(tmp,'big.jpg'); Image.new('RGB',(3000,2000),(200,80,120)).save(big)
bad=os.path.join(tmp,'bad.jpg'); open(bad,'wb').write(b'not an image')
H={'o':{'id':'o','name':'OOTD','type':'yesno','days':[1]*7,'shared':True,'created':1,'createdDay':'2026-11-01','preset':'ootd'}}
KP={'k1':{'day':'2026-11-10','hid':'','cap':'Pink linen','at':1762800000000,'sh':True},
    'k2':{'day':'2026-11-10','hid':'','cap':'Private one','at':1762800001000,'sh':False}}
INIT=f"""
localStorage.setItem('h3-whoami','Nina');
localStorage.setItem('h3c-prof-Nina',JSON.stringify({{setup:true,big3:{{sun:'Libra',moon:'Pisces',rising:'Leo'}}}}));
localStorage.setItem('h3c-habits-Nina',JSON.stringify({json.dumps(H)}));
localStorage.setItem('h3c-pic-Kellye',JSON.stringify({json.dumps(KP)}));
"""
TINY='data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA='
with sync_playwright() as pw:
    b=pw.chromium.launch()
    for w in (360,390):
        ctx=b.new_context(viewport={'width':w,'height':800}); page=ctx.new_page()
        page.clock.install(time=datetime.datetime(2026,11,11,12,0,0))
        page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
        page.add_init_script(INIT)
        errs=[]; page.on('pageerror',lambda e: errs.append(str(e)))
        page.goto('file://'+os.path.abspath(APP)+'#today'); page.wait_for_selector('.habit')
        page.evaluate(f"PD.set('Kellye:k1','{TINY}');PD.set('Kellye:k1-t','{TINY}');PD.set('Kellye:k2-t','{TINY}')")
        ck(f'{w} OOTD row has Add photo',page.locator('[data-act=picadd]').count()==1)
        page.click('[data-act=picadd]'); page.wait_for_selector('#picsheet:not([hidden]) .two')
        ck(f'{w} sheet offers camera and library',page.locator('#picsheet label[for=ps-cam]').count()==1 and page.locator('#picsheet label[for=ps-lib]').count()==1)
        ck(f'{w} camera input asks for the camera',page.locator('#ps-cam').get_attribute('capture')=='environment')
        # bad file
        page.set_input_files('#ps-lib',bad); page.wait_for_selector('#picsheet [role=alert]')
        ck(f'{w} bad photo says so','would not load' in page.locator('#picsheet [role=alert]').text_content())
        page.set_input_files('#ps-lib',big); page.wait_for_selector('#picsheet .prev')
        dims=page.evaluate("new Promise(r=>{const i=new Image();i.onload=()=>r([i.width,i.height]);i.src=document.querySelector('#picsheet .prev').src;})")
        ck(f'{w} big photo shrunk to 1600',max(dims)==1600 and dims[0]/dims[1]>1.4)
        page.fill('#ps-cap','Sunday best')
        page.evaluate("render()")
        ck(f'{w} sheet and caption survive a redraw',page.locator('#picsheet:not([hidden]) #ps-cap').input_value()=='Sunday best')
        small=page.evaluate("[...document.querySelectorAll('#picsheet input')].filter(i=>i.type!=='file'&&parseFloat(getComputedStyle(i).fontSize)<16).length")
        ck(f'{w} caption box is 16px',small==0)
        page.click('[data-act=pssave]'); page.wait_for_selector('#picsheet[hidden]',state='attached')
        ix=json.loads(page.evaluate("localStorage.getItem('h3c-pic-Nina')"))
        e=list(ix.values())[0]; pid=list(ix.keys())[0]
        ck(f'{w} index saved with habit, day, caption, shared',e['hid']=='o' and e['day']=='2026-11-11' and e['cap']=='Sunday best' and e['sh'] is True)
        ck(f'{w} full and small copies held',page.evaluate(f"PD.get('Nina:{pid}').startsWith('data:image/jpeg')&&PD.has('Nina:{pid}-t')"))
        ck(f'{w} index holds no image data',len(json.dumps(ix))<400)
        lg=json.loads(page.evaluate("localStorage.getItem('h3c-log-Nina')"))
        ck(f'{w} OOTD ticked for today',lg.get('2026-11-11',{}).get('o')==1)
        ck(f'{w} row now says Photo added','Photo added' in page.locator('#app').text_content() and page.locator('[data-act=picadd]').count()==0)
        # Photos page
        page.goto('file://'+os.path.abspath(APP)+'#photos'); page.wait_for_selector('.pgrid')
        page.evaluate(f"PD.set('Kellye:k1-t','{TINY}')")
        ck(f'{w} Photos tab exists in Coven',[t.strip() for t in page.locator('.seg button').all_text_contents()][:3]==['The Tea','Standings','Photos'])
        ck(f'{w} grid shows Nina and Kellye shared, not the private one',page.locator('.pcell').count()==2)
        page.click('[data-act=picf][data-v=mine]')
        ck(f'{w} Mine shows only mine',page.locator('.pcell').count()==1)
        ck(f'{w} Photos page has Add a photo',page.locator('.pill[data-act=picadd]').count()==1)
        ck(f'{w} Photos no sideways scroll',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        # viewer
        page.click('.pcell'); page.wait_for_selector('.pview')
        t=page.locator('#app').text_content()
        ck(f'{w} viewer shows caption and reactions','Sunday best' in t and page.locator('.rx button').count()==3)
        page.click('[data-act=picdel]'); ck(f'{w} delete asks twice','Tap again to delete' in page.locator('#app').text_content())
        page.click('[data-act=picdel]'); page.wait_for_selector('.pgrid,.card')
        ck(f'{w} delete removes it and returns to Photos',page.evaluate('location.hash')=='#photos' and json.loads(page.evaluate("localStorage.getItem('h3c-pic-Nina')")).get(pid) is None)
        # Tea feed
        page.goto('file://'+os.path.abspath(APP)+'#coven'); page.wait_for_selector('.feed')
        page.evaluate(f"PD.set('Kellye:k1','{TINY}')"); page.evaluate("render()")
        ft=page.locator('#app').text_content()
        ck(f'{w} Tea shows Kellye shared photo with caption','added a photo' in ft and 'Pink linen' in ft)
        ck(f'{w} Tea hides the private photo','Private one' not in ft)
        ck(f'{w} feed photo has reactions',page.locator('.feed:has(.feedpic) .rx button').count()==3)
        # cancel and escape
        page.goto('file://'+os.path.abspath(APP)+'#photos'); page.wait_for_selector('.pill[data-act=picadd]')
        page.click('.pill[data-act=picadd]'); page.wait_for_selector('#picsheet:not([hidden])')
        page.click('#picsheet [data-act=pscancel].link'); ck(f'{w} Cancel closes the sheet',page.locator('#picsheet[hidden]').count()==1)
        page.click('.pill[data-act=picadd]'); page.keyboard.press('Escape'); ck(f'{w} Escape closes the sheet',page.locator('#picsheet[hidden]').count()==1)
        # from Photos page: no habit, no tick, shared
        page.click('.pill[data-act=picadd]'); page.set_input_files('#ps-cam',big); page.wait_for_selector('#picsheet .prev'); page.click('[data-act=pssave]')
        page.wait_for_selector('#picsheet[hidden]',state='attached')
        ix=json.loads(page.evaluate("localStorage.getItem('h3c-pic-Nina')")); e=list(ix.values())[0]
        ck(f'{w} page photo has no habit and is shared',e['hid']=='' and e['sh'] is True)
        ck(f'{w} no page errors',not errs)
        if w==390:
            page.wait_for_timeout(900); page.screenshot(path='/tmp/shots/photos390.png',full_page=True)
        ctx.close()
    b.close()
print(f'{checks-fails}/{checks} checks passed'); raise SystemExit(1 if fails else 0)
