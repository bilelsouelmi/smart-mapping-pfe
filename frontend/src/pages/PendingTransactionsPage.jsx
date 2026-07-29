import { useState, useEffect } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { toast } from 'react-toastify';
import { Lock, RefreshCw, Check, X, Download, Clock, FileWarning, Eye } from 'lucide-react';
import Layout from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import API_BASE_URL from '../config/api';

const API = `${API_BASE_URL}/api`;

const STATUS_META = {
  pending: { label: 'Pending', color: '#f59e0b' },
  approved: { label: 'Approved', color: '#10b981' },
  rejected: { label: 'Rejected', color: '#ef4444' },
};

const VALIDATION_STATUS_META = {
  pending: { label: 'Needs correction', color: '#f59e0b' },
  resolved: { label: 'Resolved', color: '#10b981' },
  dismissed: { label: 'Dismissed', color: '#6b7280' },
};

// Two hold types share this queue: large-amount (approver_role="admin",
// see transform_mapping.py's _required_approvals_for_amount) and PEP
// match (approver_role="compliance_officer"). pending_reason is set
// server-side for PEP holds; large-amount holds don't set it, so fall
// back to the approvals-remaining phrasing.
const pendingReason = (t) => t.pending_reason || `Large amount — awaiting ${t.required_approvals - t.approvals_received} more approval${t.required_approvals - t.approvals_received === 1 ? '' : 's'}`;

const ASSIGNED_TO = { admin: 'Admin (any except submitter)', compliance_officer: 'Compliance officer (any except submitter)' };

