import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity, AlertTriangle, Bell, CalendarDays,
  Check, ChevronDown, ChevronRight, CircleHelp, ClipboardCheck, Clock3,
  Filter, LayoutDashboard, MapPin, Menu, MoreHorizontal, PackageCheck,
  Search, Settings2, ShieldCheck, Snowflake, Thermometer, Truck, Waves, X,
} from 'lucide-react';

const sample = {
  metrics: {
    active_shipments: 128,
    monitored_containers: 86,
    open_excursions: 7,
    compliance_rate: 98.6,
    total_readings: 284690,
    flagged_gaps: 3,
  },
  trend: [
    { date: '08:00', temperature: 4.1, humidity: 54 },
    { date: '10:00', temperature: 4.4, humidity: 57 },
    { date: '12:00', temperature: 4.2, humidity: 55 },
    { date: '14:00', temperature: 4.7, humidity: 61 },
    { date: '16:00', temperature: 4.3, humidity: 58 },
    { date: '18:00', temperature: 4.5, humidity: 56 },
    { date: '20:00', temperature: 4.1, humidity: 53 },
  ],
  recent_24h: {
    readings: 2840,
    sensors_reporting: 86,
    shipments_monitored: 128,
    average_temperature_c: 4.4,
    minimum_temperature_c: 1.6,
    maximum_temperature_c: 9.2,
    average_humidity_pct: 56.3,
    flagged_readings: 3,
    compliance_rate: 98.6,
    window_start: '2025-01-14T20:00:00Z',
    window_end: '2025-01-15T20:00:00Z',
    excursions: 4,
    data_gaps: 3,
    dataset_age_seconds: null,
  },
  severity_breakdown: [{ severity: 'Critical', count: 2 }, { severity: 'High', count: 2 }, { severity: 'Medium', count: 3 }],
  recent_excursions: [
    { id: 'EX-2048', shipment_id: 'SHP-8821', product_name: 'Oncology biologics', location: 'Rotterdam, NL', severity: 'Critical', status: 'Open', started_at: '2025-01-15T10:42:00Z', duration_minutes: 42, temperature_c: 9.2, threshold_min_c: 2, threshold_max_c: 8 },
    { id: 'EX-2047', shipment_id: 'SHP-8816', product_name: 'mRNA vaccine · Batch 04', location: 'Frankfurt, DE', severity: 'High', status: 'Investigating', started_at: '2025-01-15T09:18:00Z', duration_minutes: 86, temperature_c: 8.7, threshold_min_c: 2, threshold_max_c: 8 },
    { id: 'EX-2046', shipment_id: 'SHP-8809', product_name: 'Insulin glargine', location: 'Brussels, BE', severity: 'Medium', status: 'Open', started_at: '2025-01-15T08:54:00Z', duration_minutes: 18, temperature_c: 1.6, threshold_min_c: 2, threshold_max_c: 8 },
    { id: 'EX-2045', shipment_id: 'SHP-8792', product_name: 'Cell therapy · CTX-8', location: 'Paris, FR', severity: 'Medium', status: 'Monitoring', started_at: '2025-01-15T07:32:00Z', duration_minutes: 12, temperature_c: 8.3, threshold_min_c: 2, threshold_max_c: 8 },
  ],
  shipments: [
    { id: 'SHP-8821', product_name: 'Oncology biologics', origin: 'Basel, CH', destination: 'Rotterdam, NL', status: 'In transit', departed_at: '2025-01-14T06:00:00Z', eta: '2025-01-15T15:40:00Z', container_id: 'CN-0482', temperature_c: 9.2, humidity_pct: 58, excursion_count: 1 },
    { id: 'SHP-8816', product_name: 'mRNA vaccine · Batch 04', origin: 'Berlin, DE', destination: 'Frankfurt, DE', status: 'In transit', departed_at: '2025-01-15T05:30:00Z', eta: '2025-01-15T16:20:00Z', container_id: 'CN-0391', temperature_c: 4.8, humidity_pct: 55, excursion_count: 1 },
    { id: 'SHP-8809', product_name: 'Insulin glargine', origin: 'Copenhagen, DK', destination: 'Brussels, BE', status: 'In transit', departed_at: '2025-01-14T22:15:00Z', eta: '2025-01-15T19:00:00Z', container_id: 'CN-0267', temperature_c: 1.6, humidity_pct: 51, excursion_count: 1 },
  ],
  actions: [
    { id: 'CA-391', excursion_id: 'EX-2048', owner: 'Maya Patel', status: 'In progress', due_at: '2025-01-15T12:00:00Z', description: 'Verify reefer unit and transfer to backup container' },
    { id: 'CA-390', excursion_id: 'EX-2047', owner: 'Jonas Weber', status: 'Pending', due_at: '2025-01-15T13:30:00Z', description: 'Review sensor calibration and confirm product stability' },
  ],
};

const navItems = [
  { label: 'Overview', icon: LayoutDashboard },
  { label: 'Shipments', icon: Truck },
  { label: 'Containers', icon: PackageCheck },
  { label: 'Sensors', icon: Activity },
  { label: 'Excursions', icon: AlertTriangle },
  { label: 'Corrective actions', icon: ClipboardCheck },
];

const viewPaths = {
  Shipments: '/api/shipments',
  Containers: '/api/containers',
  Sensors: '/api/sensors',
  Excursions: '/api/excursions',
  'Corrective actions': '/api/actions',
  'Compliance center': '/api/compliance',
  Notifications: '/api/notifications',
};

const viewDescriptions = {
  Shipments: 'Shipment status, route, assigned container, and latest recorded conditions.',
  Containers: 'Container lifecycle, capacity, active shipment, and assigned sensor.',
  Sensors: 'Sensor calibration state, shipment assignment, and most recent reading.',
  Excursions: 'Temperature and humidity excursions with measured values and product limits.',
  'Corrective actions': 'Investigations and corrective-action status with shipment context.',
  'Compliance center': 'Effective product policies, monitored readings, exceptions, and calibration coverage.',
  Notifications: 'Operational notifications generated from shipment and excursion events.',
  Settings: 'CryoNexa environment and dataset configuration.',
};

