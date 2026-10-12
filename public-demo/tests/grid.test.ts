import assert from 'node:assert/strict';
import test from 'node:test';
import {forecastFromRows,makePlan,validatePlan} from '../lib/grid.ts';
const half=1_800_000,origin=Date.parse('2026-10-01T00:00:00Z');
const rows=Array.from({length:9*48},(_,i)=>({from:new Date(origin-9*48*half+i*half).toISOString(),to:new Date(origin-9*48*half+(i+1)*half).toISOString(),intensity:{actual:30+i%48*3}}));
const request={battery_kwh:14.4,power_kw:7.2,efficiency:.9,available_hours:24,carbon_weight:1,tariff:'flat' as const,flat_pence:25};
test('48 ordered forecasts, excluding ineligible observations',()=>{
 const a=forecastFromRows(rows,origin,origin);assert.equal(a.slots.length,48);
 const changed=rows.map(r=>({...r,intensity:{actual:Date.parse(r.from)>origin-5*half?1400:r.intensity.actual}}));
 assert.deepEqual(a.slots,forecastFromRows(changed,origin,origin).slots);
});
test('source gaps and duplicates fail closed',()=>{
 assert.throws(()=>forecastFromRows(rows.slice(150),origin,origin));
 assert.throws(()=>forecastFromRows([...rows,rows[0]],origin,origin));
});
test('energy and power constraints and objective hold',()=>{
 const f=forecastFromRows(rows,origin,origin),p=makePlan(f,request);
 assert.ok(Math.abs(p.slots.reduce((s,x)=>s+x.grid_kwh,0)-16)<1e-8);
 assert.ok(p.slots.every(x=>x.grid_kwh<=3.6+1e-8));
 assert.ok(p.predicted_carbon_kg<=p.immediate_carbon_kg+1e-8);
 assert.ok(Math.abs(p.estimated_cost_gbp-4)<1e-8);
});
test('feasibility and exact numeric inputs are enforced',()=>{
 assert.throws(()=>validatePlan({...request,available_hours:.5}));
 assert.throws(()=>validatePlan({...request,battery_kwh:NaN}));
 assert.throws(()=>validatePlan({...request,power_kw:'7.2'}));
 assert.throws(()=>validatePlan({...request,available_hours:1.1}));
});
test('cost-first plan cannot cost more than immediate plan',()=>{
 const p=makePlan(forecastFromRows(rows,origin,origin),{...request,tariff:'illustrative',carbon_weight:0});
 assert.ok(p.estimated_cost_gbp<=p.immediate_cost_gbp+1e-8);
});
