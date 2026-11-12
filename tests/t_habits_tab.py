"""Habits tab (index.html): Your habits and Overall views, both only for you. Old #journey links land here.
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
def days(a,b): return [f'2026-11-{d:02d}' for d in range(a,b+1)]
log={}
for d in days(1,4)+days(6,11): log.setdefault(d,{})['a']=1
for d in days(3,10): log.setdefault(d,{})['b']=1
def init(habits):
    return f"""
      localStorage.setItem('h3-whoami','Nina');
      localStorage.setItem('h3c-prof-Nina',JSON.stringify({{setup:true,big3:{{sun:'Libra',moon:'Pisces',rising:''}}}}));
      localStorage.setItem('h3c-habits-Nina',JSON.stringify({json.dumps(habits)}));
      localStorage.setItem('h3c-log-Nina',JSON.stringify({json.dumps(log)}));
    """
H={'a':{'id':'a','name':'Move 30 min','type':'yesno','days':[1]*7,'shared':False,'created':1,'createdDay':'2026-11-01','preset':'move'},
   'b':{'id':'b','name':'Journal 15 min','type':'yesno','days':[1]*7,'shared':False,'created':2,'createdDay':'2026-11-03','preset':'journal'},
   'z':{'id':'z','name':'Old habit','type':'yesno','days':[1]*7,'shared':False,'created':3,'createdDay':'2026-11-01','archived':True}}
with sync_playwright() as pw:
    b=pw.chromium.launch()
    for w in (360,390,430):
        ctx=b.new_context(viewport={'width':w,'height':800},device_scale_factor=1)
        page=ctx.new_page()
        page.clock.install(time=datetime.datetime(2026,11,11,12,0,0))
        page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
        page.add_init_script(init(H))
        errs=[]
        page.on('pageerror',lambda e: errs.append(str(e)))
        page.goto('file://'+os.path.abspath(APP)+'#today'); page.wait_for_selector('.strip')
        navt=[x.strip() for x in page.locator('nav a').all_text_contents()]
        ck(f'{w} nav says Today, Coven, Habits, Me',[n for n in navt if n][:4]==['Today','Coven','Habits','Me'])
        page.click('nav a[href="#habits"]'); page.wait_for_selector('.seg')
        ck(f'{w} Habits tab title',T(page,'.body .h1')=='Habits')
        ck(f'{w} Habits tab is highlighted',page.locator('nav a.on[href="#habits"]').count()==1)
        ck(f'{w} two views: Your habits, Overall',[x.strip() for x in page.locator('.seg button').all_text_contents()]==['Your habits','Overall'])
        ck(f'{w} Your habits is the first view',page.locator('.seg button.on').text_content().strip()=='Your habits')
        ck(f'{w} lists the two active habits, not the archived one',page.locator('.hcard').count()==2)
        ck(f'{w} streak text',page.locator('.hcard').nth(0).locator('.tags').text_content().strip()=='6 now · 6 best' and page.locator('.hcard').nth(1).locator('.tags').text_content().strip()=='8 now · 8 best')
        ck(f'{w} last 7 days summary',page.locator('.hcard .d7').nth(0).get_attribute('aria-label')=='Last 7 days, 6 done' and page.locator('.hcard .d7').nth(1).get_attribute('aria-label')=='Last 7 days, 6 done')
        ck(f'{w} seven day bars',page.locator('.hcard').nth(0).locator('.d7 i').count()==7 and page.locator('.hcard').nth(0).locator('.d7 i.on').count()==6)
        ck(f'{w} habits have their icons',page.locator('.hcard .hico.i-move').count()==1 and page.locator('.hcard .hico.i-journal').count()==1)
        ck(f'{w} Add a habit button',T(page,'#addhabit2')=='Add a habit' and page.evaluate("document.getElementById('addhabit2').getBoundingClientRect().height")>=44)
        ck(f'{w} archived habits live here',page.locator('.card:has(.label:text-is("Archived")) .chip').count()==1)
        ck(f'{w} no sideways scroll',page.evaluate("document.documentElement.scrollWidth<=innerWidth"))
        # open a habit, back returns here, tab stays highlighted
        page.click('.hcard .name >> nth=0'); page.wait_for_selector('.big')
        ck(f'{w} habit page opened from Habits keeps Habits highlighted',page.locator('nav a.on[href="#habits"]').count()==1)
        page.click('.top a.link >> nth=0'); page.wait_for_selector('.seg')
        ck(f'{w} Back returns to Habits',page.evaluate("location.hash")=='#habits')
        # add flow closes back to Habits
        page.click('#addhabit2'); page.wait_for_selector('.opt.pk')
        page.click('.top a[data-act=closeadd]'); page.wait_for_selector('.seg')
        ck(f'{w} Close on New habit returns to Habits',page.evaluate("location.hash")=='#habits')
        # Overall
        page.click('.seg button >> nth=1'); page.wait_for_selector('.stats3')
        stats=[x.strip() for x in page.locator('.stat b').all_text_contents()]
        ck(f'{w} Overall headline numbers {stats}',stats==['18','8','9'])
        ck(f'{w} longest streak names the habit',T(page,'.stat .sn')=='Journal 15 min')
        ck(f'{w} calendar month name',T(page,'.card:has(.cal) .label')=='November')
        ck(f'{w} calendar starts on the right weekday (Nov 1 is a Sunday, Monday first)',page.locator('.cal i.e').count()==6)
        ck(f'{w} calendar has 30 days',page.locator('.cal i:not(.e)').count()==30)
        ck(f'{w} full days are darkest, partial days lighter',page.locator('.cal i.l4').count()==9 and page.locator('.cal i.l2').count()==2)
        ck(f'{w} day 5 label',page.locator('.cal i[aria-label="November 5, 1 of 2 done"]').count()==1)
        ck(f'{w} today is marked',page.locator('.cal i.today').count()==1 and T(page,'.cal i.today')=='11')
        ck(f'{w} days ahead are dashed and empty',page.locator('.cal i.f').count()==19)
        rows=[' '.join(x.split()) for x in page.locator('.orow').all_text_contents()]
        ck(f'{w} per-habit rows {rows}',rows==['Move 30 min10 of 11 days','Journal 15 min8 of 9 days'])
        ck(f'{w} Overall shows only you (no coven names)',page.locator('#app').text_content().count('Kellye')==0 and page.locator('#app').text_content().count('Lauren')==0)
        ck(f'{w} Overall has no sideways scroll',page.evaluate("document.documentElement.scrollWidth<=innerWidth"))
        # back to Your habits
        page.click('.seg button >> nth=0'); page.wait_for_selector('.hcard')
        ck(f'{w} switching back works',page.locator('.hcard').count()==2)
        # old links
        page.goto('file://'+os.path.abspath(APP)+'#journey'); page.wait_for_selector('.seg')
        ck(f'{w} old #journey link lands on Habits',T(page,'.body .h1')=='Habits' and page.evaluate("location.hash")=='#habits')
        # Me no longer holds archived
        page.goto('file://'+os.path.abspath(APP)+'#me'); page.wait_for_selector('.mehead')
        ck(f'{w} Me no longer lists archived habits',page.locator('#app .label:text-is("Archived")').count()==0)
        # Bring back works from Habits
        page.goto('file://'+os.path.abspath(APP)+'#habits'); page.wait_for_selector('.seg')
        page.click('.chip[data-act=unarch]'); page.wait_for_timeout(200)
        ck(f'{w} Bring back adds it to the list',page.locator('.hcard').count()==3 and page.locator('.chip[data-act=unarch]').count()==0)
        ck(f'{w} no script errors {errs[:2]}',errs==[])
        ctx.close()
    # empty state
    ctx=b.new_context(viewport={'width':390,'height':800},device_scale_factor=1)
    page=ctx.new_page(); page.clock.install(time=datetime.datetime(2026,11,11,12,0,0))
    page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
    page.add_init_script(init({}))
    page.goto('file://'+os.path.abspath(APP)+'#habits'); page.wait_for_selector('.seg')
    ck('empty: invites the first habit','No habits yet' in T(page,'.body') and page.locator('#addhabit2').count()==1)
    page.click('.seg button >> nth=1')
    ck('empty: Overall says so','your month builds here' in T(page,'.body'))
    ctx.close()
    b.close()
print(f'{checks} checks, {fails} failed')
raise SystemExit(1 if fails else 0)
