"""The Morning Show (index.html): habit row link, habit page button, start screen, scenes, timer, pause,
skip, back, early stop, finish with auto-check and Undo, sound switch, music row, reduced motion.
Runs with Firebase blocked, so the app uses its local cache only. Never touches the real database."""
import os, json
from playwright.sync_api import sync_playwright
HERE=os.path.dirname(os.path.abspath(__file__))
APP=os.environ.get('SPELLCHECK_HABITS', os.path.join(HERE,'..','index.html'))
fails=0; checks=0
def ck(name,ok):
    global fails,checks
    checks+=1
    if not ok: fails+=1; print('FAIL',name)

INIT="""
  localStorage.setItem('h3-whoami','Nina');
  localStorage.setItem('h3c-prof-Nina',JSON.stringify({setup:true,big3:{sun:'Libra',moon:'Pisces',rising:''}}));
  const hb={a:{id:'a',name:'Move',type:'yesno',days:[1,1,1,1,1,1,1],shared:true,created:1,createdDay:'2026-11-01',preset:'move'},
            s:{id:'s',name:'The Morning Show 8 min',type:'yesno',days:[1,1,1,1,1,1,1],shared:false,created:2,createdDay:'2026-11-01',preset:'show'}};
  localStorage.setItem('h3c-habits-Nina',JSON.stringify(hb));
  window.__off=0; window.__showNow=()=>Date.now()+window.__off;
  window.__locks=0; window.__rels=0;
  Object.defineProperty(navigator,'wakeLock',{configurable:true,value:{request:async()=>{window.__locks++;return{release(){window.__rels++;},addEventListener(){}};}}});
"""
def adv(page,sec):
    page.evaluate(f"window.__off+={int(sec*1000)}")
    page.wait_for_timeout(180)
def txt(page,sel): return (page.locator(sel).first.text_content() or '').strip()
def figsig(page): return page.evaluate("[...document.querySelectorAll('#sh-fig path')].map(p=>p.getAttribute('d')).join('|')")
def is_checked(page): return page.evaluate("(()=>{const h=JSON.parse(localStorage.getItem('h3c-log-Nina')||'{}');return Object.values(h).some(d=>d&&d.s>=1);})()")

