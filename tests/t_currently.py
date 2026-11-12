"""Currently (reading, watching, listening) and Shared reads (index.html): edit on Me, show on profiles, shares in The Tea.
Clock pinned to Wed Nov 11 2026. Firebase blocked. The media Worker is mocked. Never touches the real database."""
import os, json, datetime
from playwright.sync_api import sync_playwright
HERE=os.path.dirname(os.path.abspath(__file__))
APP=os.environ.get('SPELLCHECK_HABITS', os.path.join(HERE,'..','index.html'))
fails=0; checks=0
def ck(name,ok):
    global fails,checks
    checks+=1
    if not ok: fails+=1; print('FAIL',name)
KC={'reading':{'t':'Piranesi','u':'https://books.example.com/p','i':'','s':'Susanna Clarke'},
    'hist':[{'f':'reading','t':'Piranesi','u':'','at':'2026-11-09T12:00:00.000Z'}]}
KS=[{'id':'a','u':'https://example.com/read','l':'A good read','at':'2026-11-10T20:00:00.000Z'},
    {'id':'bad','u':'javascript:alert(1)','l':'Nope','at':'2026-11-10T21:00:00.000Z'}]
INIT=f"""
  localStorage.setItem('h3-whoami','Nina');
  localStorage.setItem('h3c-prof-Nina',JSON.stringify({{setup:true,big3:{{sun:'Libra',moon:'Pisces',rising:'Leo'}}}}));
  localStorage.setItem('h3c-prof-Kellye',JSON.stringify({{setup:true,big3:{{sun:'Aries',moon:'Cancer',rising:''}}}}));
  localStorage.setItem('h3c-cur-Kellye',JSON.stringify({json.dumps(KC)}));
  localStorage.setItem('h3c-shr-Kellye',JSON.stringify({json.dumps(KS)}));
"""
RES={'results':[{'title':'Tomorrow, and Tomorrow','subtitle':'Gabrielle Zevin','image':'https://img.example.com/t.jpg','url':'https://books.example.com/t'},
                {'title':'Tomorrow Will Be Different','subtitle':'Someone Else','image':'','url':''}]}
def mock(page,mode):
    def h(r):
        u=r.request.url
        if 'workers.dev' in u:
            if mode=='down': return r.abort()
            return r.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps(RES))
        if u.startswith('http'): return r.abort()
        return r.continue_()
    page.route('**/*',h)
def new(b,w,mode='ok'):
    ctx=b.new_context(viewport={'width':w,'height':800})
    page=ctx.new_page(); page.clock.install(time=datetime.datetime(2026,11,11,12,0,0))
    mock(page,mode); page.add_init_script(INIT)
    errs=[]; page.on('pageerror',lambda e: errs.append(str(e)))
    return ctx,page,errs
def load(page,h):
    page.goto('file://'+os.path.abspath(APP)+h); page.wait_for_selector('nav')
    page.wait_for_timeout(300)
