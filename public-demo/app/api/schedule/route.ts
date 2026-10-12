import {liveForecast,makePlan,validatePlan} from '@/lib/grid';
export async function POST(req:Request){
 let plan;
 try{const raw=await req.text();if(raw.length>4096)return Response.json({error:'Request too large'},{status:413});plan=validatePlan(JSON.parse(raw));}
 catch(e){return Response.json({error:String(e)},{status:422});}
 try{return Response.json(makePlan(await liveForecast(),plan),{headers:{'Cache-Control':'no-store'}});}
 catch(e){console.error('schedule_unavailable',String(e));return Response.json({error:'Live data unavailable; no schedule can be computed.'},{status:503});}
}
