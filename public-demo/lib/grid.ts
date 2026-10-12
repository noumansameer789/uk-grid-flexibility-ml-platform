export type Slot = {timestamp:string; carbon:number};
export type Forecast = {issued_at:string; fetched_at:string; source:string; model:string; observation_cutoff:string; slots:Slot[]};
export const SOURCE = 'https://api.carbonintensity.org.uk';
const HALF = 1_800_000, DAY = 86_400_000;
export function forecastFromRows(rows:unknown, origin:number, fetched:number):Forecast {
  if(!Array.isArray(rows) || origin % HALF !== 0) throw new Error('Invalid source response or origin');
  const values = new Map<number,number>();
  for(const row of rows) {
    const t=Date.parse(row?.from), end=Date.parse(row?.to), n=row?.intensity?.actual;
    if(!Number.isFinite(t) || t%HALF || end-t!==HALF || values.has(t)) throw new Error('Source interval contract failed');
    if(n===null) continue;
    if(typeof n!=='number' || !Number.isFinite(n) || n<0 || n>1500) throw new Error('Source intensity contract failed');
    values.set(t,n);
  }
  const cutoff=origin-2*3_600_000-HALF;
  const slots=Array.from({length:48},(_,i)=>{
    const target=origin+i*HALF, history:number[]=[];
    for(let d=1;d<=8;d++) {
      const past=target-d*DAY;
      if(past<=cutoff && values.has(past) && history.length<7) history.push(values.get(past)!);
    }
    if(history.length!==7) throw new Error('Seven complete eligible days are required. Live source has gaps.');
    return {timestamp:new Date(target).toISOString(),carbon:history.reduce((a,b)=>a+b,0)/7};
  });
  return {issued_at:new Date(origin).toISOString(),fetched_at:new Date(fetched).toISOString(),source:SOURCE,
    model:'seven_day_mean',observation_cutoff:new Date(cutoff).toISOString(),slots};
}
let memo:{at:number; origin:number; data:Forecast}|undefined;
export async function liveForecast():Promise<Forecast> {
  const now=Date.now(),origin=(Math.floor(now/HALF)+1)*HALF;
  if(memo && memo.origin===origin && now-memo.at<300_000) return memo.data;
  const start=new Date(origin-9*DAY).toISOString().slice(0,16)+'Z';
  const end=new Date(origin-2*3_600_000).toISOString().slice(0,16)+'Z';
  const response=await fetch(`${SOURCE}/intensity/${start}/${end}`,{headers:{Accept:'application/json'},signal:AbortSignal.timeout(15_000)});
  if(!response.ok) throw new Error(`Live data source returned HTTP ${response.status}`);
  const text=await response.text();
  if(text.length>1_000_000) throw new Error('Source payload exceeded size limit');
  const data=forecastFromRows(JSON.parse(text).data,origin,Date.now());
  memo={at:now,origin,data};
  return data;
}
export type RequestPlan={battery_kwh:number;power_kw:number;efficiency:number;available_hours:number;carbon_weight:number;tariff:'flat'|'illustrative';flat_pence:number};
export function validatePlan(value:unknown):RequestPlan {
  if(!value || typeof value!=='object' || Array.isArray(value)) throw new Error('A JSON object is required');
  const v=value as RequestPlan;
  const limits:[keyof RequestPlan,number,number][]=[['battery_kwh',0.1,100],['power_kw',0.1,22],['efficiency',0.5,1],['available_hours',0.5,24],['carbon_weight',0,1],['flat_pence',0,100]];
  for(const [key,lo,hi] of limits) if(typeof v[key]!=='number' || !Number.isFinite(v[key]) || Number(v[key])<lo || Number(v[key])>hi) throw new Error(`${key} must be between ${lo} and ${hi}`);
  if(v.available_hours*2%1) throw new Error('available_hours must be a multiple of 0.5');
  if(!['flat','illustrative'].includes(v.tariff)) throw new Error('Unknown tariff');
  if(v.battery_kwh/v.efficiency>v.power_kw*v.available_hours+1e-9) throw new Error('Charging request is infeasible: increase the window or power, or reduce energy.');
  return v;
}
export function makePlan(forecast:Forecast,v:RequestPlan) {
  v=validatePlan(v);
  const candidates=forecast.slots.slice(0,v.available_hours*2).map((s,i)=>{
    const hour=Number(new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/London',hour:'2-digit',hourCycle:'h23'}).format(new Date(s.timestamp)));
    return {...s,index:i,price_pence:v.tariff==='flat'?v.flat_pence:(hour>=7&&hour<23?35:15),grid_kwh:0};
  });
  const cmax=Math.max(...candidates.map(s=>s.carbon),1),pmax=Math.max(...candidates.map(s=>s.price_pence),1);
  const order=[...candidates].sort((a,b)=>(v.carbon_weight*a.carbon/cmax+(1-v.carbon_weight)*a.price_pence/pmax)-(v.carbon_weight*b.carbon/cmax+(1-v.carbon_weight)*b.price_pence/pmax)||a.index-b.index);
  let remaining=v.battery_kwh/v.efficiency;
  for(const slot of order){slot.grid_kwh=Math.min(remaining,v.power_kw*0.5);remaining=Math.max(0,remaining-slot.grid_kwh);}
  if(remaining>1e-7) throw new Error('Energy constraint could not be satisfied');
  let immediateRemaining=v.battery_kwh/v.efficiency, immediateCarbon=0,immediateCost=0;
  for(const slot of candidates){const e=Math.min(immediateRemaining,v.power_kw*0.5);immediateRemaining-=e;immediateCarbon+=e*slot.carbon;immediateCost+=e*slot.price_pence/100;}
  const grams=candidates.reduce((s,x)=>s+x.grid_kwh*x.carbon,0),cost=candidates.reduce((s,x)=>s+x.grid_kwh*x.price_pence/100,0);
  return {forecast,request:v,slots:candidates,grid_kwh:v.battery_kwh/v.efficiency,predicted_carbon_kg:grams/1000,estimated_cost_gbp:cost,immediate_carbon_kg:immediateCarbon/1000,immediate_cost_gbp:immediateCost,
    proxy_reduction_percent:immediateCarbon>0?100*(1-grams/immediateCarbon):null,
    interpretation:'Forecast-based average-intensity proxy, not measured or marginal avoided emissions. Illustrative tariff is not a live market price.'};
}
