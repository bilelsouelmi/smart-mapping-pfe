import { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Trash2, Edit2, Play, Settings,
         ArrowDownCircle, ArrowUpCircle, Wifi, FolderOpen, Globe, Zap } from 'lucide-react';
import Layout from '../components/Layout';
import PasswordInput from '../components/PasswordInput';
import API_BASE_URL from '../config/api';

const API = `${API_BASE_URL}/api`;

const TRANSPORT_ICONS = {
  FILE:     FolderOpen,
  REST:     Globe,
  RABBITMQ: Wifi,
  KAFKA:    Zap,
};

const TRANSPORT_COLORS = {
  FILE:     '#10b981',
  REST:     '#06b6d4',
  RABBITMQ: '#f59e0b',
  KAFKA:    '#a78bfa',
};

// NOTE: mapping is intentionally NOT configured here. A TransportConfig
// (Config IN/OUT) is a reusable transport definition (folder, REST URL,
// queue...) independent of any specific mapping. The Mapping is chosen
// once, at the Pipeline (Consommation) level, where Config IN + Mapping +
// Config OUT are combined. Keeping mapping_id off this form avoids
// hardcoding a config to a single mapping and keeps configs reusable
// across multiple pipelines.
const EMPTY_FORM = {
  name: '', direction: 'IN', transport_type: 'FILE',
  description: '', is_active: true,
  // FILE
  file_path: '', file_pattern: '*.txt', file_output_path: '',
  // REST
  rest_url: '', rest_method: 'POST', rest_auth_type: 'NONE', rest_auth_value: '',
  // RabbitMQ
  rabbitmq_host: 'localhost', rabbitmq_port: 5672, rabbitmq_vhost: '/',
  rabbitmq_username: 'guest', rabbitmq_password: 'guest',
  rabbitmq_queue: '', rabbitmq_exchange: '', rabbitmq_routing_key: '',
  // Kafka
  kafka_bootstrap_servers: 'kafka:9092', kafka_topic: '',
  kafka_group_id: 'smart-mapping-group', kafka_security_protocol: 'PLAINTEXT',
  kafka_sasl_mechanism: 'PLAIN', kafka_sasl_username: '', kafka_sasl_password: '',
};

