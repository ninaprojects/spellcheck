"""Comments (index.html): on Tea posts and photos. Each person writes her own h3-cmt record.
Clock pinned to Thu Nov 12 2026, noon. Firebase blocked. Never touches the real database."""
import os, json, datetime
from playwright.sync_api import sync_playwright
HERE=os.path.dirname(os.path.abspath(__file__))
APP=os.environ.get('SPELLCHECK_HABITS', os.path.join(HERE,'..','index.html'))
fails=0; checks=0
def ck(name,ok):
    global fails,checks
    checks+=1
    if not ok: fails+=1; print('FAIL',name)
NOW=datetime.datetime(2026,11,12,12,0,0)
def ms(mins_ago): return int((NOW-datetime.timedelta(minutes=mins_ago)).timestamp()*1000)
HN={'o':{'id':'o','name':'OOTD','type':'yesno','days':[1]*7,'shared':True,'created':1,'createdDay':'2026-11-01','preset':'ootd'}}
HK={'w':{'id':'w','name':'Walk','type':'yesno','days':[1]*7,'shared':True,'created':1,'createdDay':'2026-11-01'}}
KP={'k1':{'day':'2026-11-11','hid':'','cap':'Pink linen','at':ms(1500),'sh':True}}
LC={'pic:Kellye:k1':[{'id':'c1','t':'the shoulders on this','at':ms(120),'o':'Kellye'}]}
CC={'pic:Kellye:k1':[{'id':'c2','t':'<img src=x onerror=alert(1)>','at':ms(40)}]}
TINY='data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA='
def init(extra=''):
    return f"""localStorage.setItem('h3-whoami','Nina');
localStorage.setItem('h3c-prof-Nina',JSON.stringify({{setup:true,big3:{{sun:'Libra',moon:'Pisces',rising:'Leo'}}}}));
localStorage.setItem('h3c-habits-Nina',JSON.stringify({json.dumps(HN)}));
localStorage.setItem('h3c-habits-Kellye',JSON.stringify({json.dumps(HK)}));
localStorage.setItem('h3c-log-Kellye',JSON.stringify({{'2026-11-12':{{w:1}}}}));
localStorage.setItem('h3c-pic-Kellye',JSON.stringify({json.dumps(KP)}));
localStorage.setItem('h3c-cmt-Lauren',JSON.stringify({json.dumps(LC)}));
localStorage.setItem('h3c-cmt-Carolina',JSON.stringify({json.dumps(CC)}));{extra}"""
def open_page(b,w,hashq='#coven',extra=''):
    ctx=b.new_context(viewport={'width':w,'height':800}); page=ctx.new_page()
    page.clock.install(time=NOW)
    page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
    page.add_init_script(init(extra))
    errs=[]; page.on('pageerror',lambda e: errs.append(str(e))); page.on('dialog',lambda d:(errs.append('dialog'),d.dismiss()))
    page.goto('file://'+os.path.abspath(APP)+hashq); page.wait_for_timeout(400)
    page.evaluate(f"['Kellye:k1','Kellye:k1-t'].forEach(k=>PD.set(k,'{TINY}'))")
    return ctx,page,errs
