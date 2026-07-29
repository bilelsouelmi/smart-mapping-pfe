import { useState, useEffect } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { toast } from 'react-toastify';
import { Activity, RefreshCw, Clock, ShieldAlert, FileWarning, Lock, TrendingUp } from 'lucide-react';
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import Layout from '../components/Layout';
import API_BASE_URL from '../config/api';

const API = `${API_BASE_URL}/api`;

const toLocalInputValue = (d) => {
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};
const defaultStart = () => { const d = new Date(); d.setDate(d.getDate() - 30); d.setHours(0, 0, 0, 0); return toLocalInputValue(d); };
const defaultEnd = () => toLocalInputValue(new Date());

// Quick presets — 30 days by default meant a chart that's 90% flat empty
// space whenever real activity only spans the last day or two of testing;
// letting the presenter jump to a denser window is worth more than a
// fixed lookback nobody asked for.
const RANGE_PRESETS = [
  { label: '24h', days: 1 },
  { label: '7j', days: 7 },
  { label: '30j', days: 30 },
  { label: '90j', days: 90 },
];

const fmtDuration = (seconds) => {
  if (seconds === null || seconds === undefined) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
};

const SlaDashboardPage = () => {
  const [startDatetime, setStartDatetime] = useState(defaultStart());
  const [endDatetime, setEndDatetime] = useState(defaultEnd());
  const [summary, setSummary] = useState(null);
  const [timeseries, setTimeseries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchAll = async (silent = false, overrideRange = null) => {
    if (!silent) setLoading(true);
    try {
      const params = {
        start_datetime: overrideRange?.start ?? startDatetime,
        end_datetime: overrideRange?.end ?? endDatetime,
      };
      const [summaryRes, seriesRes] = await Promise.all([
        axios.get(`${API}/reports/sla-summary`, { params }),
        axios.get(`${API}/reports/sla-timeseries`, { params }),
      ]);
      setSummary(summaryRes.data);
      setTimeseries(seriesRes.data.map(d => ({
        ...d,
        label: d.date.slice(5),
        total: d.transforms + d.holds + d.blocks + d.validation_failures,
      })));
      setLastUpdated(new Date());
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load SLA dashboard');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const [activePreset, setActivePreset] = useState(null);
  const applyPreset = (days) => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - days);
    if (days > 1) start.setHours(0, 0, 0, 0);
    const startStr = toLocalInputValue(start);
    const endStr = toLocalInputValue(end);
    setStartDatetime(startStr);
    setEndDatetime(endStr);
    setActivePreset(days);
    fetchAll(false, { start: startStr, end: endStr });
  };

  // Auto-refresh keeps the dashboard live without a manual click — a
  // silent background refetch (no loading spinner) every 30s, same
  // interval the pipeline auto-consumption scheduler already uses
  // elsewhere in this app, so the whole platform feels consistent about
  // what "near real-time" means. Paused whenever the date range covers
  // anything other than "now" — refreshing a fixed historical window on
  // a timer would just be wasted requests for data that can't change.
  useEffect(() => {
    if (!autoRefresh) return;
    const isLiveWindow = Math.abs(new Date(endDatetime) - new Date()) < 5 * 60 * 1000;
    if (!isLiveWindow) return;
    const interval = setInterval(() => fetchAll(true), 30000);
    return () => clearInterval(interval);
  }, [autoRefresh, startDatetime, endDatetime]);

  return (
    <Layout>
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{
            fontSize: '2.5rem', fontWeight: '800', margin: 0,
            background: 'linear-gradient(135deg, #667eea 0%, #06b6d4 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
          }}>
            ⚡ SLA / Performance Dashboard
          </h1>
          <p style={{ color: '#a0a0a0', marginTop: '0.5rem', maxWidth: '760px' }}>
            How the platform is performing over a date range — transform volume, how long holds take to clear,
            validation failure rate, and outright block/flag rate. Aggregated from data every other feature already tracks.
          </p>
        </div>

        <div style={{
          display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap', marginBottom: '1.5rem',
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '12px', padding: '1rem'
        }}>
          <div style={{ display: 'flex', gap: '6px' }}>
            {RANGE_PRESETS.map(p => (
              <button key={p.days} onClick={() => applyPreset(p.days)} style={{
                padding: '9px 14px', borderRadius: '10px', fontSize: '0.82rem', fontWeight: '700', cursor: 'pointer',
                background: activePreset === p.days ? 'linear-gradient(135deg, #667eea 0%, #06b6d4 100%)' : 'rgba(255,255,255,0.05)',
                border: `1px solid ${activePreset === p.days ? 'transparent' : 'rgba(255,255,255,0.1)'}`,
                color: activePreset === p.days ? 'white' : '#9ca3af'
              }}>
                {p.label}
              </button>
            ))}
          </div>
          <div>
            <label style={labelStyle}>Start date &amp; time</label>
            <input type="datetime-local" value={startDatetime} onChange={e => { setStartDatetime(e.target.value); setActivePreset(null); }} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>End date &amp; time</label>
            <input type="datetime-local" value={endDatetime} onChange={e => { setEndDatetime(e.target.value); setActivePreset(null); }} style={inputStyle} />
          </div>
          <button onClick={() => fetchAll(false)} style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '10px 18px', background: 'rgba(167,139,250,0.15)',
            border: '1px solid rgba(167,139,250,0.3)', borderRadius: '10px',
            color: '#a78bfa', cursor: 'pointer', fontWeight: '600'
          }}>
            <RefreshCw size={16} /> Refresh
          </button>
          <button onClick={() => setAutoRefresh(v => !v)} style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '10px 18px',
            background: autoRefresh ? 'rgba(16,185,129,0.15)' : 'rgba(255,255,255,0.05)',
            border: `1px solid ${autoRefresh ? 'rgba(16,185,129,0.3)' : 'rgba(255,255,255,0.1)'}`,
            borderRadius: '10px', color: autoRefresh ? '#6ee7b7' : '#9ca3af', cursor: 'pointer', fontWeight: '600'
          }}>
            <span style={{
              width: '8px', height: '8px', borderRadius: '50%',
              background: autoRefresh ? '#10b981' : '#6b7280',
              boxShadow: autoRefresh ? '0 0 8px #10b981' : 'none',
              animation: autoRefresh ? 'sla-pulse 1.5s ease-in-out infinite' : 'none'
            }} />
            {autoRefresh ? 'Live (30s)' : 'Auto-refresh off'}
          </button>
          {lastUpdated && (
            <span style={{ color: '#6b7280', fontSize: '0.8rem', alignSelf: 'center' }}>
              Last updated: {lastUpdated.toLocaleTimeString()}
            </span>
          )}
        </div>
        <style>{`@keyframes sla-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }`}</style>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>Loading...</div>
        ) : !summary ? null : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
              <StatCard icon={Activity} color="#06b6d4" label="Transforms Completed" value={summary.total_transforms} />
              <StatCard icon={Lock} color="#f59e0b" label="Holds Created" value={summary.holds_created}
                sub={`${summary.holds_still_pending} still pending`} />
              <StatCard icon={Clock} color="#a78bfa" label="Avg Turnaround — Admin Holds" value={fmtDuration(summary.avg_turnaround_seconds.admin)}
                sla={summary.sla_status?.admin} />
              <StatCard icon={Clock} color="#ef4444" label="Avg Turnaround — PEP Holds" value={fmtDuration(summary.avg_turnaround_seconds.compliance_officer)}
                sla={summary.sla_status?.compliance_officer} />
              <StatCard icon={FileWarning} color="#f59e0b" label="Validation Failures" value={summary.validation_failures}
                sub={`${summary.validation_status_counts.resolved} resolved, ${summary.validation_status_counts.dismissed} dismissed, ${summary.validation_status_counts.pending} pending`} />
              <StatCard icon={ShieldAlert} color="#ef4444" label="Outright Blocks/Flags" value={
                Object.values(summary.block_counts).reduce((a, b) => a + b, 0)
              } sub={Object.entries(summary.block_counts).map(([k, v]) => `${v} ${k}`).join(', ') || 'none'} />
            </div>

            <div style={{
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '16px', padding: '1.5rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'white', fontWeight: '700' }}>
                  <TrendingUp size={20} color="#667eea" /> Daily Activity
                </div>
                <span style={{ color: '#6b7280', fontSize: '0.8rem' }}>
                  {timeseries.reduce((s, d) => s + d.total, 0)} événements sur la période
                </span>
              </div>
              <ResponsiveContainer width="100%" height={320}>
                <ComposedChart data={timeseries} barGap={2} barCategoryGap="20%">
                  <defs>
                    <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#667eea" stopOpacity={0.9} />
                      <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.9} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" vertical={false} />
                  <XAxis dataKey="label" stroke="#a0a0a0" fontSize={12} />
                  <YAxis stroke="#a0a0a0" allowDecimals={false} fontSize={12} />
                  <Tooltip content={<ActivityTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                  <Legend wrapperStyle={{ fontSize: '0.8rem' }} />
                  <Bar dataKey="transforms" name="Transforms" stackId="a" fill="#06b6d4" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="holds" name="Holds Created" stackId="a" fill="#f59e0b" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="blocks" name="Blocks/Flags" stackId="a" fill="#ef4444" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="validation_failures" name="Validation Failures" stackId="a" fill="#a78bfa" radius={[6, 6, 0, 0]} />
                  <Line type="monotone" dataKey="total" name="Total (tendance)" stroke="url(#colorTotal)"
                    strokeWidth={3} dot={{ r: 3, fill: '#667eea', strokeWidth: 0 }}
                    activeDot={{ r: 6, fill: '#06b6d4' }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </motion.div>
    </Layout>
  );
};

// Custom tooltip so the daily breakdown reads as a clear mini-report
// (with the total called out) instead of recharts' default plain list.
const ActivityTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;
  const total = payload.find(p => p.dataKey === 'total')?.value ?? 0;
  const bars = payload.filter(p => p.dataKey !== 'total');
  return (
    <div style={{
      background: 'rgba(26, 26, 46, 0.97)', border: '1px solid rgba(255,255,255,0.12)',
      borderRadius: '10px', padding: '10px 14px', backdropFilter: 'blur(10px)',
      boxShadow: '0 8px 24px rgba(0,0,0,0.4)'
    }}>
      <div style={{ color: 'white', fontWeight: '700', fontSize: '0.85rem', marginBottom: '6px' }}>
        {label} — {total} événement{total > 1 ? 's' : ''}
      </div>
      {bars.map(p => (
        <div key={p.dataKey} style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', fontSize: '0.78rem', color: '#d1d5db' }}>
          <span style={{ color: p.fill || p.color }}>● {p.name}</span>
          <span style={{ fontWeight: '700' }}>{p.value}</span>
        </div>
      ))}
    </div>
  );
};