const ConfigPage = () => {
  const [configs, setConfigs]       = useState([]);
  const [showForm, setShowForm]     = useState(false);
  const [form, setForm]             = useState(EMPTY_FORM);
  const [editId, setEditId]         = useState(null);
  const [loading, setLoading]       = useState(false);
  const [testResults, setTestResults] = useState({});
  const [activeTab, setActiveTab]   = useState('IN');

  useEffect(() => { fetchConfigs(); }, []);

  const fetchConfigs = async () => {
    try { const r = await axios.get(`${API}/configs/`); setConfigs(r.data); }
    catch (e) { console.error(e); }
  };

  const handleSubmit = async () => {
    if (!form.name || !form.transport_type) return;
    if (form.transport_type === 'RABBITMQ' && (!form.rabbitmq_username || !form.rabbitmq_password || !form.rabbitmq_queue)) {
      alert('RabbitMQ: Username, Password and Queue Name are required'); return;
    }
    if (form.transport_type === 'FILE' && form.direction === 'IN' && !form.file_path) {
      alert('File System: Input Folder Path is required'); return;
    }
    if (form.transport_type === 'KAFKA' && (!form.kafka_bootstrap_servers || !form.kafka_topic)) {
      alert('Kafka: Bootstrap Servers and Topic are required'); return;
    }
    if (form.transport_type === 'REST' && !form.rest_url) {
      alert('REST: URL is required'); return;
    }
    setLoading(true);
    try {
      const payload = { ...form };
      if (editId) { await axios.put(`${API}/configs/${editId}`, payload); }
      else        { await axios.post(`${API}/configs/`, payload); }
      fetchConfigs();
      setShowForm(false);
      setForm(EMPTY_FORM);
      setEditId(null);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const handleEdit = (config) => {
    setForm({ ...EMPTY_FORM, ...config });
    setEditId(config.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this configuration?')) return;
    await axios.delete(`${API}/configs/${id}`);
    fetchConfigs();
  };

  const handleTest = async (id) => {
    setTestResults(prev => ({ ...prev, [id]: { status: 'testing' } }));
    try {
      const r = await axios.post(`${API}/configs/${id}/test`);
      setTestResults(prev => ({ ...prev, [id]: r.data }));
    } catch (e) {
      setTestResults(prev => ({ ...prev, [id]: { status: 'error', message: e.message } }));
    }
  };

  const handleTrigger = async (id) => {
    try {
      const r = await axios.post(`${API}/configs/${id}/trigger`);
      alert(`✅ ${r.data.message}`);
    } catch (e) {
      alert(`❌ ${e.response?.data?.detail || e.message}`);
    }
  };

  const filtered = configs.filter(c => c.direction === activeTab);

  return (
    <Layout>
      <GlobalStyle />
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
                background: 'linear-gradient(135deg, #a78bfa 0%, #06b6d4 100%)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', marginBottom: '0.25rem'
              }}>
                ⚙️ Configuration
              </h1>
              <p style={{ color: '#a0a0a0', fontSize: '1rem' }}>
                Configure how files are consumed (IN) and produced (OUT)
              </p>
            </div>
            <button onClick={() => { 
                setForm({...EMPTY_FORM, direction: activeTab}); 
                setEditId(null); 
                setShowForm(true); 
              }}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '10px 20px',
                background: 'linear-gradient(135deg, #a78bfa 0%, #06b6d4 100%)',
                border: 'none', borderRadius: '10px', color: 'white',
                fontWeight: '700', cursor: 'pointer', fontSize: '0.95rem'
              }}>
              <Plus size={18} /> New Config
            </button>
          </motion.div>

          {/* Tabs */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '1.5rem' }}>
            {['IN', 'OUT'].map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)} style={{
                padding: '10px 28px',
                background: activeTab === tab
                  ? tab === 'IN' ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'
                  : 'rgba(255,255,255,0.05)',
                border: `1px solid ${activeTab === tab ? (tab === 'IN' ? '#10b981' : '#ef4444') : 'rgba(255,255,255,0.1)'}`,
                borderRadius: '8px',
                color: activeTab === tab ? (tab === 'IN' ? '#10b981' : '#ef4444') : '#6b7280',
                fontWeight: '700', cursor: 'pointer', fontSize: '0.95rem',
                display: 'flex', alignItems: 'center', gap: '6px'
              }}>
                {tab === 'IN' ? <ArrowDownCircle size={16}/> : <ArrowUpCircle size={16}/>}
                Config {tab}
                <span style={{
                  background: activeTab === tab ? (tab === 'IN' ? '#10b981' : '#ef4444') : '#374151',
                  color: 'white', borderRadius: '999px', padding: '1px 8px', fontSize: '12px'
                }}>
                  {configs.filter(c => c.direction === tab).length}
                </span>
              </button>
            ))}
          </div>

          {/* Config list */}
          {filtered.length === 0 ? (
            <GlassCard>
              <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>
                <Settings size={48} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />
                <div>No {activeTab} configurations yet. Click <strong>New Config</strong> to add one.</div>
              </div>
            </GlassCard>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxHeight: '65vh', overflowY: 'auto' }}>
              {filtered.map(config => {
                const Icon  = TRANSPORT_ICONS[config.transport_type] || Settings;
                const color = TRANSPORT_COLORS[config.transport_type] || '#6b7280';
                const test  = testResults[config.id];
                return (
                  <motion.div key={config.id} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
                    <GlassCard>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <div style={{
                          width: '44px', height: '44px', borderRadius: '10px',
                          background: `${color}20`, border: `1px solid ${color}40`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                        }}>
                          <Icon size={20} color={color} />
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                            <span style={{ color: 'white', fontWeight: '700', fontSize: '1rem' }}>
                              {config.name}
                            </span>
                            <span style={{
                              padding: '2px 8px', borderRadius: '4px', fontSize: '11px',
                              fontWeight: '700', background: `${color}20`, color
                            }}>
                              {config.transport_type}
                            </span>
                            {!config.is_active && (
                              <span style={{
                                padding: '2px 8px', borderRadius: '4px', fontSize: '11px',
                                background: 'rgba(107,114,128,0.2)', color: '#6b7280'
                              }}>Inactive</span>
                            )}
                          </div>
                          <div style={{ color: '#6b7280', fontSize: '0.85rem', marginTop: '2px' }}>
                            {config.transport_type === 'FILE'     && (config.file_path || config.file_output_path)}
                            {config.transport_type === 'REST'     && config.rest_url}
                            {config.transport_type === 'RABBITMQ' && `${config.rabbitmq_host}:${config.rabbitmq_port} → ${config.rabbitmq_queue}`}
                            {config.transport_type === 'KAFKA'    && `${config.kafka_bootstrap_servers} → ${config.kafka_topic}`}
                          </div>
                          {test && (
                            <div style={{
                              marginTop: '4px', fontSize: '12px',
                              color: test.status === 'ok' ? '#10b981' : test.status === 'warning' ? '#f59e0b' : '#ef4444'
                            }}>
                              {test.status === 'testing' ? '⏳ Testing...' :
                               test.status === 'ok'      ? `✅ ${test.message}` :
                               test.status === 'warning' ? `⚠️ ${test.message}` :
                                                           `❌ ${test.message}`}
                            </div>
                          )}
                        </div>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <IconBtn icon={Wifi}   color="#06b6d4" title="Test"    onClick={() => handleTest(config.id)} />
                          {config.direction === 'IN' && (
                            <IconBtn icon={Play} color="#10b981" title="Trigger" onClick={() => handleTrigger(config.id)} />
                          )}
                          <IconBtn icon={Edit2}  color="#a78bfa" title="Edit"    onClick={() => handleEdit(config)} />
                          <IconBtn icon={Trash2} color="#ef4444" title="Delete"  onClick={() => handleDelete(config.id)} />
                        </div>
                      </div>
                    </GlassCard>
                  </motion.div>
                );
              })}
            </div>
          )}

          {/* Form Modal */}
          <AnimatePresence>
            {showForm && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                style={{
                  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  zIndex: 1000, padding: '1rem'
                }}
                onClick={e => e.target === e.currentTarget && setShowForm(false)}>
                <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                  style={{
                    background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '16px', padding: '2rem', width: '100%', maxWidth: '620px',
                    maxHeight: '90vh', overflowY: 'auto'
                  }}>
                  <h2 style={{ color: 'white', fontWeight: '800', marginBottom: '1.5rem', fontSize: '1.3rem' }}>
                    {editId ? '✏️ Edit Configuration' : '➕ New Configuration'}
                  </h2>

                  {/* Basic fields */}
                  <div style={{ marginBottom: '1rem' }}>
                    <FormField label="Name *">
                      <input value={form.name} onChange={e => setForm({...form, name: e.target.value})}
                        placeholder="e.g. MT103 Input" style={inputStyle} />
                    </FormField>
                  </div>

                  {/* Transport Type — full width now that Mapping field is removed.
                      Mapping is selected at the Pipeline (Consommation) level instead,
                      keeping this Config reusable across multiple pipelines. */}
                  <FormField label="Transport Type *">
                    <select value={form.transport_type}
                      onChange={e => setForm({...form, transport_type: e.target.value})} style={inputStyle}>
                      <option value="FILE">📁 File System</option>
                      <option value="REST">🌐 REST Web Service</option>
                      <option value="RABBITMQ">🐇 RabbitMQ</option>
                      <option value="KAFKA">⚡ Apache Kafka</option>
                    </select>
                  </FormField>

                  <FormField label="Description">
                    <input value={form.description} onChange={e => setForm({...form, description: e.target.value})}
                      placeholder="Optional description" style={inputStyle} />
                  </FormField>

                  {/* ── FILE fields ── */}
                  {form.transport_type === 'FILE' && (
                    <div style={sectionStyle('#10b981')}>
                      <div style={sectionTitle('#10b981')}>📁 File System Configuration</div>
                      <FormField label={form.direction === 'IN' ? 'Input Folder Path *' : 'Output Folder Path *'}>
                        <input
                          value={form.direction === 'IN' ? form.file_path : form.file_output_path}
                          onChange={e => setForm({
                            ...form,
                            [form.direction === 'IN' ? 'file_path' : 'file_output_path']: e.target.value
                          })}
                          placeholder="/app/uploads/in/mt103"
                          style={inputStyle}
                        />
                      </FormField>
                      {form.direction === 'IN' && (
                        <FormField label="File Pattern">
                          <select value={form.file_pattern}
                            onChange={e => setForm({...form, file_pattern: e.target.value})}
                            style={inputStyle}>
                            <option value="*.txt">*.txt — SWIFT MT → ISO 20022 XML</option>
                            <option value="*.xml">*.xml — ISO 20022 XML → SWIFT MT</option>
                          </select>
                        </FormField>
                      )}
                    </div>
                  )}

                  {/* ── REST fields ── */}
                  {form.transport_type === 'REST' && (
                    <div style={sectionStyle('#06b6d4')}>
                      <div style={sectionTitle('#06b6d4')}>🌐 REST Web Service Configuration</div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px', gap: '8px' }}>
                        <FormField label="URL *">
                          <input value={form.rest_url}
                            onChange={e => setForm({...form, rest_url: e.target.value})}
                            placeholder="https://api.example.com/swift/receive"
                            style={inputStyle} />
                        </FormField>
                        <FormField label="Method">
                          <select value={form.rest_method}
                            onChange={e => setForm({...form, rest_method: e.target.value})} style={inputStyle}>
                            <option value="POST">POST</option>
                            <option value="PUT">PUT</option>
                            <option value="PATCH">PATCH</option>
                            <option value="GET">GET</option>
                          </select>
                        </FormField>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                        <FormField label="Authentication">
                          <select value={form.rest_auth_type}
                            onChange={e => setForm({...form, rest_auth_type: e.target.value})} style={inputStyle}>
                            <option value="NONE">None</option>
                            <option value="BEARER">Bearer Token</option>
                            <option value="BASIC">Basic Auth</option>
                          </select>
                        </FormField>
                        {form.rest_auth_type !== 'NONE' && (
                          <FormField label="Auth Value">
                            <input value={form.rest_auth_value}
                              onChange={e => setForm({...form, rest_auth_value: e.target.value})}
                              placeholder={form.rest_auth_type === 'BEARER' ? 'your-token' : 'user:password'}
                              style={inputStyle} />
                          </FormField>
                        )}
                      </div>
                    </div>
                  )}

                  {/* ── RabbitMQ fields ── */}
                  {form.transport_type === 'RABBITMQ' && (
                    <div style={sectionStyle('#f59e0b')}>
                      <div style={sectionTitle('#f59e0b')}>🐇 RabbitMQ Configuration</div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 80px', gap: '8px' }}>
                        <FormField label="Host">
                          <input value={form.rabbitmq_host}
                            onChange={e => setForm({...form, rabbitmq_host: e.target.value})}
                            placeholder="rabbitmq" style={inputStyle} />
                        </FormField>
                        <FormField label="Port">
                          <input type="number" value={form.rabbitmq_port}
                            onChange={e => setForm({...form, rabbitmq_port: parseInt(e.target.value)})}
                            style={inputStyle} />
                        </FormField>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                        <FormField label="Username *">
                          <input value={form.rabbitmq_username}
                            onChange={e => setForm({...form, rabbitmq_username: e.target.value})}
                            placeholder="admin" style={inputStyle} />
                        </FormField>
                        <FormField label="Password *">
                          <PasswordInput value={form.rabbitmq_password}
                            onChange={e => setForm({...form, rabbitmq_password: e.target.value})}
                            placeholder="••••••••" style={inputStyle} />
                        </FormField>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                        <FormField label="Queue Name *">
                          <input value={form.rabbitmq_queue}
                            onChange={e => setForm({...form, rabbitmq_queue: e.target.value})}
                            placeholder="swift.messages.out" style={inputStyle} />
                        </FormField>
                        <FormField label="Virtual Host">
                          <input value={form.rabbitmq_vhost}
                            onChange={e => setForm({...form, rabbitmq_vhost: e.target.value})}
                            placeholder="/" style={inputStyle} />
                        </FormField>
                      </div>
                    </div>
                  )}

                  {/* ── Kafka fields ── */}
                  {form.transport_type === 'KAFKA' && (
                    <div style={sectionStyle('#a78bfa')}>
                      <div style={sectionTitle('#a78bfa')}>⚡ Apache Kafka Configuration</div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                        <FormField label="Bootstrap Servers *">
                          <input value={form.kafka_bootstrap_servers}
                            onChange={e => setForm({...form, kafka_bootstrap_servers: e.target.value})}
                            placeholder="kafka:9092" style={inputStyle} />
                        </FormField>
                        <FormField label="Topic *">
                          <input value={form.kafka_topic}
                            onChange={e => setForm({...form, kafka_topic: e.target.value})}
                            placeholder="swift.messages.out" style={inputStyle} />
                        </FormField>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                        <FormField label="Group ID">
                          <input value={form.kafka_group_id}
                            onChange={e => setForm({...form, kafka_group_id: e.target.value})}
                            placeholder="smart-mapping-group" style={inputStyle} />
                        </FormField>
                        <FormField label="Security Protocol">
                          <select value={form.kafka_security_protocol}
                            onChange={e => setForm({...form, kafka_security_protocol: e.target.value})}
                            style={inputStyle}>
                            <option value="PLAINTEXT">PLAINTEXT</option>
                            <option value="SASL_PLAINTEXT">SASL_PLAINTEXT</option>
                            <option value="SSL">SSL</option>
                            <option value="SASL_SSL">SASL_SSL</option>
                          </select>
                        </FormField>
                      </div>
                      {['SASL_PLAINTEXT', 'SASL_SSL'].includes(form.kafka_security_protocol) && (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
                          <FormField label="SASL Mechanism">
                            <select value={form.kafka_sasl_mechanism}
                              onChange={e => setForm({...form, kafka_sasl_mechanism: e.target.value})}
                              style={inputStyle}>
                              <option value="PLAIN">PLAIN</option>
                              <option value="SCRAM-SHA-256">SCRAM-SHA-256</option>
                              <option value="SCRAM-SHA-512">SCRAM-SHA-512</option>
                            </select>
                          </FormField>
                          <FormField label="Username">
                            <input value={form.kafka_sasl_username}
                              onChange={e => setForm({...form, kafka_sasl_username: e.target.value})}
                              placeholder="kafka-user" style={inputStyle} />
                          </FormField>
                          <FormField label="Password">
                            <PasswordInput value={form.kafka_sasl_password}
                              onChange={e => setForm({...form, kafka_sasl_password: e.target.value})}
                              placeholder="••••••••" style={inputStyle} />
                          </FormField>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Active toggle */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: '1rem 0 1.5rem' }}>
                    <input type="checkbox" checked={form.is_active}
                      onChange={e => setForm({...form, is_active: e.target.checked})}
                      id="active" style={{ width: '16px', height: '16px', cursor: 'pointer' }} />
                    <label htmlFor="active" style={{ color: '#a0a0a0', cursor: 'pointer' }}>Active</label>
                  </div>

                  {/* Actions */}
                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                    <button onClick={() => { setShowForm(false); setEditId(null); }} style={{
                      padding: '10px 20px', background: 'rgba(255,255,255,0.05)',
                      border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px',
                      color: '#9ca3af', cursor: 'pointer'
                    }}>Cancel</button>
                    <button onClick={handleSubmit} disabled={loading} style={{
                      padding: '10px 24px',
                      background: 'linear-gradient(135deg, #a78bfa 0%, #06b6d4 100%)',
                      border: 'none', borderRadius: '8px', color: 'white',
                      fontWeight: '700', cursor: 'pointer'
                    }}>
                      {loading ? 'Saving...' : editId ? 'Update' : 'Create'}
                    </button>
                  </div>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </Layout>
  );
};

// ── Sub-components ────────────────────────────────────────────────────────────

const GlassCard = ({ children }) => (
  <div style={{
    background: 'rgba(255,255,255,0.05)', backdropFilter: 'blur(10px)',
    borderRadius: '16px', padding: '1.25rem',
    border: '1px solid rgba(255,255,255,0.1)',
    boxShadow: '0 8px 32px rgba(0,0,0,0.3)'
  }}>{children}</div>
);

const FormField = ({ label, children }) => (
  <div style={{ marginBottom: '0.75rem' }}>
    <label style={{ display: 'block', color: '#9ca3af', fontSize: '0.8rem', marginBottom: '4px' }}>{label}</label>
    {children}
  </div>
);

const IconBtn = ({ icon: Icon, color, title, onClick }) => (
  <button onClick={onClick} title={title} style={{
    width: '32px', height: '32px', borderRadius: '6px',
    background: `${color}15`, border: `1px solid ${color}30`,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    cursor: 'pointer', transition: 'all 0.2s'
  }}>
    <Icon size={14} color={color} />
  </button>
);

const sectionStyle = (color) => ({
  background: `${color}08`,
  border: `1px solid ${color}25`,
  borderRadius: '10px',
  padding: '1rem',
  marginBottom: '1rem',
});

const sectionTitle = (color) => ({
  color, fontWeight: '700', fontSize: '0.85rem', marginBottom: '0.75rem'
});

const inputStyle = {
  width: '100%', padding: '8px 12px',
  background: '#1e2a3a',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '8px', color: 'white', fontSize: '0.9rem',
  boxSizing: 'border-box', outline: 'none'
};

const GlobalStyle = () => (
  <style>{`
    select option { background: #1e2a3a !important; color: white !important; }
    select { background: #1e2a3a !important; }
    input::placeholder { color: #4b5563; }
  `}</style>
);

export default ConfigPage;