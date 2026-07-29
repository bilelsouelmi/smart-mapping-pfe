import { useState, useEffect } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { toast } from 'react-toastify';
import { FileBarChart, RefreshCw, Download, ShieldAlert, Lock, Copy, ShieldCheck, KeyRound } from 'lucide-react';
import Layout from '../components/Layout';
import API_BASE_URL from '../config/api';

const API = `${API_BASE_URL}/api`;

const CATEGORY_META = {
  'Sanctions & PEP Screening': { color: '#ef4444', icon: ShieldAlert },
  'Large-Amount Approval': { color: '#f59e0b', icon: Lock },
  'Duplicate Detection': { color: '#06b6d4', icon: Copy },
  'Watchlist Governance': { color: '#a78bfa', icon: ShieldCheck },
  'Access Control': { color: '#10b981', icon: KeyRound },
};

// datetime-local wants local time "YYYY-MM-DDTHH:mm" — toISOString() would
// shift to UTC and show the wrong wall-clock time in the picker.
const toLocalInputValue = (d) => {
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};
const defaultStart = () => { const d = new Date(); d.setDate(d.getDate() - 30); d.setHours(0, 0, 0, 0); return toLocalInputValue(d); };
const defaultEnd = () => toLocalInputValue(new Date());
const filenameSafe = (v) => v.replace(/[:T]/g, '-');

const RegulatoryReportsPage = () => {
  const [startDatetime, setStartDatetime] = useState(defaultStart());
  const [endDatetime, setEndDatetime] = useState(defaultEnd());
  const [category, setCategory] = useState('');
  const [categories, setCategories] = useState(Object.keys(CATEGORY_META));
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const fetchSummary = async (cat = category) => {
    setLoading(true);
    try {
      const params = { start_datetime: startDatetime, end_datetime: endDatetime };
      if (cat) params.category = cat;
      const res = await axios.get(`${API}/reports/regulatory-summary`, { params });
      setSummary(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load report');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    axios.get(`${API}/reports/regulatory-categories`).then(res => setCategories(res.data)).catch(() => {});
    fetchSummary();
  }, []);

  const exportCsv = async () => {
    setExporting(true);
    try {
      const params = { start_datetime: startDatetime, end_datetime: endDatetime };
      if (category) params.category = category;
      const res = await axios.get(`${API}/reports/regulatory-export`, { params, responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data], { type: 'text/csv' }));
      const a = document.createElement('a');
      const catSuffix = category ? `_${category.replace(/[^a-zA-Z0-9]+/g, '-')}` : '';
      a.href = url; a.download = `regulatory_report_${filenameSafe(startDatetime)}_${filenameSafe(endDatetime)}${catSuffix}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error('Export failed');
    } finally {
      setExporting(false);
    }
  };

  const selectCategory = (cat) => {
    const next = cat === category ? '' : cat;
    setCategory(next);
    fetchSummary(next);
  };

  return (
    <Layout>
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{
            fontSize: '2.5rem', fontWeight: '800', margin: 0,
            background: 'linear-gradient(135deg, #ef4444 0%, #f59e0b 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
          }}>
            📋 Regulatory Reports
          </h1>
          <p style={{ color: '#a0a0a0', marginTop: '0.5rem', maxWidth: '760px' }}>
            Compliance-relevant events — sanctions/PEP screening, large-amount approval holds, duplicate detection,
            watchlist governance, access control — reshaped from the audit trail into a report a regulator or
            auditor can be handed directly.
          </p>
        </div>

        <div style={{
          display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap', marginBottom: '1.5rem',
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '12px', padding: '1rem'
        }}>
          <div>
            <label style={labelStyle}>Start date &amp; time</label>
            <input type="datetime-local" value={startDatetime} onChange={e => setStartDatetime(e.target.value)} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>End date &amp; time</label>
            <input type="datetime-local" value={endDatetime} onChange={e => setEndDatetime(e.target.value)} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>Category</label>
            <select value={category} onChange={e => { setCategory(e.target.value); fetchSummary(e.target.value); }} style={inputStyle}>
              <option value="">All categories</option>
              {categories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <button onClick={() => fetchSummary()} style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '10px 18px', background: 'rgba(167,139,250,0.15)',
            border: '1px solid rgba(167,139,250,0.3)', borderRadius: '10px',
            color: '#a78bfa', cursor: 'pointer', fontWeight: '600'
          }}>
            <RefreshCw size={16} /> Refresh
          </button>
          <button onClick={exportCsv} disabled={exporting} style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '10px 18px', background: 'rgba(16,185,129,0.15)',
            border: '1px solid rgba(16,185,129,0.3)', borderRadius: '10px',
            color: '#10b981', cursor: exporting ? 'not-allowed' : 'pointer', fontWeight: '600',
            opacity: exporting ? 0.6 : 1, marginLeft: 'auto'
          }}>
            <Download size={16} /> Export CSV
          </button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>Loading...</div>
        ) : !summary ? null : (
          <>
            <div style={{
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '16px', padding: '1.5rem', marginBottom: '1.5rem',
              display: 'flex', alignItems: 'center', gap: '1rem'
            }}>
              <FileBarChart size={32} color="#a78bfa" />
              <div>
                <div style={{ fontSize: '1.8rem', fontWeight: '800', color: 'white' }}>{summary.total_events}</div>
                <div style={{ color: '#6b7280', fontSize: '0.85rem' }}>Total compliance events, {startDatetime.replace('T', ' ')} to {endDatetime.replace('T', ' ')}</div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
              {Object.entries(summary.by_category).filter(([cat]) => !category || cat === category).map(([cat, count]) => {
                const meta = CATEGORY_META[cat] || { color: '#9ca3af', icon: FileBarChart };
                const Icon = meta.icon;
                const active = category === cat;
                return (
                  <div key={cat} onClick={() => selectCategory(cat)} title="Click to filter the report to just this category" style={{
                    background: active ? `${meta.color}12` : 'rgba(255,255,255,0.03)',
                    border: `1px solid ${meta.color}${active ? '80' : '30'}`,
                    borderRadius: '14px', padding: '1.25rem', cursor: 'pointer',
                    boxShadow: active ? `0 0 0 1px ${meta.color}40` : 'none'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.5rem' }}>
                      <Icon size={18} color={meta.color} />
                      <span style={{ color: '#9ca3af', fontSize: '0.8rem', fontWeight: '600' }}>{cat}</span>
                    </div>
                    <div style={{ fontSize: '1.6rem', fontWeight: '800', color: meta.color }}>{count}</div>
                  </div>
                );
              })}
            </div>
            {category && (
              <div style={{ marginTop: '1rem', color: '#6b7280', fontSize: '0.82rem' }}>
                Filtered to <b style={{ color: 'white' }}>{category}</b> — the export will only include this category. Click the card again, or choose "All categories", to clear it.
              </div>
            )}
          </>
        )}
      </motion.div>
    </Layout>
  );
};

const labelStyle = {
  display: 'block', color: '#6b7280', fontSize: '0.78rem', fontWeight: '600',
  textTransform: 'uppercase', marginBottom: '4px'
};

const inputStyle = {
  padding: '9px 14px', background: '#1e2a3a', border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '10px', color: 'white', fontSize: '0.85rem'
};

export default RegulatoryReportsPage;
