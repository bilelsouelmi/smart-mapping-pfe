import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
import { Home, FileOutput, LogOut, Sparkles, Layers, Shield, GitMerge, Settings, GitBranch, Users, Bell, Check, ScrollText, X, Trash2, SlidersHorizontal, ShieldAlert, KeyRound, Lock, FileBarChart, Activity, Layers2, Database } from 'lucide-react';
import { toast } from 'react-toastify';
import API_BASE_URL from '../config/api';
import { PENDING_APPROVALS_CHANGED_EVENT } from '../constants/events';
import PasswordInput from './PasswordInput';

// Shared row renderer for both the core-pipeline and secondary nav
// sections — same markup, previously duplicated inline for a single list.
const renderNavItem = (item, location, hovered) => {
  const Icon = item.icon;
  const isActive = location.pathname === item.path;
  return (
    <Link key={item.path} to={item.path}
      style={{ textDecoration: 'none', display: 'block', padding: '3px 8px' }}>
      <motion.div
        whileHover={{ background: 'rgba(255,255,255,0.07)' }}
        whileTap={{ scale: 0.97 }}
        style={{
          display: 'flex', alignItems: 'center', gap: '0.85rem',
          padding: '0.7rem 0.85rem',
          borderRadius: '10px',
          background: isActive ? `${item.color}20` : 'transparent',
          borderLeft: isActive ? `3px solid ${item.color}` : '3px solid transparent',
          cursor: 'pointer', transition: 'background 0.2s',
          overflow: 'hidden'
        }}
      >
        <Icon size={18} color={isActive ? item.color : '#6b7280'} style={{ flexShrink: 0 }} />
        <motion.span
          animate={{ opacity: hovered ? 1 : 0, x: hovered ? 0 : -8 }}
          transition={{ duration: 0.2, delay: hovered ? 0.05 : 0 }}
          style={{
            color: isActive ? item.color : '#9ca3af',
            fontWeight: isActive ? '700' : '500',
            fontSize: '0.88rem', whiteSpace: 'nowrap',
            pointerEvents: 'none'
          }}>
          {item.label}
        </motion.span>
      </motion.div>
    </Link>
  );
};

