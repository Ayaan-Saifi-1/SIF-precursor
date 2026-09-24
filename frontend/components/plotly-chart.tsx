'use client';
import { useEffect, useRef, useState } from 'react';
import type { Data, Layout } from 'plotly.js';
const emptyLayout: Partial<Layout> = {};

export default function PlotlyChart({ data, layout = emptyLayout, label, height = 310, threeDimensional = false }: {
  data: Data[]; layout?: Partial<Layout>; label: string; height?: number; threeDimensional?: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let active = true;
    let observer: ResizeObserver | undefined;
    let renderer: typeof import('plotly.js') | undefined;
    setReady(false);
    setError('');
    (threeDimensional ? import('plotly.js-gl3d-dist-min') : import('plotly.js-cartesian-dist-min')).then(async (module) => {
      if (!active) return;
      renderer = module.default;
      const chart = await renderer.react(element, data, {
        autosize: true, height,
        paper_bgcolor: '#ffffff', plot_bgcolor: '#ffffff',
        font: { family: 'IBM Plex Sans, sans-serif', size: 12, color: '#52636a' },
        margin: { t: 30, r: 24, b: 52, l: 48 },
        hoverlabel: { bgcolor: '#172f39', bordercolor: '#172f39', font: { color: '#ffffff', size: 13 } },
        legend: { orientation: 'h', x: 0, y: 1.17, font: { size: 12 } },
        ...layout,
      }, {
        responsive: true, displaylogo: false, displayModeBar: threeDimensional ? true : 'hover',
        scrollZoom: true, modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        toImageButtonOptions: { format: 'png', filename: 'ascension-chart', scale: 2 },
      });
      if (!active) return;
      setReady(true);
      observer = new ResizeObserver(() => {
        if (active && element.isConnected && renderer) {
          void Promise.resolve(renderer.Plots.resize(chart)).catch(() => {});
        }
      });
      observer.observe(element);
    }).catch(() => active && setError('Chart could not load. Refresh the page to try again.'));
    return () => { active = false; observer?.disconnect(); renderer?.purge(element); };
  }, [data, layout, height, threeDimensional]);
  return <div className="plotly-frame" style={{ minHeight: height, height: '100%', width: '100%' }}>
    {!ready && !error && <div className="chart-loading" role="status">Loading chart…</div>}
    {error && <p className="notice error" role="alert">{error}</p>}
    <div ref={host} role="img" aria-label={label} style={{ width: '100%', height: '100%', minHeight: height }} />
  </div>;
}
