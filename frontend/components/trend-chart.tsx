'use client';
import { useMemo } from 'react';
import type { Data, Layout } from 'plotly.js';
import PlotlyChart from '@/components/plotly-chart';

export default function TrendChart({ counts, ewma }: { counts: number[]; ewma: number[] }) {
  const data = useMemo<Data[]>(() => [
    { type: 'bar', name: 'Reports', x: counts.map((_, i) => 'W' + (i + 1)), y: counts,
      marker: { color: '#b9d0ce' }, hovertemplate: '%{y} reports<extra></extra>' },
    { type: 'scatter', name: 'EWMA', mode: 'lines+markers', x: ewma.map((_, i) => 'W' + (i + 1)), y: ewma,
      line: { color: '#bd613d', width: 2 }, marker: { size: 5 }, hovertemplate: 'EWMA %{y:.2f}<extra></extra>' },
  ], [counts, ewma]);
  const layout = useMemo<Partial<Layout>>(() => ({
    margin: { t: 38, r: 20, b: 34, l: 36 }, bargap: .55, hovermode: 'x unified',
    xaxis: { showgrid: false, zeroline: false },
    yaxis: { rangemode: 'tozero', gridcolor: '#edf0ee', zeroline: false },
  }), []);
  return <PlotlyChart data={data} layout={layout} height={240}
    label={'Weekly reports: ' + counts.join(', ') + '. EWMA: ' + ewma.join(', ') + '.'} />;
}
