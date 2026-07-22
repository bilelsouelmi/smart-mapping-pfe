import { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Play, Plus, Trash2, Edit2, ArrowRight, FolderOpen, Globe, Wifi,
         CheckCircle, XCircle, Clock, Zap, RefreshCw } from 'lucide-react';
import Layout from '../components/Layout';
import API_BASE_URL from '../config/api';

const API = `${API_BASE_URL}/api`;

const TRANSPORT_ICONS = { FILE: FolderOpen, REST: Globe, RABBITMQ: Wifi };
const TRANSPORT_COLORS = { FILE: '#10b981', REST: '#06b6d4', RABBITMQ: '#f59e0b' };

const EMPTY_FORM = { name: '', config_in_id: '', mapping_id: '', config_out_id: '', description: '', is_active: true };

const ConsommationPage = () => {
  const [configs, setConfigs] = useState([]);
  const [mappings, setMappings] = useState([]);
  const [pipelines, setPipelines] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState({});
  const [results, setResults] = useState({});

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const [cfgRes, mapRes, pipRes] = await Promise.all([
        axios.get(`${API}/configs/`),
        axios.get(`${API}/mappings/`),
        axios.get(`${API}/consommation/`)
      ]);
      setConfigs(cfgRes.data);
      setMappings(mapRes.data);
      setPipelines(pipRes.data);
    } catch (e) { console.error(e); }
  };

  const openCreateForm = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
  };

  const openEditForm = (pipeline) => {
    setEditingId(pipeline.id);
    setForm({
      name: pipeline.name || '',
      config_in_id: String(pipeline.config_in_id || ''),
      mapping_id: String(pipeline.mapping_id || ''),
      config_out_id: String(pipeline.config_out_id || ''),
      description: pipeline.description || '',
      is_active: pipeline.is_active ?? true
    });
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!form.name || !form.config_in_id || !form.mapping_id || !form.config_out_id) return;
    setSaving(true);
    const payload = {
      name: form.name,
      config_in_id: parseInt(form.config_in_id),
      mapping_id: parseInt(form.mapping_id),
      config_out_id: parseInt(form.config_out_id),
      description: form.description || null,
      is_active: form.is_active
    };
    try {
      if (editingId) {
        await axios.put(`${API}/consommation/${editingId}`, payload);
      } else {
        await axios.post(`${API}/consommation/`, payload);
      }
      await fetchData();
      setForm(EMPTY_FORM);
      setEditingId(null);
      setShowForm(false);
    } catch (e) {
      alert(e.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this pipeline?')) return;
    await axios.delete(`${API}/consommation/${id}`);
    await fetchData();
  };

  const handleRun = async (pipeline) => {
    setRunning(prev => ({ ...prev, [pipeline.id]: true }));
    setResults(prev => ({ ...prev, [pipeline.id]: { status: 'running', message: 'Pipeline en cours...' } }));
    try {
      const r = await axios.post(`${API}/consommation/${pipeline.id}/run`);
      setResults(prev => ({ ...prev, [pipeline.id]: {
        status: r.data.status,
        message: r.data.message,
        steps: r.data.steps,
        timestamp: new Date().toLocaleTimeString()
      }}));
    } catch (e) {
      setResults(prev => ({ ...prev, [pipeline.id]: {
        status: 'error',
        message: e.response?.data?.detail || e.message,
        timestamp: new Date().toLocaleTimeString()
      }}));
    }
    setRunning(prev => ({ ...prev, [pipeline.id]: false }));
  };

  const configsIn = configs.filter(c => c.direction === 'IN');
  const configsOut = configs.filter(c => c.direction === 'OUT');
  const isEditing = editingId !== null;

  return (
    <Layout>
      <div style={{
        minHeight: 'calc(100vh - 100px)',
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
        padding: '2rem', marginTop: '-2rem', marginLeft: '-2rem', marginRight: '-2rem',
      }}>
        <div style={{ maxWidth: '1100px', margin: '0 auto' }}>

          {/* Header */}
          <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}
            style={{ marginBottom: '2rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <h1 style={{
                fontSize: '2.5rem', fontWeight: '800',
                background: 'linear-gradient(135deg, #f59e0b 0%, #10b981 100%)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', marginBottom: '0.25rem'
              }}>
                ⚡ Consommation
              </h1>
              <p style={{ color: '#a0a0a0', fontSize: '1rem' }}>
                Configurer et exécuter les pipelines de consommation
              </p>
            </div>
            <button onClick={openCreateForm} style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '10px 20px',
              background: 'linear-gradient(135deg, #f59e0b 0%, #10b981 100%)',
              border: 'none', borderRadius: '10px', color: 'white',
              fontWeight: '700', cursor: 'pointer', fontSize: '0.95rem'
            }}>
              <Plus size={18} /> Nouveau Pipeline
            </button>
          </motion.div>

          {/* Pipeline list */}
          {pipelines.length === 0 ? (
            <GlassCard>
              <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>
                <Zap size={48} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />
                <div>No pipelines yet. Click <strong>Nouveau Pipeline</strong> to create one.</div>
              </div>
            </GlassCard>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {pipelines.map(pipeline => {
                const cfgIn = { name: pipeline.config_in_name, transport_type: pipeline.config_in_type };
                const mapping = mappings.find(m => m.id === pipeline.mapping_id) || { name: pipeline.mapping_name };
                const cfgOut = { name: pipeline.config_out_name, transport_type: pipeline.config_out_type };
                const result = results[pipeline.id];
                const isRunning = running[pipeline.id];

                return (
                  <motion.div key={pipeline.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
                    <GlassCard>
                      {/* Pipeline name */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <Zap size={20} color="#f59e0b" />
                          <span style={{ color: 'white', fontWeight: '800', fontSize: '1.1rem' }}>
                            {pipeline.name}
                          </span>
                          {!pipeline.is_active && (
                            <span style={{
                              padding: '2px 8px', borderRadius: '4px', fontSize: '10px',
                              background: 'rgba(107,114,128,0.2)', color: '#6b7280', fontWeight: '700'
                            }}>Inactive</span>
                          )}
                        </div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button onClick={() => handleRun(pipeline)} disabled={isRunning}
                            style={{
                              display: 'flex', alignItems: 'center', gap: '6px',
                              padding: '8px 20px',
                              background: isRunning
                                ? 'rgba(16,185,129,0.2)'
                                : 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
                              border: 'none', borderRadius: '8px', color: 'white',
                              fontWeight: '700', cursor: isRunning ? 'not-allowed' : 'pointer',
                              fontSize: '0.9rem'
                            }}>
                            {isRunning
                              ? <><RefreshCw size={14} style={{ animation: 'spin 1s linear infinite' }} /> Running...</>
                              : <><Play size={14} /> Start</>}
                          </button>
                          <button onClick={() => openEditForm(pipeline)} style={{
                            width: '34px', height: '34px', borderRadius: '8px',
                            background: 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.3)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            cursor: 'pointer'
                          }}>
                            <Edit2 size={14} color="#a78bfa" />
                          </button>
                          <button onClick={() => handleDelete(pipeline.id)} style={{
                            width: '34px', height: '34px', borderRadius: '8px',
                            background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            cursor: 'pointer'
                          }}>
                            <Trash2 size={14} color="#ef4444" />
                          </button>
                        </div>
                      </div>

                      {pipeline.description && (
                        <div style={{ color: '#6b7280', fontSize: '0.82rem', marginBottom: '1rem', marginTop: '-0.5rem' }}>
                          {pipeline.description}
                        </div>
                      )}

                      {/* Pipeline flow */}
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: '0.75rem',
                        flexWrap: 'wrap'
                      }}>
                        {/* Config IN */}
                        <PipelineNode
                          label="Config IN"
                          name={cfgIn?.name || 'Unknown'}
                          badge={cfgIn?.transport_type}
                          color={TRANSPORT_COLORS[cfgIn?.transport_type] || '#6b7280'}
                          Icon={TRANSPORT_ICONS[cfgIn?.transport_type] || FolderOpen}
                        />

                        <AnimatedArrow />

                        {/* Mapping */}
                        <PipelineNode
                          label="Mapping"
                          name={mapping?.name || 'Unknown'}
                          badge={`${mapping?.source || ''} → ${mapping?.target?.split('.')[0] || ''}`}
                          color="#a78bfa"
                          Icon={Zap}
                        />

                        <AnimatedArrow />

                        {/* Config OUT */}
                        <PipelineNode
                          label="Config OUT"
                          name={cfgOut?.name || 'Unknown'}
                          badge={cfgOut?.transport_type}
                          color={TRANSPORT_COLORS[cfgOut?.transport_type] || '#6b7280'}
                          Icon={TRANSPORT_ICONS[cfgOut?.transport_type] || FolderOpen}
                        />
                      </div>

                      {/* Result */}
                      {result && (
                        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                          style={{ marginTop: '1rem' }}>
                          {/* Overall status */}
                          <div style={{
                            padding: '10px 14px', borderRadius: '8px', marginBottom: '8px',
                            background: result.status === 'success' ? 'rgba(16,185,129,0.1)'
                              : result.status === 'error' ? 'rgba(239,68,68,0.1)'
                              : result.status === 'running' ? 'rgba(6,182,212,0.1)'
                              : 'rgba(245,158,11,0.1)',
                            border: `1px solid ${result.status === 'success' ? 'rgba(16,185,129,0.3)'
                              : result.status === 'error' ? 'rgba(239,68,68,0.3)'
                              : result.status === 'running' ? 'rgba(6,182,212,0.3)'
                              : 'rgba(245,158,11,0.3)'}`,
                            display: 'flex', alignItems: 'center', gap: '8px'
                          }}>
                            {result.status === 'success' ? <CheckCircle size={16} color="#10b981" />
                              : result.status === 'error' ? <XCircle size={16} color="#ef4444" />
                              : result.status === 'running' ? <RefreshCw size={16} color="#06b6d4" style={{animation:'spin 1s linear infinite'}} />
                              : <Clock size={16} color="#f59e0b" />}
                            <span style={{
                              color: result.status === 'success' ? '#10b981'
                                : result.status === 'error' ? '#ef4444'
                                : result.status === 'running' ? '#06b6d4' : '#f59e0b',
                              fontSize: '0.9rem', fontWeight: '600'
                            }}>
                              {result.message}
                            </span>
                            {result.timestamp && (
                              <span style={{ color: '#6b7280', fontSize: '0.8rem', marginLeft: 'auto' }}>
                                {result.timestamp}
                              </span>
                            )}
                          </div>
                          {/* Step details */}
                          {result.steps && result.steps.map((step, idx) => (
                            <div key={idx} style={{
                              padding: '8px 12px', borderRadius: '6px', marginBottom: '4px',
                              background: 'rgba(0,0,0,0.2)',
                              display: 'flex', alignItems: 'center', gap: '8px'
                            }}>
                              {step.status === 'ok' ? <CheckCircle size={13} color="#10b981" />
                                : step.status === 'error' ? <XCircle size={13} color="#ef4444" />
                                : <Clock size={13} color="#f59e0b" />}
                              <span style={{ color: '#a78bfa', fontSize: '11px', fontWeight: '700', minWidth: '80px' }}>
                                {step.step}
                              </span>
                              <span style={{ color: '#d1d5db', fontSize: '12px' }}>{step.message}</span>
                            </div>
                          ))}
                        </motion.div>
                      )}
                    </GlassCard>
                  </motion.div>
                );
              })}
            </div>
          )}

          {/* Form Modal — used for both Create and Edit */}
          <AnimatePresence>
            {showForm && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                style={{
                  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  zIndex: 1000, padding: '1rem'
                }}
                onClick={e => e.target === e.currentTarget && setShowForm(false)}>
                <motion.div initial={{ scale: 0.9 }} animate={{ scale: 1 }}
                  style={{
                    background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '16px', padding: '2rem', width: '100%', maxWidth: '500px',
                    maxHeight: '90vh', overflowY: 'auto'
                  }}>
                  <h2 style={{ color: 'white', fontWeight: '800', marginBottom: '1.5rem' }}>
                    {isEditing ? '✏️ Edit Pipeline' : '⚡ Nouveau Pipeline'}
                  </h2>

                  <div style={{ marginBottom: '1rem' }}>
                    <label style={{ color: '#9ca3af', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>
                      Pipeline Name *
                    </label>
                    <input value={form.name} onChange={e => setForm({...form, name: e.target.value})}
                      placeholder="e.g. MT103 → pacs.008 Pipeline"
                      style={inputStyle} />
                  </div>

                  <div style={{ marginBottom: '1rem' }}>
                    <label style={{ color: '#10b981', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>
                      ① Config IN *
                    </label>
                    <select value={form.config_in_id} onChange={e => setForm({...form, config_in_id: e.target.value})}
                      style={inputStyle}>
                      <option value="">— Select Config IN —</option>
                      {configsIn.map(c => (
                        <option key={c.id} value={c.id}>{c.name} ({c.transport_type})</option>
                      ))}
                    </select>
                  </div>

                  <div style={{ marginBottom: '1rem' }}>
                    <label style={{ color: '#a78bfa', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>
                      ② Mapping *
                    </label>
                    <select value={form.mapping_id} onChange={e => setForm({...form, mapping_id: e.target.value})}
                      style={inputStyle}>
                      <option value="">— Select Mapping —</option>
                      {mappings.map(m => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                      ))}
                    </select>
                  </div>

                  <div style={{ marginBottom: '1rem' }}>
                    <label style={{ color: '#06b6d4', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>
                      ③ Config OUT *
                    </label>
                    <select value={form.config_out_id} onChange={e => setForm({...form, config_out_id: e.target.value})}
                      style={inputStyle}>
                      <option value="">— Select Config OUT —</option>
                      {configsOut.map(c => (
                        <option key={c.id} value={c.id}>{c.name} ({c.transport_type})</option>
                      ))}
                    </select>
                  </div>

                  <div style={{ marginBottom: '1rem' }}>
                    <label style={{ color: '#9ca3af', fontSize: '0.8rem', display: 'block', marginBottom: '4px' }}>
                      Description
                    </label>
                    <input value={form.description} onChange={e => setForm({...form, description: e.target.value})}
                      placeholder="Optional description"
                      style={inputStyle} />
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1.5rem' }}>
                    <input type="checkbox" checked={form.is_active}
                      onChange={e => setForm({...form, is_active: e.target.checked})}
                      id="pipeline-active" style={{ width: '16px', height: '16px', cursor: 'pointer' }} />
                    <label htmlFor="pipeline-active" style={{ color: '#a0a0a0', cursor: 'pointer', fontSize: '0.85rem' }}>
                      Active
                    </label>
                  </div>

                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                    <button onClick={() => { setShowForm(false); setEditingId(null); }} style={{
                      padding: '10px 20px', background: 'rgba(255,255,255,0.05)',
                      border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px',
                      color: '#9ca3af', cursor: 'pointer'
                    }}>Cancel</button>
                    <button onClick={handleSave}
                      disabled={saving || !form.name || !form.config_in_id || !form.mapping_id || !form.config_out_id}
                      style={{
                        padding: '10px 24px',
                        background: 'linear-gradient(135deg, #f59e0b 0%, #10b981 100%)',
                        border: 'none', borderRadius: '8px', color: 'white',
                        fontWeight: '700', cursor: 'pointer',
                        opacity: (saving || !form.name || !form.config_in_id || !form.mapping_id || !form.config_out_id) ? 0.5 : 1
                      }}>
                      {saving ? 'Saving...' : isEditing ? 'Update Pipeline' : 'Créer Pipeline'}
                    </button>
                  </div>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <style>{`
          @keyframes spin { to { transform: rotate(360deg); } }
          select option { background: #1e2a3a !important; color: white !important; }
        `}</style>
      </div>
    </Layout>
  );
};

const PipelineNode = ({ label, name, badge, color, Icon }) => (
  <div style={{
    background: `${color}10`, border: `1px solid ${color}30`,
    borderRadius: '12px', padding: '12px 16px', minWidth: '160px', flex: 1
  }}>
    <div style={{ color: '#6b7280', fontSize: '10px', fontWeight: '700',
      textTransform: 'uppercase', marginBottom: '6px' }}>{label}</div>
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
      <Icon size={14} color={color} />
      <span style={{ color: 'white', fontWeight: '700', fontSize: '0.9rem' }}>{name}</span>
    </div>
    {badge && (
      <span style={{
        padding: '2px 6px', borderRadius: '4px', fontSize: '10px',
        background: `${color}20`, color, fontWeight: '700'
      }}>{badge}</span>
    )}
  </div>
);

const AnimatedArrow = () => (
  <motion.div animate={{ x: [0, 5, 0] }} transition={{ repeat: Infinity, duration: 1.5 }}>
    <ArrowRight size={20} color="#4b5563" />
  </motion.div>
);

const GlassCard = ({ children }) => (
  <div style={{
    background: 'rgba(255,255,255,0.05)', backdropFilter: 'blur(10px)',
    borderRadius: '16px', padding: '1.5rem',
    border: '1px solid rgba(255,255,255,0.1)',
    boxShadow: '0 8px 32px rgba(0,0,0,0.3)'
  }}>{children}</div>
);

const inputStyle = {
  width: '100%', padding: '10px 12px', background: '#1e2a3a',
  border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px',
  color: 'white', fontSize: '0.9rem', boxSizing: 'border-box', outline: 'none'
};

export default ConsommationPage;