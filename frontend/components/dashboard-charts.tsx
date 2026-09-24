'use client';
import React from 'react';
import { useMemo, useState } from 'react';
import type { Data, Layout } from 'plotly.js';
import PlotlyChart from '@/components/plotly-chart';
import ClassificationPie3D from '@/components/classification-pie-3d';
import demoLandscapeData from '@/lib/demo_landscape_data.json';

const DEMO_ACTIVITIES = ['Maintenance', 'Operations', 'Construction', 'Logistics', 'Inspection', 'Others'];
const DEMO_SITES = ['Duliajan', 'Moran', 'Naharkatiya', 'Digboi', 'Brahmaputra', 'Others'];

type Group={name:string;total:number;sif:number;non_sif:number;unresolved:number};
export type DashboardChartData={
  rules:string[];sites:string[];counts:number[][];sif_counts:number[][];site_totals:number[];
  total_reports:number;untagged_reports:number;synthetic_reports:number;timezone:string;
  classification:{sif:number;non_sif:number;unresolved:number};
  landscape:{report_id:string;site:string;activity:string;precursor:string;priority:string;probability:number|null;model_version:string;is_synthetic:boolean}[];
  daily:{date:string;total:number;sif:number;unresolved:number;non_sif:number}[];
  report_types:Group[];priorities:Group[];barrier_failures:{name:string;state:string;count:number}[];
  filter_options:{site:string[];activity:string[];report_type:string[]};
};
const axis={showline:false,zeroline:false,gridcolor:'#e1eaf4',tickfont:{size:10,color:'#315894'}};
const stack=(groups:Group[],orientation:'h'|'v'='h'):Data[]=>[
  {
    name:'SIF-potential',type:'bar',orientation,
    x:orientation==='h'?groups.map(x=>x.sif):groups.map(x=>x.name),
    y:orientation==='h'?groups.map(x=>x.name):groups.map(x=>x.sif),
    customdata:groups.map(g=>[g.name, g.sif, Math.round(g.sif/Math.max(g.total,1)*100), g.total]),
    marker:{color:'#ef4d4b'},
    hovertemplate:'<b>%{customdata[0]}</b><br><span style="color:#ff6b6b;">●</span> SIF-potential: <b>%{customdata[2]}%</b> (%{customdata[1]} reports)<br><span style="color:#8fa7c9;font-size:10px;">Category total: %{customdata[3]} reports</span><extra></extra>',
  } as Data,
  {
    name:'Non-SIF',type:'bar',orientation,
    x:orientation==='h'?groups.map(x=>x.non_sif):groups.map(x=>x.name),
    y:orientation==='h'?groups.map(x=>x.name):groups.map(x=>x.non_sif),
    customdata:groups.map(g=>[g.name, g.non_sif, Math.round(g.non_sif/Math.max(g.total,1)*100), g.total]),
    marker:{color:'#45a979'},
    hovertemplate:'<b>%{customdata[0]}</b><br><span style="color:#45d996;">●</span> Non-SIF: <b>%{customdata[2]}%</b> (%{customdata[1]} reports)<br><span style="color:#8fa7c9;font-size:10px;">Category total: %{customdata[3]} reports</span><extra></extra>',
  } as Data,
  {
    name:'Unresolved',type:'bar',orientation,
    x:orientation==='h'?groups.map(x=>x.unresolved):groups.map(x=>x.name),
    y:orientation==='h'?groups.map(x=>x.name):groups.map(x=>x.unresolved),
    customdata:groups.map(g=>[g.name, g.unresolved, Math.round(g.unresolved/Math.max(g.total,1)*100), g.total]),
    marker:{color:'#9aaabd'},
    hovertemplate:'<b>%{customdata[0]}</b><br><span style="color:#b2c2d4;">●</span> Unresolved: <b>%{customdata[2]}%</b> (%{customdata[1]} reports)<br><span style="color:#8fa7c9;font-size:10px;">Category total: %{customdata[3]} reports</span><extra></extra>',
  } as Data,
];
function MiniPanel({title,children,className=''}:{title:string;children:React.ReactNode;className?:string}){
  return <section className={'oil-panel '+className}><h2>{title}</h2>{children}</section>;
}
function aggregate(daily:{date:string;total:number;sif:number}[],mode:'monthly'|'quarterly'|'yearly'){
  const map=new Map<string,{total:number;sif:number}>();
  for(const d of daily){
    const dt=new Date(d.date);
    let key='';
    if(mode==='monthly') key=`${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2,'0')}`;
    else if(mode==='quarterly') key=`${dt.getFullYear()} Q${Math.ceil((dt.getMonth()+1)/3)}`;
    else key=`${dt.getFullYear()}`;
    const prev=map.get(key)||{total:0,sif:0};
    map.set(key,{total:prev.total+d.total,sif:prev.sif+d.sif});
  }
  const keys=[...map.keys()];
  return {x:keys,tot:keys.map(k=>map.get(k)!.total),sif:keys.map(k=>map.get(k)!.sif)};
}
const C_GRAY = '#9aaabd', C_RED = '#ef4d4b';
const TREND_DEMO_DATA = {
  monthly: {
    x: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
    tot: [120, 155, 235, 210, 285, 255, 310, 440, 310, 335, 425, 335],
    sif: [42, 63, 94, 82, 115, 112, 138, 218, 140, 128, 195, 142],
  },
  quarterly: {
    x: ['Q1', 'Q2', 'Q3', 'Q4'],
    tot: [510, 750, 1060, 1095],
    sif: [199, 309, 496, 465],
  },
  yearly: {
    x: ['2021', '2022', '2023', '2024', '2025'],
    tot: [2450, 2780, 3120, 3450, 3415],
    sif: [620, 710, 830, 940, 1469],
  },
};

