import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Layout from '../components/Layout';
import axios from 'axios';
import { toast } from 'react-toastify';
import { Trash2, Edit2, Save, X, Shield, User, Check, Clock, UserCheck, UserX, KeyRound } from 'lucide-react';

const AdminPage = () => {
  const { user: currentUser } = useAuth();
  const [searchParams] = useSearchParams();
  const [users, setUsers] = useState([]);
  const [pendingUsers, setPendingUsers] = useState([]);
  const [accessRequests, setAccessRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [editData, setEditData] = useState({});
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') === 'access' ? 'access' : 'active');
  const [processingId, setProcessingId] = useState(null);

  useEffect(() => {
    fetchUsers();
    fetchPendingUsers();
    fetchAccessRequests();
  }, []);

  useEffect(() => {
    if (searchParams.get('tab') === 'access') setActiveTab('access');
  }, [searchParams]);

  const fetchAccessRequests = async () => {
    try {
      const res = await axios.get('/api/access-requests/', { params: { status_filter: 'pending' } });
      setAccessRequests(res.data);
    } catch (err) {
      console.error('Failed to load access requests');
    }
  };

  const approveAccessRequest = async (id, request) => {
    if (processingId) return;
    if (!window.confirm(
      `Grant ${request.requester_username} permission to ${request.action_requested} "${request.md_file_name}"? ` +
      `This is a one-time authorization — it's consumed the moment they use it.`
    )) return;
    setProcessingId(id);
    try {
      await axios.post(`/api/access-requests/${id}/approve`);
      toast.success('Access granted');
      fetchAccessRequests();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Approval failed');
    } finally {
      setProcessingId(null);
    }
  };

  const denyAccessRequest = async (id, request) => {
    if (processingId) return;
    if (!window.confirm(
      `Deny ${request.requester_username}'s request to ${request.action_requested} "${request.md_file_name}"?`
    )) return;
    setProcessingId(id);
    try {
      await axios.post(`/api/access-requests/${id}/deny`);
      toast.success('Access request denied');
      fetchAccessRequests();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Denial failed');
    } finally {
      setProcessingId(null);
    }
  };

  const fetchUsers = async () => {
    try {
      const res = await axios.get('/api/users/');
      setUsers(res.data.filter(u => u.is_active));
    } catch (err) {
      toast.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const fetchPendingUsers = async () => {
    try {
      const res = await axios.get('/api/users/pending');
      setPendingUsers(res.data);
    } catch (err) {
      console.error('Failed to load pending users');
    }
  };

  const approveUser = async (userId) => {
    if (processingId) return;
    setProcessingId(userId);
    try {
      await axios.post(`/api/users/${userId}/approve`);
      toast.success('User approved successfully');
      fetchUsers();
      fetchPendingUsers();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Approval failed');
    } finally {
      setProcessingId(null);
    }
  };

  const rejectUser = async (userId) => {
    if (processingId) return;
    setProcessingId(userId);
    try {
      await axios.post(`/api/users/${userId}/reject`);
      toast.success('User rejected and removed');
      fetchPendingUsers();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Rejection failed');
    } finally {
      setProcessingId(null);
    }
  };

  const startEdit = (user) => {
    setEditingId(user.id);
    setEditData({
      username: user.username,
      email: user.email,
      full_name: user.full_name || '',
      is_active: user.is_active,
      is_admin: user.is_admin,
      is_compliance_officer: user.is_compliance_officer,
    });
  };

  const cancelEdit = () => { setEditingId(null); setEditData({}); };

  const saveEdit = async (userId) => {
    try {
      await axios.put(`/api/users/${userId}`, editData);
      toast.success('User updated successfully');
      setEditingId(null);
      fetchUsers();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Update failed');
    }
  };

  const deleteUser = async (userId) => {
    try {
      await axios.delete(`/api/users/${userId}`);
      toast.success('User deleted successfully');
      setDeleteConfirm(null);
      fetchUsers();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Delete failed');
    }
  };

  const cardStyle = {
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '16px', padding: '1.5rem', marginBottom: '1rem',
  };

  const inputStyle = {
    background: 'rgba(255,255,255,0.07)',
    border: '1px solid rgba(255,255,255,0.15)',
    borderRadius: '8px', color: 'white',
    padding: '0.4rem 0.75rem', fontSize: '0.85rem', width: '100%',
  };

  const btnStyle = (color, isDisabled = false) => ({
    display: 'flex', alignItems: 'center', gap: '6px',
    padding: '0.4rem 0.85rem', borderRadius: '8px',
    border: `1px solid ${color}40`, background: `${color}15`,
    color, cursor: isDisabled ? 'not-allowed' : 'pointer', fontSize: '0.82rem', fontWeight: '600',
    opacity: isDisabled ? 0.5 : 1,
  });

  return (
    <Layout>
      <div style={{ maxWidth: '900px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{ fontSize: '1.8rem', fontWeight: '800', color: 'white',
            display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Shield size={28} color="#a78bfa" /> User Management
          </h1>
          <p style={{ color: '#6b7280', marginTop: '0.5rem' }}>
            {users.length} active user{users.length !== 1 ? 's' : ''}
            {pendingUsers.length > 0 && (
              <span style={{ marginLeft: '0.75rem', padding: '2px 10px', borderRadius: '20px',
                background: 'rgba(245,158,11,0.15)', color: '#f59e0b',
                border: '1px solid rgba(245,158,11,0.3)', fontSize: '0.8rem', fontWeight: '600' }}>
                {pendingUsers.length} pending approval
              </span>
            )}
          </p>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '1.5rem' }}>
          {[
            { key: 'active', label: `Active Users (${users.length})`, icon: UserCheck, color: '#a78bfa' },
            { key: 'pending', label: `Pending Approval (${pendingUsers.length})`, icon: Clock, color: '#f59e0b' },
            { key: 'access', label: `Access Requests (${accessRequests.length})`, icon: KeyRound, color: '#06b6d4' },
          ].map(tab => (
            <button key={tab.key} onClick={() => setActiveTab(tab.key)} style={{
              padding: '8px 20px', borderRadius: '8px', cursor: 'pointer',
              fontWeight: '700', fontSize: '0.88rem',
              background: activeTab === tab.key ? `${tab.color}20` : 'rgba(255,255,255,0.04)',
              border: `1px solid ${activeTab === tab.key ? tab.color : 'rgba(255,255,255,0.08)'}`,
              color: activeTab === tab.key ? tab.color : '#6b7280',
              display: 'flex', alignItems: 'center', gap: '6px'
            }}>
              <tab.icon size={15} /> {tab.label}
            </button>
          ))}
        </div>

        {/* Pending tab */}
        {activeTab === 'pending' && (
          <div style={{ maxHeight: '65vh', overflowY: 'auto' }}>
          {pendingUsers.length === 0 ? (
            <div style={{ ...cardStyle, textAlign: 'center', padding: '3rem', color: '#6b7280' }}>
              <Clock size={40} style={{ margin: '0 auto 1rem', opacity: 0.3, display: 'block' }} />
              No pending accounts to approve.
            </div>
          ) : (
            pendingUsers.map(u => (
              <div key={u.id} style={{ ...cardStyle,
                border: '1px solid rgba(245,158,11,0.25)',
                background: 'rgba(245,158,11,0.04)' }}>
                <div style={{ display: 'flex', alignItems: 'center',
                  justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div style={{ width: '42px', height: '42px', borderRadius: '50%',
                      background: 'rgba(245,158,11,0.15)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      border: '2px solid rgba(245,158,11,0.3)', flexShrink: 0 }}>
                      <Clock size={18} color="#f59e0b" />
                    </div>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ color: 'white', fontWeight: '700', fontSize: '0.95rem' }}>
                          {u.username}
                        </span>
                        <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '20px',
                          background: 'rgba(245,158,11,0.15)', color: '#f59e0b',
                          border: '1px solid rgba(245,158,11,0.3)' }}>Pending</span>
                      </div>
                      <div style={{ color: '#6b7280', fontSize: '0.82rem', marginTop: '2px' }}>
                        {u.email}
                        {u.full_name && <span style={{ marginLeft: '0.75rem' }}>· {u.full_name}</span>}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button style={btnStyle('#10b981', !!processingId)} onClick={() => approveUser(u.id)} disabled={!!processingId}>
                      <UserCheck size={14} /> Approve
                    </button>
                    <button style={btnStyle('#ef4444', !!processingId)} onClick={() => rejectUser(u.id)} disabled={!!processingId}>
                      <UserX size={14} /> Reject
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
          </div>
        )}

        {/* Access Requests tab — non-admins asking to update/delete an
            already-approved Message Description (see the maker-checker
            extension: approving isn't enough, editing an existing
            reference afterward needs its own explicit grant). */}
        {activeTab === 'access' && (
          <div style={{ maxHeight: '65vh', overflowY: 'auto' }}>
          {accessRequests.length === 0 ? (
            <div style={{ ...cardStyle, textAlign: 'center', padding: '3rem', color: '#6b7280' }}>
              <KeyRound size={40} style={{ margin: '0 auto 1rem', opacity: 0.3, display: 'block' }} />
              No pending access requests.
            </div>
          ) : (
            accessRequests.map(r => (
              <div key={r.id} style={{ ...cardStyle,
                border: '1px solid rgba(6,182,212,0.25)',
                background: 'rgba(6,182,212,0.04)' }}>
                <div style={{ display: 'flex', alignItems: 'center',
                  justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div style={{ width: '42px', height: '42px', borderRadius: '50%',
                      background: 'rgba(6,182,212,0.15)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      border: '2px solid rgba(6,182,212,0.3)', flexShrink: 0 }}>
                      <KeyRound size={18} color="#06b6d4" />
                    </div>
                    <div>
                      <div style={{ color: 'white', fontWeight: '700', fontSize: '0.95rem' }}>
                        {r.requester_username}
                        <span style={{ color: '#6b7280', fontWeight: '500' }}> wants to </span>
                        <span style={{ color: '#06b6d4' }}>{r.action_requested}</span>
                        <span style={{ color: '#6b7280', fontWeight: '500' }}> "{r.md_file_name}"</span>
                      </div>
                      {r.reason && (
                        <div style={{ color: '#6b7280', fontSize: '0.82rem', marginTop: '2px' }}>
                          Reason: {r.reason}
                        </div>
                      )}
                      <div style={{ color: '#4b5563', fontSize: '0.75rem', marginTop: '2px' }}>
                        {new Date(r.created_at).toLocaleString()}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button style={btnStyle('#10b981', !!processingId)} onClick={() => approveAccessRequest(r.id, r)} disabled={!!processingId}>
                      <Check size={14} /> Grant
                    </button>
                    <button style={btnStyle('#ef4444', !!processingId)} onClick={() => denyAccessRequest(r.id, r)} disabled={!!processingId}>
                      <X size={14} /> Deny
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
          </div>
        )}

        {/* Active users tab */}
        {activeTab === 'active' && (
          <div style={{ maxHeight: '65vh', overflowY: 'auto' }}>
          {loading ? <p style={{ color: '#6b7280' }}>Loading users...</p> :
          users.map((u) => (
            <div key={u.id} style={cardStyle}>
              {editingId === u.id ? (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr',
                    gap: '0.75rem', marginBottom: '1rem' }}>
                    <div>
                      <label style={{ color: '#9ca3af', fontSize: '0.75rem',
                        display: 'block', marginBottom: '4px' }}>Username</label>
                      <input style={inputStyle} value={editData.username}
                        onChange={e => setEditData({ ...editData, username: e.target.value })} />
                    </div>
                    <div>
                      <label style={{ color: '#9ca3af', fontSize: '0.75rem',
                        display: 'block', marginBottom: '4px' }}>Email</label>
                      <input style={inputStyle} value={editData.email}
                        onChange={e => setEditData({ ...editData, email: e.target.value })} />
                    </div>
                    <div>
                      <label style={{ color: '#9ca3af', fontSize: '0.75rem',
                        display: 'block', marginBottom: '4px' }}>Full Name</label>
                      <input style={inputStyle} value={editData.full_name}
                        onChange={e => setEditData({ ...editData, full_name: e.target.value })} />
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column',
                      gap: '0.5rem', justifyContent: 'center' }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '8px',
                        cursor: 'pointer', color: '#9ca3af', fontSize: '0.85rem' }}>
                        <input type="checkbox" checked={editData.is_active}
                          onChange={e => setEditData({ ...editData, is_active: e.target.checked })} />
                        Active
                      </label>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '8px',
                        cursor: 'pointer', color: '#9ca3af', fontSize: '0.85rem' }}>
                        <input type="checkbox" checked={editData.is_admin}
                          onChange={e => setEditData({ ...editData, is_admin: e.target.checked })}
                          disabled={u.id === currentUser?.id} />
                        Admin
                      </label>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '8px',
                        cursor: 'pointer', color: '#9ca3af', fontSize: '0.85rem' }}>
                        <input type="checkbox" checked={editData.is_compliance_officer}
                          onChange={e => setEditData({ ...editData, is_compliance_officer: e.target.checked })} />
                        Compliance Officer
                      </label>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button style={btnStyle('#10b981')} onClick={() => saveEdit(u.id)}>
                      <Save size={14} /> Save
                    </button>
                    <button style={btnStyle('#6b7280')} onClick={cancelEdit}>
                      <X size={14} /> Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center',
                  justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div style={{ width: '42px', height: '42px', borderRadius: '50%',
                      background: u.is_admin ? 'rgba(167,139,250,0.2)' : 'rgba(102,126,234,0.2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      border: `2px solid ${u.is_admin ? '#a78bfa' : '#667eea'}40`, flexShrink: 0 }}>
                      {u.is_admin ? <Shield size={18} color="#a78bfa" /> : <User size={18} color="#667eea" />}
                    </div>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ color: 'white', fontWeight: '700', fontSize: '0.95rem' }}>
                          {u.username}
                        </span>
                        {u.id === currentUser?.id && (
                          <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '20px',
                            background: 'rgba(102,126,234,0.2)', color: '#667eea',
                            border: '1px solid rgba(102,126,234,0.3)' }}>You</span>
                        )}
                        <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '20px',
                          background: u.is_admin ? 'rgba(167,139,250,0.15)' : 'rgba(16,185,129,0.15)',
                          color: u.is_admin ? '#a78bfa' : '#10b981',
                          border: `1px solid ${u.is_admin ? 'rgba(167,139,250,0.3)' : 'rgba(16,185,129,0.3)'}` }}>
                          {u.is_admin ? 'Admin' : 'User'}
                        </span>
                        {u.is_compliance_officer && (
                          <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '20px',
                            background: 'rgba(239,68,68,0.15)', color: '#ef4444',
                            border: '1px solid rgba(239,68,68,0.3)' }}>Compliance Officer</span>
                        )}
                      </div>
                      <div style={{ color: '#6b7280', fontSize: '0.82rem', marginTop: '2px' }}>
                        {u.email}
                        {u.full_name && <span style={{ marginLeft: '0.75rem', color: '#4b5563' }}>· {u.full_name}</span>}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button style={btnStyle('#667eea')} onClick={() => startEdit(u)}>
                      <Edit2 size={13} /> Edit
                    </button>
                    {u.id !== currentUser?.id && (
                      deleteConfirm === u.id ? (
                        <>
                          <button style={btnStyle('#ef4444')} onClick={() => deleteUser(u.id)}>
                            <Check size={13} /> Confirm
                          </button>
                          <button style={btnStyle('#6b7280')} onClick={() => setDeleteConfirm(null)}>
                            <X size={13} /> Cancel
                          </button>
                        </>
                      ) : (
                        <button style={btnStyle('#ef4444')} onClick={() => setDeleteConfirm(u.id)}>
                          <Trash2 size={13} /> Delete
                        </button>
                      )
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default AdminPage;