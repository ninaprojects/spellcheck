// Checks the birth chart calculation in index.html against Swiss Ephemeris answers (tests/birthcalc_truth.json).
// Run: node tests/birthcalc_test.mjs
import fs from 'fs';
const html=fs.readFileSync(new URL('../index.html',import.meta.url),'utf8');
const code=html.split('/*birthcalc:start*/')[1].split('/*birthcalc:end*/')[0];
const api=new Function(code+';return {bcSun,bcMoon,bcAsc,bcUtc,bcJD,bcSign,birthChart};')();
const truth=JSON.parse(fs.readFileSync(new URL('./birthcalc_truth.json',import.meta.url),'utf8'));
let pass=0,fail=0;const ck=(n,ok,x='')=>{ok?pass++:(fail++,console.log('FAIL '+n+' '+x));};
const diff=(a,b)=>{let d=Math.abs(a-b)%360;return d>180?360-d:d;};
let ms=0,mm=0,ma=0;
for(const c of truth){const u=api.bcUtc(c.date,c.time,c.tz);const jd=api.bcJD(u);
  ms=Math.max(ms,diff(api.bcSun(jd),c.sun));mm=Math.max(mm,diff(api.bcMoon(jd),c.moon));ma=Math.max(ma,diff(api.bcAsc(jd,c.lat,c.lon),c.asc));}
ck('Sun within 0.05 degrees on 300 births',ms<0.05,ms);
ck('Moon within 0.15 degrees on 300 births',mm<0.15,mm);
ck('Rising within 0.3 degrees on 300 births',ma<0.3,ma);
console.log(`max errors: Sun ${ms.toFixed(4)}, Moon ${mm.toFixed(4)}, Rising ${ma.toFixed(4)}`);
// People we know
const k=api.birthChart({date:'1989-08-02',time:'14:07',placeTz:'America/Chicago',placeLat:41.88,placeLon:-87.63});
ck('Kellye is Leo, Leo, Scorpio',k&&k.sun[0]==='Leo'&&k.moon[0]==='Leo'&&k.rising==='Scorpio',JSON.stringify(k));
const k2=api.birthChart({date:'1989-08-02',time:'15:30',placeTz:'America/Chicago',placeLat:41.88,placeLon:-87.63});
ck('3:30pm would be Sagittarius rising',k2.rising==='Sagittarius',JSON.stringify(k2));
const kn=api.birthChart({date:'1989-08-02',noTime:true,placeTz:'America/Chicago'});
ck('no time but a place still gives Sun and Moon when they cannot change that day',kn.sun.length===1&&kn.moon[0]==='Leo'&&kn.moon.length===1&&kn.rising===null,JSON.stringify(kn));
const kw=api.birthChart({date:'1989-08-02',noTime:true});
ck('no time and no place offers two Moon signs, never a wrong one',kw.moon.includes('Leo')&&kw.moon.length===2,JSON.stringify(kw));
const n=api.birthChart({date:'1991-02-14',time:'01:30',placeTz:'Africa/Bujumbura',placeLat:-3.38,placeLon:29.36});
ck('Nina is Aquarius, Aquarius, Sagittarius',n.sun[0]==='Aquarius'&&n.moon[0]==='Aquarius'&&n.rising==='Sagittarius',JSON.stringify(n));
ck('no date gives nothing',api.birthChart({})===null);
ck('no time means no Rising',api.birthChart({date:'1991-02-14',placeTz:'Africa/Bujumbura',placeLat:-3.38,placeLon:29.36}).rising===null);
// A day the Sun changes sign (Sun enters Virgo on Aug 23 2001, early UTC) is ambiguous without a time
const amb=api.birthChart({date:'2001-08-23',noTime:true,placeTz:'UTC'});
ck('sign change day without a time offers both signs',amb.sun.length===2&&amb.sun[0]==='Leo'&&amb.sun[1]==='Virgo',JSON.stringify(amb));
// Planets (Mercury to Pluto) from the sign-change tables, against Swiss Ephemeris at 600 random moments
{
  const api2=new Function(code+';return {bcPlanetSignAt,bcPlanetSigns,bcHouse,bcOrd,birthChart,BC_SIGNS};')();
  const pt=JSON.parse(fs.readFileSync(new URL('./birthcalc_planets_truth.json',import.meta.url),'utf8'));
  let bad=0;for(const c of pt)for(const [n,i] of Object.entries(c.p))if(api2.bcPlanetSignAt(n,c.ms)!==api2.BC_SIGNS[i])bad++;
  ck('planet signs match Swiss Ephemeris on 600 random moments (4800 readings)',bad===0,bad);
  const kp=api2.birthChart({date:'1989-08-02',time:'14:07',placeTz:'America/Chicago',placeLat:41.88,placeLon:-87.63}).planets;
  const want={Mercury:'Leo',Venus:'Virgo',Mars:'Leo',Jupiter:'Cancer',Saturn:'Capricorn',Uranus:'Capricorn',Neptune:'Capricorn',Pluto:'Scorpio'};
  ck('Kellye planets: Mercury Leo, Venus Virgo, Mars Leo, Jupiter Cancer, Saturn Capricorn, Uranus Capricorn, Neptune Capricorn, Pluto Scorpio',Object.entries(want).every(([n,s])=>kp[n]&&kp[n].length===1&&kp[n][0]===s),JSON.stringify(kp));
  ck('houses count from Rising (Scorpio rising: Leo is 10th, Virgo 11th, Scorpio 1st, Capricorn 3rd, Cancer 9th)',api2.bcHouse('Leo','Scorpio')===10&&api2.bcHouse('Virgo','Scorpio')===11&&api2.bcHouse('Scorpio','Scorpio')===1&&api2.bcHouse('Capricorn','Scorpio')===3&&api2.bcHouse('Cancer','Scorpio')===9);
  ck('ordinals',[1,2,3,4,11,12,13,21,22].map(api2.bcOrd).join()==='1st,2nd,3rd,4th,11th,12th,13th,21st,22nd');
  ck('a date outside 1920 to 2016 gives no planets, not wrong ones',Object.keys(api2.birthChart({date:'1905-03-04',time:'12:00',placeTz:'America/Chicago',placeLat:41.88,placeLon:-87.63}).planets).length===0);
  const nt=api2.birthChart({date:'1989-08-02',noTime:true}).planets;
  ck('no time and no place still gives the slow planets and offers two signs for a fast one only when it could change',nt.Saturn.length===1&&nt.Pluto.length===1&&nt.Venus.length>=1);
  // Mercury changed sign on this day in 2001-08-23 or similar: find any date where a fast planet is ambiguous with no time
  let amb=0;for(let d=0;d<400;d++){const dt=new Date(Date.UTC(1990,0,1)+d*864e5).toISOString().slice(0,10);const p=api2.birthChart({date:dt,noTime:true}).planets;if(p.Mercury.length>1)amb++;}
  ck('with no time, a fast planet shows two signs on the days it changes sign',amb>=5&&amb<60,amb);
}
console.log(`birthcalc_test.mjs: ${pass+fail} checks, ${fail} failed`);
process.exit(fail?1:0);
