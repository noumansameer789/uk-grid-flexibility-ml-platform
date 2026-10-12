import {liveForecast} from '@/lib/grid';
export async function GET(){try{return Response.json(await liveForecast(),{headers:{'Cache-Control':'public, max-age=30'}})}catch(e){console.error('forecast_unavailable',String(e));return Response.json({status:'unavailable',error:'Live source is unavailable or incomplete. No replay has been substituted.'},{status:503});}}