def txt(page): return page.locator('#app').text_content() or ''
with sync_playwright() as pw:
    b=pw.chromium.launch()
    for w in (360,390,430):
        ctx,page,errs=new(b,w)
        load(page,'#me')
        ck(f'{w} Me has Currently with three fields',all(x in txt(page) for x in ('Reading','Watching','Listening')))
        ck(f'{w} Me has Shared reads',page.locator('#shr-url').count()==1)
        # search and pick
        page.fill('#cur-reading','tomorrow')
        page.wait_for_selector('#curres-reading .opt',timeout=4000)
        ck(f'{w} search shows two matches',page.locator('#curres-reading .opt').count()==2)
        page.click('#curres-reading .opt >> nth=0'); page.wait_for_timeout(200)
        a=page.locator('.cur .ct a').first
        ck(f'{w} pick saves with a link',a.text_content().strip()=='Tomorrow, and Tomorrow' and a.get_attribute('href')=='https://books.example.com/t' and a.get_attribute('rel')=='noopener noreferrer')
        saved=json.loads(page.evaluate("localStorage.getItem('h3c-cur-Nina')"))
        ck(f'{w} saved record and history',saved['reading']['t']=='Tomorrow, and Tomorrow' and saved['hist'][0]['f']=='reading')
        # typed fallback
        page.fill('#cur-watching','my own show'); page.wait_for_selector('#curres-watching [data-act=curtyped]')
        page.click('#curres-watching [data-act=curtyped]'); page.wait_for_timeout(200)
        ck(f'{w} typed value saves',json.loads(page.evaluate("localStorage.getItem('h3c-cur-Nina')"))['watching']['t']=='my own show')
        # edit and clear
        page.click('[data-act=curclear][data-f=watching]'); page.wait_for_timeout(200)
        ck(f'{w} clear empties the field','watching' not in json.loads(page.evaluate("localStorage.getItem('h3c-cur-Nina')")))
        ck(f'{w} edit shows the box',(page.click('[data-act=curedit][data-f=reading]') or True) and page.locator('#cur-reading').count()==1)
        page.click('[data-act=curcancel][data-f=reading]')
        # past updates
        page.click('[data-act=histtoggle]'); ck(f'{w} past updates open',page.locator('.hist div').count()>=1)
        # shares
        page.fill('#shr-url','not a link'); page.click('[data-act=shradd]')
        ck(f'{w} bad link is refused','does not look right' in txt(page))
        page.fill('#shr-url','example.org/story'); page.fill('#shr-label','A story')
        page.click('[data-act=shradd]'); page.wait_for_timeout(200)
        sh=json.loads(page.evaluate("localStorage.getItem('h3c-shr-Nina')"))
        ck(f'{w} share saved as https',len(sh)==1 and sh[0]['u']=='https://example.org/story' and sh[0]['l']=='A story')
        page.fill('#shr-url','https://example.org/story'); page.click('[data-act=shradd]')
        ck(f'{w} duplicate refused','already sent' in txt(page))
        ck(f'{w} Me no sideways scroll',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        # profile of Kellye
        load(page,'#person/Kellye')
        t=txt(page)
        ck(f'{w} profile shows her Currently','Piranesi' in t and 'Susanna Clarke' in t)
        ck(f'{w} profile shows her share','A good read' in t)
        ck(f'{w} planted javascript link not rendered',page.locator('a[href^="javascript"]').count()==0 and 'Nope' not in t)
        ck(f'{w} profile has no edit controls',page.locator('[data-act=curedit],[data-act=shradd],[data-act=shrdel]').count()==0)
        ck(f'{w} profile no sideways scroll',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        # Tea feed
        load(page,'#coven')
        ck(f'{w} Tea shows the shares',page.locator('.feed a.shr').count()>=2 and 'shared a read' in txt(page))
        # Today link
        load(page,'#today')
        ck(f'{w} Today link goes to Me',page.locator('a:has-text("Share what you are into")').get_attribute('href')=='#me')
        ck(f'{w} no page errors',not errs)
        if w==390:
            load(page,'#me'); page.wait_for_timeout(1200); page.screenshot(path='/tmp/shots/me390.png',full_page=True)
            load(page,'#person/Kellye'); page.wait_for_timeout(1200); page.screenshot(path='/tmp/shots/person2-390.png',full_page=True)
        ctx.close()
    # search down
    ctx,page,errs=new(b,390,'down'); load(page,'#me')
    page.fill('#cur-listening','abc'); page.wait_for_function("document.getElementById('curres-listening').textContent.includes('not available')",timeout=4000)
    ck('search down: says so and offers typed','not available' in page.locator('#curres-listening').text_content())
    ctx.close()
    # empty profile
    ctx=b.new_context(viewport={'width':390,'height':800}); page=ctx.new_page(); page.clock.install(time=datetime.datetime(2026,11,11,12,0,0)); mock(page,'ok')
    page.add_init_script(INIT.replace('h3c-cur-Kellye','x1').replace('h3c-shr-Kellye','x2')); load(page,'#person/Kellye')
    ck('empty profile lines','has not shared what she is into yet' in txt(page) and 'has not shared any reads yet' in txt(page))
    b.close()
print(f'{checks-fails}/{checks} checks passed'); raise SystemExit(1 if fails else 0)