PK='.feed[data-key="pic:Kellye:k1"]'
with sync_playwright() as pw:
    b=pw.chromium.launch()
    for w in (360,390,430):
        ctx,page,errs=open_page(b,w); page.wait_for_selector(PK)
        post=page.locator(PK)
        ck(f'{w} photo post shows both comments in order',[t.split(' ')[0] for t in post.locator('.cmt').all_text_contents()]==['Lauren','Carolina'])
        ck(f'{w} comment times','2h' in post.locator('.cmt').nth(0).text_content() and '40m' in post.locator('.cmt').nth(1).text_content())
        ck(f'{w} comment text is escaped, not run',post.locator('.cmts img').count()==0 and '<img src=x' in post.locator('.cmt').nth(1).text_content())
        ck(f'{w} no delete on other people\'s comments',post.locator('[data-act=cmtdel]').count()==0)
        ck(f'{w} every reaction post has Say something',page.locator('.feed .rx').count()==page.locator('.feed [data-act=cmtopen]').count() and page.locator('.feed [data-act=cmtopen]').count()>=2)
        ck(f'{w} Say something sits in the reaction row',post.locator('.rxrow [data-act=cmtopen]').count()==1)
        post.locator('[data-act=cmtopen]').click()
        ck(f'{w} box opens focused, link hides',page.evaluate("document.activeElement&&document.activeElement.id==='cmt-in'") and post.locator('[data-act=cmtopen]').count()==0)
        ck(f'{w} box is 16px',page.evaluate("parseFloat(getComputedStyle(document.getElementById('cmt-in')).fontSize)")>=16)
        ck(f'{w} 280 character limit',page.locator('#cmt-in').get_attribute('maxlength')=='280')
        page.keyboard.type('framing this')
        page.evaluate("renderSoft()")
        ck(f'{w} a sync while typing does not wipe the box',page.locator('#cmt-in').input_value()=='framing this' and page.evaluate("document.activeElement.id==='cmt-in'") and page.evaluate('ui.dirty===true'))
        page.evaluate("render()")
        ck(f'{w} a redraw keeps the text and focus',page.locator('#cmt-in').input_value()=='framing this' and page.evaluate("document.activeElement.id==='cmt-in'"))
        page.keyboard.press('Enter'); page.wait_for_timeout(100)
        mine=json.loads(page.evaluate("localStorage.getItem('h3c-cmt-Nina')"))
        e=mine.get('pic:Kellye:k1',[{}])[0]
        ck(f'{w} Enter saves my comment with owner and time',e.get('t')=='framing this' and e.get('o')=='Kellye' and abs(e.get('at',0)-ms(0))<60000 and e.get('id','').startswith('c'))
        ck(f'{w} box closes and my comment shows last with now and Delete',page.locator('#cmt-in').count()==0 and post.locator('.cmt').nth(2).text_content().startswith('Nina') and 'now' in post.locator('.cmt').nth(2).text_content() and post.locator('.cmt').nth(2).locator('[data-act=cmtdel]').count()==1)
        # Post button, empty post, cancel, escape
        post.locator('[data-act=cmtopen]').click(); page.click('[data-act=cmtpost]')
        ck(f'{w} empty post saves nothing',len(json.loads(page.evaluate("localStorage.getItem('h3c-cmt-Nina')"))['pic:Kellye:k1'])==1)
        post.locator('[data-act=cmtopen]').click(); page.fill('#cmt-in','second'); page.click('[data-act=cmtpost]')
        ck(f'{w} Post button saves',len(json.loads(page.evaluate("localStorage.getItem('h3c-cmt-Nina')"))['pic:Kellye:k1'])==2)
        post.locator('[data-act=cmtopen]').click(); page.click('[data-act=cmtcancel]')
        ck(f'{w} Cancel closes the box',page.locator('#cmt-in').count()==0)
        post.locator('[data-act=cmtopen]').click(); page.keyboard.press('Escape')
        ck(f'{w} Escape closes the box',page.locator('#cmt-in').count()==0)
        # delete
        post.locator('[data-act=cmtdel]').first.click()
        ck(f'{w} Delete removes only mine',len(json.loads(page.evaluate("localStorage.getItem('h3c-cmt-Nina')"))['pic:Kellye:k1'])==1 and post.locator('.cmt').count()==3)
        post.locator('[data-act=cmtdel]').first.click()
        ck(f'{w} last delete removes the key',json.loads(page.evaluate("localStorage.getItem('h3c-cmt-Nina')"))=={})
        # check-in post owner
        fk=page.locator('.feed[data-key^="f:Kellye:w:"]')
        ck(f'{w} check-in post has Say something',fk.locator('[data-act=cmtopen]').count()==1)
        fk.locator('[data-act=cmtopen]').click(); page.keyboard.type('proud of you'); page.keyboard.press('Enter')
        mine=json.loads(page.evaluate("localStorage.getItem('h3c-cmt-Nina')"))
        ck(f'{w} check-in comment carries Kellye as owner',any(v[0].get('o')=='Kellye' and k.startswith('f:Kellye:w:') for k,v in mine.items()))
        ck(f'{w} no sideways scroll',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        # photo viewer
        page.goto('file://'+os.path.abspath(APP)+'#photo/Kellye.k1'); page.wait_for_selector('.pview')
        ck(f'{w} viewer shows comments and Say something',page.locator('#app .cmt').count()==2 and page.locator('#app [data-act=cmtopen]').count()==1)
        page.click('#app [data-act=cmtopen]'); page.keyboard.type('from the viewer'); page.click('[data-act=cmtpost]')
        ck(f'{w} viewer comment saved on the same post id','pic:Kellye:k1' in json.loads(page.evaluate("localStorage.getItem('h3c-cmt-Nina')")) and page.locator('#app .cmt').count()==3)
        page.click('#app [data-act=cmtopen]'); page.fill('#cmt-in','leaving'); page.goto('file://'+os.path.abspath(APP)+'#photos'); page.wait_for_selector('.pgrid')
        ck(f'{w} leaving the page closes an open box',page.evaluate('ui.cmt')==None)
        ck(f'{w} no page errors or dialogs',not errs)
        if w==390:
            page.goto('file://'+os.path.abspath(APP)+'#coven'); page.wait_for_selector(PK); page.locator(PK).locator('[data-act=cmtopen]').click(); page.keyboard.type('stealing this look')
            page.wait_for_timeout(1000); page.locator(PK).screenshot(path='/tmp/shots/cmt-390-post.png')
        ctx.close()
    # pushes: a photo push opens the viewer, a check-in push scrolls to the post and highlights it
    ctx,page,errs=open_page(b,390,'#today'); page.wait_for_selector('.habit')
    page.evaluate("openPostFromPush('pic:Kellye:k1')"); page.wait_for_selector('.pview')
    ck('push about a photo opens its viewer',page.evaluate('location.hash')=='#photo/Kellye.k1')
    fid=page.evaluate("'f:Kellye:w:2026-11-12'")
    page.evaluate(f"openPostFromPush('{fid}')"); page.wait_for_selector(f'.feed[data-key="{fid}"].pulse',timeout=5000)
    ck('push about a check-in opens The Tea and highlights it',page.evaluate('location.hash')=='#coven')
    ctx.close()
    ctx,page,errs=open_page(b,390,'?push=tea&post='+'f%3AKellye%3Aw%3A2026-11-12'+'#coven/tea')
    page.wait_for_selector('.feed[data-key="f:Kellye:w:2026-11-12"].pulse',timeout=5000)
    ck('opening from a closed app lands on the post and cleans the link',page.evaluate('location.search')=='' and page.evaluate('location.hash')=='#coven')
    ck('no page errors on push open',not errs)
    ctx.close(); b.close()
print(f'{checks-fails}/{checks} checks passed'); raise SystemExit(1 if fails else 0)