const Layout = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [hovered, setHovered] = useState(false);
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);

  const closeChangePassword = () => {
    setShowChangePassword(false);
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
  };

  const handleChangePassword = async () => {
    if (newPassword.length < 8) {
      toast.error('New password must be at least 8 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error("New passwords don't match");
      return;
    }
    setChangingPassword(true);
    try {
      await axios.post(`${API_BASE_URL}/api/users/me/change-password`, {
        current_password: currentPassword,
        new_password: newPassword,
      });
      toast.success('Password changed successfully');
      closeChangePassword();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to change password');
    } finally {
      setChangingPassword(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Admin-only: how many Message Descriptions are waiting for approval
  // (see the maker-checker gate in message_descriptions.py). The backend
  // itself returns 0 for non-admins, but skipping the call entirely for
  // them avoids a pointless request on every page for users who could
  // never act on this anyway.
  useEffect(() => {
    if (!user?.is_admin) return;
    let cancelled = false;
    const fetchCount = async () => {
      try {
        const res = await axios.get(`${API_BASE_URL}/api/message-descriptions/pending-approval-count`);
        if (!cancelled) setPendingApprovals(res.data.count || 0);
      } catch {
        // Silent — a notification badge failing to load isn't worth
        // interrupting the user with an error.
      }
    };
    fetchCount();
    const interval = setInterval(fetchCount, 30000);
    // Immediate refetch right after an approve/reject/delete elsewhere in
    // the app, instead of waiting up to 30s and looking stale/broken.
    window.addEventListener(PENDING_APPROVALS_CHANGED_EVENT, fetchCount);
    return () => {
      cancelled = true;
      clearInterval(interval);
      window.removeEventListener(PENDING_APPROVALS_CHANGED_EVENT, fetchCount);
    };
  }, [user?.is_admin]);

  // Personal notifications — every user, not just admins (this is the
  // OTHER side of maker-checker: when YOUR proposal gets approved or
  // rejected on someone else's screen, this is how you find out).
  const [notifications, setNotifications] = useState([]);
  const [unreadNotifCount, setUnreadNotifCount] = useState(0);
  const [showNotifPanel, setShowNotifPanel] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetchUnread = async () => {
      try {
        const res = await axios.get(`${API_BASE_URL}/api/notifications/unread-count`);
        if (!cancelled) setUnreadNotifCount(res.data.count || 0);
      } catch {
        // Silent, same reasoning as the pending-approvals badge above.
      }
    };
    fetchUnread();
    const interval = setInterval(fetchUnread, 30000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  const toggleNotifPanel = async () => {
    const next = !showNotifPanel;
    setShowNotifPanel(next);
    if (next) {
      try {
        const res = await axios.get(`${API_BASE_URL}/api/notifications/`);
        setNotifications(res.data);
      } catch {
        // Panel just shows empty — not worth a hard error for this.
      }
    }
  };

  const markAllNotificationsRead = async () => {
    try {
      await axios.post(`${API_BASE_URL}/api/notifications/mark-all-read`);
      setUnreadNotifCount(0);
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    } catch {
      // Non-critical — worst case the badge stays until next poll.
    }
  };

  const deleteNotification = async (id) => {
    const target = notifications.find(n => n.id === id);
    setNotifications(prev => prev.filter(n => n.id !== id));
    if (target && !target.is_read) setUnreadNotifCount(prev => Math.max(0, prev - 1));
    try {
      await axios.delete(`${API_BASE_URL}/api/notifications/${id}`);
    } catch {
      // Non-critical — worst case it reappears next time the panel opens.
    }
  };

  const handleNotificationClick = async (n) => {
    if (!n.is_read) {
      setUnreadNotifCount(prev => Math.max(0, prev - 1));
      setNotifications(prev => prev.map(x => x.id === n.id ? { ...x, is_read: true } : x));
      try {
        await axios.post(`${API_BASE_URL}/api/notifications/${n.id}/read`);
      } catch {
        // Non-critical — worst case the badge stays until next poll.
      }
    }
    if (n.link) {
      setShowNotifPanel(false);
      navigate(n.link);
    }
  };

  const clearAllNotifications = async () => {
    setNotifications([]);
    setUnreadNotifCount(0);
    try {
      await axios.delete(`${API_BASE_URL}/api/notifications/`);
    } catch {
      // Non-critical — worst case they reappear next time the panel opens.
    }
  };

  // Core pipeline, in the order it's actually walked: Message Description
  // (upload+approve a reference) -> Mapping (map fields, Transform a
  // file) -> Outputs (past results). Validate sits alongside Mapping
  // rather than between it and Outputs — it's not a step performed in
  // sequence, it's a check Transform already runs automatically (see
  // WorkflowSteps), plus a standalone tool reachable any time. Everything
  // else is a secondary tool, not part of that core pipeline — kept below
  // a visual divider.
  const navItems = [
    { path: '/dashboard',             icon: Home,          label: 'Dashboard',       color: '#667eea' },
    { path: '/message-descriptions',  icon: Layers,        label: 'Message Desc',    color: '#06b6d4' },
    { path: '/mappings',              icon: GitMerge,      label: 'Mapping',         color: '#f472b6' },
    { path: '/validate',              icon: Shield,        label: 'Validate',        color: '#10b981' },
    { path: '/outputs',               icon: FileOutput,    label: 'Outputs',         color: '#10b981' },
  ];

  const secondaryNavItems = [
    { path: '/config',                icon: Settings,           label: 'Configuration',     color: '#a78bfa' },
    { path: '/pipeline',              icon: GitBranch,          label: 'Consommation',      color: '#f59e0b' },
    { path: '/business-variables',    icon: SlidersHorizontal,  label: 'Business Variables', color: '#06b6d4' },
    { path: '/reference-data',        icon: Database,           label: 'Reference Data',    color: '#06b6d4' },
    { path: '/pending-transactions',  icon: Lock,               label: 'Pending Transactions', color: '#f59e0b' },
    { path: '/batch',                 icon: Layers2,            label: 'Batch Processing',  color: '#f472b6' },
  ];

  const adminNavItems = [
    { path: '/admin',      icon: Users,       label: 'User Management', color: '#ef4444' },
    { path: '/audit-log',  icon: ScrollText,  label: 'Audit Log',       color: '#ef4444' },
  ];

  const complianceNavItems = [
    { path: '/watchlist',  icon: ShieldAlert, label: 'Watchlist',       color: '#ef4444' },
  ];

  // Admin OR compliance officer — same gating as the backend's
  // _require_compliance_access, since this report is compliance's own
  // deliverable, not an admin-only oversight tool.
  const reportsNavItems = [
    { path: '/reports',        icon: FileBarChart, label: 'Regulatory Reports', color: '#ef4444' },
    { path: '/sla-dashboard',  icon: Activity,      label: 'SLA Dashboard',     color: '#06b6d4' },
  ];

  const sidebarWidth = hovered ? '220px' : '64px';

  return (
    <div style={{ minHeight: '100vh', display: 'flex',
      background: 'linear-gradient(135deg, #0f0f23 0%, #1a1a2e 50%, #16213e 100%)' }}>

      <motion.div
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        animate={{ width: sidebarWidth }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        style={{
          position: 'fixed', top: 0, left: 0, height: '100vh',
          background: 'rgba(26, 26, 46, 0.97)', backdropFilter: 'blur(20px)',
          borderRight: '1px solid rgba(255,255,255,0.08)',
          display: 'flex', flexDirection: 'column',
          zIndex: 1000, overflow: 'hidden',
          boxShadow: hovered ? '6px 0 40px rgba(0,0,0,0.4)' : '2px 0 15px rgba(0,0,0,0.2)',
          transition: 'box-shadow 0.3s ease'
        }}
      >
        <div style={{
          padding: '1.25rem',
          display: 'flex', alignItems: 'center', gap: '0.75rem',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
          minHeight: '64px', overflow: 'hidden'
        }}>
          <Sparkles size={22} color="#667eea" style={{ flexShrink: 0 }} />
          <motion.span
            animate={{ opacity: hovered ? 1 : 0, x: hovered ? 0 : -10 }}
            transition={{ duration: 0.2 }}
            style={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              fontWeight: '800', fontSize: '1.05rem', whiteSpace: 'nowrap',
              pointerEvents: 'none'
            }}>
            Smart Mapping
          </motion.span>
        </div>

        {user?.is_admin && pendingApprovals > 0 && (
          <Link to="/message-descriptions" style={{ textDecoration: 'none', display: 'block', padding: '3px 8px 0' }}>
            <motion.div
              whileHover={{ background: 'rgba(245,158,11,0.12)' }}
              whileTap={{ scale: 0.97 }}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.85rem',
                padding: '0.7rem 0.85rem', borderRadius: '10px',
                background: 'rgba(245,158,11,0.08)',
                border: '1px solid rgba(245,158,11,0.25)',
                cursor: 'pointer', overflow: 'hidden', position: 'relative'
              }}
            >
              <div style={{ position: 'relative', flexShrink: 0 }}>
                <Bell size={18} color="#f59e0b" />
                <span style={{
                  position: 'absolute', top: '-6px', right: '-8px',
                  background: '#ef4444', color: 'white', borderRadius: '999px',
                  fontSize: '10px', fontWeight: '800', lineHeight: 1,
                  padding: '2px 5px', minWidth: '16px', textAlign: 'center'
                }}>
                  {pendingApprovals}
                </span>
              </div>
              <motion.span
                animate={{ opacity: hovered ? 1 : 0, x: hovered ? 0 : -8 }}
                transition={{ duration: 0.2 }}
                style={{
                  color: '#f59e0b', fontWeight: '700', fontSize: '0.85rem',
                  whiteSpace: 'nowrap', pointerEvents: 'none'
                }}>
                {pendingApprovals} pending approval{pendingApprovals > 1 ? 's' : ''}
              </motion.span>
            </motion.div>
          </Link>
        )}

        <nav style={{ flex: 1, padding: '0.75rem 0', overflowY: 'auto', overflowX: 'hidden' }}>
          {navItems.map((item) => renderNavItem(item, location, hovered))}

          <div style={{ margin: '0.5rem 1rem', borderTop: '1px solid rgba(255,255,255,0.08)' }} />

          {secondaryNavItems.map((item) => renderNavItem(item, location, hovered))}

          {(user?.is_admin || user?.is_compliance_officer) && (
            <div style={{ margin: '0.5rem 1rem', borderTop: '1px solid rgba(239,68,68,0.15)' }} />
          )}
          {user?.is_admin && adminNavItems.map((item) => renderNavItem(item, location, hovered))}
          {user?.is_compliance_officer && complianceNavItems.map((item) => renderNavItem(item, location, hovered))}
          {(user?.is_admin || user?.is_compliance_officer) && reportsNavItems.map((item) => renderNavItem(item, location, hovered))}
        </nav>

        <div style={{ padding: '0 8px', position: 'relative' }}>
          <motion.button
            whileHover={{ background: 'rgba(255,255,255,0.06)' }}
            whileTap={{ scale: 0.97 }}
            onClick={toggleNotifPanel}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.85rem', width: '100%',
              padding: '0.7rem 0.85rem', marginBottom: '6px',
              background: showNotifPanel ? 'rgba(255,255,255,0.06)' : 'transparent',
              border: 'none', borderRadius: '10px', cursor: 'pointer', overflow: 'hidden'
            }}
          >
            <div style={{ position: 'relative', flexShrink: 0 }}>
              <Bell size={18} color={unreadNotifCount > 0 ? '#06b6d4' : '#6b7280'} />
              {unreadNotifCount > 0 && (
                <span style={{
                  position: 'absolute', top: '-6px', right: '-8px',
                  background: '#ef4444', color: 'white', borderRadius: '999px',
                  fontSize: '10px', fontWeight: '800', lineHeight: 1,
                  padding: '2px 5px', minWidth: '16px', textAlign: 'center'
                }}>
                  {unreadNotifCount}
                </span>
              )}
            </div>
            <motion.span
              animate={{ opacity: hovered ? 1 : 0, x: hovered ? 0 : -8 }}
              transition={{ duration: 0.2 }}
              style={{
                color: unreadNotifCount > 0 ? '#06b6d4' : '#9ca3af',
                fontWeight: '600', fontSize: '0.85rem', whiteSpace: 'nowrap', pointerEvents: 'none'
              }}>
              Notifications
            </motion.span>
          </motion.button>

          {createPortal(
            <AnimatePresence>
              {showNotifPanel && (
                <motion.div
                  initial={{ opacity: 0, y: 10, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 10, scale: 0.98 }}
                  style={{
                    position: 'fixed', bottom: '4.5rem', left: '72px',
                    width: '320px', maxHeight: '380px', overflowY: 'auto',
                    background: 'rgba(26,26,46,0.98)', backdropFilter: 'blur(20px)',
                    border: '1px solid rgba(255,255,255,0.1)', borderRadius: '14px',
                    boxShadow: '0 12px 40px rgba(0,0,0,0.5)', zIndex: 9999, padding: '0.75rem'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem', padding: '0 0.25rem' }}>
                    <span style={{ color: 'white', fontWeight: '700', fontSize: '0.9rem' }}>Notifications</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      {unreadNotifCount > 0 && (
                        <button onClick={markAllNotificationsRead} style={{
                          display: 'flex', alignItems: 'center', gap: '4px',
                          background: 'none', border: 'none', color: '#06b6d4',
                          fontSize: '0.75rem', cursor: 'pointer', padding: '2px 4px'
                        }}>
                          <Check size={12} /> Mark all read
                        </button>
                      )}
                      {notifications.length > 0 && (
                        <button onClick={clearAllNotifications} style={{
                          display: 'flex', alignItems: 'center', gap: '4px',
                          background: 'none', border: 'none', color: '#ef4444',
                          fontSize: '0.75rem', cursor: 'pointer', padding: '2px 4px'
                        }}>
                          <Trash2 size={12} /> Clear all
                        </button>
                      )}
                    </div>
                  </div>
                  {notifications.length === 0 ? (
                    <div style={{ color: '#6b7280', fontSize: '0.85rem', textAlign: 'center', padding: '1.5rem 0.5rem' }}>
                      No notifications yet
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {notifications.map(n => (
                        <div
                          key={n.id}
                          onClick={() => handleNotificationClick(n)}
                          style={{
                            padding: '0.6rem 0.7rem', borderRadius: '8px',
                            background: n.is_read ? 'transparent' : 'rgba(6,182,212,0.08)',
                            border: `1px solid ${n.is_read ? 'rgba(255,255,255,0.05)' : 'rgba(6,182,212,0.2)'}`,
                            display: 'flex', alignItems: 'flex-start', gap: '6px',
                            cursor: n.link ? 'pointer' : 'default'
                          }}
                        >
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ color: n.is_read ? '#9ca3af' : '#e5e7eb', fontSize: '0.8rem', lineHeight: 1.4 }}>
                              {n.message}
                            </div>
                            <div style={{ color: '#6b7280', fontSize: '0.7rem', marginTop: '3px' }}>
                              {new Date(n.created_at).toLocaleString()}
                            </div>
                          </div>
                          <button
                            onClick={(e) => { e.stopPropagation(); deleteNotification(n.id); }}
                            title="Delete"
                            style={{
                              background: 'none', border: 'none', color: '#6b7280',
                              cursor: 'pointer', padding: '2px', flexShrink: 0, borderRadius: '4px'
                            }}
                            onMouseEnter={e => { e.currentTarget.style.color = '#ef4444'; }}
                            onMouseLeave={e => { e.currentTarget.style.color = '#6b7280'; }}
                          >
                            <X size={14} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>,
            document.body
          )}
        </div>

        <div style={{
          padding: '0.75rem 8px',
          borderTop: '1px solid rgba(255,255,255,0.08)',
          display: 'flex', flexDirection: 'column', gap: '6px'
        }}>
          <div
            onClick={() => setShowChangePassword(true)}
            title="Change password"
            style={{
              display: 'flex', alignItems: 'center', gap: '0.75rem',
              padding: '0.6rem 0.85rem',
              background: 'rgba(255,255,255,0.04)',
              borderRadius: '10px', overflow: 'hidden', cursor: 'pointer'
            }}>
            <span style={{ fontSize: '1rem', flexShrink: 0 }}>
              {user?.is_admin ? '🛡️' : '👤'}
            </span>
            <motion.div
              animate={{ opacity: hovered ? 1 : 0, x: hovered ? 0 : -8 }}
              transition={{ duration: 0.2 }}
              style={{ overflow: 'hidden', pointerEvents: 'none', flex: 1 }}
            >
              <div style={{
                color: 'white', fontWeight: '600', fontSize: '0.85rem',
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
              }}>
                {user?.username}
              </div>
              <div style={{
                fontSize: '0.7rem',
                color: user?.is_admin ? '#a78bfa' : '#667eea',
                fontWeight: '600'
              }}>
                {user?.is_admin ? 'Administrator' : 'User'}
              </div>
            </motion.div>
            <KeyRound size={14} color="#6b7280" style={{ flexShrink: 0 }} />
          </div>

          <motion.button
            whileHover={{ background: 'rgba(239,68,68,0.15)' }}
            whileTap={{ scale: 0.97 }}
            onClick={handleLogout}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.75rem',
              padding: '0.6rem 0.85rem',
              background: 'rgba(239,68,68,0.08)',
              color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)',
              borderRadius: '10px', cursor: 'pointer', fontWeight: '600',
              fontSize: '0.85rem', width: '100%', overflow: 'hidden'
            }}
          >
            <LogOut size={16} style={{ flexShrink: 0 }} />
            <motion.span
              animate={{ opacity: hovered ? 1 : 0, x: hovered ? 0 : -8 }}
              transition={{ duration: 0.2 }}
              style={{ whiteSpace: 'nowrap', pointerEvents: 'none' }}>
              Logout
            </motion.span>
          </motion.button>
        </div>
      </motion.div>

      {createPortal(
        <AnimatePresence>
          {showChangePassword && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              style={{
                position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                zIndex: 2000, padding: '1rem'
              }}
              onClick={e => e.target === e.currentTarget && !changingPassword && closeChangePassword()}>
              <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                style={{
                  background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '16px', padding: '2rem', width: '100%', maxWidth: '420px'
                }}>
                <h2 style={{ color: 'white', fontWeight: '800', marginBottom: '1.5rem', fontSize: '1.2rem',
                  display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <KeyRound size={20} color="#06b6d4" /> Change Password
                </h2>

                <label style={modalLabelStyle}>Current Password</label>
                <PasswordInput
                  value={currentPassword}
                  onChange={e => setCurrentPassword(e.target.value)}
                  style={modalInputStyle}
                  autoComplete="current-password"
                />

                <label style={{ ...modalLabelStyle, marginTop: '1rem' }}>New Password</label>
                <PasswordInput
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  style={modalInputStyle}
                  placeholder="Min 8 characters"
                  autoComplete="new-password"
                />

                <label style={{ ...modalLabelStyle, marginTop: '1rem' }}>Confirm New Password</label>
                <PasswordInput
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  style={modalInputStyle}
                  autoComplete="new-password"
                />

                <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
                  <button onClick={closeChangePassword} disabled={changingPassword} style={{
                    padding: '0.6rem 1.2rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.15)',
                    background: 'none', color: '#9ca3af', cursor: changingPassword ? 'not-allowed' : 'pointer', fontWeight: '600'
                  }}>Cancel</button>
                  <button onClick={handleChangePassword} disabled={changingPassword} style={{
                    padding: '0.6rem 1.2rem', borderRadius: '8px', border: '1px solid rgba(6,182,212,0.3)',
                    background: 'rgba(6,182,212,0.15)', color: '#06b6d4', cursor: changingPassword ? 'not-allowed' : 'pointer',
                    fontWeight: '600', opacity: changingPassword ? 0.6 : 1
                  }}>{changingPassword ? 'Saving...' : 'Save'}</button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body
      )}

      <motion.main
        animate={{ marginLeft: sidebarWidth }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        style={{
          flex: 1, minHeight: '100vh',
          padding: '2rem',
          position: 'relative', zIndex: 1,
          overflowX: 'hidden'
        }}
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          {children}
        </motion.div>
      </motion.main>

      <style>{`
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
      `}</style>
    </div>
  );
};

const modalLabelStyle = {
  display: 'block', color: '#9ca3af', fontSize: '0.8rem', fontWeight: '600', marginBottom: '0.4rem'
};

const modalInputStyle = {
  background: 'rgba(255,255,255,0.07)',
  border: '1px solid rgba(255,255,255,0.15)',
  borderRadius: '8px', color: 'white',
  padding: '0.5rem 0.75rem', fontSize: '0.85rem',
};

export default Layout;