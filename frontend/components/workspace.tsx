'use client';
import { useEffect, useState, useRef } from 'react';
import Link from 'next/link';
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  ChevronRight,
  ClipboardCheck,
  FileText,
  Layers3,
  LoaderCircle,
  ShieldAlert,
  TriangleAlert,
  Upload,
  Plus,
  RefreshCw,
  Shield,
  Check,
  CircleX,
  MapPin,
  Network,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import {
  SidebarProvider,
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarFooter,
  SidebarTrigger,
  useSidebar,
} from '@/components/ui/sidebar';
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import { api } from '@/lib/api';
import TrendChart from '@/components/trend-chart';
import DashboardCharts, { type DashboardChartData } from '@/components/dashboard-charts';
import { contextGroups } from '@/lib/input-fields';
import ComingSoon from '@/components/coming-soon';

type View = 'dashboard' | 'analyze' | 'precursors' | 'review';
const navigation = [
  ['dashboard', 'Overview', BarChart3],
  ['analyze', 'Reports & analysis', FileText],
  ['precursors', 'Precursor library', Layers3],
  ['review', 'HSE review', ClipboardCheck],
] as const;
const names = {
  dashboard: 'Safety overview',
  analyze: 'Report analysis',
  precursors: 'Precursor library',
  review: 'HSE review',
};
const human = (s: any) =>
  String(s ?? 'Unknown')
    .replaceAll('_', ' ')
    .toLowerCase()
    .replace(/^\w/, (c) => c.toUpperCase());
