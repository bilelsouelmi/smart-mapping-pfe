import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-toastify';
import { Database, RefreshCw, Search, Plus, Edit2, Trash2, Save, X, Check, Power, UploadCloud } from 'lucide-react';
import Layout from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import API_BASE_URL from '../config/api';

const API = `${API_BASE_URL}/api`;

// Label/color per category — CATEGORIES itself comes from the backend
// (GET /categories) so a new category introduced there shows up here
// without a frontend change; these are just cosmetic fallbacks for the
// ones we know about today.
const CATEGORY_META = {
  ISO_CURRENCY: { label: 'ISO Currency', color: '#06b6d4' },
  COUNTRY: { label: 'Countries', color: '#a78bfa' },
  CHARGE_CODE: { label: 'Charge Codes', color: '#f472b6' },
};

// Per-category metadata sub-fields shown as their own table columns/form
// inputs instead of a raw JSON blob. A category with no entry here (e.g.
// CHARGE_CODE, or any brand-new category an admin creates through the
// generic Category input) falls back to the plain Description column —
// same "new code lists need no frontend change" reasoning as CATEGORIES.
const META_FIELDS = {
  ISO_CURRENCY: [
    { key: 'symbol', label: 'Symbol', placeholder: '€' },
    { key: 'decimal_places', label: 'Decimals', placeholder: '2', numeric: true },
  ],
  COUNTRY: [
    { key: 'iso3', label: 'ISO3', placeholder: 'FRA' },
    { key: 'numeric_code', label: 'Numeric', placeholder: '250' },
  ],
};

const codeLabelFor = (cat) => (cat === 'COUNTRY' ? 'ISO2' : 'Code');

