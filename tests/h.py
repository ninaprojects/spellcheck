import json, base64, io, time, os, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.environ.get('SPELLCHECK_APP', os.path.join(HERE, '..', 'index.html'))
from playwright.sync_api import sync_playwright

PNG = 'data:image/png;base64,' + base64.b64encode(bytes.fromhex(
 '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cfc0f01f0005000201a5f645400000000049454e44ae426082')).decode()

FIREBASE_STUB = r"""
(function(){
  const store = window.__FB = window.__FB || {};
  function snap(v){ return { exists(){ return v!==undefined && v!==null; }, val(){ return v===undefined?null:v; } }; }
  const listeners = {};
  window.firebase = {
    initializeApp(){},
    database(){ return { ref(path){ return {
      once(){ return Promise.resolve(snap(store[path])); },
      on(evt, cb){ (listeners[path] = listeners[path]||[]).push(cb); setTimeout(()=>cb(snap(store[path])),0); },
      off(){},
      set(v){
        window.__SETS = (window.__SETS||[]); window.__SETS.push(path);
        if(window.__FAIL_SETS) return new Promise((_,rej)=>setTimeout(()=>rej(new Error('offline')), 150));
        return new Promise(res=>setTimeout(()=>{ store[path]=v; res(); }, window.__SET_DELAY||120));
      },
      remove(){ delete store[path]; return Promise.resolve(); }
    }; } }; },
    messaging(){ return { getToken(){ return Promise.resolve(null); }, onMessage(){} }; }
  };
  firebase.database.ServerValue = {TIMESTAMP:1};
})();
"""

def seed_nina(session_loc='', daily_loc='', with_photos=True):
    iso = '2026-10-01T09:05:00.000Z'
    day1 = {"journaled":True,"noPhone":True,"waterOz":0,"gratitude":"","hasPhoto":with_photos,"photoType":"image/png","photoCaption":"","photoLocation":daily_loc,"photoAt":iso}
    sess = lambda done,ph: {"done":done,"timestamp":iso if done else None,"hasPhoto":ph,"photoType":"image/png" if ph else None,"photoCaption":"","photoLocation":session_loc if ph else ""}
    wk = {"sessions":[sess(True,with_photos),sess(False,False),sess(False,False)],"shares":[],"article":{"url":"","label":"","timestamp":None},"noSpend":{"done":False,"timestamp":None}}
    data = {"placements":{"sun":"Aquarius","moon":"Aquarius","rising":"Sagittarius","notes":""},"currently":{"reading":"","watching":"","listening":""},"kickoffIntention":"","hasProfilePic":False,"closingToast":"","days":{"1":day1},"weeks":{"0":wk}}
    fb = {"recalData/r2:recal:Nina": json.dumps(data)}
    if with_photos:
        fb["recalData/r2:recal-daily-photo:Nina:1"] = PNG
        fb["recalData/r2:recal-photo:Nina:0:0"] = PNG
    return fb

OVERPASS = {"elements":[
 {"type":"node","id":1,"lat":34.01960,"lon":-118.49100,"tags":{"name":"Equinox Santa Monica","leisure":"fitness_centre"}},
 {"type":"way","id":2,"center":{"lat":34.01900,"lon":-118.49300},"tags":{"name":"Tongva Park","leisure":"park"}},
 {"type":"node","id":3,"lat":34.01985,"lon":-118.49150,"tags":{"name":"Blue Bottle Coffee","amenity":"cafe"}},
 {"type":"node","id":4,"lat":34.01950,"lon":-118.49120,"tags":{"name":"Equinox Santa Monica","leisure":"fitness_centre"}},
 {"type":"node","id":5,"lat":34.01955,"lon":-118.49125,"tags":{"shop":"clothes"}},
 {"type":"node","id":6,"lat":34.02050,"lon":-118.49200,"tags":{"name":"Corner Boutique","shop":"clothes"}}
]}
BDC = {"city":"Santa Monica","locality":"Santa Monica","principalSubdivision":"California"}

class Env:
    def __init__(self, pw, fb, geo=(34.0195,-118.4912), overpass='ok', width=390, height=844, who='Nina', fail_sets=False, set_delay=120, ua=None, notif='default'):
        self.reqs=[]
        self.browser = pw.chromium.launch()
        ctx_args = dict(viewport={'width':width,'height':height}, device_scale_factor=2, has_touch=True, is_mobile=True)
        if ua: ctx_args['user_agent'] = ua
        if geo:
            ctx_args.update(geolocation={'latitude':geo[0],'longitude':geo[1]}, permissions=['geolocation'])
        self.ctx = self.browser.new_context(**ctx_args)
        self.page = self.ctx.new_page()
        self.errors=[]
        import datetime
        self.page.clock.install(time=datetime.datetime(2026,10,1,12,0,0))
        self.page.add_init_script("window.__NREQ = 0; try{ Object.defineProperty(Notification, 'permission', {get: ()=> '%s', configurable:true}); Notification.requestPermission = ()=>{ window.__NREQ++; return Promise.resolve('%s'==='denied'?'denied':'granted'); }; }catch(e){}" % (notif, notif))
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.page.on('console', lambda m: self.errors.append('console:'+m.text) if m.type=='error' else None)
        self.page.add_init_script("window.__FB = %s; window.__FAIL_SETS=%s; window.__SET_DELAY=%d; localStorage.setItem('recal-whoami','%s');" % (json.dumps(fb), 'true' if fail_sets else 'false', set_delay, who))
        def handler(route):
            url = route.request.url
            if 'firebase-app-compat' in url:
                route.fulfill(status=200, content_type='application/javascript', body=FIREBASE_STUB)
            elif 'firebasejs' in url or 'html2canvas' in url or 'tesseract' in url:
                route.fulfill(status=200, content_type='application/javascript', body='')
            elif 'fonts.googleapis' in url:
                route.fulfill(status=200, content_type='text/css', body='')
            elif 'overpass' in url:
                self.reqs.append(('overpass', route.request.post_data or ''))
                if overpass=='ok':
                    route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin':'*'}, body=json.dumps(OVERPASS))
                elif overpass=='empty':
                    route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin':'*'}, body=json.dumps({"elements":[]}))
                else:
                    route.fulfill(status=503, headers={'access-control-allow-origin':'*'}, body='busy')
            elif 'bigdatacloud' in url:
                self.reqs.append(('bdc', url))
                route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin':'*'}, body=json.dumps(BDC))
            elif url.startswith('file://'):
                route.continue_()
            else:
                route.abort()
        self.page.route('**/*', handler)
    def open(self, path=APP):
        self.page.goto('file://'+path)
        self.page.wait_for_timeout(1500)
    def close(self): self.browser.close()
