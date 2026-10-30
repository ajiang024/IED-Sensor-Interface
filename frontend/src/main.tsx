import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ResponsiveContainer, ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import './style.css';

type Dashboard = {filter:{capacity:number;used:number;installed:number};life:number;remaining:number;status:string;lifetime:number;history:{date:string;liters:number;life:number}[];notifications:{id:number;time:number;message:string;seen:number}[];connected:boolean;flowing:boolean;source:string|null;last_seen:number|null};
const number = (v:number) => v.toLocaleString(undefined,{maximumFractionDigits:1});
async function api(path:string, body?:unknown) {
  const r = await fetch('/api/'+path, body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!r.ok){ let detail = 'Request failed'; try { detail = (await r.json()).detail || detail; } catch {} throw new Error(typeof detail==='string'?detail:JSON.stringify(detail)); }
  return r.json();
}
function App(){
 const [data,setData]=useState<Dashboard|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function refresh(){try{setData(await api('dashboard'));setError('');}catch(e){setError((e as Error).message+' — check that the backend is running.');}}
 useEffect(()=>{void refresh();const id=setInterval(()=>void refresh(),2000);return()=>clearInterval(id);},[]);
 async function action(path:string,body:unknown={}){setBusy(true);try{await api(path,body);await refresh();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 const unread=data?.notifications.filter(n=>!n.seen).length||0;
 return <div className="shell">
 <main><header className="project-header"><span className="project-name">Team Black IED</span><span className={'connection '+(data?.connected?'online':'')}><i/> {data?.connected?(data.source==='demo'?'Demo connected':'Sensor connected'):'Sensor offline'}</span></header>
 {error&&<div role="alert" className="error">{error}</div>}
 <section className="banner"><div><span className="eyebrow">A SMALL HABIT. A BIG DIFFERENCE.</span><h2>Fresh water starts<br/>with a healthy filter.</h2><p>Your filter’s story, one liter at a time.</p></div><div className="water-art" aria-hidden="true"><div className="ripple r1"/><div className="ripple r2"/><div className="drop">◊</div><span>EVERY DROP COUNTS</span></div></section>
 <div className="section-heading"><h2>System overview</h2><span>{data?.flowing?'● Water is flowing':'○ No flow detected'}</span></div>
 <section className="cards"><article className="card"><div className="card-label">VOLUME FILTERED <span>↗</span></div><div className="metric">{number(data?.filter.used||0)} <small>L</small></div><p>Through your current filter</p><div className="card-foot">{number(data?.lifetime||0)} L across all filter records</div></article>
 <article className="card health"><div className="card-label">ESTIMATED FILTER LIFE <span>✧</span></div><div className={'metric status '+(data?.status==='Poor'?'poor':'')}>{data?.status||'—'} <span className="percent">{number(data?.life||0)}%</span></div><div className="progress"><div style={{width:`${data?.life||0}%`,background:data?.status==='Poor'?'#c57242':undefined}}/></div><p>Based on rated capacity and measured usage</p></article>
 <article className="card"><div className="card-label">ESTIMATED WATER REMAINING <span>♧</span></div><div className="metric">{number(data?.remaining||0)} <small>L</small></div><p>Before rated capacity is reached</p><div className="card-foot">Filter capacity · {number(data?.filter.capacity||1000)} L</div></article></section>
 <section className="lower"><article className="chart panel"><div className="panel-head"><div><h2>Your water over time</h2><p>Daily volume and estimated filter life · current filter · UTC</p></div><span className="tag">Daily</span></div>{data?.history.length?<ResponsiveContainer width="100%" height={270}><ComposedChart data={data.history} margin={{top:15,right:0,left:0,bottom:10}}><CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#e7ece8"/><XAxis dataKey="date" tick={{fontSize:11}} tickFormatter={v=>v.slice(5)} axisLine={false} tickLine={false}/><YAxis yAxisId="volume" tick={{fontSize:11}} unit=" L" axisLine={false} tickLine={false}/><YAxis yAxisId="life" orientation="right" domain={[0,100]} unit="%" tick={{fontSize:11}} axisLine={false} tickLine={false}/><Tooltip/><Bar yAxisId="volume" name="Volume (L)" dataKey="liters" fill="#80b9a7" radius={[5,5,0,0]} maxBarSize={52}/><Line yAxisId="life" name="Filter life (%)" dataKey="life" stroke="#264f44" strokeWidth={3} dot={{r:4}}/></ComposedChart></ResponsiveContainer>:<div className="empty"><span>≈</span><strong>Your first drop starts the story.</strong><p>Connect your sensor or add a demo reading to see your chart.</p></div>}<div className="legend"><span>▰ Volume filtered</span><span>― Estimated filter life</span></div></article>
 <article className="panel notifications"><div className="panel-head"><h2>Notifications <span className="count">{unread}</span></h2><button disabled={!unread||busy} onClick={()=>void action('notifications/read')}>Mark read</button></div><div className="alert-list">{data?.notifications.length?data.notifications.map(n=><div className={'notice '+(!n.seen?'unread':'')} key={n.id}><span>◉</span><div><p>{n.message}</p><time>{new Date(n.time*1000).toLocaleString()}</time></div></div>):<div className="quiet"><span>✓</span><strong>All clear.</strong><p>Filter alerts and stopped-flow events will appear here.</p></div>}</div><div className="note">Flow stopping suggests a session ended; it does not confirm a completed batch.</div></article></section>
 <section className="demo-strip"><div><strong>Meet your dashboard.</strong><p>Add 25 L of simulated water to try the live calculations.</p></div><button className="primary" disabled={busy||!data} onClick={()=>void action('demo')}>{busy?'Working…':'+ Add demo reading'}</button></section>
 <footer><span>flow. / Thoughtful water monitoring</span><span>Usage-based estimates · Not a water-quality measurement</span></footer></main></div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