const ReferenceDataPage = () => {
  const { user } = useAuth();
  const [categories, setCategories] = useState([]);
  const [activeCategory, setActiveCategory] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editData, setEditData] = useState({});
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createData, setCreateData] = useState({ category: '', code: '', name: '', description: '', is_active: true, meta: {} });
  const [togglingId, setTogglingId] = useState(null);

  const fetchCategories = async () => {
    try {
      const res = await axios.get(`${API}/reference-data/categories`);
      setCategories(res.data);
      if (!activeCategory && res.data.length) setActiveCategory(res.data[0]);
    } catch (e) {
      toast.error('Failed to load categories');
    }
  };

  const fetchRows = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/reference-data/`);
      setRows(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load reference data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchCategories(); fetchRows(); }, []);

  const metaFields = META_FIELDS[activeCategory] || [];

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows
      .filter(r => r.category === activeCategory)
      .filter(r => {
        if (!q) return true;
        if (r.code.toLowerCase().includes(q) || r.name.toLowerCase().includes(q)) return true;
        if (r.description && r.description.toLowerCase().includes(q)) return true;
        if (r.metadata) {
          return Object.values(r.metadata).some(v => v != null && String(v).toLowerCase().includes(q));
        }
        return false;
      });
  }, [rows, activeCategory, search]);

  const countFor = (cat) => rows.filter(r => r.category === cat).length;

  const startEdit = (r) => {
    setEditingId(r.id);
    const fields = META_FIELDS[r.category] || [];
    const metaData = {};
    fields.forEach(f => { metaData[`meta_${f.key}`] = r.metadata?.[f.key] ?? ''; });
    setEditData({ code: r.code, name: r.name, description: r.description || '', is_active: r.is_active, ...metaData });
  };
  const cancelEdit = () => { setEditingId(null); setEditData({}); };

  const saveEdit = async (id) => {
    const row = rows.find(r => r.id === id);
    const fields = META_FIELDS[row.category] || [];
    setSaving(true);
    try {
      const payload = { code: editData.code, name: editData.name, is_active: editData.is_active };
      if (fields.length) {
        const metadata = { ...(row.metadata || {}) };
        fields.forEach(f => {
          const v = editData[`meta_${f.key}`];
          metadata[f.key] = f.numeric ? (v === '' ? null : Number(v)) : (v || null);
        });
        payload.metadata = metadata;
      } else {
        payload.description = editData.description || null;
      }
      await axios.put(`${API}/reference-data/${id}`, payload);
      toast.success('Entry updated');
      setEditingId(null);
      fetchRows();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  // Quick toggle, separate from the full Edit flow — in a banking context
  // "deactivate" is the everyday action (stop a code from validating
  // while keeping its history), Delete is the rare/exceptional one. This
  // is a one-click flip instead of Edit -> toggle checkbox -> Save.
  const toggleActive = async (r) => {
    setTogglingId(r.id);
    try {
      await axios.put(`${API}/reference-data/${r.id}`, { is_active: !r.is_active });
      toast.success(r.is_active ? `"${r.code}" deactivated` : `"${r.code}" activated`);
      fetchRows();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Update failed');
    } finally {
      setTogglingId(null);
    }
  };

  const deleteRow = async (id) => {
    try {
      await axios.delete(`${API}/reference-data/${id}`);
      toast.success('Entry deleted');
      setDeleteConfirm(null);
      fetchRows();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Delete failed');
    }
  };

  const createRow = async () => {
    if (!createData.category || !createData.code.trim() || !createData.name.trim()) {
      toast.error('Category, code and name are required');
      return;
    }
    setSaving(true);
    try {
      const fields = META_FIELDS[createData.category] || [];
      const payload = {
        category: createData.category, code: createData.code, name: createData.name, is_active: createData.is_active,
      };
      if (fields.length) {
        const metadata = {};
        fields.forEach(f => {
          const v = createData.meta[f.key];
          metadata[f.key] = f.numeric ? (v ? Number(v) : null) : (v || null);
        });
        payload.metadata = metadata;
      } else {
        payload.description = createData.description || null;
      }
      await axios.post(`${API}/reference-data/`, payload);
      toast.success('Entry created');
      setShowCreate(false);
      setCreateData({ category: activeCategory || '', code: '', name: '', description: '', is_active: true, meta: {} });
      fetchRows();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Creation failed');
    } finally {
      setSaving(false);
    }
  };

  const openCreate = () => {
    setCreateData({ category: activeCategory || categories[0] || '', code: '', name: '', description: '', is_active: true, meta: {} });
    setShowCreate(true);
  };

  const runImport = async () => {
    setImporting(true);
    try {
      const res = await axios.post(`${API}/reference-data/import`);
      const { currencies, countries } = res.data;
      toast.success(
        `Imported: currencies ${currencies.inserted} new / ${currencies.updated} updated, ` +
        `countries ${countries.inserted} new / ${countries.updated} updated`
      );
      fetchRows();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  const createFields = META_FIELDS[createData.category] || [];

  return (
    <Layout>
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div style={{ marginBottom: '2rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 style={{
              fontSize: '2.5rem', fontWeight: '800', margin: 0,
              background: 'linear-gradient(135deg, #06b6d4 0%, #667eea 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
            }}>
              🗂️ Reference Data
            </h1>
            <p style={{ color: '#a0a0a0', marginTop: '0.5rem' }}>
              Code lists Validation Rules check field values against (currencies, countries, charge codes) —
              {user?.is_admin ? ' edit here, no code change needed.' : ' read-only view, ask an admin to change a value.'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            {user?.is_admin && (
              <>
                <button onClick={openCreate} style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  padding: '10px 18px', background: 'rgba(16,185,129,0.15)',
                  border: '1px solid rgba(16,185,129,0.3)', borderRadius: '10px',
                  color: '#10b981', cursor: 'pointer', fontWeight: '600'
                }}>
                  <Plus size={16} /> New Entry
                </button>
                <button onClick={runImport} disabled={importing} style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  padding: '10px 18px', background: 'rgba(245,158,11,0.15)',
                  border: '1px solid rgba(245,158,11,0.3)', borderRadius: '10px',
                  color: '#f59e0b', cursor: importing ? 'not-allowed' : 'pointer', fontWeight: '600',
                  opacity: importing ? 0.6 : 1
                }} title="Import/update from lookup_currencies.csv and lookup_country_codes.csv">
                  <UploadCloud size={16} /> {importing ? 'Importing...' : 'Import Datasets'}
                </button>
              </>
            )}
            <button onClick={fetchRows} style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '10px 18px', background: 'rgba(167,139,250,0.15)',
              border: '1px solid rgba(167,139,250,0.3)', borderRadius: '10px',
              color: '#a78bfa', cursor: 'pointer', fontWeight: '600'
            }}>
              <RefreshCw size={16} /> Refresh
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
          {categories.map(cat => {
            const meta = CATEGORY_META[cat] || { label: cat, color: '#9ca3af' };
            const active = activeCategory === cat;
            return (
              <button key={cat} onClick={() => setActiveCategory(cat)} style={{
                padding: '10px 18px', borderRadius: '10px', fontWeight: '700', fontSize: '0.85rem', cursor: 'pointer',
                background: active ? `${meta.color}20` : 'rgba(255,255,255,0.03)',
                border: `1px solid ${active ? meta.color : 'rgba(255,255,255,0.08)'}`,
                color: active ? meta.color : '#9ca3af'
              }}>
                {meta.label} <span style={{ opacity: 0.6, fontWeight: '600' }}>({countFor(cat)})</span>
              </button>
            );
          })}
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
            placeholder="Search by code, name or metadata (e.g. symbol, ISO3)..."
            style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: 'white', fontSize: '0.9rem' }}
          />
          <span style={{ color: '#6b7280', fontSize: '0.8rem' }}>{filtered.length} entries</span>
        </div>

        <div style={{
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '16px', overflow: 'hidden'
        }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>Loading...</div>
          ) : filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>
              <Database size={40} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />
              No entries in this category yet.
            </div>
          ) : (
            <div style={{ overflowX: 'auto', overflowY: 'auto', maxHeight: '65vh' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                    {[
                      codeLabelFor(activeCategory), 'Name',
                      ...(metaFields.length ? metaFields.map(f => f.label) : ['Description']),
                      'Status', 'Last updated', user?.is_admin ? 'Actions' : ''
                    ].map((h, i) => (
                      <th key={`${h}-${i}`} style={{ textAlign: 'left', padding: '0.85rem 1rem', color: '#6b7280', fontSize: '0.78rem', textTransform: 'uppercase', whiteSpace: 'nowrap', position: 'sticky', top: 0, background: '#1a1a2e' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r, i) => {
                    const isEditing = editingId === r.id;
                    const fields = META_FIELDS[r.category] || [];
                    return (
                      <motion.tr key={r.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.02 }}
                        style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '0.75rem 1rem' }}>
                          {isEditing ? (
                            <input value={editData.code} onChange={e => setEditData({ ...editData, code: e.target.value.toUpperCase() })} style={{ ...inputStyle, width: '90px' }} />
                          ) : (
                            <span style={{ color: 'white', fontWeight: '700', fontSize: '0.85rem', fontFamily: 'monospace' }}>{r.code}</span>
                          )}
                        </td>
                        <td style={{ padding: '0.75rem 1rem' }}>
                          {isEditing ? (
                            <input value={editData.name} onChange={e => setEditData({ ...editData, name: e.target.value })} style={{ ...inputStyle, width: '100%' }} />
                          ) : (
                            <span style={{ color: '#d1d5db', fontSize: '0.85rem' }}>{r.name}</span>
                          )}
                        </td>
                        {fields.length ? (
                          fields.map(f => (
                            <td key={f.key} style={{ padding: '0.75rem 1rem' }}>
                              {isEditing ? (
                                <input value={editData[`meta_${f.key}`] ?? ''} placeholder={f.placeholder}
                                  onChange={e => setEditData({ ...editData, [`meta_${f.key}`]: e.target.value })}
                                  style={{ ...inputStyle, width: '90px' }} />
                              ) : (
                                <span style={{ color: '#9ca3af', fontSize: '0.8rem' }}>{r.metadata?.[f.key] ?? '—'}</span>
                              )}
                            </td>
                          ))
                        ) : (
                          <td style={{ padding: '0.75rem 1rem', maxWidth: '260px' }}>
                            {isEditing ? (
                              <input value={editData.description} onChange={e => setEditData({ ...editData, description: e.target.value })}
                                placeholder="Optional" style={{ ...inputStyle, width: '100%' }} />
                            ) : (
                              <span style={{ color: '#9ca3af', fontSize: '0.8rem' }}>{r.description || '—'}</span>
                            )}
                          </td>
                        )}
                        <td style={{ padding: '0.75rem 1rem' }}>
                          {isEditing ? (
                            <button onClick={() => setEditData({ ...editData, is_active: !editData.is_active })} style={iconBtnStyle(editData.is_active ? '#10b981' : '#6b7280', false)}>
                              {editData.is_active ? <Check size={14} /> : <X size={14} />}
                            </button>
                          ) : (
                            <span style={{
                              display: 'inline-flex', alignItems: 'center', gap: '5px',
                              padding: '2px 10px', borderRadius: '999px', fontSize: '0.72rem', fontWeight: '700',
                              background: r.is_active ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.12)',
                              color: r.is_active ? '#6ee7b7' : '#fca5a5'
                            }}>
                              <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: r.is_active ? '#10b981' : '#ef4444' }} />
                              {r.is_active ? 'Active' : 'Inactive'}
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '0.75rem 1rem', color: '#6b7280', fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
                          {r.updated_by_username ? (
                            <>
                              <div>{r.updated_by_username}</div>
                              {r.updated_at && <div style={{ fontSize: '0.7rem', opacity: 0.7 }}>{new Date(r.updated_at).toLocaleString()}</div>}
                            </>
                          ) : '—'}
                        </td>
                        {user?.is_admin && (
                          <td style={{ padding: '0.75rem 1rem' }}>
                            {isEditing ? (
                              <div style={{ display: 'flex', gap: '6px' }}>
                                <button onClick={() => saveEdit(r.id)} disabled={saving} style={iconBtnStyle('#10b981', saving)}><Save size={14} /></button>
                                <button onClick={cancelEdit} disabled={saving} style={iconBtnStyle('#6b7280', saving)}><X size={14} /></button>
                              </div>
                            ) : deleteConfirm === r.id ? (
                              <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                                <span style={{ color: '#ef4444', fontSize: '0.75rem' }}>Delete?</span>
                                <button onClick={() => deleteRow(r.id)} style={iconBtnStyle('#ef4444', false)}><Trash2 size={14} /></button>
                                <button onClick={() => setDeleteConfirm(null)} style={iconBtnStyle('#6b7280', false)}><X size={14} /></button>
                              </div>
                            ) : (
                              <div style={{ display: 'flex', gap: '6px' }}>
                                <button onClick={() => toggleActive(r)} disabled={togglingId === r.id || !!editingId}
                                  title={r.is_active ? 'Deactivate' : 'Activate'}
                                  style={iconBtnStyle(r.is_active ? '#f59e0b' : '#10b981', togglingId === r.id || !!editingId)}>
                                  <Power size={14} />
                                </button>
                                <button onClick={() => startEdit(r)} disabled={!!editingId} style={iconBtnStyle('#a78bfa', !!editingId)}><Edit2 size={14} /></button>
                                <button onClick={() => setDeleteConfirm(r.id)} disabled={!!editingId} style={iconBtnStyle('#ef4444', !!editingId)}><Trash2 size={14} /></button>
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
                ➕ New Reference Data Entry
              </h2>

              <label style={labelStyle}>Category *</label>
              <select value={createData.category}
                onChange={e => setCreateData({ ...createData, category: e.target.value, meta: {} })}
                style={{ ...inputStyle, width: '100%', marginBottom: '1rem' }}>
                {categories.map(c => <option key={c} value={c}>{(CATEGORY_META[c] || { label: c }).label}</option>)}
              </select>

              <label style={labelStyle}>{codeLabelFor(createData.category)} *</label>
              <input value={createData.code} onChange={e => setCreateData({ ...createData, code: e.target.value.toUpperCase() })}
                placeholder="e.g. EUR" style={{ ...inputStyle, width: '100%', marginBottom: '1rem' }} />

              <label style={labelStyle}>Name *</label>
              <input value={createData.name} onChange={e => setCreateData({ ...createData, name: e.target.value })}
                placeholder="e.g. Euro" style={{ ...inputStyle, width: '100%', marginBottom: '1rem' }} />

              {createFields.length ? (
                createFields.map(f => (
                  <div key={f.key}>
                    <label style={labelStyle}>{f.label}</label>
                    <input value={createData.meta[f.key] || ''} placeholder={f.placeholder}
                      onChange={e => setCreateData({ ...createData, meta: { ...createData.meta, [f.key]: e.target.value } })}
                      style={{ ...inputStyle, width: '100%', marginBottom: '1rem' }} />
                  </div>
                ))
              ) : (
                <>
                  <label style={labelStyle}>Description</label>
                  <input value={createData.description} onChange={e => setCreateData({ ...createData, description: e.target.value })}
                    placeholder="e.g. Euro, official currency of the European Union" style={{ ...inputStyle, width: '100%', marginBottom: '1rem' }} />
                </>
              )}

              <label style={{ ...labelStyle, display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                <input type="checkbox" checked={createData.is_active} onChange={e => setCreateData({ ...createData, is_active: e.target.checked })} />
                Active
              </label>

              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
                <button onClick={() => setShowCreate(false)} style={{
                  padding: '0.6rem 1.2rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.15)',
                  background: 'none', color: '#9ca3af', cursor: 'pointer', fontWeight: '600'
                }}>Cancel</button>
                <button onClick={createRow} disabled={saving} style={{
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

export default ReferenceDataPage;
