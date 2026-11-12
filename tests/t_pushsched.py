"""Push refresh (Nov 2026), app side (index.html): the schedule the push Worker reads (h3-sched-<Person>),
Currently updates in The Tea, and the new onboarding line. Clock pinned to Wed Nov 11 2026, Firebase replaced
by an in-memory stub. Never touches the real database."""
import os, json, datetime
from playwright.sync_api import sync_playwright
HERE=os.path.dirname(os.path.abspath(__file__))
APP=os.environ.get('SPELLCHECK_HABITS', os.path.join(HERE,'..','index.html'))
fails=0; checks=0
def ck(name,ok,detail=None):
    global fails,checks
    checks+=1
    if not ok: fails+=1; print('FAIL',name,'' if detail is None else str(detail)[:300])
KC={'reading':{'t':'Piranesi','u':'','i':'','s':'Susanna Clarke'},'hist':[{'f':'reading','t':'Piranesi','u':'','at':'2026-11-10T12:00:00.000Z'}]}
STUB=r"""
(function(){
  const store=window.__FB={};window.__SETS=[];
  const snap=v=>({exists(){return v!=null;},val(){return v==null?null:v;}});
  window.firebase={initializeApp(){},database(){return{ref(path){return{
    once(){return Promise.resolve(snap(store[path]));},
    on(e,cb){setTimeout(()=>cb(snap(store[path])),0);},off(){},
    set(v){window.__SETS.push(path);store[path]=v;return Promise.resolve();}};}};},
    messaging(){return{getToken(){return Promise.resolve(null);},onMessage(){}};}};
})();
"""
INIT=f"""
  localStorage.setItem('h3-whoami','Nina');
  localStorage.setItem('h3c-prof-Nina',JSON.stringify({{setup:true,big3:{{sun:'Libra',moon:'Pisces',rising:'Leo'}}}}));
  localStorage.setItem('h3c-prof-Kellye',JSON.stringify({{setup:true}}));
  localStorage.setItem('h3c-cur-Kellye',JSON.stringify({json.dumps(KC)}));
"""
def new(b,w,stub=True):
    ctx=b.new_context(viewport={'width':w,'height':800})
    page=ctx.new_page(); page.clock.install(time=datetime.datetime(2026,11,11,12,0,0))
    page.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
    if stub: page.add_init_script(STUB)
    page.add_init_script(INIT)
    errs=[]; page.on('pageerror',lambda e: errs.append(str(e)))
    return ctx,page,errs
def load(page,h=''):
    page.goto('file://'+os.path.abspath(APP)+h); page.wait_for_selector('nav'); page.wait_for_timeout(400)
html=open(APP,encoding='utf-8').read()
ck('onboarding: new notifications line is in, the stale one is gone','Nosy is a love language.' in html and 'keeps sending its usual ones too' not in html)
with sync_playwright() as pw:
    b=pw.chromium.launch()
    for w in (360,390,430):
        ctx,page,errs=new(b,w)
        load(page,'#today')
        raw=page.evaluate("window.__FB['recalData/h3-sched-Nina']")
        ck(f'{w} schedule is written for her',isinstance(raw,str),raw)
        s=json.loads(raw) if isinstance(raw,str) else {'brew':{},'sky':{}}
        ck(f'{w} brew questions for the next days',s['brew'].get('2026-11-11') and len(s['brew'])>=5,s['brew'])
        q=page.evaluate("brewQ('2026-11-11')")
        ck(f'{w} the brew question matches what the card shows',s['brew'].get('2026-11-11')==q,(q,s['brew'].get('2026-11-11')))
        ck(f'{w} sky days: Wednesday, the big sky days, New and Full Moons',all(k in s['sky'] for k in ('2026-11-11','2026-11-13','2026-11-18','2026-11-22','2026-11-24')),list(s['sky']))
        ck(f'{w} sky days: ordinary days are left out','2026-11-12' not in s['sky'] and '2026-11-14' not in s['sky'],list(s['sky']))
        h=page.evaluate("forecastFor('Nina','2026-11-13').headline")
        ck(f'{w} sky headline is the one Read your sky shows',s['sky'].get('2026-11-13',{}).get('h')==h and s['sky']['2026-11-13'].get('ev')=='Mercury and Venus turn forward',(h,s['sky'].get('2026-11-13')))
        ck(f'{w} only her own record is written',all(p.endswith('-Nina') for p in page.evaluate("window.__SETS")),page.evaluate("window.__SETS"))
        n=len(page.evaluate("window.__SETS")); page.evaluate("render()"); page.wait_for_timeout(300)
        ck(f'{w} no rewrite when nothing changed',len(page.evaluate("window.__SETS"))==n)
        ck(f'{w} the Saved pill stays quiet for the schedule',page.locator('#sync').text_content() in ('',None))
        # Currently in The Tea
        load(page,'#coven')
        t=page.locator('#app').text_content()
        line=page.evaluate("fill(pick(CUR_LINES.reading,'cur:Kellye:2026-11-10T12:00:00.000Z'),{name:'Kellye'})")
        ck(f'{w} Currently update shows in The Tea',(line+': Piranesi') in t,(line,t[:400]))
        ck(f'{w} Currently post has reactions',page.locator('.feed:has-text("Piranesi") .rx button').count()==3)
        ck(f'{w} no sideways scroll',page.evaluate("document.documentElement.scrollWidth<=innerWidth"))
        ck(f'{w} no page errors',not errs,errs)
        ctx.close()
    # preview mode never writes draft questions
    ctx,page,errs=new(b,390)
    load(page,'?brew=preview#today')
    ck('preview: no schedule written',page.evaluate("window.__FB['recalData/h3-sched-Nina']") is None)
    ctx.close()
    # no Big 3: brew still written, no sky days
    ctx,page,errs=new(b,390)
    page.add_init_script("localStorage.setItem('h3c-prof-Nina',JSON.stringify({setup:true}));")
    load(page,'#today')
    s=json.loads(page.evaluate("window.__FB['recalData/h3-sched-Nina']") or '{"brew":{},"sky":{}}')
    ck('no Big 3: brew is written, sky is left empty',len(s['brew'])>=5 and s['sky']=={},s)
    ctx.close()
    b.close()
print(f'{checks} checks, {fails} failed')
