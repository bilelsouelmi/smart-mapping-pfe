import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-toastify';
import { ShieldAlert, RefreshCw, Search, Plus, Check, X, Clock, MinusCircle } from 'lucide-react';
import Layout from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import API_BASE_URL from '../config/api';

const API = `${API_BASE_URL}/api`;
const LIST_TYPES = ['SANCTIONS', 'PEP'];

const TYPE_COLORS = {
  SANCTIONS: '#ef4444',
  PEP: '#f59e0b',
};

const STATUS_META = {
  pending_add: { label: 'Pending Add', color: '#f59e0b' },
  active: { label: 'Active', color: '#10b981' },
  pending_remove: { label: 'Pending Removal', color: '#f59e0b' },
  rejected: { label: 'Rejected', color: '#6b7280' },
};

const WatchlistPage = () => {
  const { user } = useAuth();
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [createData, setCreateData] = useState({ name: '', list_type: 'SANCTIONS', notes: '' });

  const fetchEntities = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/watchlist/`);
      setEntities(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load watchlist');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchEntities(); }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return entities.filter(e =>
      (!filterType || e.list_type === filterType) &&
      (!q || e.name.toLowerCase().includes(q) || (e.notes || '').toLowerCase().includes(q))
    );
  }, [entities, search, filterType]);

  const proposeEntity = async () => {
    if (!createData.name.trim()) {
      toast.error('Name is required');
      return;
    }
    setSaving(true);
    try {
      await axios.post(`${API}/watchlist/`, { ...createData, notes: createData.notes || null });
      toast.success('Proposed — waiting for another compliance officer to approve');
      setShowCreate(false);
      setCreateData({ name: '', list_type: 'SANCTIONS', notes: '' });
      fetchEntities();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Proposal failed');
    } finally {
      setSaving(false);
    }
  };

  const requestRemoval = async (id) => {
    setBusyId(id);
    try {
      await axios.post(`${API}/watchlist/${id}/request-removal`);
      toast.success('Removal requested — waiting for another compliance officer to confirm');
      fetchEntities();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Request failed');
    } finally {
      setBusyId(null);
    }
  };

  const approve = async (id) => {
    setBusyId(id);
    try {
      await axios.post(`${API}/watchlist/${id}/approve`);
      toast.success('Approved');
      fetchEntities();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Approval failed');
    } finally {
      setBusyId(null);
    }
  };

  const reject = async (id) => {
    setBusyId(id);
    try {
      await axios.post(`${API}/watchlist/${id}/reject`);
      toast.success('Rejected');
      fetchEntities();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Rejection failed');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Layout>
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div style={{ marginBottom: '2rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 style={{
              fontSize: '2.5rem', fontWeight: '800', margin: 0,
              background: 'linear-gradient(135deg, #ef4444 0%, #f59e0b 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
            }}>
              🚫 Sanctions & PEP Watchlist
            </h1>
            <p style={{ color: '#a0a0a0', marginTop: '0.5rem', maxWidth: '760px' }}>
              Names checked against every MT103's ordering customer and beneficiary during transform —
              a sanctions match blocks the transform, a PEP match holds it for compliance officer review before release.
              Dual control: adding or removing an entry needs a <b>different</b> compliance officer to approve it —
              you can't approve your own proposal. Demo/synthetic data only, not a real sanctions list.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button onClick={() => setShowCreate(true)} style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '10px 18px', background: 'rgba(16,185,129,0.15)',
              border: '1px solid rgba(16,185,129,0.3)', borderRadius: '10px',
              color: '#10b981', cursor: 'pointer', fontWeight: '600'
            }}>
              <Plus size={16} /> Propose Entry
            </button>
            <button onClick={fetchEntities} style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '10px 18px', background: 'rgba(167,139,250,0.15)',
              border: '1px solid rgba(167,139,250,0.3)', borderRadius: '10px',
              color: '#a78bfa', cursor: 'pointer', fontWeight: '600'
            }}>
              <RefreshCw size={16} /> Refresh
            </button>
          </div>
        </div>

        <div style={{
          display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '1.5rem',
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '12px', padding: '0.75rem 1rem'
        }}>
          <Search size={16} color="#6b7280" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name or notes..."
            style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: 'white', fontSize: '0.9rem' }}
          />
          <select value={filterType} onChange={e => setFilterType(e.target.value)} style={selectStyle}>
            <option value="">All lists</option>
            {LIST_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <span style={{ color: '#6b7280', fontSize: '0.8rem' }}>{filtered.length} / {entities.length}</span>
        </div>

        <div style={{
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '16px', overflow: 'hidden'
        }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>Loading...</div>
          ) : filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>
              <ShieldAlert size={40} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />
              No entries match this search.
            </div>
          ) : (
            <div style={{ maxHeight: '65vh', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                  {['Name', 'List', 'Status', 'Proposed by', 'Reviewed by', 'Actions'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '0.85rem 1rem', color: '#6b7280', fontSize: '0.78rem', textTransform: 'uppercase', position: 'sticky', top: 0, background: '#1a1a2e' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((e, i) => {
                  const isPending = e.status === 'pending_add' || e.status === 'pending_remove';
                  const isOwnProposal = e.proposed_by_username === user?.username;
                  const statusMeta = STATUS_META[e.status] || { label: e.status, color: '#9ca3af' };
                  return (
                    <motion.tr key={e.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.02 }}
                      style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={{ padding: '0.75rem 1rem', color: 'white', fontWeight: '700', fontSize: '0.85rem' }}>{e.name}</td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span style={{
                          padding: '2px 10px', borderRadius: '999px', fontSize: '0.72rem', fontWeight: '700',
                          background: `${TYPE_COLORS[e.list_type] || '#6b7280'}20`,
                          color: TYPE_COLORS[e.list_type] || '#9ca3af'
                        }}>
                          {e.list_type}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span style={{
                          padding: '2px 10px', borderRadius: '999px', fontSize: '0.72rem', fontWeight: '700',
                          background: `${statusMeta.color}20`, color: statusMeta.color,
                          display: 'inline-flex', alignItems: 'center', gap: '4px'
                        }}>
                          {isPending && <Clock size={11} />}
                          {statusMeta.label}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: '#9ca3af', fontSize: '0.8rem' }}>{e.proposed_by_username || '—'}</td>
                      <td style={{ padding: '0.75rem 1rem', color: '#6b7280', fontSize: '0.78rem' }}>{e.reviewed_by_username || '—'}</td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        {isPending && isOwnProposal && (
                          <span style={{ color: '#6b7280', fontSize: '0.75rem', fontStyle: 'italic' }}>
                            Awaiting another officer's review
                          </span>
                        )}
                        {isPending && !isOwnProposal && (
                          <div style={{ display: 'flex', gap: '6px' }}>
                            <button onClick={() => approve(e.id)} disabled={busyId === e.id} style={iconBtnStyle('#10b981', busyId === e.id)}><Check size={14} /></button>
                            <button onClick={() => reject(e.id)} disabled={busyId === e.id} style={iconBtnStyle('#ef4444', busyId === e.id)}><X size={14} /></button>
                          </div>
                        )}
                        {e.status === 'active' && (
                          <button onClick={() => requestRemoval(e.id)} disabled={busyId === e.id} style={iconBtnStyle('#f59e0b', busyId === e.id)} title="Request removal">
                            <MinusCircle size={14} />
                          </button>
                        )}
                        {e.status === 'rejected' && <span style={{ color: '#4b5563', fontSize: '0.75rem' }}>—</span>}
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
            </div>
          )}
        </div>
      </motion.div>

      <AnimatePresence>
        {showCreate && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            style={{
              position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              zIndex: 1000, padding: '1rem'
            }}
            onClick={e => e.target === e.currentTarget && setShowCreate(false)}>
            <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
              style={{
                background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '16px', padding: '2rem', width: '100%', maxWidth: '480px'
              }}>
              <h2 style={{ color: 'white', fontWeight: '800', marginBottom: '0.5rem', fontSize: '1.3rem' }}>
                ➕ Propose Watchlist Entry
              </h2>
              <p style={{ color: '#6b7280', fontSize: '0.8rem', marginBottom: '1.5rem' }}>
                This won't be enforced until another compliance officer approves it.
              </p>

              <label style={labelStyle}>Name *</label>
              <input value={createData.name} onChange={e => setCreateData({ ...createData, name: e.target.value })}
                placeholder="e.g. JOHN DOE or ACME CORP" style={{ ...inputStyle, width: '100%', marginBottom: '1rem' }} />

              <label style={labelStyle}>List</label>
              <select value={createData.list_type} onChange={e => setCreateData({ ...createData, list_type: e.target.value })}
                style={{ ...inputStyle, width: '100%', marginBottom: '1rem' }}>
                {LIST_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>

              <label style={labelStyle}>Notes</label>
              <input value={createData.notes} onChange={e => setCreateData({ ...createData, notes: e.target.value })}
                placeholder="Optional context" style={{ ...inputStyle, width: '100%', marginBottom: '1.5rem' }} />

              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                <button onClick={() => setShowCreate(false)} style={{
                  padding: '0.6rem 1.2rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.15)',
                  background: 'none', color: '#9ca3af', cursor: 'pointer', fontWeight: '600'
                }}>Cancel</button>
                <button onClick={proposeEntity} disabled={saving} style={{
                  padding: '0.6rem 1.2rem', borderRadius: '8px', border: '1px solid rgba(16,185,129,0.3)',
                  background: 'rgba(16,185,129,0.15)', color: '#10b981', cursor: saving ? 'not-allowed' : 'pointer',
                  fontWeight: '600', opacity: saving ? 0.6 : 1
                }}>{saving ? 'Proposing...' : 'Propose'}</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </Layout>
  );
};

const inputStyle = {
  background: 'rgba(255,255,255,0.07)',
  border: '1px solid rgba(255,255,255,0.15)',
  borderRadius: '6px', color: 'white',
  padding: '5px 9px', fontSize: '0.82rem',
};

const selectStyle = {
  padding: '6px 12px', background: '#1e2a3a', border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '8px', color: 'white', fontSize: '0.85rem'
};

const labelStyle = {
  display: 'block', color: '#9ca3af', fontSize: '0.8rem', fontWeight: '600', marginBottom: '0.4rem'
};

const iconBtnStyle = (color, disabled) => ({
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: '28px', height: '28px', borderRadius: '6px',
  border: `1px solid ${color}40`, background: `${color}15`,
  color, cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
});

export default WatchlistPage;
