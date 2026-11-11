"""New habit tracker (index.html): Today strip and progress, all-done moment, Me tab, notification row.
Runs with Firebase blocked, so the app uses its local cache only. Never touches the real database."""
import os, json, sys
from playwright.sync_api import sync_playwright
HERE=os.path.dirname(os.path.abspath(__file__))
APP=os.environ.get('SPELLCHECK_HABITS', os.path.join(HERE,'..','index.html'))
fails=0; checks=0
def ck(name,ok):
    global fails,checks
    checks+=1
    if not ok: fails+=1; print('FAIL',name)
def seed(page):
    page.add_init_script("""
      localStorage.setItem('h3-whoami','Nina');
      localStorage.setItem('h3c-prof-Nina',JSON.stringify({setup:true,big3:{sun:'Libra',moon:'Pisces',rising:''}}));
      const hb={a:{id:'a',name:'Move',type:'yesno',days:[1,1,1,1,1,1,1],shared:true,created:1,createdDay:'2026-11-01',preset:'move'},b:{id:'b',name:'Read',type:'yesno',days:[1,1,1,1,1,1,1],shared:false,created:2,createdDay:'2026-11-01'}};
      localStorage.setItem('h3c-habits-Nina',JSON.stringify(hb));
    """)
with sync_playwright() as pw:
    b=pw.chromium.launch()
    for w in (360,390,430):
        ctx=b.new_context(viewport={'width':w,'height':800},device_scale_factor=1)
        page=ctx.new_page()
        page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
        seed(page)
        errs=[]
        page.on('pageerror',lambda e: errs.append(str(e)))
        page.goto('file://'+os.path.abspath(APP)+'#today')
        page.wait_for_selector('.strip')
        ck(f'{w} strip shows',page.locator('.strip').count()==1)
        ck(f'{w} progress 0 of 2','0 of 2 done today' in page.inner_text('#app'))
        ck(f'{w} no all-done yet',page.locator('.alldone').count()==0)
        ck(f'{w} every habit has an icon',page.locator('.habit .hico').count()==2)
        ck(f'{w} preset habit gets its own drawing',page.locator('.hico.i-move').count()==1 and page.locator('.hico.i-read').count()==1)
        ck(f'{w} custom habit named Read gets the read icon from its name',page.evaluate("suggestIcon('Read a chapter')==='read'&&suggestIcon('Pilates')==='stretch'&&suggestIcon('zzz qqq')==='star'"))
        ck(f'{w} every preset has a drawing and an animation',page.evaluate("ALLP.every(p=>HI[p.id]&&HI_AN[p.id])&&ALLP.length===15"))
        ck(f'{w} OOTD and No-spend are in Extras, not Body',page.evaluate("PRESETS.Extras.some(p=>p.id==='ootd')&&PRESETS.Extras.some(p=>p.id==='nospend')&&!PRESETS.Body.some(p=>p.id==='ootd')&&!PRESETS.Money"))
        page.click('[data-act=tog][data-id=a]')
        ck(f'{w} done check is teal',page.evaluate("getComputedStyle(document.querySelector('.check.on')).backgroundColor")=='rgb(227, 244, 241)')
        ck(f'{w} done icon circle stays teal',page.evaluate("getComputedStyle(document.querySelector('.habit:has(.check.on) .hico')).backgroundColor")=='rgb(227, 244, 241)')
        ck(f'{w} icon animates on tick',page.locator('.hico.go').count()==1)
        ck(f'{w} progress 1 of 2','1 of 2 done today' in page.inner_text('#app'))
        page.click('[data-act=tog][data-id=b]')
        ck(f'{w} all-done line',page.locator('.alldone').count()==1)
        ck(f'{w} burst present',page.locator('.burst i').count()==8)
        ck(f'{w} sync label not above avatar',page.evaluate("getComputedStyle(document.getElementById('sync')).bottom")!='auto')
        ck(f'{w} Today no sideways scroll',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.screenshot(path=f'/tmp/habits_today_{w}.png')
        page.goto('file://'+os.path.abspath(APP)+'#add'); page.reload(); page.wait_for_selector('.opt')
        ck(f'{w} add screen shows an icon on every preset',page.locator('.opt.pk .hico').count()==15)
        page.click('[data-act=preset][data-id=tidy]')
        ck(f'{w} chosen preset turns teal',page.evaluate("getComputedStyle(document.querySelector('.opt.on .hico')).backgroundColor")=='rgb(227, 244, 241)')
        page.fill('#hn','Pilates')
        ck(f'{w} typed name suggests an icon',page.locator('#hnico .hico.i-stretch').count()==1)
        page.click('[data-act=iconpick]')
        ck(f'{w} icon picker lists every icon',page.locator('.iconrow .hico').count()==16)
        page.click('[data-act=iconset][data-id=cook]')
        ck(f'{w} picked icon shows beside the name',page.locator('#hnico .hico.i-cook').count()==1)
        small=page.evaluate("[...document.querySelectorAll('input')].filter(i=>i.type!=='file'&&parseFloat(getComputedStyle(i).fontSize)<16).length")
        ck(f'{w} add screen inputs 16px',small==0)
        ck(f'{w} add screen no sideways scroll',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.screenshot(path=f'/tmp/habits_add_{w}.png',full_page=True)
        page.goto('file://'+os.path.abspath(APP)+'#me'); page.reload(); page.wait_for_selector('.b3')
        ck(f'{w} Me has 3 columns',page.locator('.b3c').count()==3)
        ck(f'{w} two badges one add',page.locator('.sbadge').count()==2 and page.locator('.b3add').count()==1)
        ck(f'{w} notifications row',page.locator('.mrow:has-text("Notifications")').count()==1)
        ck(f'{w} Me no sideways scroll',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.click('[data-act=birthedit]')
        small=page.evaluate("[...document.querySelectorAll('input')].filter(i=>i.type!=='file'&&parseFloat(getComputedStyle(i).fontSize)<16).length")
        ck(f'{w} inputs 16px',small==0)
        page.click('[data-act=birthedit]'); page.click('[data-act=b3edit]')
        small=page.evaluate("[...document.querySelectorAll('input')].filter(i=>i.type!=='file'&&parseFloat(getComputedStyle(i).fontSize)<16).length")
        ck(f'{w} big3 inputs 16px',small==0)
        ck(f'{w} Moon signs match the published ingress table',page.evaluate("['2026-11-03','2026-11-05','2026-11-08','2026-11-11','2026-11-13','2026-11-21'].map(moonSign).join()")=='Virgo,Libra,Scorpio,Sagittarius,Capricorn,Aries')
        page.goto('file://'+os.path.abspath(APP)+'#sky'); page.reload(); page.wait_for_selector('.skycard,.card')
        ck(f'{w} Sky page shows a Moon sign line','Moon in' in page.inner_text('#app') or 'Moon in' in page.inner_text('body'))
        page.screenshot(path=f'/tmp/habits_me_{w}.png')
        ck(f'{w} no page errors',not errs)
        ctx.close()
    b.close()
print(f't_habits.py: {checks} checks, {fails} failed')
sys.exit(1 if fails else 0)