function Badge({ value }: { value: string }) {
  return (
    <span className={'badge ' + value?.toLowerCase()}>{human(value)}</span>
  );
}
function Picker({
  value,
  onChange,
  options,
  label,
}: {
  value: string;
  onChange: (v: string) => void;
  options: readonly string[];
  label: string;
}) {
  return (
    <Select
      value={value}
      onValueChange={(v) => v !== null && onChange(String(v))}
    >
      <SelectTrigger aria-label={label}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o} value={o}>
            {human(o)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
function Panel({
  title,
  eyebrow,
  children,
  action,
  className = '',
}: {
  title: string;
  eyebrow?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={'panel ' + className}>
      <div className="panel-head">
        <div>
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="empty">
      <FileText size={24} />
      <p>{children}</p>
    </div>
  );
}
function Evidence({ analysis }: { analysis: any }) {
  const text = analysis.description;
  const spans = [...analysis.evidence_spans].sort(
    (a: any, b: any) =>
      a.start_offset - b.start_offset || b.end_offset - a.end_offset,
  );
  let end = 0;
  const nodes: React.ReactNode[] = [];
  for (const s of spans) {
    if (s.start_offset < end) continue;
    nodes.push(text.slice(end, s.start_offset));
    nodes.push(
      <mark
        key={s.start_offset}
        className={'evidence-' + s.label.toLowerCase()}
        title={human(s.label)}
      >
        {text.slice(s.start_offset, s.end_offset)}
      </mark>,
    );
    end = s.end_offset;
  }
  nodes.push(text.slice(end));
  return <div className="evidence-text">{nodes}</div>;
}
function Result({ data }: { data: any }) {
  return (
    <div className="result-stack">
      <section className={'decision ' + data.priority.toLowerCase()}>
        <div>
          <p className="eyebrow">Assessment · {data.report_id}</p>
          <h2>{human(data.sif_label).replace(/^Sif/, 'SIF')}</h2>
          <div className="inline">
            <Badge value={data.priority} />
            <span>{human(data.decision_source)}</span>
          </div>
        </div>
        <ShieldAlert size={36} />
      </section>
      <div className="model-strip">
        <span>
          Text encoder <strong>{human(data.encoder_status)}</strong>
        </span>
        <span>
          SIF classifier <strong>{human(data.classifier_status)}</strong>
        </span>
        <span>
          SIF probability{' '}
          <strong>
            {data.sif_probability == null
              ? 'Unavailable'
              : (data.sif_probability * 100).toFixed(1) + '%'}
          </strong>
        </span>
      </div>
      {data.status === 'ANALYSIS_UNAVAILABLE' && (
        <div className="notice">
          <TriangleAlert size={18} />
          <div>
            <strong>Human review required</strong>
            <p>
              {data.encoder_status === 'READY'
                ? 'No SIF probability is available. Review the evidence and safety rules below; the classifier needs training and validation.'
                : 'Model inference is unavailable. Safety rules remain active and this report is retained for review.'}
            </p>
          </div>
        </div>
      )}
      {data.hard_gate.triggered && (
        <div className="gate">
          <ShieldAlert size={20} />
          <div>
            <strong>Hard safety gate triggered</strong>
            <p>{data.hard_gate.reason.join(' + ')}</p>
            <span>Mandatory HSE review</span>
          </div>
        </div>
      )}
      <Panel title="Source evidence" eyebrow="Original narrative">
        <Evidence analysis={data} />
        <div className="legend">
          <span>
            <i className="exposure-dot" />
            Exposure
          </span>
          <span>
            <i className="hazard-dot" />
            Hazard
          </span>
          <span>
            <i className="activity-dot" />
            Activity / control
          </span>
        </div>
        <dl className="facts">
          {[
            ['Activity', data.activity],
            ['Equipment', data.equipment.join(', ')],
            ['Hazard / energy', data.hazards.join(', ')],
            [
              'Exposure',
              data.simulated
                ? 'No actual exposure identified · simulation'
                : data.exposure_status === 'EXPLICITLY_NEGATED'
                  ? 'Report explicitly states no exposure'
                  : data.exposures.join(', '),
            ],
            ['Potential consequence', data.potential_consequences.join(', ')],
          ].map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v || 'Unknown — further information needed'}</dd>
            </div>
          ))}
        </dl>
        <p className="footnote">
          Consequences are inferred safety pathways. Highlighted spans reproduce
          the submitted narrative.
        </p>
        <div className="tags">
          {data.iogp_rules.map((r: string) => (
            <span key={r}>
              <Shield size={13} />
              {r}
            </span>
          ))}
        </div>
      </Panel>
      <Panel title="Critical barriers" eyebrow="Control integrity">
        {data.barriers.length ? (
          data.barriers.map((b: any, i: number) => (
            <div className="barrier" key={i}>
              <div className="between">
                <h3>{b.name}</h3>
                <Badge value={b.state} />
              </div>
              <p>{b.threat}</p>
              <div className="barrier-meta">
                <span>Presence: {human(b.verification_status)}</span>
                <span>Effectiveness: {human(b.validation_status)}</span>
              </div>
              {b.evidence && (
                <blockquote>
                  “{b.evidence}”{' '}
                  {b.inferred && <small>· Inferred weakness</small>}
                </blockquote>
              )}
              {b.contradictory && (
                <p className="error-text">
                  Conflicting evidence — clarification required.
                </p>
              )}
            </div>
          ))
        ) : (
          <Empty>
            No critical barrier identified. HSE clarification required.
          </Empty>
        )}
      </Panel>
      {data.missing_information.length > 0 && (
        <Panel title="Information needed">
          <div className="tags missing">
            {data.missing_information.map((x: string) => (
              <span key={x}>{human(x)}</span>
            ))}
          </div>
        </Panel>
      )}
      {data.structured_evidence?.length > 0 && (
        <Panel title="Reported operational context">
          <dl className="facts">
            {data.structured_evidence.map((e: any) => (
              <div key={e.field}>
                <dt>{human(e.field)}</dt>
                <dd>{String(e.value)}</dd>
              </div>
            ))}
          </dl>
          <p className="footnote">
            Reported fields are preserved separately from extracted narrative
            evidence.
          </p>
        </Panel>
      )}
      {data.pattern_id && (
        <Link
          className="related-link"
          href={'/precursors?pattern=' + data.pattern_id}
        >
          <Layers3 />
          <div>
            <strong>{data.similar_report_count} related reports</strong>
            <p>
              {data.pattern_id} · {data.sites_affected?.length || 0} sites ·
              Curated precursor family
            </p>
          </div>
          <ArrowUpRight />
        </Link>
      )}
      <p className="footnote">
        Model: {data.model_version} · Catalogue: {data.catalogue_version} ·{' '}
        {new Date(data.analysis_timestamp).toLocaleString()}
      </p>
    </div>
  );
}
function DensityTable({ rows }: { rows: any[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {[
            'Site',
            'SIF / reports',
            'Raw',
            'Adjusted',
            '95% interval',
            'Reliability',
          ].map((x) => (
            <TableHead key={x}>{x}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r: any, i: number) => (
          <TableRow key={r.name}>
            <TableCell>
              <span className="row-number">
                {String(i + 1).padStart(2, '0')}
              </span>
              <strong>{r.name}</strong>
            </TableCell>
            <TableCell>
              {r.sif_count} <span className="muted">/ {r.total_count}</span>
            </TableCell>
            <TableCell>{r.raw_density}%</TableCell>
            <TableCell>
              <strong>{r.adjusted_density}%</strong>
            </TableCell>
            <TableCell className="muted">
              {r.lower_bound}–{r.upper_bound}%
            </TableCell>
            <TableCell>
              <span
                className={'reliability ' + r.reliability_level.toLowerCase()}
              >
                {human(r.reliability_level)} · n={r.sample_size}
              </span>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function SidebarNavItems({
  navigation,
  view,
}: {
  navigation: readonly (readonly [string, string, any])[];
  view: string;
}) {
  const { isMobile, setOpenMobile } = useSidebar();
  return (
    <nav aria-label="Main navigation">
      {navigation.map(([key, label, Icon]) => (
        <Link
          aria-current={key === view ? 'page' : undefined}
          href={'/' + key}
          key={key}
          className={'nav-link ' + (key === view ? 'active' : '')}
          onClick={() => {
            if (isMobile) setOpenMobile(false);
          }}
        >
          <Icon size={19} />
          <span>{label}</span>
        </Link>
      ))}
    </nav>
  );
}

export default function Workspace({ view }: { view: View }) {
  const [health, setHealth] = useState<any>(null),
    [charts, setCharts] = useState<DashboardChartData | null>(null),
    [summary, setSummary] = useState<any>(null),
    [sites, setSites] = useState<any[]>([]),
    [activities, setActivities] = useState<any[]>([]),
    [patterns, setPatterns] = useState<any[]>([]),
    [reviews, setReviews] = useState<any[]>([]);
  const [days, setDays] = useState('60'),
    [dashboardFilters, setDashboardFilters] = useState({site:'ALL',activity:'ALL',report_type:'ALL'}),
    [useDemo, setUseDemo] = useState(true),
    [dashboardChartCount, setDashboardChartCount] = useState<number>(9),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(''),
    [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    if (view === 'precursors' || view === 'review') {
      setLoading(false);
      setError('');
      return;
    }
    setLoading(true);
    setError('');
    const params=new URLSearchParams({days});
    if (!useDemo) params.set('demo', 'false');
    Object.entries(dashboardFilters).forEach(([key,value])=>{ if(value!=='ALL') params.set(key,value); });
    const query='?'+params.toString();
    Promise.all([
      api('/health/'),
      api('/dashboard/summary/' + query),
      api('/dashboard/site-density/' + query),
      api('/dashboard/activity-density/' + query),
      api('/patterns/' + query),
      api('/reviews/'),
      view === 'dashboard' ? api('/dashboard/charts/' + query) : Promise.resolve(null),
    ])
      .then(([h, s, sd, ad, p, r, c]) => {
        if (active) {
          setHealth(h);
          setSummary(s);
          setSites(sd);
          setActivities(ad);
          setPatterns(p);
          setReviews(r);
          setCharts(c);
        }
      })
      .catch((e) => active && setError(e.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [days, dashboardFilters, refresh, view, useDemo]);
  return (
    <SidebarProvider
      className="dashboard-mode"
      style={{ '--sidebar-width': '190px' } as React.CSSProperties}
    >
      <Sidebar className="app-sidebar">
        <SidebarHeader className="brand">
          <Link
            href="/dashboard"
            aria-label="Ascension home"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
              height: '100%',
              padding: '4px 6px',
            }}
          >
            <img
              src="/ascension-logo.png"
              alt="Ascension"
              className="brand-symbol"
              style={{
                width: 'auto',
                maxWidth: '135px',
                maxHeight: '75px',
                height: 'auto',
                objectFit: 'contain',
                filter: 'drop-shadow(0 2px 10px rgba(0, 0, 0, 0.5))',
              }}
            />
          </Link>
        </SidebarHeader>
        <SidebarContent>
          <p className="nav-label">Workspace</p>
          <SidebarNavItems navigation={navigation} view={view} />
        </SidebarContent>
        <SidebarFooter className="sidebar-footer">
          <div className="avatar">MR</div>
          <div>
            <strong>Matrika Regmi</strong>
            <span>Logged in</span>
          </div>
        </SidebarFooter>
      </Sidebar>
      <div className="app-content">
        <header className="topbar">
          <div className="inline">
            <SidebarTrigger className="mobile-trigger" />
            <span className="muted topbar-crumb-label">Operations</span>
            <ChevronRight size={13} className="topbar-crumb-sep" />
            <strong className="topbar-page-title">{names[view]}</strong>
          </div>
          <div className="workspace-status">
            <span className="demo-indicator" />
            <span className="workspace-status-text">Demo workspace</span>
          </div>
        </header>
        <main id="main-content">
          {view === 'precursors' || view === 'review' ? (
            <ComingSoon />
          ) : (
            <>
              {((view === 'dashboard' && dashboardChartCount === 9) || view === 'analyze') && (
                <div className="page-heading dashboard-page-heading">
                  <div>
                    <h1>{view === 'dashboard' ? 'Safety overview' : 'Reports & analysis'}</h1>
                    <p>
                      {view === 'dashboard'
                        ? 'AI-assisted analysis of unsafe acts, conditions, near misses and incidents.'
                        : 'Submit a report or inspect its AI-assisted safety assessment.'}
                    </p>
                  </div>
                  {view === 'dashboard' && (
                    <div className="dashboard-filters" aria-label="Dashboard filters">
                      <label style={{display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', fontSize: '11px', fontWeight: 600, color: '#073ca4'}}>
                        <input type="checkbox" checked={useDemo} onChange={e => setUseDemo(e.target.checked)} style={{margin: 0, cursor: 'pointer'}} />
                        Include Demo Data
                      </label>
                      <label><span>Period</span><select value={days} onChange={e=>setDays(e.target.value)}><option value="30">Last 30 days</option><option value="60">Last 60 days</option><option value="90">Last 90 days</option><option value="365">Last 12 months</option></select></label>
                      {([['site','All sites'],['activity','All activities'],['report_type','All report types']] as const).map(([key,label])=><label key={key}><span>{label}</span><select value={dashboardFilters[key]} onChange={e=>setDashboardFilters(v=>({...v,[key]:e.target.value}))}><option value="ALL">{label}</option>{(charts?.filter_options?.[key]||[]).map((value:string)=><option value={value} key={value}>{value}</option>)}</select></label>)}
                    </div>
                  )}
                </div>
              )}
              {view === 'dashboard' && dashboardChartCount === 9 && !loading && !error && charts && (
                <div className="oil-kpi-header">
                  {([
                    [FileText, 'Total reports', charts.total_reports, 'In selected filters'],
                    [TriangleAlert, 'SIF-potential', charts.classification.sif, `${Math.round(charts.classification.sif/Math.max(charts.total_reports,1)*100)}% of reports`],
                    [Shield, 'Non-SIF', charts.classification.non_sif, `${Math.round(charts.classification.non_sif/Math.max(charts.total_reports,1)*100)}% of reports`],
                    [CircleX, 'Unresolved', charts.classification.unresolved, 'Requires HSE review'],
                    [MapPin, 'Sites', charts.sites.length, 'With reports'],
                    [Network, 'Activity categories', activities.length, `${charts.report_types.length} report types`],
                  ] as any[]).map(([Icon,label,value,sub]:any)=><KpiHeaderCard key={label} label={label} value={value} sub={sub}/>)}
                </div>
              )}
              {error ? (
                <div className="notice error" role="alert">
                  <TriangleAlert />
                  <div>
                    <strong>Unable to load the workspace</strong>
                    <p>
                      {error.includes('fetch')
                        ? 'The local analysis service is not reachable. Start the backend and try again.'
                        : error}
                    </p>
                    <Button
                      variant="outline"
                      onClick={() => setRefresh((x) => x + 1)}
                    >
                      <RefreshCw size={16} />
                      Retry
                    </Button>
                  </div>
                </div>
              ) : loading ? (
                <div className="loading-grid" aria-label="Loading workspace">
                  {[0, 1, 2, 3].map((n) => (
                    <Skeleton key={n} className="h-32 rounded-lg" />
                  ))}
                  <Skeleton className="h-80 col-span-full" />
                </div>
              ) : (
                <>
                  {view === 'dashboard' && (
                    <Dashboard
                      summary={summary}
                      sites={sites}
                      activities={activities}
                      patterns={patterns}
                      days={days}
                      setDays={setDays}
                      charts={charts}
                      filters={dashboardFilters}
                      useDemo={useDemo}
                      selectedCount={dashboardChartCount}
                      onSelectedCountChange={setDashboardChartCount}
                    />
                  )}
                  {view === 'analyze' && <Analyze />}
                </>
              )}
            </>
          )}
          <footer className="app-footer">
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
              <img src="/ascension-logo.png" alt="" style={{ width: '18px', height: '18px', objectFit: 'contain' }} />
              ASCENSION · Safety Intelligence
            </span>
            <span>Copyright © 2026 Team Ascension. All rights reserved.</span>
          </footer>
        </main>
      </div>
    </SidebarProvider>
  );
}
function useCountUp(target: number, duration = 900) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (target === 0) { setVal(0); return; }
    let start: number | null = null;
    const step = (ts: number) => {
      if (!start) start = ts;
      const progress = Math.min((ts - start) / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      setVal(Math.round(ease * target));
      if (progress < 1) requestAnimationFrame(step);
    };
    const id = requestAnimationFrame(step);
    return () => cancelAnimationFrame(id);
  }, [target, duration]);
  return val;
}

function KpiHeaderCard({ label, value, sub }: { label: string; value: number; sub: string }) {
  const animated = useCountUp(value);
  return (
    <section className="oil-kpi">
      <div>
        <strong>{animated}</strong>
        <span>{label}</span>
        <small>{sub}</small>
      </div>
    </section>
  );
}

function Dashboard({summary,sites,activities,patterns,days,charts,useDemo,selectedCount,onSelectedCountChange}: any) {
  if (!charts) return null;
  return <div className="oil-dashboard">
    <DashboardCharts
      charts={charts}
      activities={activities}
      patterns={patterns}
      sites={sites}
      days={days}
      useDemo={useDemo}
      selectedCount={selectedCount}
      onSelectedCountChange={onSelectedCountChange}
    />
  </div>;
}

function LegacyDashboard({
  summary,
  sites,
  activities,
  patterns,
  days,
  setDays,
  charts,
}: any) {
  const top = patterns[0];
  return (
    <>
      <div className="section-toolbar">
        <div className="inline">
          <span className="section-label">Reporting period</span>
          <span className="muted">
            {sites.length} sites · {summary.synthetic_count} synthetic reports
          </span>
        </div>
        <Picker
          value={days}
          onChange={setDays}
          options={['7', '30', '60', '90', '365']}
          label="Report window in days"
        />
        <span className="muted">days</span>
      </div>
      <div className="kpi-grid">
        {[
          [
            FileText,
            'Reports analysed',
            summary.reports_analysed,
            'Structurally valid reports',
            'navy',
          ],
          [
            ShieldAlert,
            'SIF-potential reports',
            summary.sif_potential,
            'Evidence-based safety flags',
            'red',
          ],
          [
            Layers3,
            'Critical barrier failures',
            summary.critical_barrier_failures,
            'Failed · bypassed · absent',
            'orange',
          ],
          [
            ClipboardCheck,
            'Pending HSE review',
            summary.review_required,
            'Includes model-unavailable cases',
            'amber',
          ],
        ].map(([Icon, label, value, sub, color]: any) => (
          <section key={label} className={'kpi ' + color}>
            <div className="between">
              <p>{label}</p>
              <Icon size={19} />
            </div>
            <strong>{value}</strong>
            <span>{sub}</span>
          </section>
        ))}
      </div>
      {charts && <DashboardCharts charts={charts} activities={activities} patterns={patterns} sites={sites} days={days} useDemo={true} />}
      <details className="site-detail-panel">
        <summary>Site density details <span>Rates within reports, sample sizes and uncertainty</span></summary>
        <Panel
          title="Site SIF density"
          eyebrow="Site comparison"
          action={<span className="subtle-chip">Beta-binomial adjusted</span>}
          className="site-panel"
        >
          <DensityTable rows={sites} />
          <div className="panel-note">
            <TriangleAlert size={15} />
            <p>
              Report-based density, not an operational incident rate. Review
              cases remain in the denominator; {summary.unavailable} assessments
              have no model probability. Small samples need caution.
            </p>
          </div>
        </Panel>
      </details>
      <div className="dashboard-bottom">
        {top && (
          <section className="emerging-panel">
            <div className="between">
              <span className="eyebrow">PRECURSOR WATCH</span>
              <Badge value={top.trend} />
            </div>
            <Layers3 size={27} />
            <h2>{top.dominant_hazard}</h2>
            <p>
              {top.dominant_barrier} · {top.sites.length} sites
            </p>
            <div className="emerging-stats">
              <strong>
                {top.report_count}
                <span>related reports</span>
              </strong>
              <strong>
                {top.sif_count}
                <span>SIF-potential</span>
              </strong>
            </div>
            <div
              className="mini-bars"
              aria-label={'Weekly reports: ' + top.weekly_counts.join(', ')}
            >
              {top.weekly_counts.map((n: number, i: number) => (
                <span
                  key={i}
                  style={{
                    height: Math.max(
                      5,
                      (n / Math.max(...top.weekly_counts, 1)) * 50,
                    ),
                  }}
                />
              ))}
            </div>
            <Link href={'/precursors?pattern=' + top.pattern_id}>
              Inspect precursor <ArrowRight size={17} />
            </Link>
          </section>
        )}
        <Panel
          title="Priority attention"
          eyebrow="Review queue"
          action={
            <Link className="text-link" href="/review">
              View queue <ArrowRight size={15} />
            </Link>
          }
        >
          {summary.recent_critical.length ? (
            summary.recent_critical.slice(0, 4).map((r: any) => (
              <Link
                className="priority-row"
                key={r.report_id}
                href={'/analyze?report=' + r.report_id}
              >
                <span className={'priority-line ' + r.priority.toLowerCase()} />
                <div>
                  <div className="inline">
                    <strong>{r.report_id}</strong>
                    <Badge value={r.priority} />
                  </div>
                  <p>{r.description}</p>
                  <small>
                    {r.site} · {r.activity}
                  </small>
                </div>
                <ArrowUpRight size={16} />
              </Link>
            ))
          ) : (
            <Empty>No high-priority reports in this period.</Empty>
          )}
        </Panel>
      </div>
    </>
  );
}
function Analyze() {
  const empty = () => ({
    report_id: '',
    site: '',
    department: 'Operations',
    report_type: 'Near Miss',
    event_date: new Date(Date.now() - 60000 + 19800000)
      .toISOString()
      .slice(0, 10),
    event_time: new Date(Date.now() - 60000 + 19800000)
      .toISOString()
      .slice(11, 16),
    description: '',
    immediate_action: '',
    source_system: 'MANUAL_ENTRY',
    source_record_id: '',
    is_synthetic: false,
    context: {} as Record<string, string>,
  });
  const [form, setForm] = useState(empty),
    [samples, setSamples] = useState<any[]>([]),
    [result, setResult] = useState<any>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [message, setMessage] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    api('/samples/')
      .then(setSamples)
      .catch((e) => setError(e.message));
    const id = new URLSearchParams(window.location.search).get('report');
    if (id) {
      setBusy(true);
      api('/analyses/' + encodeURIComponent(id) + '/')
        .then(setResult)
        .catch((e) => setError(e.message))
        .finally(() => setBusy(false));
    }
  }, []);
  const field = (key: string, value: any) =>
    setForm((f) => ({ ...f, [key]: value }));
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const r = await api('/analyze/', {
        method: 'POST',
        body: JSON.stringify(form),
      });
      setResult(r);
      window.history.replaceState(
        window.history.state,
        '',
        '/analyze?report=' + encodeURIComponent(r.report_id),
      );
      setMessage('Report saved. Assessment and HSE review item recorded.');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function upload(file: File) {
    setBusy(true);
    setError('');
    setMessage('');
    const body = new FormData();
    body.append('file', file);
    try {
      const r = await api('/reports/import/', { method: 'POST', body });
      setMessage(r.imported + ' reports imported and analysed.');
      if (r.analyses.length) {
        setResult(r.analyses[0]);
        window.history.replaceState(
          window.history.state,
          '',
          '/analyze?report=' + encodeURIComponent(r.analyses[0].report_id),
        );
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }
  function sample(s: any) {
    setForm({
      ...empty(),
      report_id: 'DEMO-' + Date.now().toString(36).toUpperCase(),
      site: 'Duliajan · Demo',
      description: s.description,
      report_type: s.report_type,
      is_synthetic: true,
      source_system: 'SYNTHETIC_DEMO',
    });
    setResult(null);
    setMessage('');
    setError('');
  }
  if (result) {
    return (
      <div className="saved-assessment">
        <div className="assessment-toolbar">
          <span className="section-label">
            Saved report <strong>{result.report_id}</strong>
          </span>
          <div className="inline">
            <Button
              variant="outline"
              onClick={() => {
                setResult(null);
                setForm(empty());
                setMessage('');
                setError('');
                window.history.replaceState(
                  window.history.state,
                  '',
                  '/analyze',
                );
              }}
            >
              <Plus size={15} />
              New report
            </Button>
            <Link className="primary-link" href="/review">
              <ClipboardCheck size={16} />
              HSE review queue
            </Link>
          </div>
        </div>
        {message && (
          <div className="notice" role="status">
            {message}
          </div>
        )}
        <Result data={result} />
      </div>
    );
  }
  return (
    <div className="analysis-grid">
      <div>
        <Panel
          title="New safety report"
          className="intake-panel"
          action={
            <>
              <input
                ref={fileRef}
                hidden
                type="file"
                accept=".csv,.xlsx"
                aria-label="Import reports"
                onChange={(e) =>
                  e.target.files?.[0] && upload(e.target.files[0])
                }
              />
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => fileRef.current?.click()}
              >
                <Upload size={15} />
                Import file
              </Button>
            </>
          }
        >
          <details className="sample-picker">
            <summary>
              <span>Try a sample report</span>
              <span className="sample-hint">
                Fictional cases <ChevronRight size={14} />
              </span>
            </summary>
            <div className="sample-buttons">
              {samples.map((s) => (
                <Button
                  key={s.name}
                  type="button"
                  variant="outline"
                  disabled={busy}
                  onClick={() => sample(s)}
                >
                  {s.name}
                </Button>
              ))}
            </div>
          </details>
          <form onSubmit={submit}>
            <div className="form-section-heading">
              <span>01</span>
              <h3>Event details</h3>
              <small>Required fields *</small>
            </div>
            <div className="form-grid">
              {[
                ['report_id', 'Report ID', 'text'],
                ['site', 'Site', 'text'],
                ['department', 'Department', 'text'],
              ].map(([k, label, type]) => (
                <label key={k}>
                  {label} <span>*</span>
                  <Input
                    required
                    maxLength={k === 'report_id' ? 80 : 120}
                    value={(form as any)[k]}
                    onChange={(e) => field(k, e.target.value)}
                    type={type}
                  />
                </label>
              ))}
              <label>
                Report type <span>*</span>
                <Picker
                  label="Report type"
                  value={form.report_type}
                  onChange={(v) => field('report_type', v)}
                  options={[
                    'Unsafe Act',
                    'Unsafe Condition',
                    'Near Miss',
                    'Incident',
                  ]}
                />
              </label>
              <label>
                Event date <span>*</span>
                <Input
                  required
                  type="date"
                  value={form.event_date}
                  onChange={(e) => field('event_date', e.target.value)}
                />
              </label>
              <label>
                Event time · IST <span>*</span>
                <Input
                  required
                  type="time"
                  value={form.event_time}
                  onChange={(e) => field('event_time', e.target.value)}
                />
              </label>
            </div>
            <div className="form-section-heading">
              <span>02</span>
              <h3>Observation</h3>
            </div>
            <label className="full-label">
              What happened? <span>*</span>
              <Textarea
                required
                minLength={8}
                maxLength={12000}
                rows={6}
                value={form.description}
                onChange={(e) => field('description', e.target.value)}
                placeholder="Describe the activity, equipment, hazard, worker exposure and control condition…"
              />
            </label>
            <label className="full-label">
              Immediate action taken
              <Textarea
                maxLength={4000}
                rows={3}
                value={form.immediate_action}
                onChange={(e) => field('immediate_action', e.target.value)}
                placeholder="Actions taken after the observation"
              />
            </label>
            <p className="footnote">
              Immediate actions are stored separately from the event evidence.
              Unknown information should be left unknown.
            </p>
            <div className="form-section-heading context-heading">
              <span>03</span>
              <h3>Supporting information</h3>
              <small>Optional</small>
            </div>
            <details className="context-group">
              <summary>
                Source and traceability <span>Optional</span>
              </summary>
              <div className="form-grid">
                <label>
                  Source system
                  <Input
                    value={form.source_system}
                    onChange={(e) => field('source_system', e.target.value)}
                  />
                </label>
                <label>
                  Source record ID
                  <Input
                    placeholder="Defaults to report ID"
                    value={form.source_record_id}
                    onChange={(e) => field('source_record_id', e.target.value)}
                  />
                </label>
              </div>
              <p className="footnote">
                The original submission and its source are recorded
                automatically for traceability.
              </p>
            </details>
            {contextGroups.map((group) => (
              <details className="context-group" key={group.title}>
                <summary>
                  {group.title}
                  <span>Optional</span>
                </summary>
                <div className="form-grid">
                  {group.fields.map((f: any) => {
                    const [key, label, options] = f;
                    return (
                      <label key={key}>
                        {label}
                        {options ? (
                          <Picker
                            label={label}
                            value={form.context[key] || 'UNKNOWN'}
                            options={options}
                            onChange={(v) =>
                              field('context', { ...form.context, [key]: v })
                            }
                          />
                        ) : (
                          <Input
                            value={form.context[key] || ''}
                            placeholder="Unknown if not recorded"
                            onChange={(e) =>
                              field('context', {
                                ...form.context,
                                [key]: e.target.value,
                              })
                            }
                          />
                        )}
                      </label>
                    );
                  })}
                </div>
              </details>
            ))}
            <div className="submit-row">
              <Button size="lg" type="submit" disabled={busy}>
                {busy ? (
                  <LoaderCircle className="spin" size={17} />
                ) : (
                  <Activity size={17} />
                )}{' '}
                {busy ? 'Analysing…' : 'Analyze & save report'}
                <ArrowRight size={16} />
              </Button>
              <span>
                {form.is_synthetic ? 'Synthetic sample' : 'New report'}
              </span>
            </div>
            {error && (
              <div className="notice error" role="alert">
                {error}
              </div>
            )}
            {message && (
              <div className="notice" role="status">
                <Check size={18} />
                {message}
                <Link href="/review" className="text-link">
                  Open queue
                </Link>
              </div>
            )}
          </form>
        </Panel>
        <div className="intake-help">
          <Shield size={20} />
          <p>
            CSV and XLSX imports accept the same report fields. Maximum 100
            reports per file.
          </p>
        </div>
      </div>
      <div className="assessment-column">
        <aside className="awaiting-result">
          <div className="assessment-heading">
            <span className="assessment-marker" />
            <h2>Assessment</h2>
            <span>Awaiting report</span>
          </div>
          <div className="assessment-empty-body">
            <FileText size={28} strokeWidth={1.3} />
            <h3>No assessment yet.</h3>
            <p>
              Add the event details and describe what happened. The assessment
              will appear here after you submit.
            </p>
            <ol className="assessment-outline">
              <li>
                <span>01</span>
                <div>
                  <strong>Source evidence</strong>
                  <p>Activity, hazard and exposure in the report.</p>
                </div>
              </li>
              <li>
                <span>02</span>
                <div>
                  <strong>Critical barriers</strong>
                  <p>Reported controls and signs of failure.</p>
                </div>
              </li>
              <li>
                <span>03</span>
                <div>
                  <strong>HSE review</strong>
                  <p>Safety flags and information still needed.</p>
                </div>
              </li>
            </ol>
          </div>
          <div className="assessment-guidance">
            <Shield size={17} />
            <p>
              Describe observed facts. Leave unknown details blank; absence of
              injury does not establish safety.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
function Precursors({ patterns, days }: any) {
  const [selected, setSelected] = useState<string | null>(null),
    [reports, setReports] = useState<any[]>([]),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    setSelected(new URLSearchParams(window.location.search).get('pattern'));
  }, []);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    setBusy(true);
    setError('');
    api('/patterns/' + selected + '/reports/?days=' + days)
      .then((r) => active && setReports(r))
      .catch((e) => active && setError(e.message))
      .finally(() => active && setBusy(false));
    return () => {
      active = false;
    };
  }, [selected, days]);
  const current = patterns.find((p: any) => p.pattern_id === selected);
  return (
    <>
      <div className="section-toolbar">
        <span className="section-label">
          {patterns.length} PRECURSOR FAMILIES
        </span>
        <p className="muted">
          Curated hazard–barrier families · EWMA α = 0.3 · 8-week history
        </p>
      </div>
      <div className="pattern-list-heading">
        <span>Hazard / critical barrier</span>
        <span>8-week activity</span>
        <span>Reports / SIF / sites</span>
        <span>Trend</span>
      </div>
      <div className="pattern-grid">
        {patterns.map((p: any) => (
          <button
            aria-haspopup="dialog"
            onClick={() => setSelected(p.pattern_id)}
            key={p.pattern_id}
            className={
              'pattern-card ' + (selected === p.pattern_id ? 'selected' : '')
            }
          >
            <div className="pattern-identity">
              <span className="eyebrow">{p.pattern_id}</span>
              <h2>{p.dominant_hazard}</h2>
              <p>{p.dominant_barrier}</p>
              <Badge value={p.dominant_barrier_state} />
            </div>
            <div
              className="mini-bars"
              aria-label={'Weekly reports: ' + p.weekly_counts.join(', ')}
            >
              {p.weekly_counts.map((n: number, i: number) => (
                <span
                  key={i}
                  title={
                    'Week ' + (i + 1) + ': ' + n + ' reports; EWMA ' + p.ewma[i]
                  }
                  style={{
                    height: Math.max(
                      4,
                      (n / Math.max(...p.weekly_counts, 1)) * 36,
                    ),
                  }}
                />
              ))}
            </div>
            <div className="pattern-counts">
              <strong>
                {p.report_count}
                <span>reports</span>
              </strong>
              <strong>
                {p.sif_count}
                <span>SIF</span>
              </strong>
              <strong>
                {p.sites.length}
                <span>sites</span>
              </strong>
            </div>
            <div className="pattern-trend">
              <Badge value={p.trend} />
              <ArrowUpRight size={17} />
            </div>
          </button>
        ))}
      </div>
      {current && (
        <Sheet
          open={Boolean(current)}
          onOpenChange={(open) => !open && setSelected(null)}
        >
          <SheetContent className="evidence-drawer" showCloseButton={false}>
            <SheetTitle className="sr-only">{current.title}</SheetTitle>
            <SheetDescription className="sr-only">
              Precursor evidence, trend and related reports.
            </SheetDescription>
            <Panel
              title={current.title}
              action={
                <Button
                  variant="ghost"
                  aria-label="Close precursor evidence"
                  onClick={() => setSelected(null)}
                >
                  Close
                </Button>
              }
              eyebrow={current.pattern_id + ' · Supporting evidence'}
            >
              <div className="pattern-detail">
                <p>
                  <strong>Sites:</strong> {current.sites.join(', ')}
                </p>
                <p>
                  <strong>Activity:</strong> {current.activities.join(', ')} ·{' '}
                  <strong>Severity:</strong> {human(current.severity)}
                </p>
                <div className="tags">
                  {current.iogp_rules.map((r: string) => (
                    <span key={r}>{r}</span>
                  ))}
                </div>
                <TrendChart
                  counts={current.weekly_counts}
                  ewma={current.ewma}
                />
                <p className="footnote">
                  {current.period}. Weekly counts:{' '}
                  {current.weekly_counts.join(' / ')}. EWMA:{' '}
                  {current.ewma.join(' / ')}.
                </p>
              </div>
              {busy ? (
                <p className="padded">Loading source reports…</p>
              ) : error ? (
                <p role="alert" className="notice error">
                  {error}
                </p>
              ) : (
                reports.map((r) => (
                  <Link
                    className="priority-row"
                    key={r.report_id}
                    href={'/analyze?report=' + r.report_id}
                  >
                    <FileText size={18} />
                    <div>
                      <div className="inline">
                        <strong>{r.report_id}</strong>
                        <Badge value={r.priority} />
                      </div>
                      <p>{r.description}</p>
                      <small>{r.site}</small>
                    </div>
                    <ArrowUpRight size={16} />
                  </Link>
                ))
              )}
            </Panel>
          </SheetContent>
        </Sheet>
      )}
    </>
  );
}
function Reviews({ reviews, onSaved }: any) {
  const [status, setStatus] = useState('OPEN'),
    [dateOrder, setDateOrder] = useState('ALL'),
    [selected, setSelected] = useState<any>(null),
    [decision, setDecision] = useState('CONFIRM'),
    [reviewer, setReviewer] = useState(''),
    [reason, setReason] = useState(''),
    [error, setError] = useState(''),
    [message, setMessage] = useState(''),
    [busy, setBusy] = useState(false);
  const visible = reviews
    .filter((r: any) => status === 'ALL' || r.status === status)
    .sort((a: any, b: any) => {
      if (dateOrder === 'ALL') return 0;
      const aTime = new Date(a.created_at || 0).getTime();
      const bTime = new Date(b.created_at || 0).getTime();
      return dateOrder === 'LATEST' ? bTime - aTime : aTime - bTime;
    });
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api('/reviews/' + selected.id + '/decision/', {
        method: 'POST',
        body: JSON.stringify({
          decision,
          reviewer,
          override_reason: reason,
          version: selected.version,
        }),
      });
      setMessage(
        'Decision recorded for ' +
          selected.report_id +
          '. The original AI assessment is preserved.',
      );
      setSelected(null);
      onSaved();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="section-toolbar">
        <div className="inline">
          <span className="section-label">{visible.length} CASES</span>
          <p className="muted">
            Hard gates first · oldest cases within each priority
          </p>
        </div>
        <Picker
          label="Review status"
          value={status}
          onChange={setStatus}
          options={[
            'OPEN',
            'ESCALATED',
            'AWAITING_INFORMATION',
            'REVIEWED',
            'ALL',
          ]}
        />
        <Picker
          label="Date order"
          value={dateOrder}
          onChange={setDateOrder}
          options={['LATEST', 'OLDEST', 'ALL']}
        />
      </div>
      {message && (
        <div className="notice" role="status">
          {message}
        </div>
      )}
      <div className="review-layout">
        <Panel title="Review cases">
          <Table>
            <TableHeader>
              <TableRow>
                {[
                  'Priority',
                  'Report / site',
                  'Safety finding',
                  'Status',
                  '',
                ].map((x, i) => (
                  <TableHead key={i}>{x}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {visible.map((r: any) => (
                <TableRow
                  key={r.id}
                  data-state={selected?.id === r.id ? 'selected' : undefined}
                >
                  <TableCell>
                    <Badge value={r.priority} />
                  </TableCell>
                  <TableCell>
                    <strong>{r.report_id}</strong>
                    <small className="block">{r.site}</small>
                  </TableCell>
                  <TableCell className="case-finding">
                    <p>{r.description}</p>
                    <span>
                      {r.barrier_states.map(human).join(' · ') ||
                        'Barrier unknown'}
                    </span>
                    <small className="block">
                      {human(r.sif_label).replace(/^Sif/, 'SIF')} ·{' '}
                      {new Date(r.created_at).toLocaleDateString()}
                    </small>
                  </TableCell>
                  <TableCell>
                    <Badge value={r.status} />
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setSelected(r);
                        setError('');
                        setReason('');
                        setDecision('CONFIRM');
                      }}
                    >
                      Review
                      <ArrowRight size={14} />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {!visible.length && <Empty>No cases with this status.</Empty>}
        </Panel>
        {selected && (
          <Sheet
            open={Boolean(selected)}
            onOpenChange={(open) => !open && setSelected(null)}
          >
            <SheetContent className="review-drawer" showCloseButton={false}>
              <SheetTitle className="sr-only">
                Review {selected.report_id}
              </SheetTitle>
              <SheetDescription className="sr-only">
                Inspect the safety finding and record an HSE decision.
              </SheetDescription>
              <Panel
                title={selected.report_id}
                eyebrow="Record HSE decision"
                action={
                  <Button
                    variant="ghost"
                    aria-label="Close review"
                    onClick={() => setSelected(null)}
                  >
                    Close
                  </Button>
                }
              >
                <div className="review-form">
                  <Badge value={selected.priority} />
                  <p>{selected.description}</p>
                  <Link
                    className="text-link"
                    href={'/analyze?report=' + selected.report_id}
                  >
                    Inspect full evidence <ArrowUpRight size={15} />
                  </Link>
                  <ul className="reason-list">
                    {selected.review_reason.map((r: string) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                  <form onSubmit={save}>
                    <label className="full-label">
                      Reviewer <span>*</span>
                      <Input
                        required
                        maxLength={120}
                        value={reviewer}
                        onChange={(e) => setReviewer(e.target.value)}
                      />
                    </label>
                    <p className="footnote">
                      Local demo identity is self-reported and marked unverified
                      in the audit.
                    </p>
                    <label className="full-label">
                      Decision
                      <Picker
                        label="HSE decision"
                        value={decision}
                        onChange={setDecision}
                        options={[
                          'CONFIRM',
                          'DISAGREE',
                          'REQUEST_MORE_INFORMATION',
                          'ESCALATE',
                        ]}
                      />
                    </label>
                    <label className="full-label">
                      Reason / review notes{' '}
                      {decision === 'DISAGREE' && <span>*</span>}
                      <Textarea
                        required={decision === 'DISAGREE'}
                        value={reason}
                        maxLength={4000}
                        onChange={(e) => setReason(e.target.value)}
                        rows={4}
                      />
                    </label>
                    <Button size="lg" type="submit" disabled={busy}>
                      {busy ? (
                        <LoaderCircle className="spin" size={16} />
                      ) : (
                        <ClipboardCheck size={16} />
                      )}
                      Save decision
                    </Button>
                    {error && (
                      <p className="notice error" role="alert">
                        {error}
                      </p>
                    )}
                  </form>
                  {selected.decisions.length > 0 && (
                    <div className="history">
                      <h3>Decision history</h3>
                      {selected.decisions.map((d: any, i: number) => (
                        <div key={i}>
                          <strong>{human(d.decision)}</strong>
                          <p>
                            {d.reviewer} ·{' '}
                            {new Date(d.timestamp).toLocaleString()}
                          </p>
                          <p>{d.override_reason}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </Panel>
            </SheetContent>
          </Sheet>
        )}
      </div>
    </>
  );
}
