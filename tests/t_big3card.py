"""Big 3 card on Today (Nov 2026, index.html): shows while her Sun, Moon and Rising are empty, with one of the two
approved lines, "Not now" hides it for 3 days, "Add your Big 3" opens the Big 3 editor on her profile.
Clock pinned to Nov 13 2026, Firebase blocked. Never touches the real database."""
import os, json, datetime
from playwright.sync_api import sync_playwright
HERE=os.path.dirname(os.path.abspath(__file__))
APP=os.environ.get('SPELLCHECK_HABITS', os.path.join(HERE,'..','index.html'))
LINES=[('The stars are asking about you','Add your Big 3 and your daily sky and sky pushes switch on. We have so much to tell you.'),
       ('Tell us your signs','Your Sun, Moon and Rising unlock your daily sky. We promise to be extremely weird about it.')]
fails=0; checks=0
def ck(name,ok,detail=None):
    global fails,checks
    checks+=1
    if not ok: fails+=1; print('FAIL',name,'' if detail is None else str(detail)[:300])
def new(b,w,prof,extra=''):
    ctx=b.new_context(viewport={'width':w,'height':800})
    page=ctx.new_page(); page.clock.install(time=datetime.datetime(2026,11,13,12,0,0))
    page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
    page.add_init_script(f"localStorage.setItem('h3-whoami','Nina');localStorage.setItem('h3c-prof-Nina',JSON.stringify({json.dumps(prof)}));{extra}")
    errs=[]; page.on('pageerror',lambda e: errs.append(str(e)))
    return ctx,page,errs
def load(page,h='#today'):
    page.goto('file://'+os.path.abspath(APP)+h); page.reload(); page.wait_for_selector('nav'); page.wait_for_timeout(300)
with sync_playwright() as pw:
    b=pw.chromium.launch()
    for w in (360,390,430):
        ctx,page,errs=new(b,w,{'setup':True})
        load(page)
        card=page.locator('#b3hint')
        ck(f'{w} card shows with no Big 3',card.count()==1)
        t=card.text_content() if card.count() else ''
        ck(f'{w} card uses an approved line',any(h in t and body in t for h,body in LINES),t)
        ck(f'{w} birth details card does not show at the same time',page.locator('#birthhint').count()==0)
        ck(f'{w} no sideways scroll',page.evaluate("document.documentElement.scrollWidth<=innerWidth"))
        page.locator('[data-act="b3go"]').click(); page.wait_for_timeout(400)
        ck(f'{w} Add your Big 3 opens her profile',page.evaluate("location.hash")=='#me',page.evaluate("location.hash"))
        ck(f'{w} the Sun field is open and focused',page.locator('#b-sun').count()==1 and page.evaluate("document.activeElement&&document.activeElement.id")=='b-sun')
        load(page)
        page.locator('[data-act="b3hide"]').click(); page.wait_for_timeout(300)
        ck(f'{w} Not now hides it',page.locator('#b3hint').count()==0)
        ck(f'{w} Not now saves the time on this phone',abs(int(page.evaluate("localStorage.getItem('h3-b3hint:Nina')") or 0)-page.evaluate("Date.now()"))<5000)
        ck(f'{w} no page errors',not errs,errs)
        ctx.close()
        # a fresh open (new context, storage seeded) checks the 3-day rule without relying on a reload
        ctx,page,errs=new(b,w,{'setup':True},"localStorage.setItem('h3-b3hint:Nina',String(Date.now()-864e5));")
        load(page)
        ck(f'{w} still hidden a day after Not now',page.locator('#b3hint').count()==0)
        ctx.close()
        ctx,page,errs=new(b,w,{'setup':True},"localStorage.setItem('h3-b3hint:Nina',String(Date.now()-3*864e5-1000));")
        load(page)
        ck(f'{w} back after 3 days',page.locator('#b3hint').count()==1)
        ctx.close()
    ctx,page,errs=new(b,390,{'setup':True,'big3':{'sun':'Leo'}})
    load(page)
    ck('hidden once any of the Big 3 is set',page.locator('#b3hint').count()==0)
    ctx.close()
    seen=set()
    for d in range(1,15):
        ctx=b.new_context(viewport={'width':390,'height':800}); page=ctx.new_page()
        page.clock.install(time=datetime.datetime(2026,11,d,12,0,0))
        page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
        page.add_init_script("localStorage.setItem('h3-whoami','Nina');localStorage.setItem('h3c-prof-Nina',JSON.stringify({setup:true}));")
        load(page); seen.add(page.locator('#b3hint .h2').text_content()); ctx.close()
    ck('both approved lines show up across two weeks',seen=={h for h,_ in LINES},seen)
    b.close()
print(f'{checks} checks, {fails} failed')