const viewColumns = {
  Shipments: [
    ['id', 'Shipment'], ['product_name', 'Product'], ['origin', 'Origin'], ['destination', 'Destination'],
    ['status', 'Status'], ['container_id', 'Container'], ['temperature_c', 'Temperature (°C)'],
    ['humidity_pct', 'Humidity (%)'], ['eta', 'ETA'],
  ],
  Containers: [
    ['id', 'Container'], ['container_type', 'Type'], ['capacity_liters', 'Capacity (L)'],
    ['lifecycle_state', 'Lifecycle'], ['shipment_id', 'Shipment'], ['sensor_id', 'Sensor'],
  ],
  Sensors: [
    ['id', 'Sensor'], ['container_id', 'Container'], ['sensor_type', 'Type'],
    ['calibration_status', 'Calibration'], ['calibration_due_at', 'Calibration due'],
    ['shipment_id', 'Shipment'], ['last_reading_at', 'Last reading'],
  ],
  Excursions: [
    ['id', 'Excursion'], ['shipment_id', 'Shipment'], ['product_name', 'Product'], ['metric', 'Metric'],
    ['measured_value', 'Measurement'], ['severity', 'Severity'], ['status', 'Status'],
    ['duration_minutes', 'Duration (min)'], ['location', 'Location'], ['started_at', 'Started'],
  ],
  'Corrective actions': [
    ['id', 'Action'], ['excursion_id', 'Excursion'], ['shipment_id', 'Shipment'], ['owner', 'Owner'],
    ['status', 'Status'], ['due_at', 'Due'], ['description', 'Description'],
  ],
  'Compliance center': [
    ['product_name', 'Product'], ['min_temperature_c', 'Min temp (°C)'],
    ['max_temperature_c', 'Max temp (°C)'], ['min_humidity_pct', 'Min humidity (%)'],
    ['max_humidity_pct', 'Max humidity (%)'], ['permissible_excursion_minutes', 'Permissible excursion (min)'],
    ['shipment_count', 'Shipments'], ['reading_count', 'Readings'], ['flagged_readings', 'Flagged readings'],
    ['excursion_count', 'Excursions'],
  ],
  Notifications: [
    ['id', 'Notification'], ['recipient_role', 'Recipient'], ['shipment_id', 'Shipment'],
    ['excursion_id', 'Excursion'], ['message', 'Message'], ['created_at', 'Created'], ['acknowledged_at', 'Acknowledged'],
  ],
};

const viewFromHash = () => {
  const slug = window.location.hash.slice(1);
  return [...navItems.map(({ label }) => label), 'Compliance center', 'Settings', 'Notifications']
    .find((label) => label.toLowerCase().replace(/\s+/g, '-') === slug) ?? 'Overview';
};

const formatNumber = (value) => Number(value ?? 0).toLocaleString();
const formatDataAge = (ageSeconds) => {
  if (!Number.isFinite(ageSeconds)) return null;
  const isFuture = ageSeconds < 0;
  const elapsedSeconds = Math.abs(ageSeconds);
  if (elapsedSeconds < 60) return isFuture ? 'timestamp is in the future' : 'just now';
  if (elapsedSeconds < 3600) return `${Math.floor(elapsedSeconds / 60)}m ${isFuture ? 'ahead' : 'ago'}`;
  const hours = Math.floor(elapsedSeconds / 3600);
  if (hours < 24) return `${hours}h ${isFuture ? 'ahead' : 'ago'}`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h ${isFuture ? 'ahead' : 'ago'}`;
};
const dataAgeSeconds = (ageSeconds, recordedAt) => {
  if (Number.isFinite(ageSeconds)) return ageSeconds;
  const timestamp = Date.parse(recordedAt ?? '');
  return Number.isNaN(timestamp) ? null : Math.round((Date.now() - timestamp) / 1000);
};
const dateLabel = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};
const utcLabel = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : `${date.toLocaleDateString([], { month: 'short', day: 'numeric', timeZone: 'UTC' })} ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short' })}`;
};
const formatCell = (key, value, row) => {
  if (value == null || value === '') return '—';
  if (key === 'temperature_c' || key === 'measured_value') return `${value}${row.unit || '°C'}`;
  if (key === 'humidity_pct') return `${value}%`;
  if (key.includes('_at') || key === 'eta') return new Date(value).toLocaleString();
  return typeof value === 'number' ? formatNumber(value) : String(value).replaceAll('_', ' ');
};

