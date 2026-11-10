"""Daily question (the brew) in the new tracker, index.html. BREW_LIVE is on, so the card shows with no preview link.
Runs with Firebase blocked, so the app uses its local cache only. Never touches the real database."""
import os, json, sys
from datetime import datetime
from playwright.sync_api import sync_playwright
HERE=os.path.dirname(os.path.abspath(__file__))
APP=os.environ.get('SPELLCHECK_HABITS', os.path.join(HERE,'..','index.html'))
fails=0; checks=0
def ck(name,ok,detail=''):
    global fails,checks
    checks+=1
    if not ok: fails+=1; print('FAIL',name, detail if detail else '')
def seed(page, others=None):
    page.add_init_script("""
      localStorage.setItem('h3-whoami','Nina');
      localStorage.setItem('h3c-prof-Nina',JSON.stringify({setup:true,big3:{sun:'Libra',moon:'Pisces',rising:''}}));
      localStorage.setItem('h3c-habits-Nina',JSON.stringify({a:{id:'a',name:'Move',type:'yesno',days:[1,1,1,1,1,1,1],shared:true,created:1,createdDay:'2026-11-01',preset:'move'}}));
    """)
    for who, ans in (others or {}).items():
        page.add_init_script("localStorage.setItem('h3c-qa-%s',%s);" % (who, json.dumps(json.dumps(ans))))
with sync_playwright() as pw:
    b=pw.chromium.launch()
    for w in (360,390,430):
        ctx=b.new_context(viewport={'width':w,'height':800},device_scale_factor=1)
        page=ctx.new_page()
        page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
        page.clock.install(time=datetime(2026,11,10,12,0,0))
        seed(page, {'Kellye': {'2026-11-10': {'t':'Saying no to a 6am call.','at':1}}})
        errs=[]
        page.on('pageerror',lambda e: errs.append(str(e)))
        page.goto('file://'+os.path.abspath(APP)+'#today')
        page.wait_for_selector('.strip')
        txt=page.inner_text('body').lower()
        ck(f'{w} B1 the card shows with no preview link', page.locator('.brewcard').count()==1)
        ck(f'{w} B1 it says Today\'s brew', "today's brew" in txt)
        ck(f'{w} B2 others\' answers stay hidden until she answers', 'saying no to a 6am call' not in txt)
        lbl=page.get_attribute('.brewcard .con','aria-label') or ''
        ck(f'{w} B2 it says who already answered', 'kellye already answered' in lbl.lower() and 'no spoilers' in lbl.lower(), lbl)
        ck(f'{w} B3 no sideways scroll', page.evaluate("document.documentElement.scrollWidth<=window.innerWidth"))
        if w==390:
            page.click('[data-act=brewopen]'); page.wait_for_selector('#bi')
            ck('B4 the answer box is at least 16px (no iPhone zoom)', page.evaluate("parseFloat(getComputedStyle(document.getElementById('bi')).fontSize)>=16"))
            page.fill('#bi','A 7am run that I actually enjoyed.')
            page.click('[data-act=brewsave]'); page.wait_for_timeout(500)
            saved=page.evaluate("localStorage.getItem('h3c-qa-Nina')")
            d=json.loads(saved) if saved else {}
            ck('B5 the answer is saved under her own record and today', d.get('2026-11-10',{}).get('t','').startswith('A 7am run'), saved)
            lbl=page.get_attribute('.brewcard .con','aria-label') or ''
            ck('B6 after answering, the card shows her answer and 2 of 4 answered, no spoiler note', 'a 7am run' in page.inner_text('.brewcard').lower() and lbl.lower().startswith('2 of 4 answered') and 'no spoilers' not in lbl.lower(), lbl)
        ck(f'{w} no page errors', not errs, errs)
        ctx.close()
    # a later day still has a question
    ctx=b.new_context(viewport={'width':390,'height':800}); page=ctx.new_page()
    page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
    page.clock.install(time=datetime(2026,11,20,12,0,0)); seed(page)
    page.goto('file://'+os.path.abspath(APP)+'#today'); page.wait_for_selector('.strip')
    ck('B7 Nov 20 has a question too', page.locator('.brewcard').count()==1)
    b.close()
print('%d checks, %d failed' % (checks,fails))
sys.exit(1 if fails else 0)
