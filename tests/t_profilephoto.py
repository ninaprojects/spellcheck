"""Profile photo (index.html): a redraw while the phone's photo picker is open must not lose the chosen photo.
A friend's data arriving redraws the page, which used to rebuild the hidden file input. Clock pinned. Firebase blocked."""
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
good=os.path.join(tmp,'ok.jpg'); Image.new('RGB',(900,600),(200,80,120)).save(good)
bad=os.path.join(tmp,'bad.jpg'); open(bad,'wb').write(b'this is not an image')
INIT="""localStorage.setItem('h3-whoami','Nina');localStorage.setItem('h3c-prof-Nina',JSON.stringify({setup:true,big3:{sun:'Libra',moon:'Pisces',rising:'Leo'}}));"""
with sync_playwright() as pw:
    b=pw.chromium.launch()
    for w in (360,390):
        ctx=b.new_context(viewport={'width':w,'height':800}); page=ctx.new_page()
        page.clock.install(time=datetime.datetime(2026,11,11,12,0,0))
        page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
        page.add_init_script(INIT)
        errs=[]; page.on('pageerror',lambda e: errs.append(str(e)))
        page.goto('file://'+os.path.abspath(APP)+'#me'); page.wait_for_selector('#pf',state='attached')
        page.evaluate("window.__pf=document.getElementById('pf')")
        with page.expect_file_chooser() as fc:
            page.click('label.link[for=pf]')
        # a friend's update redraws the page while the picker is open
        for _ in range(3): page.evaluate("render()")
        ck(f'{w} input survives redraws while the picker is open',page.evaluate("document.getElementById('pf')===window.__pf"))
        fc.value.set_files(good); page.wait_for_function("localStorage.getItem('h3c-photo-Nina')")
        ph=json.loads(page.evaluate("localStorage.getItem('h3c-photo-Nina')"))
        ck(f'{w} photo saved as a small JPEG',ph['d'].startswith('data:image/jpeg') and len(ph['d'])<120000)
        page.wait_for_selector('.phbig img')
        ck(f'{w} avatar shows the new photo',page.locator('.phbig img').count()==1)
        ck(f'{w} redraws resume afterwards',page.evaluate("!ui.picking && !ui.dirty"))
        # a photo that will not load says so on screen
        with page.expect_file_chooser() as fc2:
            page.click('label.link[for=pf]')
        fc2.value.set_files(bad); page.wait_for_selector('.mehead [role=alert]')
        ck(f'{w} bad file shows a visible message','would not load' in page.locator('.mehead [role=alert]').text_content())
        # cancelled picker lets redraws resume
        with page.expect_file_chooser():
            page.click('label.link[for=pf]')
        ck(f'{w} redraw held while picking',page.evaluate("!!ui.picking")) 
        page.evaluate("document.getElementById('pf').dispatchEvent(new Event('cancel',{bubbles:false}))")
        ck(f'{w} cancel releases the hold',page.evaluate("!ui.picking"))
        ck(f'{w} no page errors',not errs)
        ctx.close()
    b.close()
print(f'{checks-fails}/{checks} checks passed'); raise SystemExit(1 if fails else 0)
