import { useState, useEffect } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { toast } from 'react-toastify';
import { ScrollText, RefreshCw, Filter } from 'lucide-react';
import Layout from '../components/Layout';
import API_BASE_URL from '../config/api';

const API = `${API_BASE_URL}/api`;

const ACTION_COLORS = {
  propose: '#06b6d4',
  approve: '#10b981',
  reject: '#ef4444',
  deleted: '#ef4444',
};

const AuditLogPage = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [entityType, setEntityType] = useState('');
  const [action, setAction] = useState('');

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params = {};
      if (entityType) params.entity_type = entityType;
      if (action) params.action = action;
      const res = await axios.get(`${API}/audit-logs/`, { params });
      setLogs(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load audit log');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchLogs(); }, [entityType, action]);

  return (
    <Layout>
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div style={{ marginBottom: '2rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1 style={{
              fontSize: '2.5rem', fontWeight: '800', margin: 0,
              background: 'linear-gradient(135deg, #a78bfa 0%, #667eea 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
            }}>
              📜 Audit Log
            </h1>
            <p style={{ color: '#a0a0a0', marginTop: '0.5rem' }}>
              Full compliance trail — who did what, and when
            </p>
          </div>
          <button onClick={fetchLogs} style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '10px 18px', background: 'rgba(167,139,250,0.15)',
            border: '1px solid rgba(167,139,250,0.3)', borderRadius: '10px',
            color: '#a78bfa', cursor: 'pointer', fontWeight: '600'
          }}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>

        <div style={{
          display: 'flex', gap: '1rem', marginBottom: '1.5rem',
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '12px', padding: '1rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#6b7280', fontSize: '0.85rem' }}>
            <Filter size={14} /> Filter:
          </div>
          <select value={entityType} onChange={e => setEntityType(e.target.value)} style={selectStyle}>
            <option value="">All entities</option>
            <option value="MessageDescription">Message Description</option>
          </select>
          <select value={action} onChange={e => setAction(e.target.value)} style={selectStyle}>
            <option value="">All actions</option>
            <option value="propose">Propose</option>
            <option value="approve">Approve</option>
            <option value="rejected">Reject</option>
            <option value="deleted">Delete</option>
          </select>
        </div>

        <div style={{
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '16px', overflow: 'hidden'
        }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>Loading...</div>
          ) : logs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>
              <ScrollText size={40} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />
              No audit entries match this filter yet.
            </div>
          ) : (
            <div style={{ maxHeight: '65vh', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                  {['When', 'User', 'Action', 'Entity', 'Details'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '0.85rem 1rem', color: '#6b7280', fontSize: '0.78rem', textTransform: 'uppercase', position: 'sticky', top: 0, background: '#1a1a2e' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.map((log, i) => (
                  <motion.tr key={log.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.02 }}
                    style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <td style={{ padding: '0.75rem 1rem', color: '#9ca3af', fontSize: '0.82rem', whiteSpace: 'nowrap' }}>
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: 'white', fontWeight: '600', fontSize: '0.85rem' }}>
                      {log.username}
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <span style={{
                        padding: '2px 10px', borderRadius: '999px', fontSize: '0.75rem', fontWeight: '700',
                        background: `${ACTION_COLORS[log.action] || '#6b7280'}20`,
                        color: ACTION_COLORS[log.action] || '#9ca3af'
                      }}>
                        {log.action}
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: '#9ca3af', fontSize: '0.82rem' }}>
                      {log.entity_type} #{log.entity_id}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: '#d1d5db', fontSize: '0.82rem' }}>
                      {log.details}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </div>
      </motion.div>
    </Layout>
  );
};

const selectStyle = {
  padding: '6px 12px', background: '#1e2a3a', border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '8px', color: 'white', fontSize: '0.85rem'
};

export default AuditLogPage;