function App() {
  const [dashboard, setDashboard] = useState(null);
  const [source, setSource] = useState('loading');
  const [error, setError] = useState('');
  const [activeView, setActiveView] = useState(viewFromHash);
  const [viewRecords, setViewRecords] = useState([]);
  const [viewCount, setViewCount] = useState(0);
  const [viewLoading, setViewLoading] = useState(false);
  const [viewError, setViewError] = useState('');
  const [viewPage, setViewPage] = useState(0);
  const [viewRefresh, setViewRefresh] = useState(0);
  const [viewQuery, setViewQuery] = useState('');
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [query, setQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState('All severity');
  const [mobileNav, setMobileNav] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [actionError, setActionError] = useState('');
  const [actionNotice, setActionNotice] = useState('');
  const [transitioningAction, setTransitioningAction] = useState('');
  const searchInput = useRef(null);

  function navigate(view) {
    setActiveView(view);
    setViewPage(0);
    setViewQuery('');
    setSelectedRecord(null);
    const slug = view === 'Overview' ? '' : `#${view.toLowerCase().replace(/\s+/g, '-')}`;
    if (window.location.hash !== slug) window.history.pushState(null, '', slug || window.location.pathname);
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function refreshData() {
    loadDashboard(true);
    if (viewPaths[activeView]) setViewRefresh((value) => value + 1);
  }

  async function loadDashboard(isRefresh = false) {
    if (isRefresh) setRefreshing(true);
    setError('');
    try {
      const response = await fetch('/api/dashboard', { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`Dashboard request failed (${response.status})`);
      const data = await response.json();
      if (!data || !data.metrics) throw new Error('Dashboard response is missing metrics');
      setDashboard(data);
      setSource('live');
    } catch (requestError) {
      setDashboard(sample);
      setSource('demo');
      setError(requestError.message || 'The API could not be reached.');
    } finally {
      setRefreshing(false);
    }
  }

  async function transitionAction(action) {
    const status = action.status === 'open' ? 'in_progress' : 'completed';
    setTransitioningAction(action.id);
    setActionError('');
    setActionNotice('');
    try {
      const response = await fetch(`/api/actions/${encodeURIComponent(action.id)}`, {
        method: 'PATCH',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, actor: 'quality_engineer' }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || `Action update failed (${response.status})`);
      }
      const result = await response.json();
      setActionNotice(`Action ${action.id} marked ${result.status.replace('_', ' ')}. History event recorded.`);
      await loadDashboard(true);
      if (activeView === 'Corrective actions') {
        const response = await fetch(`/api/actions?limit=25&offset=${viewPage * 25}`, { headers: { Accept: 'application/json' } });
        if (!response.ok) throw new Error(`Corrective actions request failed (${response.status})`);
        const result = await response.json();
        setViewRecords(result.items);
      }
    } catch (requestError) {
      setActionError(requestError.message || 'The corrective action could not be updated.');
    } finally {
      setTransitioningAction('');
    }
  }

  useEffect(() => { loadDashboard(); }, []);

  useEffect(() => {
    const syncView = () => {
      setActiveView(viewFromHash());
      setViewPage(0);
      setSelectedRecord(null);
    };
    window.addEventListener('popstate', syncView);
    window.addEventListener('hashchange', syncView);
    return () => {
      window.removeEventListener('popstate', syncView);
      window.removeEventListener('hashchange', syncView);
    };
  }, []);

  useEffect(() => {
    const endpoint = viewPaths[activeView];
    if (!endpoint) {
      setViewRecords([]);
      setViewCount(0);
      setViewError('');
      return undefined;
    }

    const controller = new AbortController();
    async function loadView() {
      setViewLoading(true);
      setViewError('');
      try {
        const url = activeView === 'Compliance center'
          ? endpoint
          : `${endpoint}?limit=25&offset=${viewPage * 25}`;
        const response = await fetch(url, { headers: { Accept: 'application/json' }, signal: controller.signal });
        if (!response.ok) throw new Error(`${activeView} request failed (${response.status})`);
        const result = await response.json();
        if (!Array.isArray(result.items) || !Number.isFinite(result.count)) {
          throw new Error(`${activeView} response has an invalid list shape`);
        }
        setViewRecords(result.items);
        setViewCount(result.count);
      } catch (requestError) {
        if (requestError.name !== 'AbortError') {
          setViewError(requestError.message || `Could not load ${activeView.toLowerCase()}.`);
          setViewRecords([]);
          setViewCount(0);
        }
      } finally {
        if (!controller.signal.aborted) setViewLoading(false);
      }
    }
    loadView();
    return () => controller.abort();
  }, [activeView, viewPage, viewRefresh]);

  useEffect(() => {
    if (activeView === 'Excursions') searchInput.current?.focus();
  }, [activeView]);

  useEffect(() => {
    const handleShortcut = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        navigate('Excursions');
      }
    };
    window.addEventListener('keydown', handleShortcut);
    return () => window.removeEventListener('keydown', handleShortcut);
  }, []);

  const excursions = dashboard?.recent_excursions ?? [];
  const filteredExcursions = useMemo(() => excursions.filter((item) => {
    const matchesText = `${item.id} ${item.shipment_id} ${item.product_name} ${item.location}`.toLowerCase().includes(query.toLowerCase());
    const matchesSeverity = severityFilter === 'All severity' || item.severity?.toLowerCase() === severityFilter.toLowerCase();
    return matchesText && matchesSeverity;
  }), [excursions, query, severityFilter]);
  const metrics = dashboard?.metrics ?? {};
  const recent24h = dashboard?.recent_24h ?? {};
  const datasetAge = source === 'live'
    ? formatDataAge(dataAgeSeconds(recent24h.dataset_age_seconds, recent24h.window_end))
    : null;
  const latestTrend = dashboard?.trend?.[dashboard.trend.length - 1];
  const criticalCount = dashboard?.severity_breakdown?.find((item) => item.severity?.toLowerCase() === 'critical')?.count ?? 0;

  return (
    <div className="app-shell">
      {mobileNav && <button className="mobile-backdrop" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
      <aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
        <div className="brand">
          <div className="brand-mark"><Snowflake size={20} strokeWidth={2.2} /></div>
          <div><span className="brand-name">cryonexa</span><span className="brand-caption">COLD CHAIN INTELLIGENCE</span></div>
          <button className="icon-btn sidebar-close" aria-label="Close menu" onClick={() => setMobileNav(false)}><X size={18} /></button>
        </div>
        <div className="workspace-select">
          <div className="workspace-avatar">NC</div>
          <div className="workspace-copy"><strong>CryoNexa Operations</strong><span>Cold chain workspace</span></div>
        </div>
        <div className="nav-section-label">WORKSPACE</div>
        <nav className="main-nav" aria-label="Main navigation">
          {navItems.map(({ label, icon: Icon }) => {
            const count = label === 'Shipments' ? metrics.active_shipments
              : label === 'Excursions' ? metrics.open_excursions : null;
            return (
            <button key={label} className={`nav-item ${activeView === label ? 'nav-active' : ''}`} onClick={() => navigate(label)} aria-current={activeView === label ? 'page' : undefined}>
              <Icon size={17} strokeWidth={1.8} /><span>{label}</span>{count != null && <span className={`nav-count ${label === 'Excursions' ? 'nav-count-alert' : ''}`}>{formatNumber(count)}</span>}
            </button>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="compliance-promo">
            <div className="promo-icon"><ShieldCheck size={18} /></div>
            <strong>Compliance center</strong>
            <p>Product limits, sensor quality, and custody are monitored.</p>
            <button onClick={() => navigate('Compliance center')}>View compliance <ChevronRight size={14} /></button>
          </div>
          <button className={`nav-item ${activeView === 'Settings' ? 'nav-active' : ''}`} onClick={() => navigate('Settings')} aria-current={activeView === 'Settings' ? 'page' : undefined}><Settings2 size={17} /><span>Settings</span></button>
          <div className="user-profile">
            <div className="user-avatar">AM</div>
            <div className="workspace-copy"><strong>Plant operator</strong><span>Operations team</span></div>
            <MoreHorizontal size={18} />
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <button className="icon-btn menu-toggle" aria-label="Open menu" onClick={() => setMobileNav(true)}><Menu size={20} /></button>
          <div className="breadcrumbs"><button onClick={() => navigate('Overview')}>Operations</button><ChevronRight size={14} /><strong>{activeView}</strong></div>
          <div className="topbar-right">
            <div className="system-status"><span className="status-dot" /> {metrics.open_excursions ? 'Exceptions need review' : 'Monitoring active'}</div>
            <button className="icon-btn top-icon" aria-label="Search excursions" onClick={() => navigate('Excursions')}><Search size={18} /></button>
            <button className="icon-btn top-icon notification-button" aria-label="Notifications" onClick={() => navigate('Notifications')}><Bell size={18} /><i /></button>
            <div className="top-divider" />
            <div className="top-date"><CalendarDays size={15} /><span>{new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}</span></div>
          </div>
        </header>

        <div className="content">
          <section className="page-heading">
            <div>
              <div className="eyebrow"><span className="eyebrow-line" /> COLD-CHAIN OPERATIONS</div>
              <h1>{activeView === 'Overview' ? <>Cold chain overview <span className="wave">✦</span></> : activeView}</h1>
              <p>{activeView === 'Overview' ? 'Shipment conditions, excursions, and actions across your monitored journeys.' : viewDescriptions[activeView]}</p>
            </div>
            {activeView !== 'Settings' && <div className="heading-actions">
              <button className="button button-secondary" onClick={refreshData} disabled={refreshing || viewLoading}>
                <Activity size={16} className={refreshing ? 'spin' : ''} /> {refreshing ? 'Refreshing' : 'Refresh data'}
              </button>
            </div>}
          </section>

          {source === 'loading' && <div className="data-banner loading-banner"><span className="spinner" /> Connecting to your monitoring network…</div>}
          {source === 'demo' && <div className="data-banner demo-banner"><div><CircleHelp size={17} /><span><strong>Demo data</strong> — live monitoring API is unavailable{error ? ` (${error})` : ''}. Showing sample operational data, not live readings.</span></div><button onClick={() => loadDashboard(true)}>Retry connection <ChevronRight size={14} /></button></div>}
          {source === 'live' && <div className="live-indicator"><span className="status-dot" /> API connected <span className="live-separator">·</span> Synthetic dataset, not a live sensor feed</div>}

          {activeView === 'Overview' ? <>
          <section className="recent-window" aria-label="Latest 24 hour summary">
            <div className="recent-window-heading">
              <div className="recent-window-title"><span className="window-kicker"><Clock3 size={13} /> LATEST 24-HOUR WINDOW</span><strong>{utcLabel(recent24h.window_start)} – {utcLabel(recent24h.window_end)}</strong>{datasetAge && <span className="dataset-age"><Clock3 size={12} /> Latest reading {utcLabel(recent24h.window_end)} · {datasetAge}</span>}</div>
              <span className="synthetic-tag">SIMULATED READINGS</span>
            </div>
            <div className="recent-window-metrics">
              <SnapshotMetric label="Readings" value={formatNumber(recent24h.readings)} detail="in selected window" icon={Activity} />
              <SnapshotMetric label="Sensors reporting" value={formatNumber(recent24h.sensors_reporting)} detail={`${formatNumber(recent24h.shipments_monitored)} journeys`} icon={PackageCheck} />
              <SnapshotMetric label="Average temperature" value={recent24h.average_temperature_c == null ? '—' : `${recent24h.average_temperature_c}°C`} detail={recent24h.minimum_temperature_c == null ? 'No readings' : `${recent24h.minimum_temperature_c}°C to ${recent24h.maximum_temperature_c}°C`} icon={Thermometer} />
              <SnapshotMetric label="Average humidity" value={recent24h.average_humidity_pct == null ? '—' : `${recent24h.average_humidity_pct}%`} detail={`${formatNumber(recent24h.flagged_readings)} ${recent24h.flagged_readings === 1 ? 'flag' : 'flags'} · ${formatNumber(recent24h.data_gaps)} ${recent24h.data_gaps === 1 ? 'gap' : 'gaps'}`} icon={Waves} />
              <SnapshotMetric label="Excursions" value={formatNumber(recent24h.excursions)} detail={`${recent24h.compliance_rate ?? '—'}% in product range`} icon={AlertTriangle} />
            </div>
            <p className="window-explainer">Window is anchored to the newest available recorded reading. Averages combine product journeys; use each shipment’s policy range to assess its readings.</p>
          </section>
          <section className="metrics-grid" aria-label="Operational metrics">
            <MetricCard title="Active shipments" value={formatNumber(metrics.active_shipments)} icon={Truck} color="blue" detail="Currently in transit" loading={source === 'loading'} onClick={() => navigate('Shipments')} />
            <MetricCard title="Monitored containers" value={formatNumber(metrics.monitored_containers)} icon={PackageCheck} color="teal" detail="Assigned to active shipments" loading={source === 'loading'} onClick={() => navigate('Containers')} />
            <MetricCard title="Open excursions" value={formatNumber(metrics.open_excursions)} icon={AlertTriangle} color="amber" detail={`${criticalCount} critical · require review`} loading={source === 'loading'} onClick={() => navigate('Excursions')} />
            <MetricCard title="Condition compliance" value={`${metrics.compliance_rate ?? '—'}%`} icon={ShieldCheck} color="green" detail="Readings within product policies" loading={source === 'loading'} onClick={() => navigate('Compliance center')} />
          </section>

          <section className="analytics-grid">
            <article className="panel trend-panel">
              <div className="panel-header">
                <div><div className="panel-title-row"><h2>Temperature & humidity</h2><span className="live-tag"><i /> HOURLY</span></div><p>Average readings across all journeys in the selected window</p></div>
                <div className="chart-actions"><span className="select-button">Last 24 hours</span></div>
              </div>
              <div className="chart-legend"><span><i className="legend-temp" /> Temperature <b>{latestTrend?.temperature ?? '—'}°C</b></span><span><i className="legend-humidity" /> Humidity <b>{latestTrend?.humidity ?? '—'}%</b></span><span className="threshold-note"><ShieldCheck size={12} /> Policy limits vary by product</span></div>
              <div className="chart-wrap">
                {dashboard?.trend?.length
                  ? <TrendChart data={dashboard.trend} />
                  : <EmptyState text="Temperature and humidity trends will appear when readings are available." />}
              </div>
              <div className="chart-footnote"><span><Waves size={14} /> {formatNumber(recent24h.readings)} readings · hourly averages</span><span><Clock3 size={13} /> Through {utcLabel(recent24h.window_end)}</span></div>
            </article>
            <article className="panel excursion-panel">
              <div className="panel-header">
                <div><h2>Excursion overview</h2><p>Open exceptions by severity</p></div>
              </div>
              <div className="severity-total"><strong>{formatNumber(metrics.open_excursions)}</strong><span>open excursions</span><span className="severity-period">by severity</span></div>
              <div className="severity-bars">
                {['Critical', 'High', 'Medium'].map((level) => {
                  const rows = dashboard?.severity_breakdown ?? [];
                  const count = rows.find((item) => item.severity?.toLowerCase() === level.toLowerCase())?.count ?? 0;
                  const max = Math.max(1, ...rows.map((item) => item.count ?? 0));
                  return <div className="severity-row" key={level}><div className="severity-label"><span className={`severity-dot ${level.toLowerCase()}`} />{level}<b>{count}</b></div><div className="severity-track"><span className={`severity-fill ${level.toLowerCase()}`} style={{ width: `${Math.max(count ? 9 : 0, (count / max) * 100)}%` }} /></div></div>;
                })}
              </div>
              <div className="excursion-divider" />
              <div className="small-stat-row"><span><span className="tiny-indicator red" /> Flagged data gaps</span><strong>{formatNumber(metrics.flagged_gaps)}</strong></div>
              <div className="small-stat-row"><span><span className="tiny-indicator green" /> Within safe range</span><strong>{metrics.compliance_rate ?? '—'}%</strong></div>
              <button className="text-link" onClick={() => navigate('Excursions')}>View excursion report <ChevronRight size={15} /></button>
            </article>
          </section>

          <section className="bottom-grid">
            <article className="panel exceptions-panel">
              <div className="panel-header exceptions-header">
                <div><div className="panel-title-row"><h2>Recent excursions</h2><span className="table-count">{excursions.length}</span></div><p>Temperature and humidity events requiring attention</p></div>
                <button className="text-link desktop-link" onClick={() => navigate('Excursions')}>View all excursions <ChevronRight size={15} /></button>
              </div>
              <div className="table-toolbar">
                <label className="search-field"><Search size={15} /><input ref={searchInput} placeholder="Search shipments, products..." value={query} onChange={(event) => setQuery(event.target.value)} /><kbd>⌘ K</kbd></label>
                <label className="filter-select"><Filter size={14} /><select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}><option>All severity</option><option>Critical</option><option>High</option><option>Medium</option></select><ChevronDown size={13} /></label>
                <button className="icon-btn filter-button" aria-label="Clear excursion filters" onClick={() => { setQuery(''); setSeverityFilter('All severity'); }}><X size={16} /></button>
              </div>
              <div className="table-scroll">
                <table>
                  <thead><tr><th>SHIPMENT / PRODUCT</th><th>LOCATION</th><th>SEVERITY</th><th>MEASUREMENT</th><th>DURATION</th><th>STATUS</th><th /></tr></thead>
                  <tbody>
                    {filteredExcursions.map((item) => <tr key={item.id}>
                      <td><div className="shipment-cell"><span className={`product-icon ${item.severity?.toLowerCase()}`}>{item.metric === 'humidity' ? <Waves size={15} /> : <Thermometer size={15} />}</span><span><strong>{item.shipment_id}</strong><small>{item.product_name}</small></span></div></td>
                      <td><div className="location-cell"><MapPin size={13} />{item.location || '—'}</div></td>
                      <td><span className={`severity-badge ${item.severity?.toLowerCase()}`}>{item.severity}</span></td>
                      <td><span className={`temp-reading ${isOutOfRange(item) ? 'temp-alert' : ''}`}>{measurementValue(item) ?? '—'} {measurementUnit(item)}</span><small className="threshold">{item.threshold_min ?? item.threshold_min_c ?? '—'}–{item.threshold_max ?? item.threshold_max_c ?? '—'} {measurementUnit(item)} product range</small></td>
                      <td><span className="duration-cell"><Clock3 size={13} />{formatDuration(item.duration_minutes)}</span></td>
                      <td><span className={`status-badge ${item.status?.toLowerCase().replace(/\s/g, '-')}`}>{item.status}</span></td>
                      <td><button className="row-action" aria-label={`Open ${item.id}`} onClick={() => setSelectedRecord({ title: item.id, record: item, view: 'Excursions' })}><ChevronRight size={16} /></button></td>
                    </tr>)}
                    {!filteredExcursions.length && <tr><td colSpan="7"><EmptyState text={excursions.length ? 'No excursions match these filters.' : 'No excursions to display. Shipments are within their configured limits.'} /></td></tr>}
                  </tbody>
                </table>
              </div>
              <div className="table-footer"><span>Showing <strong>{filteredExcursions.length}</strong> of <strong>{excursions.length}</strong> recent excursions</span><button className="text-link mobile-link" onClick={() => navigate('Excursions')}>View all <ChevronRight size={14} /></button><div className="pagination"><span>Recent</span></div></div>
            </article>
            <aside className="panel action-panel">
              <div className="panel-header action-heading"><div><h2>Action required</h2><p>Keep your shipments on track</p></div><span className="action-count">{dashboard?.actions?.length ?? 0}</span></div>
              <div className="action-list">
                {(dashboard?.actions ?? []).slice(0, 3).map((action) => {
                  const related = excursions.find((event) => event.id === action.excursion_id);
                  return <div className="action-item" key={action.id}>
                    <div className={`action-check ${action.status?.toLowerCase().replace(/\s/g, '-')}`}><Check size={13} /></div>
                    <div className="action-copy"><div className="action-meta"><strong>{action.excursion_id}</strong><span>{action.status}</span></div><p>{action.description}</p><div className="action-assignee"><span className="mini-avatar">{(action.owner || 'NA').split(' ').map((part) => part[0]).join('').slice(0, 2)}</span><span>{action.owner || 'Unassigned'}</span><i /> <Clock3 size={12} /> Due {dateLabel(action.due_at)}{related && <span className="action-temp">{measurementValue(related)} {measurementUnit(related)}</span>}</div>
                      {['open', 'in_progress'].includes(action.status) && <button className="action-transition" disabled={source !== 'live' || transitioningAction === action.id} onClick={() => transitionAction(action)}>{transitioningAction === action.id ? 'Saving…' : action.status === 'open' ? 'Start investigation' : 'Complete action'}</button>}
                    </div>
                  </div>;
                })}
                {!(dashboard?.actions ?? []).length && <EmptyState text="No corrective actions are currently assigned." />}
              </div>
              {actionError && <p className="action-error" role="alert">{actionError}</p>}
              {actionNotice && <p className="action-notice" role="status">{actionNotice}</p>}
              <div className="action-footer"><span><span className="status-dot" /> Updates are recorded in action history</span><button aria-label="View corrective actions" onClick={() => navigate('Corrective actions')}><CircleHelp size={14} /></button></div>
            </aside>
          </section>

          <section className="route-strip panel">
            <div className="route-title"><div className="route-icon"><Truck size={17} /></div><div><h2>Shipments in transit</h2><p>Latest route and container status</p></div></div>
            <div className="route-list">
              {(dashboard?.shipments ?? []).slice(0, 3).map((shipment) => <div className="route-item" key={shipment.id}>
                <div className="route-item-main"><strong>{shipment.id}</strong><span>{shipment.product_name}</span></div>
                <div className="route-path"><span>{shipment.origin}</span><span className="route-line"><i /><i /><i /></span><span>{shipment.destination}</span></div>
                <div className="route-conditions"><span className={isOutOfRange(shipment) ? 'condition-warn' : ''}><Thermometer size={13} />{shipment.temperature_c}°C</span><span><Waves size={13} />{shipment.humidity_pct}%</span></div>
                <div className="route-eta"><small>ETA</small><strong>{dateLabel(shipment.eta)}</strong></div>
                <span className={`route-status ${shipment.status?.toLowerCase().replace(/\s/g, '-')}`}><i />{shipment.status}</span>
                <button className="row-action" aria-label={`Open shipment ${shipment.id}`} onClick={() => setSelectedRecord({ title: shipment.id, record: shipment, view: 'Shipments' })}><ChevronRight size={16} /></button>
              </div>)}
              {!(dashboard?.shipments ?? []).length && <EmptyState text="No shipments are currently in transit." />}
            </div>
            <button className="all-shipments" onClick={() => navigate('Shipments')}>View all shipments <ChevronRight size={14} /></button>
          </section>
          </> : (
            <DataView
              view={activeView}
              records={viewRecords}
              count={viewCount}
              loading={viewLoading}
              error={viewError}
              page={viewPage}
              query={viewQuery}
              searchRef={searchInput}
              onQueryChange={(value) => { setViewQuery(value); setViewPage(0); }}
              onPageChange={setViewPage}
              onSelect={(record) => setSelectedRecord({ title: record.id || record.product_name || activeView, record, view: activeView })}
              onNavigate={navigate}
              onTransitionAction={transitionAction}
              transitioningAction={transitioningAction}
              actionError={actionError}
              actionNotice={actionNotice}
            />
          )}
          <footer className="page-footer"><span>© 2026 CryoNexa · Cold-chain operations</span><span><span className={`footer-dot ${source}`} />{source === 'live' ? 'API connected' : source === 'demo' ? 'Demo data mode' : 'Connecting'}<span className="footer-divider" />v1.0.0</span></footer>
        </div>
      </main>
      {selectedRecord && <RecordDialog title={selectedRecord.title} record={selectedRecord.record} view={selectedRecord.view} onClose={() => setSelectedRecord(null)} />}
    </div>
  );
}

function MetricCard({ title, value, icon: Icon, color, detail, loading, onClick }) {
  return <button className="metric-card metric-card-button" onClick={onClick}><div className="metric-top"><span>{title}</span><span className={`metric-icon ${color}`}><Icon size={17} /></span></div><div className={`metric-value ${loading ? 'skeleton-text' : ''}`}>{loading ? '—' : value}</div><div className="metric-change"><span>{detail}</span></div></button>;
}

function DataView({ view, records, count, loading, error, page, query, searchRef, onQueryChange, onPageChange, onSelect, onNavigate, onTransitionAction, transitioningAction, actionError, actionNotice }) {
  const columns = viewColumns[view] ?? [];
  const [severityFilter, setSeverityFilter] = useState('All severity');
  const filtered = useMemo(() => records.filter((row) => {
    const matchesText = JSON.stringify(row).toLowerCase().includes(query.toLowerCase());
    const matchesSeverity = view !== 'Excursions' || severityFilter === 'All severity'
      || row.severity?.toLowerCase() === severityFilter.toLowerCase();
    return matchesText && matchesSeverity;
  }), [records, query, severityFilter, view]);
  const pages = Math.max(1, Math.ceil(count / 25));
  const settings = view === 'Settings';
  return (
    <section className="panel data-view" aria-label={`${view} data`}>
      {settings ? (
        <div className="settings-grid">
          <article><span>Frontend</span><strong>React + Vite</strong><small>Dashboard interface</small></article>
          <article><span>Operations API</span><strong>FastAPI</strong><small>Local endpoint: /api</small></article>
          <article><span>Operational database</span><strong>SQLite</strong><small>Generated local dataset</small></article>
          <article><span>Generation seed</span><strong>20261022</strong><small>Deterministic synthetic data</small></article>
          <article><span>Sampling interval</span><strong>5 minutes</strong><small>Temperature and humidity readings</small></article>
          <article><span>Data provenance</span><strong>Synthetic only</strong><small>No external or personal data sources</small></article>
          <button className="button button-secondary settings-link" onClick={() => onNavigate('Compliance center')}>Review product policies <ChevronRight size={14} /></button>
        </div>
      ) : (
        <>
          {view === 'Compliance center' && <div className="compliance-summary"><span><ShieldCheck size={17} /> Current effective product policies</span><span>{count} products covered</span></div>}
          <div className="data-toolbar">
            <label className="search-field"><Search size={15} /><input ref={view === 'Excursions' ? searchRef : undefined} placeholder={`Search ${view.toLowerCase()} on this page...`} value={query} onChange={(event) => onQueryChange(event.target.value)} /><kbd>⌕</kbd></label>
            {view === 'Excursions' && <label className="filter-select"><Filter size={14} /><select aria-label="Filter excursion severity" value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}><option>All severity</option><option>Critical</option><option>High</option><option>Medium</option></select><ChevronDown size={13} /></label>}
            <span className="data-count">{loading ? 'Loading…' : `${formatNumber(count)} records`}</span>
          </div>
          {error && <div className="data-error" role="alert">{error}</div>}
          {view === 'Corrective actions' && actionError && <div className="data-error" role="alert">{actionError}</div>}
          {view === 'Corrective actions' && actionNotice && <div className="action-notice" role="status">{actionNotice}</div>}
          <div className="table-scroll">
            <table className="records-table">
              <thead><tr>{columns.map(([key, label]) => <th key={key}>{label}</th>)}<th>Details</th>{view === 'Corrective actions' && <th>Update</th>}</tr></thead>
              <tbody>
                {!loading && !error && filtered.map((record, index) => (
                  <tr key={record.id ?? `${record.product_id}-${record.policy_id ?? index}`}>
                    {columns.map(([key]) => <td key={key}>{key === columns[0][0]
                      ? <button className="record-link" onClick={() => onSelect(record)}>{formatCell(key, record[key], record)}</button>
                      : formatCell(key, record[key], record)}</td>)}
                    <td><button className="row-action" aria-label={`View details for ${record.id ?? record.product_name}`} onClick={() => onSelect(record)}><ChevronRight size={16} /></button></td>
                    {view === 'Corrective actions' && <td>{['open', 'in_progress'].includes(record.status)
                      ? <button className="action-transition" disabled={transitioningAction === record.id} onClick={() => onTransitionAction(record)}>{transitioningAction === record.id ? 'Saving…' : record.status === 'open' ? 'Start investigation' : 'Complete action'}</button>
                      : <span className="status-badge completed">Completed</span>}</td>}
                  </tr>
                ))}
                {!loading && !error && !filtered.length && <tr><td colSpan={columns.length + (view === 'Corrective actions' ? 3 : 2)}><EmptyState text={records.length ? 'No records on this page match your search.' : `No ${view.toLowerCase()} records are available.`} /></td></tr>}
              </tbody>
            </table>
          </div>
          {view !== 'Compliance center' && <div className="table-footer">
            <span>Showing <strong>{count ? page * 25 + 1 : 0}–{Math.min((page + 1) * 25, count)}</strong> of <strong>{formatNumber(count)}</strong> {view.toLowerCase()}</span>
            <div className="pagination">
              <button disabled={page === 0 || loading} aria-label="Previous page" onClick={() => onPageChange(page - 1)}><ChevronRight className="chevron-left" size={14} /></button>
              <span>{page + 1} / {pages}</span>
              <button disabled={page + 1 >= pages || loading} aria-label="Next page" onClick={() => onPageChange(page + 1)}><ChevronRight size={14} /></button>
            </div>
          </div>}
        </>
      )}
    </section>
  );
}

function ContainerMonitoring({ data, error, loading, offset, onOffsetChange }) {
  if (loading && !data) return <div className="container-monitoring-loading"><span className="spinner" /> Loading container readings…</div>;
  if (error) return <div className="data-error" role="alert">{error}</div>;
  if (!data) return null;

  const readings = [...data.readings].reverse();
  const latest = data.readings[0];
  const hasOlder = offset + data.reading_limit < data.reading_count;
  const excursions = data.excursions;

  return (
    <div className="container-monitoring">
      <div className="container-monitoring-heading">
        <div><h3>Sensor history</h3><span>{data.container.sensor_id || 'No sensor assigned'} · {formatNumber(data.reading_count)} total readings</span></div>
        {latest && <span className={`quality-pill ${latest.quality_status}`}>{latest.quality_status.replaceAll('_', ' ')}</span>}
      </div>
      {data.container.sensor_id && readings.length > 0 ? <>
        <div className="monitoring-window">Temperature and humidity by recorded interval · Threshold band reflects the policy applied to each reading</div>
        <MetricTrendChart readings={readings} metric="temperature_c" label="Temperature" unit="°C" minKey="min_temperature_c" maxKey="max_temperature_c" />
        <MetricTrendChart readings={readings} metric="humidity_pct" label="Humidity" unit="%RH" minKey="min_humidity_pct" maxKey="max_humidity_pct" />
        <div className="reading-table-heading">
          <strong>Recent reading history</strong>
          <span>Showing {data.readings.length ? offset + 1 : 0}–{Math.min(offset + data.readings.length, data.reading_count)} of {formatNumber(data.reading_count)}</span>
        </div>
        <div className="table-scroll reading-table-scroll">
          <table className="reading-table">
            <thead><tr><th>Recorded</th><th>Shipment / product</th><th>Temperature</th><th>Humidity</th><th>Quality</th><th>Route stop</th></tr></thead>
            <tbody>{data.readings.slice(0, 25).map((reading) => <tr key={reading.id}>
              <td>{new Date(reading.recorded_at).toLocaleString()}</td>
              <td><span>{reading.shipment_id}</span><small>{reading.product_name}</small></td>
              <td className={reading.temperature_c < reading.min_temperature_c || reading.temperature_c > reading.max_temperature_c ? 'reading-outside' : ''}>
                {reading.temperature_c} °C <small>{reading.min_temperature_c}–{reading.max_temperature_c} °C</small>
              </td>
              <td className={reading.humidity_pct < reading.min_humidity_pct || reading.humidity_pct > reading.max_humidity_pct ? 'reading-outside' : ''}>
                {reading.humidity_pct} %RH <small>{reading.min_humidity_pct}–{reading.max_humidity_pct} %RH</small>
              </td>
              <td><span className={`quality-pill ${reading.quality_status}`}>{reading.quality_status.replaceAll('_', ' ')}</span></td>
              <td>{reading.location || '—'}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <div className="reading-history-pagination">
          <button className="button button-secondary" disabled={offset === 0 || loading} onClick={() => onOffsetChange(Math.max(0, offset - data.reading_limit))}>Newer readings</button>
          <span>{offset === 0 ? 'Latest readings' : `Older readings · offset ${offset}`}</span>
          <button className="button button-secondary" disabled={!hasOlder || loading} onClick={() => onOffsetChange(offset + data.reading_limit)}>Older readings</button>
        </div>
      </> : <EmptyState text="No sensor readings are available for this container." />}

      <div className="container-excursions">
        <div className="reading-table-heading"><strong>Excursion history</strong><span>{excursions.length} events</span></div>
        {excursions.length ? <div className="table-scroll reading-table-scroll">
          <table className="reading-table">
            <thead><tr><th>Excursion</th><th>Shipment / product</th><th>Metric / observed range</th><th>Duration</th><th>Severity / status</th></tr></thead>
            <tbody>{excursions.map((excursion) => {
              const isTemperature = excursion.metric === 'temperature';
              const minimum = isTemperature ? excursion.min_temperature_c : excursion.min_humidity_pct;
              const maximum = isTemperature ? excursion.max_temperature_c : excursion.max_humidity_pct;
              return <tr key={excursion.id}>
                <td><strong>{excursion.id}</strong><small>{new Date(excursion.started_at).toLocaleString()}</small></td>
                <td><span>{excursion.shipment_id}</span><small>{excursion.product_name}</small></td>
                <td>{excursion.min_value}–{excursion.max_value} {excursion.unit}<small>Policy range: {minimum}–{maximum} {excursion.unit}</small></td>
                <td>{excursion.duration_minutes} min{excursion.reported_duration_minutes != null && excursion.reported_duration_minutes !== excursion.duration_minutes && <small>Reported: {excursion.reported_duration_minutes} min</small>}</td>
                <td><span className={`severity-badge ${excursion.severity}`}>{excursion.severity}</span><small>{excursion.status.replaceAll('_', ' ')}</small></td>
              </tr>;
            })}</tbody>
          </table>
        </div> : <EmptyState text="No excursions have been recorded for this container." />}
      </div>
    </div>
  );
}

function MetricTrendChart({ readings, metric, label, unit, minKey, maxKey }) {
  const width = 800;
  const height = 190;
  const left = 43;
  const right = 18;
  const top = 14;
  const bottom = 31;
  const values = readings.map((reading) => Number(reading[metric])).filter(Number.isFinite);
  if (!values.length) return null;
  const policyBounds = readings.flatMap((reading) => [Number(reading[minKey]), Number(reading[maxKey])]).filter(Number.isFinite);
  const minValue = Math.min(...values, ...policyBounds);
  const maxValue = Math.max(...values, ...policyBounds);
  const padding = Math.max((maxValue - minValue) * 0.1, 0.5);
  const chartMin = minValue - padding;
  const chartMax = maxValue + padding;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const x = (index) => left + (readings.length < 2 ? plotWidth / 2 : index * plotWidth / (readings.length - 1));
  const y = (value) => top + (chartMax - Number(value)) * plotHeight / (chartMax - chartMin);
  const line = readings.map((reading, index) => `${x(index)},${y(reading[metric])}`).join(' ');
  const upper = readings.map((reading, index) => `${x(index)},${y(reading[maxKey])}`);
  const lower = readings.map((reading, index) => `${x(index)},${y(reading[minKey])}`).reverse();
  const band = [...upper, ...lower].join(' ');
  const ticks = [...new Set([0, Math.floor((readings.length - 1) / 2), readings.length - 1])];

  return <section className="metric-history-chart" aria-label={`${label} history chart`}>
    <div className="metric-history-title"><strong>{label}</strong><span>{readings.at(-1)?.[metric]} {unit} latest</span></div>
    <div className="metric-history-legend"><span><i className="measured-key" />Measured</span><span><i className="policy-key" />Allowed product threshold</span><span><i className="excursion-key" />Out of policy</span></div>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label} sensor readings with product-specific threshold band`}>
      {[0, 0.5, 1].map((fraction) => {
        const gridY = top + fraction * plotHeight;
        const value = chartMax - fraction * (chartMax - chartMin);
        return <g key={fraction}>
          <line x1={left} y1={gridY} x2={width - right} y2={gridY} stroke="#203540" strokeDasharray="3 5" />
          <text x={left - 8} y={gridY + 3} textAnchor="end" fill="#718994" fontSize="10">{value.toFixed(1)}</text>
        </g>;
      })}
      <polygon points={band} fill="#39c7b9" opacity=".14" />
      <polyline points={line} fill="none" stroke="#38c9bc" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
      {readings.map((reading, index) => {
        const outOfPolicy = reading[metric] < reading[minKey] || reading[metric] > reading[maxKey];
        return <circle key={reading.id} cx={x(index)} cy={y(reading[metric])} r={readings.length > 100 ? 1.5 : 2.5} fill={outOfPolicy ? '#f08c72' : '#50d4c3'}>
          <title>{`${new Date(reading.recorded_at).toLocaleString()}: ${reading[metric]} ${unit}; policy ${reading[minKey]}–${reading[maxKey]} ${unit}; ${reading.quality_status}`}</title>
        </circle>;
      })}
      {ticks.map((index) => <text key={index} x={x(index)} y={height - 7} textAnchor={index === 0 ? 'start' : index === readings.length - 1 ? 'end' : 'middle'} fill="#718994" fontSize="9">{new Date(readings[index].recorded_at).toLocaleString()}</text>)}
    </svg>
  </section>;
}

function RecordDialog({ title, record, view, onClose }) {
  const [history, setHistory] = useState([]);
  const [historyError, setHistoryError] = useState('');
  const [containerMonitoring, setContainerMonitoring] = useState(null);
  const [containerError, setContainerError] = useState('');
  const [containerLoading, setContainerLoading] = useState(false);
  const [readingOffset, setReadingOffset] = useState(0);
  useEffect(() => {
    if (view !== 'Corrective actions' || !record.id) return undefined;
    const controller = new AbortController();
    fetch(`/api/actions/${encodeURIComponent(record.id)}/history`, { headers: { Accept: 'application/json' }, signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Action history request failed (${response.status})`);
        const result = await response.json();
        setHistory(result.events);
      })
      .catch((requestError) => {
        if (requestError.name !== 'AbortError') setHistoryError(requestError.message || 'Could not load action history.');
      });
    return () => controller.abort();
  }, [record, view]);
  useEffect(() => {
    if (view !== 'Containers' || !record.id) return undefined;
    const controller = new AbortController();
    async function loadMonitoring() {
      setContainerLoading(true);
      setContainerError('');
      try {
        const response = await fetch(
          `/api/containers/${encodeURIComponent(record.id)}/monitoring?limit=288&offset=${readingOffset}`,
          { headers: { Accept: 'application/json' }, signal: controller.signal },
        );
        if (!response.ok) throw new Error(`Container monitoring request failed (${response.status})`);
        const result = await response.json();
        if (!result.container || !Array.isArray(result.readings) || !Array.isArray(result.excursions)) {
          throw new Error('Container monitoring response has an invalid shape.');
        }
        setContainerMonitoring(result);
      } catch (requestError) {
        if (requestError.name !== 'AbortError') {
          setContainerError(requestError.message || 'Could not load container readings.');
          setContainerMonitoring(null);
        }
      } finally {
        if (!controller.signal.aborted) setContainerLoading(false);
      }
    }
    loadMonitoring();
    return () => controller.abort();
  }, [record.id, readingOffset, view]);
  useEffect(() => {
    const onKeyDown = (event) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);
  return (
    <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="record-dialog" role="dialog" aria-modal="true" aria-labelledby="record-dialog-title">
        <header><div><span>RECORD DETAILS</span><h2 id="record-dialog-title">{title}</h2></div><button className="icon-btn" aria-label="Close details" onClick={onClose}><X size={18} /></button></header>
        <dl>{Object.entries(record).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{formatCell(key, value, record)}</dd></div>)}</dl>
        {view === 'Containers' && <ContainerMonitoring
          data={containerMonitoring}
          error={containerError}
          loading={containerLoading}
          offset={readingOffset}
          onOffsetChange={setReadingOffset}
        />}
        {view === 'Corrective actions' && <div className="record-history"><h3>Status history</h3>{historyError && <p className="data-error" role="alert">{historyError}</p>}{history.map((event) => <div key={event.id}><strong>{event.from_status ? `${event.from_status.replaceAll('_', ' ')} → ` : ''}{event.to_status.replaceAll('_', ' ')}</strong><span>{new Date(event.occurred_at).toLocaleString()} · {event.actor}</span>{event.note && <p>{event.note}</p>}</div>)}</div>}
      </section>
    </div>
  );
}