const StatCard = ({ icon: Icon, color, label, value, sub, sla }) => (
  <div style={{
    background: 'rgba(255,255,255,0.03)', border: `1px solid ${color}30`,
    borderRadius: '14px', padding: '1.25rem'
  }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Icon size={18} color={color} />
        <span style={{ color: '#9ca3af', fontSize: '0.8rem', fontWeight: '600' }}>{label}</span>
      </div>
      {/* within_target is None when there's no resolved hold yet to
          judge — distinct from an actual breach, so no badge at all
          rather than a misleading pass/fail on zero data. */}
      {sla && sla.within_target !== null && (
        <span style={{
          padding: '2px 8px', borderRadius: '20px', fontSize: '10px', fontWeight: '700',
          background: sla.within_target ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
          color: sla.within_target ? '#6ee7b7' : '#fca5a5',
          border: `1px solid ${sla.within_target ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`
        }}>
          {sla.within_target ? '✓ Within SLA' : '⚠ Breached'}
        </span>
      )}
    </div>
    <div style={{ fontSize: '1.6rem', fontWeight: '800', color }}>{value}</div>
    {sub && <div style={{ color: '#6b7280', fontSize: '0.75rem', marginTop: '2px' }}>{sub}</div>}
    {sla && <div style={{ color: '#6b7280', fontSize: '0.7rem', marginTop: '2px' }}>Target: ≤ {sla.target_hours}h</div>}
  </div>
);

const labelStyle = {
  display: 'block', color: '#6b7280', fontSize: '0.78rem', fontWeight: '600',
  textTransform: 'uppercase', marginBottom: '4px'
};

const inputStyle = {
  padding: '9px 14px', background: '#1e2a3a', border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '10px', color: 'white', fontSize: '0.85rem'
};

export default SlaDashboardPage;