const PendingTransactionsPage = () => {
  const { user } = useAuth();
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [statusFilter, setStatusFilter] = useState('pending');

  const [validations, setValidations] = useState([]);
  const [validationsLoading, setValidationsLoading] = useState(true);
  const [validationsFilter, setValidationsFilter] = useState('pending');
  const [busyValidationId, setBusyValidationId] = useState(null);
  const [viewingValidation, setViewingValidation] = useState(null);

  const fetchTransactions = async (filter = statusFilter) => {
    setLoading(true);
    try {
      const params = filter === 'all' ? {} : { status_filter: filter };
      const res = await axios.get(`${API}/pending-transactions/`, { params });
      setTransactions(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load transactions');
    } finally {
      setLoading(false);
    }
  };

  const fetchValidations = async (filter = validationsFilter) => {
    setValidationsLoading(true);
    try {
      const params = filter === 'all' ? {} : { status_filter: filter };
      const res = await axios.get(`${API}/pending-validations/`, { params });
      setValidations(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load validation corrections');
    } finally {
      setValidationsLoading(false);
    }
  };

  useEffect(() => { fetchTransactions(statusFilter); }, [statusFilter]);
  useEffect(() => { fetchValidations(validationsFilter); }, [validationsFilter]);

  const dismissValidation = async (id) => {
    setBusyValidationId(id);
    try {
      await axios.post(`${API}/pending-validations/${id}/dismiss`);
      toast.success('Dismissed');
      fetchValidations();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Dismiss failed');
    } finally {
      setBusyValidationId(null);
    }
  };

  const approve = async (id) => {
    setBusyId(id);
    try {
      await axios.post(`${API}/pending-transactions/${id}/approve`);
      toast.success('Approved');
      fetchTransactions();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Approval failed');
    } finally {
      setBusyId(null);
    }
  };

  const reject = async (id) => {
    setBusyId(id);
    try {
      await axios.post(`${API}/pending-transactions/${id}/reject`);
      toast.success('Rejected');
      fetchTransactions();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Rejection failed');
    } finally {
      setBusyId(null);
    }
  };

  const download = async (id, filename) => {
    try {
      const res = await axios.get(`${API}/pending-transactions/${id}/download`, { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/xml' }));
      const a = document.createElement('a');
      a.href = url; a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error('Download failed — not yet approved?');
    }
  };

  return (
    <Layout>
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div style={{ marginBottom: '2rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 style={{
              fontSize: '2.5rem', fontWeight: '800', margin: 0,
              background: 'linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
            }}>
              🔒 Pending Transactions
            </h1>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={selectStyle}>
              <option value="pending">Pending (needs action)</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="all">All</option>
            </select>
            <button onClick={() => fetchTransactions()} style={{
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
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '16px', overflow: 'hidden'
        }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>Loading...</div>
          ) : transactions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>
              <Lock size={40} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />
              {statusFilter === 'pending' ? 'Nothing needs action right now.' : 'No transactions match this filter.'}
            </div>
          ) : (
            <div style={{ maxHeight: '65vh', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                  {['Reference', 'Type', 'Amount', 'Status', 'Pending Reason', 'Assigned To', 'Submitted by', 'Actions'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '0.85rem 1rem', color: '#6b7280', fontSize: '0.78rem', textTransform: 'uppercase', whiteSpace: 'nowrap', position: 'sticky', top: 0, background: '#1a1a2e' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {transactions.map((t, i) => {
                  const isOwn = t.submitted_by_username === user?.username;
                  const statusMeta = STATUS_META[t.status] || { label: t.status, color: '#9ca3af' };
                  return (
                    <motion.tr key={t.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.02 }}
                      style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={{ padding: '0.75rem 1rem', color: 'white', fontWeight: '700', fontSize: '0.85rem' }}>
                        {t.reference || '—'}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: '#9ca3af', fontSize: '0.82rem' }}>
                        {t.mt_type}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: '#d1d5db', fontSize: '0.85rem' }}>
                        {t.amount} {t.currency}
                      </td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span style={{
                          padding: '2px 10px', borderRadius: '999px', fontSize: '0.72rem', fontWeight: '700',
                          background: `${statusMeta.color}20`, color: statusMeta.color,
                          display: 'inline-flex', alignItems: 'center', gap: '4px', whiteSpace: 'nowrap'
                        }}>
                          {t.status === 'pending' && <Clock size={11} />}
                          {statusMeta.label}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: '#9ca3af', fontSize: '0.8rem' }}>
                        {t.status === 'pending' ? pendingReason(t) : '—'}
                        {t.approver_usernames.length > 0 && (
                          <div style={{ color: '#6b7280', fontSize: '0.72rem' }}>Approved by: {t.approver_usernames.join(', ')}</div>
                        )}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: '#9ca3af', fontSize: '0.82rem' }}>
                        {t.status === 'pending' ? (ASSIGNED_TO[t.approver_role] || ASSIGNED_TO.admin) : '—'}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: '#9ca3af', fontSize: '0.82rem' }}>
                        {t.submitted_by_username || '—'}{isOwn && ' (you)'}
                      </td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        {(() => {
                          const canAct = t.approver_role === 'compliance_officer' ? user?.is_compliance_officer : user?.is_admin;
                          if (t.status === 'pending' && canAct && !isOwn) {
                            return (
                              <div style={{ display: 'flex', gap: '6px' }}>
                                <button onClick={() => approve(t.id)} disabled={busyId === t.id} style={iconBtnStyle('#10b981', busyId === t.id)}><Check size={14} /></button>
                                <button onClick={() => reject(t.id)} disabled={busyId === t.id} style={iconBtnStyle('#ef4444', busyId === t.id)}><X size={14} /></button>
                              </div>
                            );
                          }
                          if (t.status === 'pending' && isOwn) {
                            return <span style={{ color: '#6b7280', fontSize: '0.75rem', fontStyle: 'italic' }}>Awaiting {t.approver_role === 'compliance_officer' ? 'compliance officer(s)' : 'other admin(s)'}</span>;
                          }
                          return null;
                        })()}
                        {t.status === 'approved' && (
                          <button onClick={() => download(t.id, t.output_filename)} style={iconBtnStyle('#06b6d4', false)} title="Download"><Download size={14} /></button>
                        )}
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
            </div>
          )}
        </div>

        <div style={{ marginTop: '2.5rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <h2 style={{ fontSize: '1.4rem', fontWeight: '700', margin: 0, color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileWarning size={22} /> Failed Validations
          </h2>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <select value={validationsFilter} onChange={e => setValidationsFilter(e.target.value)} style={selectStyle}>
              <option value="pending">Needs correction</option>
              <option value="resolved">Resolved</option>
              <option value="dismissed">Dismissed</option>
              <option value="all">All</option>
            </select>
            <button onClick={() => fetchValidations()} style={{
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
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '16px', overflow: 'hidden'
        }}>
          {validationsLoading ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>Loading...</div>
          ) : validations.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>
              <FileWarning size={40} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />
              {validationsFilter === 'pending' ? 'No outstanding corrections.' : 'No records match this filter.'}
            </div>
          ) : (
            <div style={{ maxHeight: '50vh', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                  {['File', 'Type', 'Failed Fields', 'Status', 'Submitted by', 'Actions'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '0.85rem 1rem', color: '#6b7280', fontSize: '0.78rem', textTransform: 'uppercase', whiteSpace: 'nowrap', position: 'sticky', top: 0, background: '#1a1a2e' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {validations.map((v, i) => {
                  const isOwn = v.submitted_by_username === user?.username;
                  const statusMeta = VALIDATION_STATUS_META[v.status] || { label: v.status, color: '#9ca3af' };
                  return (
                    <motion.tr key={v.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.02 }}
                      style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={{ padding: '0.75rem 1rem', color: 'white', fontWeight: '700', fontSize: '0.85rem' }}>
                        {v.original_filename}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: '#9ca3af', fontSize: '0.82rem' }}>
                        {v.mt_type}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: '#d1d5db', fontSize: '0.85rem' }}>
                        {v.failed_count}
                      </td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span style={{
                          padding: '2px 10px', borderRadius: '999px', fontSize: '0.72rem', fontWeight: '700',
                          background: `${statusMeta.color}20`, color: statusMeta.color,
                          display: 'inline-flex', alignItems: 'center', gap: '4px', whiteSpace: 'nowrap'
                        }}>
                          {v.status === 'pending' && <Clock size={11} />}
                          {statusMeta.label}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: '#9ca3af', fontSize: '0.82rem' }}>
                        {v.submitted_by_username || '—'}{isOwn && ' (you)'}
                      </td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button onClick={() => setViewingValidation(v)} style={iconBtnStyle('#a78bfa', false)} title="View Errors"><Eye size={14} /></button>
                          {v.status === 'pending' && (isOwn || user?.is_admin) && (
                            <button onClick={() => dismissValidation(v.id)} disabled={busyValidationId === v.id} style={iconBtnStyle('#ef4444', busyValidationId === v.id)} title="Dismiss"><X size={14} /></button>
                          )}
                        </div>
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

      {viewingValidation && (
        <div onClick={() => setViewingValidation(null)} style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem'
        }}>
          <div onClick={e => e.stopPropagation()} style={{
            background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '16px',
            padding: '1.75rem', maxWidth: '600px', width: '100%', maxHeight: '80vh', overflowY: 'auto'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ margin: 0, color: 'white', fontSize: '1.15rem' }}>{viewingValidation.original_filename}</h3>
              <button onClick={() => setViewingValidation(null)} style={iconBtnStyle('#9ca3af', false)}><X size={14} /></button>
            </div>
            {viewingValidation.errors?.length > 0 && (
              <>
                <div style={{ color: '#ef4444', fontWeight: '700', fontSize: '0.85rem', marginBottom: '0.5rem' }}>Errors ({viewingValidation.errors.length})</div>
                {viewingValidation.errors.map((e, idx) => (
                  <div key={idx} style={{ padding: '0.6rem 0.8rem', marginBottom: '0.4rem', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: '8px', fontSize: '0.82rem' }}>
                    <div style={{ color: 'white', fontWeight: '600' }}>{e.field}</div>
                    <div style={{ color: '#d1d5db' }}>{(e.errors || []).join(', ')}</div>
                  </div>
                ))}
              </>
            )}
            {viewingValidation.warnings?.length > 0 && (
              <>
                <div style={{ color: '#f59e0b', fontWeight: '700', fontSize: '0.85rem', margin: '1rem 0 0.5rem' }}>Warnings ({viewingValidation.warnings.length})</div>
                {viewingValidation.warnings.map((w, idx) => (
                  <div key={idx} style={{ padding: '0.6rem 0.8rem', marginBottom: '0.4rem', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: '8px', fontSize: '0.82rem' }}>
                    <div style={{ color: 'white', fontWeight: '600' }}>{w.field}</div>
                    <div style={{ color: '#d1d5db' }}>{w.message}</div>
                  </div>
                ))}
              </>
            )}
            {!(viewingValidation.errors?.length) && !(viewingValidation.warnings?.length) && (
              <div style={{ color: '#6b7280', textAlign: 'center', padding: '1rem' }}>No details recorded.</div>
            )}
          </div>
        </div>
      )}
    </Layout>
  );
};

const selectStyle = {
  padding: '9px 14px', background: '#1e2a3a', border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '10px', color: 'white', fontSize: '0.85rem', cursor: 'pointer'
};

const iconBtnStyle = (color, disabled) => ({
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: '28px', height: '28px', borderRadius: '6px',
  border: `1px solid ${color}40`, background: `${color}15`,
  color, cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
});

export default PendingTransactionsPage;