function makeTrendTraces(px:string[],ptot:number[],psif:number[]):Data[]{
  return [
    {name:'',type:'scatter',mode:'lines',x:px,y:ptot,line:{color:'rgba(154,170,189,0.30)',width:8,shape:'spline',smoothing:1.1},hoverinfo:'skip',showlegend:false} as any,
    {name:'',type:'scatter',mode:'lines',x:px,y:psif,line:{color:'rgba(239,77,75,0.30)',width:8,shape:'spline',smoothing:1.1},hoverinfo:'skip',showlegend:false} as any,
    {name:'Total Reports',type:'scatter',mode:'lines+markers',x:px,y:ptot,cliponaxis:false,line:{color:C_GRAY,width:3,shape:'spline',smoothing:1.1},marker:{size:9,color:'#000000',symbol:'circle',line:{color:C_GRAY,width:2.5}},fill:'tozeroy',fillcolor:'rgba(154,170,189,0.10)',hovertemplate:'<b>Total Reports</b>: %{y:,}<extra></extra>'} as any,
    {name:'SIF-Potential',type:'scatter',mode:'lines+markers',x:px,y:psif,cliponaxis:false,line:{color:C_RED,width:3,shape:'spline',smoothing:1.1},marker:{size:9,color:'#000000',symbol:'circle',line:{color:C_RED,width:2.5}},fill:'tozeroy',fillcolor:'rgba(239,77,75,0.12)',hovertemplate:'<b>SIF-Potential</b>: %{y:,}<extra></extra>'} as any,
  ];
}
export default function DashboardCharts({
  charts,
  activities,
  patterns,
  sites,
  days,
  useDemo = true,
  selectedCount: controlledCount,
  onSelectedCountChange,
}: {
  charts: DashboardChartData;
  activities: any[];
  patterns: any[];
  sites: any[];
  days: string;
  useDemo?: boolean;
  selectedCount?: number;
  onSelectedCountChange?: (count: number) => void;
}) {
  const [internalSelectedCount, setInternalSelectedCount] = useState(9);
  const selectedCount = controlledCount !== undefined ? controlledCount : internalSelectedCount;
  const setSelectedCount = (val: number) => {
    setInternalSelectedCount(val);
    onSelectedCountChange?.(val);
  };
  const [fullScreenIndex, setFullScreenIndex] = useState(0);
  const [splitIndex1, setSplitIndex1] = useState(0);
  const [splitIndex2, setSplitIndex2] = useState(1);
  const [gridIndex1, setGridIndex1] = useState(0);
  const [gridIndex2, setGridIndex2] = useState(1);
  const [gridIndex3, setGridIndex3] = useState(2);
  const [gridIndex4, setGridIndex4] = useState(4);
  const [trendPeriod, setTrendPeriod] = useState<'monthly' | 'quarterly' | 'yearly'>('monthly');
  const scored = useMemo(() => charts.landscape.filter(r=>r.probability!==null), [charts.landscape]);
  const unscored = useMemo(() => charts.landscape.filter(r=>r.probability===null), [charts.landscape]);
  const acts = useMemo(() => [...new Set(charts.landscape.map(r=>r.activity))], [charts.landscape]);
  const siteNames = useMemo(() => [...new Set(charts.landscape.map(r=>r.site))], [charts.landscape]);
  const jitter = (text:string,salt:number)=>{let n=salt; for(const c of text) n = (n*31 + c.charCodeAt(0))%997; return (n/997-0.5)*0.48;};
  const size = (priority:string)=>({LOW:4,MEDIUM:6,HIGH:8,CRITICAL:11}[priority]||5);

  const currentActs = useDemo ? DEMO_ACTIVITIES : (acts.length > 0 ? acts : DEMO_ACTIVITIES);
  const currentSites = useDemo ? DEMO_SITES : (siteNames.length > 0 ? siteNames : DEMO_SITES);

  const landscapeData = useMemo<Data[]>(() => {
    if (useDemo) {
      return [
        {
          type: 'scatter3d',
          mode: 'markers',
          name: 'Precursor report',
          x: demoLandscapeData.x,
          y: demoLandscapeData.y,
          z: demoLandscapeData.z,
          customdata: demoLandscapeData.customdata as any,
          marker: {
            size: demoLandscapeData.marker_size,
            color: demoLandscapeData.marker_color,
            colorscale: demoLandscapeData.colorscale as any,
            cmin: 0,
            cmax: 60,
            opacity: 0.95,
            line: { width: 0.5, color: 'rgba(0,0,0,0.15)' },
            colorbar: {
              title: { text: '<b>SIF Probability (%)</b>', font: { size: 11, color: '#1749a0' }, side: 'right' },
              thickness: 14,
              len: 0.65,
              x: 1.02,
              y: 0.5,
              tickfont: { size: 10, color: '#315894' },
              dtick: 10,
              outlinewidth: 0,
            },
          },
          hovertemplate: demoLandscapeData.hovertemplate,
        } as Data,
      ];
    }
    return [
      {
        type: 'scatter3d',
        mode: 'markers',
        name: 'Model score',
        x: scored.map(r=>acts.indexOf(r.activity)+jitter(r.report_id,17)),
        y: scored.map(r=>Number(r.probability)*100),
        z: scored.map(r=>siteNames.indexOf(r.site)+jitter(r.report_id,43)),
        customdata: scored.map(r=>[r.report_id,r.site,r.activity,r.precursor,r.priority]),
        marker: {
          size: scored.map(r=>size(r.priority)),
          color: scored.map(r=>Number(r.probability)*100),
          cmin: 0,
          cmax: 100,
          opacity: 0.9,
          colorscale: [[0,'#1577e8'],[.35,'#00b5ba'],[.58,'#f1d72e'],[.78,'#ff8e19'],[1,'#e42323']],
          colorbar: { title: { text: 'SIF %', side: 'right' }, thickness: 12, len: 0.65, outlinewidth: 0 },
        },
        hovertemplate: '<b>%{customdata[0]}</b><br>Site: %{customdata[1]}<br>Activity: %{customdata[2]}<br>Precursor: %{customdata[3]}<br>Priority: %{customdata[4]}<br>SIF probability: %{y:.1f}%<extra></extra>',
      } as Data,
      {
        type: 'scatter3d',
        mode: 'markers',
        name: 'Probability unavailable',
        x: unscored.map(r=>acts.indexOf(r.activity)+jitter(r.report_id,17)),
        y: unscored.map(()=>-10),
        z: unscored.map(r=>siteNames.indexOf(r.site)+jitter(r.report_id,43)),
        customdata: unscored.map(r=>[r.report_id,r.site,r.activity,r.precursor,r.priority]),
        marker: { size: unscored.map(r=>size(r.priority)), color: '#9aaabd', opacity: 0.5 },
        hovertemplate: '<b>%{customdata[0]}</b><br>Site: %{customdata[1]}<br>Activity: %{customdata[2]}<br>Precursor: %{customdata[3]}<br>Priority: %{customdata[4]}<br><b>Probability unavailable</b><extra></extra>',
      } as Data,
    ];
  }, [useDemo, scored, unscored, acts, siteNames]);

  const landscapeLayout = useMemo<Partial<Layout>>(() => ({
    margin: { l: 10, r: 10, t: 15, b: 15 },
    paper_bgcolor: '#ffffff',
    plot_bgcolor: '#ffffff',
    legend: { orientation: 'h', x: 0, y: 1.05, font: { size: 9.5, color: '#315894' } },
    scene: {
      bgcolor: '#ffffff',
      aspectmode: 'manual',
      aspectratio: { x: 1.24, y: 0.92, z: 0.96 },
      camera: {
        eye: { x: -2.65, y: 1.88, z: 1.32 },
        center: { x: 0, y: -0.05, z: 0 },
        up: { x: 0, y: 1, z: 0 },
      },
      xaxis: {
        title: { text: '<b>Activity</b>', font: { size: 11.5, color: '#1749a0' } },
        tickvals: currentActs.map((_, i) => i),
        ticktext: currentActs,
        range: [-0.6, currentActs.length - 0.4],
        color: '#1749a0',
        gridcolor: '#cfe0f2',
        linecolor: '#8bb4e8',
        backgroundcolor: '#f7fbff',
        showbackground: true,
        tickfont: { size: 10, color: '#275294' },
      },
      yaxis: {
        title: { text: '<b>SIF Probability (%)</b>', font: { size: 11.5, color: '#1749a0' } },
        tickvals: useDemo ? [0, 10, 20, 30, 40, 50, 60] : [-10, 0, 20, 40, 60, 80, 100],
        ticktext: useDemo ? undefined : ['Unavailable', '0%', '20%', '40%', '60%', '80%', '100%'],
        ticksuffix: useDemo ? '%' : undefined,
        range: useDemo ? [0, 65] : [-15, 100],
        color: '#1749a0',
        gridcolor: '#cfe0f2',
        linecolor: '#8bb4e8',
        backgroundcolor: '#f7fbff',
        showbackground: true,
        tickfont: { size: 10, color: '#275294' },
      },
      zaxis: {
        title: { text: '<b>Site</b>', font: { size: 11.5, color: '#1749a0' } },
        tickvals: currentSites.map((_, i) => i),
        ticktext: currentSites,
        range: [-0.6, currentSites.length - 0.4],
        color: '#1749a0',
        gridcolor: '#cfe0f2',
        linecolor: '#8bb4e8',
        backgroundcolor: '#f7fbff',
        showbackground: true,
        tickfont: { size: 10, color: '#275294' },
      },
    },
  }) as Partial<Layout>, [useDemo, currentActs, currentSites]);

  const landscapeLayoutGrid4 = useMemo<Partial<Layout>>(() => ({
    margin: { l: 6, r: 6, t: 8, b: 8 },
    paper_bgcolor: '#ffffff',
    plot_bgcolor: '#ffffff',
    legend: { orientation: 'h', x: 0, y: 1.05, font: { size: 8.5, color: '#315894' } },
    scene: {
      bgcolor: '#ffffff',
      aspectmode: 'manual',
      aspectratio: { x: 1.28, y: 0.86, z: 0.90 },
      camera: {
        eye: { x: -1.72, y: 1.22, z: 0.86 },
        center: { x: 0, y: -0.06, z: 0 },
        up: { x: 0, y: 1, z: 0 },
      },
      xaxis: {
        title: { text: '<b>Activity</b>', font: { size: 9.5, color: '#1749a0' } },
        tickvals: currentActs.map((_, i) => i),
        ticktext: currentActs,
        range: [-0.6, currentActs.length - 0.4],
        color: '#1749a0',
        gridcolor: '#cfe0f2',
        linecolor: '#8bb4e8',
        backgroundcolor: '#f7fbff',
        showbackground: true,
        tickfont: { size: 8.5, color: '#275294' },
      },
      yaxis: {
        title: { text: '<b>SIF Prob (%)</b>', font: { size: 9.5, color: '#1749a0' } },
        tickvals: useDemo ? [0, 20, 40, 60] : [0, 25, 50, 75, 100],
        ticksuffix: '%',
        range: useDemo ? [0, 65] : [-10, 100],
        color: '#1749a0',
        gridcolor: '#cfe0f2',
        linecolor: '#8bb4e8',
        backgroundcolor: '#f7fbff',
        showbackground: true,
        tickfont: { size: 8.5, color: '#275294' },
      },
      zaxis: {
        title: { text: '<b>Site</b>', font: { size: 9.5, color: '#1749a0' } },
        tickvals: currentSites.map((_, i) => i),
        ticktext: currentSites,
        range: [-0.6, currentSites.length - 0.4],
        color: '#1749a0',
        gridcolor: '#cfe0f2',
        linecolor: '#8bb4e8',
        backgroundcolor: '#f7fbff',
        showbackground: true,
        tickfont: { size: 8.5, color: '#275294' },
      },
    },
  }) as Partial<Layout>, [useDemo, currentActs, currentSites]);

  const ruleMatrix = charts.counts;
  const heatMax = Math.max(1,...ruleMatrix.flat());
  const heatData = useMemo<Data[]>(()=>[{type:'heatmap',x:charts.rules,y:charts.sites,z:ruleMatrix,zmin:0,zmax:heatMax,xgap:2,ygap:2,colorscale:[[0,'#f3f8fd'],[.3,'#bad9f3'],[.65,'#4b9ade'],[1,'#084f9d']],colorbar:{thickness:8,len:.8,outlinewidth:0},hovertemplate:'<b>%{y}</b><br>%{x}<br>%{z} reports<extra></extra>'}] as Data[],[charts,ruleMatrix,heatMax]);

  const topActivities = [...activities].sort((a,b)=>b.sif_count-a.sif_count||b.total_count-a.total_count).slice(0,7);
  const activityData:Data[]=[
    {name:'SIF-potential',type:'bar',orientation:'h',y:topActivities.map(a=>a.name),x:topActivities.map(a=>a.sif_count),marker:{color:'#ef4d4b'}},
    {name:'Other / unresolved',type:'bar',orientation:'h',y:topActivities.map(a=>a.name),x:topActivities.map(a=>a.total_count-a.sif_count),marker:{color:'#9fb5cb'}},
  ];

  const currentTrend = useMemo(() => {
    if (useDemo) {
      return TREND_DEMO_DATA[trendPeriod];
    }
    const agg = aggregate(charts.daily, trendPeriod);
    if (!agg.x || agg.x.length === 0) {
      return TREND_DEMO_DATA[trendPeriod];
    }
    return { x: agg.x, tot: agg.tot, sif: agg.sif };
  }, [useDemo, trendPeriod, charts.daily]);

  const trendData = useMemo<Data[]>(() => {
    return makeTrendTraces(currentTrend.x, currentTrend.tot, currentTrend.sif);
  }, [currentTrend]);

  const trendLayout = useMemo<Partial<Layout>>(() => ({
    paper_bgcolor: '#ffffff',
    plot_bgcolor: '#ffffff',
    font: { family: 'Inter, sans-serif', color: '#1749a0' },
    margin: { l: 56, r: 18, t: 40, b: 46 },
    legend: {
      orientation: 'h',
      yanchor: 'bottom',
      y: 1.15,
      xanchor: 'left',
      x: 0,
      font: { size: 10, color: '#1749a0' },
      bgcolor: 'rgba(255,255,255,0)',
    },
    xaxis: {
      showgrid: true,
      gridcolor: '#e4edf6',
      gridwidth: 1,
      showline: true,
      linecolor: '#c2d5e8',
      zeroline: false,
      tickmode: 'array',
      tickvals: currentTrend.x,
      range: [-0.6, currentTrend.x.length - 0.4],
      tickfont: { size: 10.5, color: '#315894' },
      fixedrange: true,
    },
    yaxis: {
      showgrid: true,
      gridcolor: '#e4edf6',
      gridwidth: 1,
      showline: true,
      linecolor: '#c2d5e8',
      zeroline: false,
      title: { text: 'Number of Reports', font: { size: 10.5, color: '#1749a0' }, standoff: 10 },
      tickfont: { size: 10, color: '#315894' },
      fixedrange: true,
    },
    hovermode: 'x unified',
    hoverlabel: {
      bgcolor: 'rgba(11, 29, 58, 0.96)',
      font: { size: 12.5, family: 'Inter, sans-serif', color: '#ffffff' },
      bordercolor: 'rgba(100, 160, 255, 0.5)',
    },
  }), [currentTrend]);

  const landscapeLayoutFullScreen = useMemo<Partial<Layout>>(() => ({
    margin: { l: 20, r: 20, t: 25, b: 20 },
    paper_bgcolor: '#ffffff',
    plot_bgcolor: '#ffffff',
    legend: { orientation: 'h', x: 0, y: 1.05, font: { size: 11, color: '#315894' } },
    scene: {
      bgcolor: '#ffffff',
      aspectmode: 'manual',
      aspectratio: { x: 1.5, y: 0.95, z: 1.0 },
      camera: {
        eye: { x: -2.45, y: 1.75, z: 1.20 },
        center: { x: 0, y: -0.06, z: 0 },
        up: { x: 0, y: 1, z: 0 },
      },
      xaxis: {
        title: { text: '<b>Activity</b>', font: { size: 13, color: '#1749a0' } },
        tickvals: currentActs.map((_, i) => i),
        ticktext: currentActs,
        range: [-0.6, currentActs.length - 0.4],
        color: '#1749a0',
        gridcolor: '#cfe0f2',
        linecolor: '#8bb4e8',
        backgroundcolor: '#f7fbff',
        showbackground: true,
        tickfont: { size: 11, color: '#275294' },
      },
      yaxis: {
        title: { text: '<b>SIF Probability (%)</b>', font: { size: 13, color: '#1749a0' } },
        tickvals: useDemo ? [0, 10, 20, 30, 40, 50, 60] : [-10, 0, 20, 40, 60, 80, 100],
        ticktext: useDemo ? undefined : ['Unavailable', '0%', '20%', '40%', '60%', '80%', '100%'],
        ticksuffix: useDemo ? '%' : undefined,
        range: useDemo ? [0, 65] : [-15, 100],
        color: '#1749a0',
        gridcolor: '#cfe0f2',
        linecolor: '#8bb4e8',
        backgroundcolor: '#f7fbff',
        showbackground: true,
        tickfont: { size: 11, color: '#275294' },
      },
      zaxis: {
        title: { text: '<b>Site</b>', font: { size: 13, color: '#1749a0' } },
        tickvals: currentSites.map((_, i) => i),
        ticktext: currentSites,
        range: [-0.6, currentSites.length - 0.4],
        color: '#1749a0',
        gridcolor: '#cfe0f2',
        linecolor: '#8bb4e8',
        backgroundcolor: '#f7fbff',
        showbackground: true,
        tickfont: { size: 11, color: '#275294' },
      },
    },
  }) as Partial<Layout>, [useDemo, currentActs, currentSites]);

  const trendLayoutFullScreen = useMemo<Partial<Layout>>(() => ({
    paper_bgcolor: '#ffffff',
    plot_bgcolor: '#ffffff',
    font: { family: 'Inter, sans-serif', color: '#1749a0' },
    margin: { l: 70, r: 35, t: 45, b: 60 },
    legend: {
      orientation: 'h',
      yanchor: 'bottom',
      y: 1.08,
      xanchor: 'left',
      x: 0,
      font: { size: 11.5, color: '#1749a0' },
      bgcolor: 'rgba(255,255,255,0)',
    },
    xaxis: {
      showgrid: true,
      gridcolor: '#e4edf6',
      gridwidth: 1,
      showline: true,
      linecolor: '#c2d5e8',
      zeroline: false,
      tickmode: 'array',
      tickvals: currentTrend.x,
      range: [-0.6, currentTrend.x.length - 0.4],
      tickfont: { size: 12, color: '#315894' },
      fixedrange: true,
    },
    yaxis: {
      showgrid: true,
      gridcolor: '#e4edf6',
      gridwidth: 1,
      showline: true,
      linecolor: '#c2d5e8',
      zeroline: false,
      title: { text: 'Number of Reports', font: { size: 12, color: '#1749a0' }, standoff: 12 },
      tickfont: { size: 11.5, color: '#315894' },
      fixedrange: true,
    },
    hovermode: 'x unified',
    hoverlabel: {
      bgcolor: 'rgba(11, 29, 58, 0.96)',
      font: { size: 13, family: 'Inter, sans-serif', color: '#ffffff' },
      bordercolor: 'rgba(100, 160, 255, 0.5)',
    },
  }), [currentTrend]);

  const trendLayoutSplit = useMemo<Partial<Layout>>(() => ({
    paper_bgcolor: '#ffffff',
    plot_bgcolor: '#ffffff',
    font: { family: 'Inter, sans-serif', color: '#1749a0' },
    margin: { l: 60, r: 24, t: 40, b: 50 },
    legend: {
      orientation: 'h',
      yanchor: 'bottom',
      y: 1.10,
      xanchor: 'left',
      x: 0,
      font: { size: 10.5, color: '#1749a0' },
      bgcolor: 'rgba(255,255,255,0)',
    },
    xaxis: {
      showgrid: true,
      gridcolor: '#e4edf6',
      gridwidth: 1,
      showline: true,
      linecolor: '#c2d5e8',
      zeroline: false,
      tickmode: 'array',
      tickvals: currentTrend.x,
      range: [-0.6, currentTrend.x.length - 0.4],
      tickfont: { size: 11, color: '#315894' },
      fixedrange: true,
    },
    yaxis: {
      showgrid: true,
      gridcolor: '#e4edf6',
      gridwidth: 1,
      showline: true,
      linecolor: '#c2d5e8',
      zeroline: false,
      title: { text: 'Number of Reports', font: { size: 11, color: '#1749a0' }, standoff: 10 },
      tickfont: { size: 10.5, color: '#315894' },
      fixedrange: true,
    },
    hovermode: 'x unified',
    hoverlabel: {
      bgcolor: 'rgba(11, 29, 58, 0.96)',
      font: { size: 12.5, family: 'Inter, sans-serif', color: '#ffffff' },
      bordercolor: 'rgba(100, 160, 255, 0.5)',
    },
  }), [currentTrend]);

  const trendLayoutGrid4 = useMemo<Partial<Layout>>(() => ({
    paper_bgcolor: '#ffffff',
    plot_bgcolor: '#ffffff',
    font: { family: 'Inter, sans-serif', color: '#1749a0' },
    margin: { l: 42, r: 14, t: 22, b: 28 },
    legend: {
      orientation: 'h',
      yanchor: 'bottom',
      y: 1.05,
      xanchor: 'left',
      x: 0,
      font: { size: 8.5, color: '#1749a0' },
      bgcolor: 'rgba(255,255,255,0)',
    },
    xaxis: {
      showgrid: true,
      gridcolor: '#e4edf6',
      gridwidth: 1,
      showline: true,
      linecolor: '#c2d5e8',
      zeroline: false,
      tickmode: 'array',
      tickvals: currentTrend.x,
      range: [-0.6, currentTrend.x.length - 0.4],
      tickfont: { size: 8.5, color: '#315894' },
      fixedrange: true,
    },
    yaxis: {
      showgrid: true,
      gridcolor: '#e4edf6',
      gridwidth: 1,
      showline: true,
      linecolor: '#c2d5e8',
      zeroline: false,
      title: { text: 'Reports', font: { size: 8.5, color: '#1749a0' }, standoff: 6 },
      tickfont: { size: 8.5, color: '#315894' },
      fixedrange: true,
    },
    hovermode: 'x unified',
    hoverlabel: {
      bgcolor: 'rgba(11, 29, 58, 0.96)',
      font: { size: 10, family: 'Inter, sans-serif', color: '#ffffff' },
      bordercolor: 'rgba(100, 160, 255, 0.5)',
    },
  }), [currentTrend]);

  const CHART_OPTIONS = [
    { id: 'report_types', label: 'SIF Potential by Report Type' },
    { id: 'landscape', label: 'SIF Precursor Landscape (3D)' },
    { id: 'classification', label: 'Assessment Mix (3D Classification Pie)' },
    { id: 'severity', label: 'Reports by Severity vs SIF Classification' },
    { id: 'trend', label: 'SIF Reports Trend' },
    { id: 'patterns', label: 'Top Recurring Precursor Patterns' },
    { id: 'barriers', label: 'Barrier Failure Analysis' },
    { id: 'flow', label: 'Precursor → Activity → Life-Saving Rule' },
    { id: 'density', label: 'SIF Precursor Density Ranking' },
  ];

  const renderSectionHeader = (
    title: string,
    sectionLabel?: string,
    onChangeChart?: (idx: number) => void,
    currentIdx?: number
  ) => {
    if (!onChangeChart || currentIdx === undefined) return null;
    return (
      <div className="oil-split-pane-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, overflow: 'hidden' }}>
          {sectionLabel && <span className="oil-split-badge">{sectionLabel}</span>}
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#0430bd', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
            {title}
          </span>
        </div>
        <select
          value={currentIdx}
          onChange={(e) => onChangeChart(Number(e.target.value))}
          className="chart-mode-select"
          style={{ fontSize: '11px', padding: '3px 8px', fontWeight: 600, minWidth: '170px', maxWidth: '240px' }}
        >
          {CHART_OPTIONS.map((opt, idx) => (
            <option key={opt.id} value={idx}>
              {idx + 1}. {opt.label}
            </option>
          ))}
        </select>
      </div>
    );
  };

  const panelRenderers = [
    // 0: SIF Potential by Report Type
    (mode: 'fullscreen' | 'split' | 'grid4' | 'grid', sectionLabel?: string, onChangeChart?: (idx: number) => void) => {
      const isFull = mode === 'fullscreen';
      const isSplit = mode === 'split';
      const isGrid4 = mode === 'grid4';
      const chartH = isFull ? 620 : isSplit ? 480 : isGrid4 ? 230 : 265;
      const hasHeader = Boolean(onChangeChart);
      return (
        <section key="report_types" className={`oil-panel ${isFull ? 'oil-panel-fullscreen' : ''}`}>
          {hasHeader && renderSectionHeader('SIF Potential by Report Type', sectionLabel, onChangeChart, 0)}
          {!hasHeader && <h2>SIF Potential by Report Type</h2>}
          <PlotlyChart
            data={stack(charts.report_types)}
            height={chartH}
            label="SIF classification by report type"
            layout={{
              barmode: 'stack',
              bargap: isFull ? 0.28 : isSplit ? 0.28 : isGrid4 ? 0.38 : 0.30,
              margin: isFull ? { l: 150, r: 35, t: 45, b: 60 } : isSplit ? { l: 120, r: 25, t: 40, b: 50 } : isGrid4 ? { l: 92, r: 16, t: 26, b: 30 } : { l: 86, r: 16, t: 40, b: 46 },
              paper_bgcolor: '#ffffff',
              plot_bgcolor: '#ffffff',
              xaxis: { ...axis, tickformat: 'd', tickfont: { size: isFull ? 12 : isSplit ? 11 : isGrid4 ? 9 : 10, color: '#315894' } },
              yaxis: { ...axis, showgrid: false, autorange: 'reversed', tickfont: { size: isFull ? 12 : isSplit ? 11 : isGrid4 ? 9 : 10, color: '#315894' } },
              legend: {
                orientation: 'h',
                x: 0,
                y: isFull ? 1.08 : isSplit ? 1.10 : isGrid4 ? 1.06 : 1.14,
                xanchor: 'left',
                yanchor: 'bottom',
                font: { size: isFull ? 11 : isSplit ? 10.5 : isGrid4 ? 9 : 9.5, color: '#315894' },
                bgcolor: 'rgba(255,255,255,0)',
              },
              hoverlabel: {
                bgcolor: 'rgba(11, 29, 58, 0.96)',
                bordercolor: 'rgba(100, 160, 255, 0.4)',
                font: { family: 'Inter, sans-serif', size: 12, color: '#ffffff' },
                align: 'left',
              },
            }}
          />
        </section>
      );
    },

    // 1: SIF Precursor Landscape (3D)
    (mode: 'fullscreen' | 'split' | 'grid4' | 'grid', sectionLabel?: string, onChangeChart?: (idx: number) => void) => {
      const isFull = mode === 'fullscreen';
      const isSplit = mode === 'split';
      const isGrid4 = mode === 'grid4';
      const chartH = isFull ? 620 : isSplit ? 480 : isGrid4 ? 280 : 460;
      const hasHeader = Boolean(onChangeChart);
      return (
        <section key="landscape" className="oil-panel oil-landscape" style={{ minHeight: isFull ? 'calc(100vh - 280px)' : isSplit ? 'calc(100vh - 320px)' : isGrid4 ? '0' : '480px' }}>
          {hasHeader && renderSectionHeader('SIF Precursor Landscape (3D)', sectionLabel, onChangeChart, 1)}
          {!hasHeader && (
            <div className="oil-landscape-header">
              <h2 style={{ fontSize: '14px', margin: 0, padding: '7px 9px 2px', color: '#0430bd' }}>SIF Precursor Landscape (3D)</h2>
            </div>
          )}
          <div className="oil-panel-meta" style={{ padding: isGrid4 ? '2px 8px' : '4px 9px 4px', fontSize: isGrid4 ? '8.5px' : '9px' }}>
            <div>
              {useDemo
                ? 'Each point represents a precursor report (size = severity, color = SIF probability) · Scroll to zoom'
                : 'Each point is a report · size is priority · color is model probability · Scroll to zoom'}
            </div>
            <div style={{ color: '#1749a0', fontSize: isFull ? '12px' : isGrid4 ? '9px' : '10.5px', fontWeight: 600, marginTop: '2px' }}>
              {useDemo ? '900 reports (Demo dataset)' : `${scored.length} scored · ${unscored.length} probability unavailable`}
            </div>
          </div>
          <PlotlyChart
            data={landscapeData}
            layout={isFull ? landscapeLayoutFullScreen : isGrid4 ? landscapeLayoutGrid4 : landscapeLayout}
            height={chartH}
            threeDimensional
            label="Three-dimensional precursor landscape by activity, probability and site"
          />
        </section>
      );
    },

    // 2: Assessment Mix (3D Classification Pie)
    (mode: 'fullscreen' | 'split' | 'grid4' | 'grid', sectionLabel?: string, onChangeChart?: (idx: number) => void) => {
      const isFull = mode === 'fullscreen';
      const isGrid4 = mode === 'grid4';
      const hasHeader = Boolean(onChangeChart);
      return (
        <ClassificationPie3D
          key="pie3d"
          compact={mode === 'grid' || isGrid4}
          fullScreen={isFull}
          classification={charts.classification}
          rules={charts.rules}
          counts={charts.counts}
          sectionHeader={hasHeader ? renderSectionHeader('Assessment Mix (3D Classification Pie)', sectionLabel, onChangeChart, 2) : undefined}
        />
      );
    },

    // 3: Reports by Severity vs SIF Classification
    (mode: 'fullscreen' | 'split' | 'grid4' | 'grid', sectionLabel?: string, onChangeChart?: (idx: number) => void) => {
      const isFull = mode === 'fullscreen';
      const isSplit = mode === 'split';
      const isGrid4 = mode === 'grid4';
      const chartH = isFull ? 620 : isSplit ? 480 : isGrid4 ? 230 : 265;
      const hasHeader = Boolean(onChangeChart);
      return (
        <section key="severity" className={`oil-panel ${isFull ? 'oil-panel-fullscreen' : ''}`}>
          {hasHeader && renderSectionHeader('Reports by Severity vs SIF Classification', sectionLabel, onChangeChart, 3)}
          {!hasHeader && <h2>Reports by Severity vs SIF Classification</h2>}
          <PlotlyChart
            data={stack(charts.priorities, 'v')}
            height={chartH}
            label="Reports by severity and SIF classification"
            layout={{
              barmode: 'stack',
              bargap: isFull ? 0.30 : isSplit ? 0.30 : isGrid4 ? 0.38 : 0.32,
              margin: isFull ? { l: 70, r: 35, t: 45, b: 60 } : isSplit ? { l: 56, r: 20, t: 40, b: 50 } : isGrid4 ? { l: 40, r: 14, t: 26, b: 30 } : { l: 48, r: 14, t: 40, b: 46 },
              paper_bgcolor: '#ffffff',
              plot_bgcolor: '#ffffff',
              xaxis: { ...axis, showgrid: false, tickfont: { size: isFull ? 12 : isSplit ? 11 : isGrid4 ? 9 : 10, color: '#315894' } },
              yaxis: { ...axis, tickformat: 'd', tickfont: { size: isFull ? 12 : isSplit ? 11 : isGrid4 ? 9 : 10, color: '#315894' } },
              legend: {
                orientation: 'h',
                x: 0,
                y: isFull ? 1.08 : isSplit ? 1.10 : isGrid4 ? 1.06 : 1.14,
                xanchor: 'left',
                yanchor: 'bottom',
                font: { size: isFull ? 11 : isSplit ? 10.5 : isGrid4 ? 9 : 9.5, color: '#315894' },
                bgcolor: 'rgba(255,255,255,0)',
              },
              hoverlabel: {
                bgcolor: 'rgba(11, 29, 58, 0.96)',
                bordercolor: 'rgba(100, 160, 255, 0.4)',
                font: { family: 'Inter, sans-serif', size: 12, color: '#ffffff' },
                align: 'left',
              },
            }}
          />
        </section>
      );
    },

    // 4: SIF Reports Trend
    (mode: 'fullscreen' | 'split' | 'grid4' | 'grid', sectionLabel?: string, onChangeChart?: (idx: number) => void) => {
      const isFull = mode === 'fullscreen';
      const isSplit = mode === 'split';
      const isGrid4 = mode === 'grid4';
      const chartH = isFull ? 620 : isSplit ? 480 : isGrid4 ? 200 : 265;
      const hasHeader = Boolean(onChangeChart);
      return (
        <section key="trend" className="oil-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          {hasHeader && renderSectionHeader('SIF Reports Trend', sectionLabel, onChangeChart, 4)}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: isGrid4 ? '2px 8px' : '6px 12px', background: '#fbfdff', borderBottom: '1px solid #e7eff7' }}>
            {!hasHeader && (
              <h2 style={{ margin: 0, color: '#0430bd', fontSize: isFull ? '17px' : isGrid4 ? '13px' : '14px', lineHeight: 1.25, fontWeight: 600 }}>
                SIF Reports Trend
              </h2>
            )}
            <div className="trend-dropdown-wrapper" style={{ display: 'flex', alignItems: 'center', gap: isGrid4 ? '4px' : '8px', marginLeft: 'auto' }}>
              <span style={{ fontSize: isGrid4 ? '9.5px' : '11px', fontWeight: 600, color: '#315da6' }}>Period:</span>
              <div style={{ position: 'relative', display: 'inline-block' }}>
                <select
                  value={trendPeriod}
                  onChange={(e) => setTrendPeriod(e.target.value as any)}
                  className="trend-select-dropdown"
                  style={{
                    background: '#000000',
                    color: '#ffffff',
                    border: '1.5px solid #000000',
                    borderRadius: '4px',
                    padding: isGrid4 ? '1px 18px 1px 6px' : '2px 22px 2px 8px',
                    fontSize: isGrid4 ? '9.5px' : '11px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    appearance: 'none',
                    WebkitAppearance: 'none',
                  }}
                >
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="yearly">Yearly</option>
                </select>
                <span style={{ position: 'absolute', right: '5px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: '#ffffff', fontSize: '7px' }}>
                  ▼
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: isGrid4 ? '2px' : '4px' }}>
                {(['monthly', 'quarterly', 'yearly'] as const).map((p) => (
                  <button
                    key={p}
                    type="button"
                    className={`trend-menu-btn ${trendPeriod === p ? 'selected' : ''}`}
                    onClick={() => setTrendPeriod(p)}
                    style={{ fontSize: isGrid4 ? '9px' : '10.5px', padding: isGrid4 ? '1px 5px' : '2px 7px' }}
                  >
                    {p.charAt(0).toUpperCase() + p.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <PlotlyChart
            data={trendData}
            height={chartH}
            label="SIF and total report trend by period"
            layout={isFull ? trendLayoutFullScreen : isSplit ? trendLayoutSplit : isGrid4 ? trendLayoutGrid4 : trendLayout}
          />
        </section>
      );
    },

    // 5: Top Recurring Precursor Patterns
    (mode: 'fullscreen' | 'split' | 'grid4' | 'grid', sectionLabel?: string, onChangeChart?: (idx: number) => void) => {
      const isFull = mode === 'fullscreen';
      const isSplit = mode === 'split';
      const isGrid4 = mode === 'grid4';
      const list = isFull ? patterns : isSplit ? patterns.slice(0, 16) : isGrid4 ? patterns.slice(0, 10) : patterns.slice(0, 8);
      const hasHeader = Boolean(onChangeChart);
      return (
        <section key="patterns" className="oil-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          {hasHeader && renderSectionHeader('Top Recurring Precursor Patterns', sectionLabel, onChangeChart, 5)}
          {!hasHeader && <h2>Top Recurring Precursor Patterns</h2>}
          <div style={{ overflowX: 'auto', flex: 1, maxHeight: isGrid4 ? '215px' : undefined }}>
            <table>
              <thead>
                <tr><th>#</th><th>Precursor</th><th>Count</th><th>% SIF</th><th>Trend</th></tr>
              </thead>
              <tbody>
                {list.map((p: any, i: number) => {
                  const sifPct = Math.round(p.sif_count / Math.max(p.report_count, 1) * 100);
                  return (
                    <tr key={p.pattern_id || i}>
                      <td><span className="oil-rank-badge">{i + 1}</span></td>
                      <td><strong>{p.dominant_hazard}</strong></td>
                      <td><strong>{p.report_count}</strong></td>
                      <td>
                        <span className={`oil-sif-pill ${sifPct >= 70 ? 'high' : sifPct >= 40 ? 'med' : 'low'}`}>
                          {sifPct}%
                        </span>
                      </td>
                      <td className={'trend ' + p.trend.toLowerCase()}>
                        {p.trend === 'INCREASING' ? '↑' : p.trend === 'DECREASING' ? '↓' : '–'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      );
    },

    // 6: Barrier Failure Analysis
    (mode: 'fullscreen' | 'split' | 'grid4' | 'grid', sectionLabel?: string, onChangeChart?: (idx: number) => void) => {
      const isFull = mode === 'fullscreen';
      const isSplit = mode === 'split';
      const isGrid4 = mode === 'grid4';
      const list = isFull ? charts.barrier_failures : isSplit ? charts.barrier_failures.slice(0, 16) : isGrid4 ? charts.barrier_failures.slice(0, 10) : charts.barrier_failures.slice(0, 8);
      const hasHeader = Boolean(onChangeChart);
      return (
        <section key="barriers" className="oil-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          {hasHeader && renderSectionHeader('Barrier Failure Analysis', sectionLabel, onChangeChart, 6)}
          {!hasHeader && <h2>Barrier Failure Analysis</h2>}
          <div style={{ overflowX: 'auto', flex: 1, maxHeight: isGrid4 ? '215px' : undefined }}>
            <table>
              <thead>
                <tr><th>#</th><th>Barrier</th><th>State</th><th>Count</th></tr>
              </thead>
              <tbody>
                {list.map((b, i) => (
                  <tr key={b.name + b.state + i}>
                    <td><span className="oil-rank-badge">{i + 1}</span></td>
                    <td><strong>{b.name}</strong></td>
                    <td><span className={'state ' + b.state.toLowerCase()}>{b.state}</span></td>
                    <td><strong className="oil-barrier-count">{b.count}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      );
    },

    // 7: Precursor → Activity → Life-Saving Rule
    (mode: 'fullscreen' | 'split' | 'grid4' | 'grid', sectionLabel?: string, onChangeChart?: (idx: number) => void) => {
      const isFull = mode === 'fullscreen';
      const isSplit = mode === 'split';
      const isGrid4 = mode === 'grid4';
      const list = isFull ? patterns : isSplit ? patterns.slice(0, 16) : isGrid4 ? patterns.slice(0, 10) : patterns.slice(0, 8);
      const hasHeader = Boolean(onChangeChart);
      return (
        <section key="flow" className="oil-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          {hasHeader && renderSectionHeader('Precursor → Activity → Life-Saving Rule', sectionLabel, onChangeChart, 7)}
          {!hasHeader && <h2>Precursor → Activity → Life-Saving Rule</h2>}
          <div className="flow-list" style={{ flex: 1, overflowY: 'auto', maxHeight: isGrid4 ? '215px' : undefined }}>
            {list.map((p: any, i: number) => (
              <div className="flow-row" key={p.pattern_id || i}>
                <span className="flow-precursor" title={p.dominant_hazard}>{p.dominant_hazard}</span>
                <b className="flow-arrow">→</b>
                <span className="flow-activity" title={p.activities?.[0] || 'General'}>{p.activities?.[0] || 'General'}</span>
                <b className="flow-arrow">→</b>
                <span className="flow-rule" title={p.iogp_rules?.[0] || 'No rule tag'}>{p.iogp_rules?.[0] || 'No rule tag'}</span>
              </div>
            ))}
          </div>
        </section>
      );
    },

    // 8: SIF Precursor Density Ranking
    (mode: 'fullscreen' | 'split' | 'grid4' | 'grid', sectionLabel?: string, onChangeChart?: (idx: number) => void) => {
      const isFull = mode === 'fullscreen';
      const isSplit = mode === 'split';
      const isGrid4 = mode === 'grid4';
      const list = isFull ? sites : isSplit ? sites.slice(0, 16) : isGrid4 ? sites.slice(0, 10) : sites.slice(0, 8);
      const hasHeader = Boolean(onChangeChart);
      return (
        <section key="density" className="oil-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          {hasHeader && renderSectionHeader('SIF Precursor Density Ranking', sectionLabel, onChangeChart, 8)}
          {!hasHeader && <h2>SIF Precursor Density Ranking</h2>}
          <div style={{ overflowX: 'auto', flex: 1, maxHeight: isGrid4 ? '215px' : undefined }}>
            <table>
              <thead>
                <tr><th>#</th><th>Site</th><th>Reports</th><th>SIF</th><th>Density</th></tr>
              </thead>
              <tbody>
                {list.map((s: any, i: number) => {
                  const densityVal = typeof s.adjusted_density === 'number' ? s.adjusted_density : parseFloat(s.adjusted_density) || 0;
                  return (
                    <tr key={s.name + i}>
                      <td><span className="oil-rank-badge">{i + 1}</span></td>
                      <td><strong>{s.name}</strong></td>
                      <td>{s.total_count}</td>
                      <td><span className="oil-sif-count-badge">{s.sif_count}</span></td>
                      <td>
                        <div className="density-cell">
                          <span style={{ width: Math.min(100, Math.max(0, densityVal)) + '%' }} />
                          <b className="density-val">{densityVal}%</b>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      );
    },
  ];

  if (selectedCount === 1) {
    return (
      <>
        <div className="chart-controls" style={{ marginBottom: '14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
          <label style={{ fontSize: '12px', fontWeight: 600, color: '#073ca4', display: 'flex', alignItems: 'center', gap: '6px' }}>
            Charts to display:
            <select
              value={selectedCount}
              onChange={(e) => setSelectedCount(Number(e.target.value))}
              className="chart-mode-select"
            >
              <option value={1}>1 (full screen)</option>
              <option value={2}>2 (split)</option>
              <option value={4}>4 (grid)</option>
              <option value={9}>All</option>
            </select>
          </label>
        </div>

        <div className="oil-fullscreen-container">
          {panelRenderers[fullScreenIndex]?.('fullscreen', 'Full screen', setFullScreenIndex)}
        </div>
      </>
    );
  }

  if (selectedCount === 2) {
    return (
      <>
        <div className="chart-controls" style={{ marginBottom: '14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
          <label style={{ fontSize: '12px', fontWeight: 600, color: '#073ca4', display: 'flex', alignItems: 'center', gap: '6px' }}>
            Charts to display:
            <select
              value={selectedCount}
              onChange={(e) => setSelectedCount(Number(e.target.value))}
              className="chart-mode-select"
            >
              <option value={1}>1 (full screen)</option>
              <option value={2}>2 (split)</option>
              <option value={4}>4 (grid)</option>
              <option value={9}>All</option>
            </select>
          </label>
        </div>

        <div className="oil-split-container">
          <div className="oil-split-pane">
            {panelRenderers[splitIndex1]?.('split', 'Section 1', setSplitIndex1)}
          </div>
          <div className="oil-split-pane">
            {panelRenderers[splitIndex2]?.('split', 'Section 2', setSplitIndex2)}
          </div>
        </div>
      </>
    );
  }

  if (selectedCount === 4) {
    return (
      <>
        <div className="chart-controls" style={{ marginBottom: '14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
          <label style={{ fontSize: '12px', fontWeight: 600, color: '#073ca4', display: 'flex', alignItems: 'center', gap: '6px' }}>
            Charts to display:
            <select
              value={selectedCount}
              onChange={(e) => setSelectedCount(Number(e.target.value))}
              className="chart-mode-select"
            >
              <option value={1}>1 (full screen)</option>
              <option value={2}>2 (split)</option>
              <option value={4}>4 (grid)</option>
              <option value={9}>All</option>
            </select>
          </label>
        </div>

        <div className="oil-grid4-container">
          <div className="oil-grid4-pane">
            {panelRenderers[gridIndex1]?.('grid4', 'Section 1', setGridIndex1)}
          </div>
          <div className="oil-grid4-pane">
            {panelRenderers[gridIndex2]?.('grid4', 'Section 2', setGridIndex2)}
          </div>
          <div className="oil-grid4-pane">
            {panelRenderers[gridIndex3]?.('grid4', 'Section 3', setGridIndex3)}
          </div>
          <div className="oil-grid4-pane">
            {panelRenderers[gridIndex4]?.('grid4', 'Section 4', setGridIndex4)}
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="chart-controls" style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <label style={{ fontSize: '12px', fontWeight: 600, color: '#073ca4' }}>
          Charts to display:
          <select
            value={selectedCount}
            onChange={(e) => setSelectedCount(Number(e.target.value))}
            className="chart-mode-select"
            style={{ marginLeft: '4px' }}
          >
            <option value={1}>1 (full screen)</option>
            <option value={2}>2 (split)</option>
            <option value={4}>4 (grid)</option>
            <option value={9}>All</option>
          </select>
        </label>
      </div>
      <div className="oil-analytics-grid">
        {Array.from({ length: 9 }).map((_, i) => (
          <React.Fragment key={i}>
            {panelRenderers[i]?.('grid')}
          </React.Fragment>
        ))}
      </div>
    </>
  );
}