with sync_playwright() as pw:
    b=pw.chromium.launch()
    for w in (360,390,430):
        ctx=b.new_context(viewport={'width':w,'height':780},device_scale_factor=1,has_touch=True,is_mobile=True)
        page=ctx.new_page()
        page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
        page.add_init_script(INIT)
        errs=[]
        page.on('pageerror',lambda e: errs.append(str(e)) if 'Access is denied' not in str(e) else None)
        page.goto('file://'+os.path.abspath(APP)+'#today')
        page.wait_for_selector('.strip')
        # row link
        ck(f'{w} row shows Take the stage on the show habit only',page.locator('.showlink').count()==1)
        ck(f'{w} show habit has its own icon',page.locator('.hico.i-show').count()==1)
        page.click('.showlink')
        page.wait_for_selector('#show:not([hidden])')
        ck(f'{w} start screen opens',txt(page,'.sh-scr.on h1')=='Ready when you are')
        ck(f'{w} start lists the eight scenes with real move names',page.locator('.sh-list li').count()==8 and txt(page,'.sh-list li:nth-child(1)')=='Curtain Up (Lymph Jumps)' and txt(page,'.sh-list li:nth-child(8)')=='Encore (Twisted Jumps)')
        ck(f'{w} start says screen stays on when wake lock exists','Your screen stays on during the show' in txt(page,'.sh-scr.on'))
        ck(f'{w} app is hidden behind the show',page.evaluate("document.getElementById('app').inert===true"))
        ck(f'{w} start screen has no sideways scroll',page.evaluate("document.getElementById('show').scrollWidth<=document.getElementById('show').clientWidth"))
        # sound switch remembered
        ck(f'{w} sound on by default',page.get_attribute('[data-sh=sound]','aria-checked')=='true')
        page.click('[data-sh=sound]')
        ck(f'{w} sound switch off is remembered',page.get_attribute('[data-sh=sound]','aria-checked')=='false' and page.evaluate("localStorage.getItem('h3-show-sound')")=='0')
        page.click('[data-sh=sound]')
        ck(f'{w} sound switch back on',page.evaluate("localStorage.getItem('h3-show-sound')")=='1')
        # music row
        page.click('[data-sh=music]')
        src=page.evaluate("(document.querySelector('#sh-plf iframe')||{}).src||''")
        ck(f'{w} music row loads the playlist embed','open.spotify.com/embed/playlist/2iaaO0dqExGv34ILmxgV1M' in src)
        ck(f'{w} music row has an Open in Spotify link',page.get_attribute('#sh-pla','href')=='https://open.spotify.com/playlist/2iaaO0dqExGv34ILmxgV1M')
        ck(f'{w} player slot shows on start',page.locator('#sh-pl:not(.hid)').count()==1)
        # begin
        page.click('[data-sh=go]')
        page.wait_for_timeout(150)
        ck(f'{w} scene 1 title shows name and real move',txt(page,'#sh-name')=='Curtain Up (Lymph Jumps)')
        ck(f'{w} scene 1 label',txt(page,'#sh-top')=='Scene 1 of 8')
        ck(f'{w} scene 1 cue is the approved cue',txt(page,'#sh-cue')=='Bounce lightly on the spot, arms loose, like the curtain just went up.')
        ck(f'{w} wake lock requested',page.evaluate("window.__locks")>=1)
        ck(f'{w} player stays on the scene screen',page.locator('#sh-pl:not(.hid)').count()==1 and page.locator('#sh-plf iframe').count()==1)
        ck(f'{w} back is hidden on scene 1',page.locator('#sh-back').is_hidden())
        ck(f'{w} figure is drawn',len(figsig(page))>500)
        sigs={figsig(page)}
        for _ in range(4):
            page.wait_for_timeout(130); sigs.add(figsig(page))
        ck(f'{w} figure moves',len(sigs)>1)
        ck(f'{w} scene screen has no sideways scroll',page.evaluate("document.getElementById('show').scrollWidth<=document.getElementById('show').clientWidth"))
        # scene advances by the clock, with the between-scene line first
        adv(page,60)
        ck(f'{w} scene 2 after a minute',txt(page,'#sh-top')=='Scene 2 of 8' and txt(page,'#sh-name')=='The Soloist (Arm Swings)')
        ck(f'{w} between-scene line shows first',txt(page,'#sh-cue')=='Shake it out. On to the next one.')
        adv(page,2.5)
        ck(f'{w} then the cue',txt(page,'#sh-cue').startswith('One arm swings up'))
        # pause holds the clock
        t_before=txt(page,'#sh-tm')
        page.click('.sh-scr.on [data-sh=pause]')
        ck(f'{w} intermission copy',txt(page,'.sh-scr.on h1')=='Intermission' and 'We paused the show. It picks up right where you left off.' in txt(page,'.sh-scr.on'))
        ck(f'{w} intermission shows scene count',txt(page,'#sh-pk')=='2 of 8')
        ck(f'{w} wake lock released on pause',page.evaluate("window.__rels")>=1)
        adv(page,120)
        page.click('.sh-scr.on [data-sh=resume]'); page.wait_for_timeout(150)
        ck(f'{w} resume keeps the same scene and time',txt(page,'#sh-top')=='Scene 2 of 8' and txt(page,'#sh-tm')==t_before)
        # skip and back
        page.click('[data-sh=skip]'); page.click('[data-sh=skip]'); page.click('[data-sh=skip]')
        ck(f'{w} skip moves on',txt(page,'#sh-top')=='Scene 5 of 8')
        ck(f'{w} halfway line at scene 5',txt(page,'#sh-half')=='Four scenes down, four to go. Take a breath, we are loving this.' and page.locator('#sh-half').is_visible())
        page.click('[data-sh=back]')
        ck(f'{w} back goes to the last scene',txt(page,'#sh-top')=='Scene 4 of 8' and page.locator('#sh-half').is_hidden())
        ck(f'{w} scene 4 cue',txt(page,'#sh-cue').startswith('Bend your knees, fold forward'))
        for _ in range(4): page.click('[data-sh=skip]')
        ck(f'{w} last scene button says Finish',txt(page,'#sh-top')=='Scene 8 of 8' and txt(page,'#sh-skip')=='Finish')
        ck(f'{w} not checked yet',not is_checked(page))
        # finish by the clock
        adv(page,61)
        ck(f'{w} finish screen after the last minute',txt(page,'.sh-scr.on h1')=='Bravo')
        ck(f'{w} finish copy','The show is done and your habit is checked off. Nicely done.' in txt(page,'.sh-scr.on'))
        ck(f'{w} habit is checked off',is_checked(page))
        ck(f'{w} player hidden on finish',page.locator('#sh-pl.hid').count()==1)
        page.click('.sh-scr.on [data-sh=undo]'); page.wait_for_timeout(150)
        ck(f'{w} undo closes the show and unchecks',page.locator('#show[hidden]').count()==1 and not is_checked(page))
        ck(f'{w} app is usable again',page.evaluate("document.getElementById('app').inert!==true")and page.locator('.showlink').count()==1)
        ck(f'{w} wake lock released at the end',page.evaluate("window.__rels")>=2)
        # finish via Back to today keeps the check, row turns done
        page.click('.showlink'); page.click('[data-sh=go]'); page.wait_for_timeout(100)
        for _ in range(8): page.click('[data-sh=skip]')
        ck(f'{w} skipping through the last scene finishes',txt(page,'.sh-scr.on h1')=='Bravo' and is_checked(page))
        page.click('.sh-scr.on [data-sh=close]'); page.wait_for_timeout(150)
        ck(f'{w} row shows the check after the show',page.locator('.habit:has([data-id=s].check.on)').count()==1)
        # early stop: leave it
        page.click('[data-act=tog][data-id=s]')
        ck(f'{w} unchecked by hand',not is_checked(page))
        page.click('.showlink'); page.click('[data-sh=go]'); page.click('.sh-scr.on [data-sh=stop]')
        ck(f'{w} early stop copy','Stopping early is completely fine with us. Count it or leave it, both are fine.' in txt(page,'.sh-scr.on'))
        page.click('.sh-scr.on [data-sh=close]'); page.wait_for_timeout(100)
        ck(f'{w} leaving early does not check the habit',not is_checked(page) and page.locator('#show[hidden]').count()==1)
        # early stop: count it
        page.click('.showlink'); page.click('[data-sh=go]'); page.click('.sh-scr.on [data-sh=stop]'); page.click('.sh-scr.on [data-sh=count]')
        ck(f'{w} count it checks the habit',txt(page,'.sh-scr.on h1')=='Bravo' and is_checked(page))
        page.click('.sh-scr.on [data-sh=close]')
        # the show survives an app redraw
        page.click('.showlink'); page.wait_for_selector('#show:not([hidden])')
        page.evaluate("render()"); page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        ck(f'{w} a redraw of the app does not wipe the show',page.locator('#show:not([hidden])').count()==1 and txt(page,'.sh-scr.on h1')=='Ready when you are')
        page.keyboard.press('Escape')
        ck(f'{w} Escape closes the start screen',page.locator('#show[hidden]').count()==1)
        # closing stops the music
        page.click('.showlink'); page.click('[data-sh=music]'); page.click('.sh-scr.on [data-sh=close]')
        ck(f'{w} closing removes the player',page.locator('#sh-plf iframe').count()==0)
        # habit page button
        page.goto('file://'+os.path.abspath(APP)+'#habit/s'); page.wait_for_selector('.big')
        ck(f'{w} habit page has the button',page.locator('.body [data-act=showopen]').count()==1)
        page.click('.body [data-act=showopen]')
        ck(f'{w} habit page button opens the show',page.locator('#show:not([hidden])').count()==1)
        page.click('.sh-scr.on [data-sh=close]')
        # the Move habit has no show link
        page.goto('file://'+os.path.abspath(APP)+'#habit/a'); page.wait_for_selector('.big')
        ck(f'{w} other habits have no show button',page.locator('[data-act=showopen]').count()==0)
        ck(f'{w} no script errors {errs[:2]}',errs==[])
        ctx.close()
    # reduced motion: the figure holds still, the clock keeps running
    ctx=b.new_context(viewport={'width':390,'height':780},device_scale_factor=1,reduced_motion='reduce')
    page=ctx.new_page()
    page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
    page.add_init_script(INIT)
    page.goto('file://'+os.path.abspath(APP)+'#today'); page.wait_for_selector('.strip')
    page.click('.showlink'); page.click('[data-sh=go]'); page.wait_for_timeout(200)
    a=figsig(page); t0=txt(page,'#sh-tm'); adv(page,5)
    ck('reduced motion: figure holds still',figsig(page)==a)
    ck('reduced motion: timer keeps running',txt(page,'#sh-tm')!=t0)
    ctx.close()
    # no wake lock support: the start screen does not promise one
    ctx=b.new_context(viewport={'width':390,'height':780},device_scale_factor=1)
    page=ctx.new_page()
    page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
    page.add_init_script(INIT+"Object.defineProperty(navigator,'wakeLock',{configurable:true,value:undefined});" )
    page.goto('file://'+os.path.abspath(APP)+'#today'); page.wait_for_selector('.strip')
    page.click('.showlink')
    ck('no wake lock: start screen does not say the screen stays on','screen stays on' not in txt(page,'.sh-scr.on'))
    page.click('[data-sh=go]'); page.wait_for_timeout(150)
    ck('no wake lock: show still runs',txt(page,'#sh-top')=='Scene 1 of 8')
    ctx.close()
    b.close()
print(f'{checks} checks, {fails} failed')
raise SystemExit(1 if fails else 0)
