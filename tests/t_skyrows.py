"""Read your sky: degree-based planet rows. Planet positions, natal degrees, aspects within 2 degrees, phases, until dates,
the approved line pool, daily rotation, the quiet line with the next hit, and the rows in the pop-out. Firebase blocked, clock pinned.
The birth details here are made up for the test."""
import os, sys, datetime, json, re
from playwright.sync_api import sync_playwright
APP=os.path.abspath(os.environ.get('SPELLCHECK_HABITS', os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','index.html')))
fails=0;checks=0
def ck(n,ok,info=None):
    global fails,checks;checks+=1
    if not ok: fails+=1;print('FAIL',n,info if info is not None else '')
BIRTH={'date':'1991-02-13','time':'01:30','placeTz':'America/Chicago','placeLat':41.8781,'placeLon':-87.6298,'place':'Chicago, Illinois'}
def init(birth=BIRTH,big3={'sun':'Aquarius','moon':'Aquarius','rising':'Sagittarius'}):
    prof={'setup':True,'name':'Nina','big3':big3}
    if birth: prof['birth']=birth
    return ("localStorage.setItem('h3-whoami','Nina');localStorage.setItem('h3c-prof-Nina',%s);"
            "localStorage.setItem('h3c-prof-Kellye',%s);") % (json.dumps(json.dumps(prof)),json.dumps(json.dumps(dict(prof,name='Kellye'))))
# Reference longitudes from astronomy-engine (geocentric, true ecliptic of date) at noon Pacific
TRUTH={"2026-11-16":{"Sun":234.477,"Mercury":215.909,"Venus":203.018,"Mars":146.141},"2027-03-01":{"Sun":341.002,"Mercury":321.083,"Venus":300.666,"Mars":146.843},"2027-08-20":{"Sun":147.583,"Mercury":156.872,"Venus":150.016,"Mars":202.114}}
CHIP=re.compile(r'^(Sun|Mercury|Venus|Mars) · (conjunction|sextile|square|trine|opposition) · (your|Kellye’s) (Sun|Moon|Rising) · (until [A-Z][a-z]{2} \d{1,2}|last day today)$')
with sync_playwright() as pw:
    b=pw.chromium.launch()
    def new(date,w=390,script=None):
        c=b.new_context(viewport={'width':w,'height':800});p=c.new_page()
        p.route('**/*',lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
        p.clock.install(time=datetime.datetime.fromisoformat(date+'T12:00:00'));p.add_init_script(script or init());return p
    p=new('2026-11-16');errs=[];p.on('pageerror',lambda e:errs.append(str(e)))
    p.goto('file://'+APP+'#today');p.wait_for_selector('.tc')
    # planet positions
    worst=p.evaluate("(T)=>{let w=0;for(const k in T)for(const pl in T[k]){let d=Math.abs(skyLon(pl,skyNoonJd(k))-T[k][pl]);d=Math.min(d,360-d);w=Math.max(w,d);}return w}",TRUTH)
    ck('planet positions within 0.05 degrees of astronomy-engine',worst<0.05,worst)
    # natal degrees
    nd=p.evaluate("natalDeg('Nina')")
    ck('natal degrees: Sun, Moon and Rising from full birth details',nd and all(k in nd for k in ('Sun','Moon','Rising')),nd)
    ck('natal Sun is Aquarius, Rising is a real degree',nd and 300<=nd['Sun']<330 and 0<=nd['Rising']<360,nd)
    ck('no birth time: no Rising',p.evaluate("(()=>{D.prof.Nina.birth={date:'1991-02-13',noTime:true,placeTz:'America/Chicago',placeLat:41.8,placeLon:-87.6};const v=natalDeg('Nina');return v&&v.Sun!=null&&v.Rising==null})()"))
    ck('no Moon degree when the Moon moves too much on an unknown time',p.evaluate("(()=>{const v=natalDeg('Nina');return v.Moon==null})()"))
    ck('no birth date: no natal degrees',p.evaluate("(()=>{D.prof.Nina.birth={};return natalDeg('Nina')===null})()"))
    p.evaluate("D.prof.Nina.birth="+json.dumps(BIRTH))
    # scan 90 days for rows and quiet days
    scan=p.evaluate("""(()=>{const t=todayK();const days=[];for(let i=0;i<90;i++){const k=addDays(t,i);days.push({k,hits:skyHits('Nina',k),rows:skyPlanetRows('Nina',k)});}return days})()""")
    rowday=next((d for d in scan if d['rows']),None);quietday=next((d for d in scan if not d['rows']),None)
    ck('a test chart gets planet rows within 90 days, and a quiet day too',rowday is not None and quietday is not None)
    ck('every hit is within 2 degrees, every day',p.evaluate("(()=>{const t=todayK();for(let i=0;i<90;i++){const k=addDays(t,i);for(const h of skyHits('Nina',k)){const ang={conjunction:0,sextile:60,square:90,trine:120,opposition:180}[h.asp];if(skyOrbAt(h.pl,natalDeg('Nina')[h.pt],ang,k)>2)return false;}}return true})()"))
    ck('at most 3 planet rows a day',all(len(d['rows'])<=3 for d in scan))
    # phases and until dates along one stretch
    seq=p.evaluate("""(()=>{const t=todayK();for(let i=0;i<90;i++){const k=addDays(t,i);const h=skyHits('Nina',k)[0];if(!h)continue;const out=[];
       for(let d=h.start;d<=h.until;d=addDays(d,1)){const x=skyHits('Nina',d).find(y=>y.pl===h.pl&&y.pt===h.pt&&y.asp===h.asp);out.push(x?x.phase:'gone');}
       const ang={conjunction:0,sextile:60,square:90,trine:120,opposition:180}[h.asp];
       return {out,after:skyOrbAt(h.pl,natalDeg('Nina')[h.pt],ang,addDays(h.until,1)),before:skyOrbAt(h.pl,natalDeg('Nina')[h.pt],ang,addDays(h.start,-1)),key:h.pl+h.asp+h.pt}}return null})()""")
    ck('a stretch runs building, then peak, then easing',seq and 'gone' not in seq['out'] and seq['out'].count('peak')>=1 and re.match(r'^(building,)*(peak,)+(easing,)*$',','.join(seq['out'])+','),seq)
    ck('until is the last day in orb, start the first',seq and seq['after']>2 and seq['before']>2,seq)
    # lines come from the approved pool and rotate
    pool=p.evaluate("PLANET_POOL")
    allines=[l for v in pool.values() for l in v]
    ck('pool: 566 approved lines in 119 slots',len(allines)==566 and len(pool)==119,(len(allines),len(pool)))
    ck('pool: keys are planet-aspect-point-phase',all(re.match(r'^(sun|mercury|venus|mars)-(conjunction|sextile|square|trine|opposition)-(sun|moon|rising)-(building|peak|easing)$',k) for k in pool))
    ck('pool: no em or en dashes, no exclamation points',not any(re.search('[–—!]',l) for l in allines))
    ck('pool: no retired phrases',not any(re.search(r'said what we said|lowkey iconic|everything hallelujah',l,re.I) for l in allines))
    ck('pool: no line twice',len(allines)==len(set(allines)))
    rot=p.evaluate("""(()=>{const t=todayK();for(let i=0;i<90;i++){const k=addDays(t,i),k2=addDays(k,1);for(const r of skyPlanetRows('Nina',k)){const r2=skyPlanetRows('Nina',k2).find(y=>y.pl===r.pl&&y.pt===r.pt&&y.asp===r.asp&&y.phase===r.phase);if(r2&&skyPool(r).length>1)return [r.txt,r2.txt]}}return null})()""")
    ck('the same row on back-to-back days shows a different line',rot is None or rot[0]!=rot[1],rot)
    ck('every shown line is in its own pool',all(r['txt'] in pool['-'.join([r['pl'],r['asp'],r['pt'],r['phase']]).lower()] for d in scan for r in d['rows']))
    ck('no errors',not errs,errs)
    # the pop-out on a day with rows
    q=new(rowday['k']);q.goto('file://'+APP+'#sky');q.wait_for_selector('.skybox')
    chips=q.evaluate("[...document.querySelectorAll('.skybox .chipx')].map(e=>e.textContent).filter(t=>!t.startsWith('Moon'))")
    ck(rowday['k']+': planet chips read Planet · aspect · your point · until date',len(chips)==len(rowday['rows']) and all(CHIP.match(c) for c in chips),chips)
    ck(rowday['k']+': Moon rows come first, then planet rows',q.evaluate("(()=>{const c=[...document.querySelectorAll('.skybox .chipx')].map(e=>e.textContent);const i=c.findIndex(t=>!t.startsWith('Moon'));return i>0&&c.slice(i).every(t=>!t.startsWith('Moon'))})()"))
    ck(rowday['k']+': no quiet line on a day with rows',q.locator('.skybox .skyquiet').count()==0)
    ck(rowday['k']+': no astrology words in the planet lines',not any(re.search(r'\b(trine|sextile|square|opposition|conjunction|retrograde)\b',t,re.I) for t in q.evaluate("[...document.querySelectorAll('.skybox .srow .sd')].map(e=>e.textContent)")))
    q.click('[data-act=skywho][data-p=Kellye]')
    kchips=q.evaluate("[...document.querySelectorAll('.skybox .chipx')].map(e=>e.textContent).filter(t=>!t.startsWith('Moon'))")
    ck('another person: chips say her name',kchips and all('Kellye’s' in c for c in kchips),kchips)
    q.screenshot(path='/tmp/sky_planet_rows.png',full_page=True)
    for w in (360,430):
        r=new(rowday['k'],w);r.goto('file://'+APP+'#sky');r.wait_for_selector('.skybox')
        ck(f'{w}: no sideways scroll with planet rows',r.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        ck(f'{w}: chips fit on screen',r.evaluate("[...document.querySelectorAll('.skybox .chipx')].every(e=>e.getBoundingClientRect().right<=innerWidth)"))
    # a quiet day: one approved quiet line and the next hit
    q=new(quietday['k']);q.goto('file://'+APP+'#sky');q.wait_for_selector('.skybox')
    ql=q.evaluate("(()=>{const e=document.querySelector('.skybox .skyquiet .sd');return e?e.firstChild.textContent:''})()")
    ck(quietday['k']+': quiet day shows an approved quiet line',ql in q.evaluate("FC.QUIET"),ql)
    nx=q.evaluate("(()=>{const e=document.querySelector('.skybox .skynext');return e?e.textContent:''})()")
    m=re.match(r'^Next up: (Sun|Mercury|Venus|Mars) meets your (Sun|Moon|Rising), ([A-Z][a-z]{2} \d{1,2})$',nx)
    ck(quietday['k']+': quiet day names the next hit',m is not None,nx)
    ck(quietday['k']+': the next hit really is the next day with a row',q.evaluate("(()=>{const n=skyNextHit('Nina',todayK());if(!n)return false;for(let d=addDays(todayK(),1);d<n.day;d=addDays(d,1))if(skyPlanetRows('Nina',d).length)return false;return skyPlanetRows('Nina',n.day).length>0})()"))
    b.close()
print(f't_skyrows.py: {checks} checks, {fails} failed');sys.exit(1 if fails else 0)