function EmptyState({ text }) {
  return <div className="empty-state"><Snowflake size={20} /><span>{text}</span></div>;
}

function SnapshotMetric({ label, value, detail, icon: Icon }) {
  return <div className="snapshot-metric">
    <div className="snapshot-icon"><Icon size={15} /></div>
    <div className="snapshot-copy"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>
  </div>;
}

function TrendChart({ data }) {
  const width = 800;
  const height = 220;
  const left = 38;
  const right = 38;
  const top = 14;
  const bottom = 28;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const hasValue = (value) => value != null && Number.isFinite(Number(value));
  const temperatures = data.map((item) => item.temperature).filter(hasValue).map(Number);
  const minTemperature = Math.floor(Math.min(...temperatures));
  const maxTemperature = Math.ceil(Math.max(...temperatures));
  const temperatureRange = Math.max(1, maxTemperature - minTemperature);
  const x = (index) => left + (data.length < 2 ? plotWidth / 2 : index * plotWidth / (data.length - 1));
  const yTemperature = (value) => top + (maxTemperature - Number(value)) * plotHeight / temperatureRange;
  const yHumidity = (value) => top + (100 - Number(value)) * plotHeight / 100;
  const linePath = (key, y) => data.reduce((segments, item, index) => {
    if (!hasValue(item[key])) return [...segments, ''];
    const point = `${x(index)},${y(item[key])}`;
    if (!segments.length || !segments[segments.length - 1]) return [...segments, `M${point}`];
    segments[segments.length - 1] += ` L${point}`;
    return segments;
  }, []).filter(Boolean).join(' ');
  const temperatureLine = linePath('temperature', yTemperature);
  const humidityLine = linePath('humidity', yHumidity);
  const tickIndexes = [...new Set([0, Math.floor((data.length - 1) / 2), data.length - 1])];

  return <svg className="trend-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Hourly average temperature and humidity over the latest 24 hours">
    {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
      const y = top + fraction * plotHeight;
      const temperature = (maxTemperature - fraction * temperatureRange).toFixed(0);
      const humidity = Math.round(100 - fraction * 100);
      return <g key={fraction}>
        <line x1={left} y1={y} x2={width - right} y2={y} stroke="#203540" strokeDasharray="3 5" />
        <text x={left - 8} y={y + 3} textAnchor="end" fill="#718994" fontSize="10">{temperature}</text>
        <text x={width - right + 8} y={y + 3} textAnchor="start" fill="#718994" fontSize="10">{humidity}</text>
      </g>;
    })}
    <path d={temperatureLine} fill="none" stroke="#38c9bc" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
    <path d={humidityLine} fill="none" stroke="#8098f5" strokeWidth="2" strokeDasharray="5 5" strokeLinejoin="round" strokeLinecap="round" />
    {data.map((item, index) => <g key={item.hour ?? item.date}>
      {hasValue(item.temperature) && <circle cx={x(index)} cy={yTemperature(item.temperature)} r="3" fill="#38c9bc"><title>{`${item.hour ?? item.date}: ${item.temperature}°C · ${item.reading_count} readings`}</title></circle>}
      {hasValue(item.humidity) && <circle cx={x(index)} cy={yHumidity(item.humidity)} r="3" fill="#8098f5"><title>{`${item.hour ?? item.date}: ${item.humidity}% RH · ${item.reading_count} readings`}</title></circle>}
    </g>)}
    {tickIndexes.map((index) => {
      const timestamp = data[index].hour ?? data[index].date;
      const label = data[index].hour
        ? new Date(data[index].hour).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })
        : data[index].date;
      return <text key={timestamp} x={x(index)} y={height - 7} textAnchor={index === 0 ? 'start' : index === data.length - 1 ? 'end' : 'middle'} fill="#718994" fontSize="10">{label} UTC</text>;
    })}
  </svg>;
}

function isOutOfRange(item) {
  const value = measurementValue(item);
  const minimum = item.threshold_min ?? item.threshold_min_c ?? Number.NEGATIVE_INFINITY;
  const maximum = item.threshold_max ?? item.threshold_max_c ?? Number.POSITIVE_INFINITY;
  return value != null && (value < minimum || value > maximum);
}

function measurementValue(item) {
  return item.measured_value ?? item.temperature_c;
}

function measurementUnit(item) {
  return item.unit ?? '°C';
}

function formatDuration(minutes = 0) {
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return hours ? `${hours}h ${remainder}m` : `${remainder} min`;
}

export default App;
