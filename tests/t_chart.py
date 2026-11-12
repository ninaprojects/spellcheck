"""Birth chart screenshot: the OCR text is stubbed, so this checks parsing, the confirm card and saving."""
import os, sys, json, base64
from playwright.sync_api import sync_playwright
HERE=os.path.dirname(os.path.abspath(__file__)); APP=os.path.abspath(os.path.join(HERE,'..','index.html'))
fails=0; checks=0
def ck(n,ok):
    global fails,checks; checks+=1
    if not ok: fails+=1; print('FAIL',n)
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
open('/tmp/chart.png','wb').write(PNG)
def stub(text):
    return "window.Tesseract={recognize:async()=>({data:{text:%s}})};"%json.dumps(text)
with sync_playwright() as pw:
    b=pw.chromium.launch()
    for label,text,expect in [('label first','Sun Libra\nMoon Pisces\nRising Aries',('Libra','Pisces','Aries')),('sign first','Scorpio SUN\nCancer MOON\nLeo ASCENDANT',('Scorpio','Cancer','Leo')),('partial','Sun Gemini\nnothing else',('Gemini','',''))]:
        pg=b.new_page(viewport={'width':390,'height':800})
        pg.route('**/*',lambda r: r.fulfill(body=stub(text),content_type='application/javascript') if 'tesseract' in r.request.url else (r.abort() if r.request.url.startswith('http') else r.continue_()))
        pg.add_init_script("localStorage.setItem('h3-whoami','Nina');localStorage.setItem('h3c-prof-Nina',JSON.stringify({setup:true,big3:{moon:'Taurus'}}))")
        errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto('file://'+APP+'#me/settings');pg.reload();pg.wait_for_selector('#cf',state='attached')
        pg.set_input_files('#cf','/tmp/chart.png')
        pg.wait_for_selector('[data-act=chartsave]')
        txt=pg.inner_text('#app')
        ck(label+': found card',all((not v) or v in txt for v in expect))
        ck(label+': no sideways scroll',pg.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        pg.click('[data-act=chartsave]')
        saved=json.loads(pg.evaluate("localStorage.getItem('h3c-prof-Nina')"))['big3']
        ck(label+': sun saved',saved.get('sun','')==expect[0])
        ck(label+': moon '+('replaced' if expect[1] else 'kept'),saved.get('moon')==(expect[1] or 'Taurus'))
        ck(label+': no page errors',not errs)
        pg.close()
    # nothing readable
    pg=b.new_page(viewport={'width':390,'height':800})
    pg.route('**/*',lambda r: r.fulfill(body=stub('hello world'),content_type='application/javascript') if 'tesseract' in r.request.url else (r.abort() if r.request.url.startswith('http') else r.continue_()))
    pg.add_init_script("localStorage.setItem('h3-whoami','Nina');localStorage.setItem('h3c-prof-Nina',JSON.stringify({setup:true}))")
    pg.goto('file://'+APP+'#me/settings');pg.reload();pg.wait_for_selector('#cf',state='attached');pg.set_input_files('#cf','/tmp/chart.png')
    pg.wait_for_selector('text=We could not read the signs')
    ck('unreadable shows help',True)
    b.close()
print(f't_chart.py: {checks} checks, {fails} failed'); sys.exit(1 if fails else 0)
