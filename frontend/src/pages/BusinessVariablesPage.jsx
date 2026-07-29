import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-toastify';
import { SlidersHorizontal, RefreshCw, Search, Plus, Edit2, Trash2, Save, X } from 'lucide-react';
import Layout from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import API_BASE_URL from '../config/api';

const API = `${API_BASE_URL}/api`;
const VALID_TYPES = ['STRING', 'INTEGER', 'DECIMAL', 'BOOLEAN'];

const TYPE_COLORS = {
  STRING: '#06b6d4',
  INTEGER: '#a78bfa',
  DECIMAL: '#f472b6',
  BOOLEAN: '#f59e0b',
};

const BusinessVariablesPage = () => {
  const { user } = useAuth();
  const [variables, setVariables] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editData, setEditData] = useState({});
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createData, setCreateData] = useState({ name: '', value: '', var_type: 'STRING', description: '', currency: '' });

  const fetchVariables = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/business-variables/`);
      setVariables(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load business variables');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchVariables(); }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return variables;
    return variables.filter(v =>
      v.name.toLowerCase().includes(q) ||
      (v.description || '').toLowerCase().includes(q)
    );
  }, [variables, search]);

  const startEdit = (v) => {
    setEditingId(v.id);
    setEditData({ value: v.value, var_type: v.var_type, description: v.description || '', currency: v.currency || '' });
  };

  const cancelEdit = () => { setEditingId(null); setEditData({}); };

  const saveEdit = async (id) => {
    setSaving(true);
    try {
      await axios.put(`${API}/business-variables/${id}`, editData);
      toast.success('Variable updated');
      setEditingId(null);
      fetchVariables();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  const deleteVariable = async (id) => {
    try {
      await axios.delete(`${API}/business-variables/${id}`);
      toast.success('Variable deleted');
      setDeleteConfirm(null);
      fetchVariables();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Delete failed');
    }
  };

  const createVariable = async () => {
    if (!createData.name.trim() || !createData.value.trim()) {
      toast.error('Name and value are required');
      return;
    }
    setSaving(true);
    try {
      await axios.post(`${API}/business-variables/`, {
        ...createData,
        currency: createData.currency || null,
        description: createData.description || null,
      });
      toast.success('Variable created');
      setShowCreate(false);
      setCreateData({ name: '', value: '', var_type: 'STRING', description: '', currency: '' });
      fetchVariables();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Creation failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Layout>
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div style={{ marginBottom: '2rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 style={{
              fontSize: '2.5rem', fontWeight: '800', margin: 0,
              background: 'linear-gradient(135deg, #a78bfa 0%, #667eea 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
            }}>
              ⚙️ Business Variables
            </h1>
            <p style={{ color: '#a0a0a0', marginTop: '0.5rem' }}>
              Thresholds, feature flags, and constants used by every transformation —
              {user?.is_admin ? ' edit a value here and it applies immediately, no redeploy.' : ' read-only view, ask an admin to change a value.'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            {user?.is_admin && (
              <button onClick={() => setShowCreate(true)} style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '10px 18px', background: 'rgba(16,185,129,0.15)',
                border: '1px solid rgba(16,185,129,0.3)', borderRadius: '10px',
                color: '#10b981', cursor: 'pointer', fontWeight: '600'
              }}>
                <Plus size={16} /> New Variable
              </button>
            )}
            <button onClick={fetchVariables} style={{
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
            placeholder="Search by name or description..."
            style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: 'white', fontSize: '0.9rem' }}
          />
          <span style={{ color: '#6b7280', fontSize: '0.8rem' }}>{filtered.length} / {variables.length}</span>
        </div>

        <div style={{
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '16px', overflow: 'hidden'
        }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>Loading...</div>
          ) : filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>
              <SlidersHorizontal size={40} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />
              No variables match this search.
            </div>
          ) : (
            <div style={{ overflowX: 'auto', overflowY: 'auto', maxHeight: '65vh' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                    {['Name', 'Value', 'Type', 'Currency', 'Description', 'Last updated by', user?.is_admin ? 'Actions' : ''].map(h => (
                      <th key={h} style={{ textAlign: 'left', padding: '0.85rem 1rem', color: '#6b7280', fontSize: '0.78rem', textTransform: 'uppercase', whiteSpace: 'nowrap', position: 'sticky', top: 0, background: '#1a1a2e' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((v, i) => {
                    const isEditing = editingId === v.id;
                    return (
                      <motion.tr key={v.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.015 }}
                        style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '0.75rem 1rem', color: 'white', fontWeight: '700', fontSize: '0.85rem', fontFamily: 'monospace' }}>
                          {v.name}
                        </td>
                        <td style={{ padding: '0.75rem 1rem' }}>
                          {isEditing ? (
                            <input value={editData.value} onChange={e => setEditData({ ...editData, value: e.target.value })} style={inputStyle} />
                          ) : (
                            <span style={{ color: '#d1d5db', fontSize: '0.85rem', fontFamily: 'monospace' }}>{v.value}</span>
                          )}
                        </td>
                        <td style={{ padding: '0.75rem 1rem' }}>
                          {isEditing ? (
                            <select value={editData.var_type} onChange={e => setEditData({ ...editData, var_type: e.target.value })} style={inputStyle}>
                              {VALID_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                            </select>
                          ) : (
                            <span style={{
                              padding: '2px 10px', borderRadius: '999px', fontSize: '0.72rem', fontWeight: '700',
                              background: `${TYPE_COLORS[v.var_type] || '#6b7280'}20`,
                              color: TYPE_COLORS[v.var_type] || '#9ca3af'
                            }}>
                              {v.var_type}
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '0.75rem 1rem', color: '#9ca3af', fontSize: '0.82rem' }}>
                          {isEditing ? (
                            <input value={editData.currency} onChange={e => setEditData({ ...editData, currency: e.target.value })} placeholder="—" style={{ ...inputStyle, width: '70px' }} />
                          ) : (v.currency || '—')}
                        </td>
                        <td style={{ padding: '0.75rem 1rem', color: '#9ca3af', fontSize: '0.8rem', maxWidth: '320px' }}>
                          {isEditing ? (
                            <input value={editData.description} onChange={e => setEditData({ ...editData, description: e.target.value })} style={inputStyle} />
                          ) : (v.description || '—')}
                        </td>
                        <td style={{ padding: '0.75rem 1rem', color: '#6b7280', fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
                          {v.updated_by_username || '—'}
                        </td>
                        {user?.is_admin && (
                          <td style={{ padding: '0.75rem 1rem' }}>
                            {isEditing ? (
                              <div style={{ display: 'flex', gap: '6px' }}>
                                <button onClick={() => saveEdit(v.id)} disabled={saving} style={iconBtnStyle('#10b981', saving)}><Save size={14} /></button>
                                <button onClick={cancelEdit} disabled={saving} style={iconBtnStyle('#6b7280', saving)}><X size={14} /></button>
                              </div>
                            ) : deleteConfirm === v.id ? (
                              <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                                <span style={{ color: '#ef4444', fontSize: '0.75rem' }}>Delete?</span>
                                <button onClick={() => deleteVariable(v.id)} style={iconBtnStyle('#ef4444', false)}><Trash2 size={14} /></button>
                                <button onClick={() => setDeleteConfirm(null)} style={iconBtnStyle('#6b7280', false)}><X size={14} /></button>
                              </div>
                            ) : (
                              <div style={{ display: 'flex', gap: '6px' }}>
                                <button onClick={() => startEdit(v)} disabled={!!editingId} style={iconBtnStyle('#a78bfa', !!editingId)}><Edit2 size={14} /></button>
                                <button onClick={() => setDeleteConfirm(v.id)} disabled={!!editingId} style={iconBtnStyle('#ef4444', !!editingId)}><Trash2 size={14} /></button>
                              </div>
                            )}
                          </td>
                        )}
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
              <h2 style={{ color: 'white', fontWeight: '800', marginBottom: '1.5rem', fontSize: '1.3rem' }}>
                ➕ New Business Variable
              </h2>

              <label style={labelStyle}>Name *</label>
              <input value={createData.name} onChange={e => setCreateData({ ...createData, name: e.target.value.toUpperCase().replace(/\s+/g, '_') })}
                placeholder="e.g. MAX_RETRY_COUNT" style={{ ...inputStyle, width: '100%', marginBottom: '1rem' }} />

              <label style={labelStyle}>Value *</label>
              <input value={createData.value} onChange={e => setCreateData({ ...createData, value: e.target.value })}
                placeholder="e.g. 3" style={{ ...inputStyle, width: '100%', marginBottom: '1rem' }} />

              <label style={labelStyle}>Type</label>
              <select value={createData.var_type} onChange={e => setCreateData({ ...createData, var_type: e.target.value })}
                style={{ ...inputStyle, width: '100%', marginBottom: '1rem' }}>
                {VALID_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>

              <label style={labelStyle}>Currency (optional)</label>
              <input value={createData.currency} onChange={e => setCreateData({ ...createData, currency: e.target.value.toUpperCase() })}
                placeholder="e.g. EUR" style={{ ...inputStyle, width: '100%', marginBottom: '1rem' }} />

              <label style={labelStyle}>Description</label>
              <input value={createData.description} onChange={e => setCreateData({ ...createData, description: e.target.value })}
                placeholder="What this variable controls" style={{ ...inputStyle, width: '100%', marginBottom: '1.5rem' }} />

              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                <button onClick={() => setShowCreate(false)} style={{
                  padding: '0.6rem 1.2rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.15)',
                  background: 'none', color: '#9ca3af', cursor: 'pointer', fontWeight: '600'
                }}>Cancel</button>
                <button onClick={createVariable} disabled={saving} style={{
                  padding: '0.6rem 1.2rem', borderRadius: '8px', border: '1px solid rgba(16,185,129,0.3)',
                  background: 'rgba(16,185,129,0.15)', color: '#10b981', cursor: saving ? 'not-allowed' : 'pointer',
                  fontWeight: '600', opacity: saving ? 0.6 : 1
                }}>{saving ? 'Creating...' : 'Create'}</button>
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

const labelStyle = {
  display: 'block', color: '#9ca3af', fontSize: '0.8rem', fontWeight: '600', marginBottom: '0.4rem'
};

const iconBtnStyle = (color, disabled) => ({
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: '28px', height: '28px', borderRadius: '6px',
  border: `1px solid ${color}40`, background: `${color}15`,
  color, cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
});

export default BusinessVariablesPage;
