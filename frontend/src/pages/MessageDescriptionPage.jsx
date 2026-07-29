import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-toastify';
import { ChevronDown, ChevronRight, Plus, Edit2, Trash2, RefreshCw, FileText, Layers, X, Check, Upload, Shield, KeyRound, ArrowLeft, Clock } from 'lucide-react';
import Layout from '../components/Layout';
import WorkflowSteps from '../components/WorkflowSteps';
import { useAuth } from '../contexts/AuthContext';
import { PENDING_APPROVALS_CHANGED_EVENT } from '../constants/events';

const API = 'http://localhost:8000/api';

// Notifies Layout.jsx's sidebar badge to refetch immediately instead of
// waiting for its 30s poll — otherwise approving/rejecting something here
// leaves a visibly stale count until the next tick, which reads as "did
// this actually work?" rather than a smooth, immediate confirmation.
const notifyPendingApprovalsChanged = () => {
  window.dispatchEvent(new Event(PENDING_APPROVALS_CHANGED_EVENT));
};

const ELEMENT_TYPES = ['STRING', 'INTEGER', 'DECIMAL', 'DATE', 'CODE', 'COMPOSITE', 'BOOLEAN'];
const PATTERNS = [
  '^[a-zA-Z0-9\\s\\.\\-\\:]*$',
  '^[a-zA-Z0-9]*$',
  '^[a-zA-Z]*$',
  '^[a-z]*$',
  '^[A-Z]*$',
  '^[0-9]*$',
];

const MessageDescriptionPage = () => {
  const { user } = useAuth();
  const [selectedMD, setSelectedMD] = useState(null);
  const [elements, setElements] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState('create');
  const [modalElement, setModalElement] = useState(null);
  const [modalParentId, setModalParentId] = useState(null);
  const [importing, setImporting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [settingStandard, setSettingStandard] = useState(false);
  const [approving, setApproving] = useState(false);
  const [pendingList, setPendingList] = useState([]);
  const [loadingPending, setLoadingPending] = useState(false);
  const [showAccessRequestModal, setShowAccessRequestModal] = useState(false);
  const [accessRequestAction, setAccessRequestAction] = useState('delete');
  const [accessRequestReason, setAccessRequestReason] = useState('');
  const [requestingAccess, setRequestingAccess] = useState(false);
  const fileInputRef = useRef(null);

  // The notification badge in the sidebar links here promising "N pending
  // approvals" to review, but until now this page had no way to actually
  // BROWSE an existing Message Description — only upload a brand new one.
  // Fetch the pending ones (admin-only, mirrors the maker-checker gate in
  // message_descriptions.py) so clicking the badge leads somewhere useful.
  useEffect(() => {
    if (selectedMD || !user?.is_admin) return;
    const fetchPending = async () => {
      setLoadingPending(true);
      try {
        const r = await axios.get(`${API}/message-descriptions/`);
        const pending = (r.data || []).filter(
          md => md.approved === null && md.column_structure && md.column_structure.length > 0
        );
        setPendingList(pending);
      } catch (e) {
        console.error(e);
      } finally {
        setLoadingPending(false);
      }
    };
    fetchPending();
  }, [selectedMD, user?.is_admin]);

  // Approved references, browsable by EVERYONE (not admin-gated like the
  // pending list above) — otherwise there was no way for a regular user
  // to even find an existing approved Message Description to view it,
  // let alone use the new "Request Access" button on one.
  const [approvedList, setApprovedList] = useState([]);
  const [loadingApproved, setLoadingApproved] = useState(false);

  useEffect(() => {
    if (selectedMD) return;
    const fetchApproved = async () => {
      setLoadingApproved(true);
      try {
        const r = await axios.get(`${API}/message-descriptions/`);
        const approved = (r.data || []).filter(md => md.approved === true);
        setApprovedList(approved);
      } catch (e) {
        console.error(e);
      } finally {
        setLoadingApproved(false);
      }
    };
    fetchApproved();
  }, [selectedMD]);

  // A non-admin proposer has no other way to find their own submission
  // again once they've navigated away — the pending-approvals list above
  // is admin-only (it's a review queue, not a "my submissions" view), so
  // after uploading and generating an MD, a regular user could lose track
  // of it entirely while it sits waiting for an admin. This finds their
  // own most recent submission (pending or approved) regardless of role.
  const [myLastRequest, setMyLastRequest] = useState(null);

  useEffect(() => {
    if (selectedMD || !user?.id) return;
    const fetchMyLast = async () => {
      try {
        const r = await axios.get(`${API}/message-descriptions/`);
        const mine = (r.data || []).filter(md => md.user_id === user.id);
        mine.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        setMyLastRequest(mine[0] || null);
      } catch (e) {
        console.error(e);
      }
    };
    fetchMyLast();
  }, [selectedMD, user?.id]);

  // Restore state from sessionStorage on mount
  useEffect(() => {
    const saved = sessionStorage.getItem('md_page_state');
    if (saved) {
      try {
        const { md, file } = JSON.parse(saved);
        if (md) {
          setSelectedMD(md);
          setUploadedFile(file);
        }
      } catch (e) {}
    }
  }, []);

  // Save state to sessionStorage when MD changes
  useEffect(() => {
    if (selectedMD) {
      sessionStorage.setItem('md_page_state', JSON.stringify({
        md: selectedMD,
        file: uploadedFile
      }));
      fetchElements(selectedMD.id);
    } else {
      sessionStorage.removeItem('md_page_state');
    }
  }, [selectedMD]);

  const fetchElements = async (mdId) => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/message-descriptions/${mdId}/elements`);
      setElements(r.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const handleFileUpload = async (file) => {
    if (!file) return;
    setUploading(true);
    setUploadedFile(file.name);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await axios.post(`${API}/files/analyze`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setSelectedMD(res.data);
      setElements([]);
    } catch (e) {
      const errMsg = e.response?.data?.detail || e.message || 'Upload failed';
      if (!errMsg.includes('LLM') && !errMsg.includes('JSON')) {
        toast.error(errMsg);
      }
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  };

  const handleGenerate = async () => {
    if (!selectedMD) return;
    setImporting(true);
    // "import-from-blocks" builds a real hierarchical tree from
    // mt_blocks/sub_fields — populated for BOTH SWIFT MT text (block4
    // tags) and ISO 20022 XML (dotted XML paths, via
    // extract_xml_source_fields in file_processor.py). Anything with a
    // detected mt_type — whichever side was actually uploaded — has that
    // structure; only truly generic tabular files (CSV/JSON/Excel, no
    // mt_type) fall back to the flat column importer.
    const isStructuredMessage = selectedMD.mt_type || selectedMD.file_type === 'XML_MT';
    const endpoint = isStructuredMessage
      ? `${API}/message-descriptions/${selectedMD.id}/elements/import-from-blocks`
      : `${API}/message-descriptions/${selectedMD.id}/elements/import-from-columns`;
    try {
      await axios.post(endpoint);
      await fetchElements(selectedMD.id);
      // ── Auto Set as Standard after generation ──────────────────────────────
      // Rules are saved to DB automatically — no manual click needed
      await axios.post(`${API}/validation/validation-rules/import-from-md/${selectedMD.id}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Generation failed');
    } finally { setImporting(false); }
  };

  const handleApprove = async () => {
    if (!selectedMD) return;
    setApproving(true);
    try {
      const r = await axios.put(`${API}/message-descriptions/${selectedMD.id}`, { approved: true });
      setSelectedMD(r.data);
      toast.success(`✅ Approved — "${r.data.file_name}" is now the reference for ${r.data.mt_type || r.data.file_type}`);
      notifyPendingApprovalsChanged();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Approve failed');
    } finally { setApproving(false); }
  };

  const handleReject = async () => {
    if (!selectedMD) return;
    if (!window.confirm(
      `Reject and discard "${selectedMD.file_name}"? This deletes the generated Message Description ` +
      `(and its elements) entirely — it will not be saved. This cannot be undone.`
    )) return;
    setApproving(true);
    try {
      await axios.delete(`${API}/message-descriptions/${selectedMD.id}`);
      toast.info(`Rejected and discarded "${selectedMD.file_name}"`);
      notifyPendingApprovalsChanged();
      handleNewFile();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Reject failed');
    } finally { setApproving(false); }
  };

  // Same underlying DELETE as handleReject, but for an ALREADY-approved MD
  // — Reject's button only shows pre-approval (approved !== true), so this
  // covers "I approved it, but actually I want it gone" after the fact.
  const handleDeleteMD = async () => {
    if (!selectedMD) return;
    if (!window.confirm(
      `Delete "${selectedMD.file_name}" from the database? This removes the approved Message Description ` +
      `and its elements entirely, and it will no longer be usable as a reference anywhere ` +
      `(mappings, validation). This cannot be undone.`
    )) return;
    setApproving(true);
    try {
      await axios.delete(`${API}/message-descriptions/${selectedMD.id}`);
      toast.info(`Deleted "${selectedMD.file_name}"`);
      notifyPendingApprovalsChanged();
      handleNewFile();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Delete failed');
    } finally { setApproving(false); }
  };

  // Non-admins can't act directly on an already-approved reference (see
  // the access-grant gate in message_descriptions.py) — this submits a
  // request an admin reviews from the Access Requests tab on the Admin
  // page. One-time-use once granted: exercising it consumes the grant.
  const handleRequestAccess = async () => {
    if (!selectedMD) return;
    setRequestingAccess(true);
    try {
      await axios.post(`${API}/access-requests/`, {
        message_description_id: selectedMD.id,
        action_requested: accessRequestAction,
        reason: accessRequestReason || null,
      });
      toast.success('Access request sent — an admin will review it.');
      setShowAccessRequestModal(false);
      setAccessRequestReason('');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Request failed');
    } finally { setRequestingAccess(false); }
  };

  // Regenerates validation_rules from the CURRENT elements (including any
  // Reference Category tag) without touching the element tree itself —
  // the counterpart to "Generate MD", which also regenerates rules but
  // only as a side effect of first wiping and rebuilding every element
  // from the raw parsed file (losing manual edits like a tag set here).
  // Use this after editing an element, not Generate MD.
  const handleSyncValidationRules = async () => {
    if (!selectedMD) return;
    setSettingStandard(true);
    try {
      const r = await axios.post(`${API}/validation/validation-rules/import-from-md/${selectedMD.id}`);
      toast.success(r.data.message || 'Validation rules synced');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to sync validation rules');
    } finally { setSettingStandard(false); }
  };

  const handleNewFile = () => {
    setSelectedMD(null);
    setElements([]);
    setUploadedFile(null);
    sessionStorage.removeItem('md_page_state');
    sessionStorage.removeItem('validate_page_state');
    window.dispatchEvent(new CustomEvent('validate-reset'));
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDelete = async (elementId) => {
    if (!window.confirm('Delete this element and all its children?')) return;
    try {
      await axios.delete(`${API}/message-descriptions/${selectedMD.id}/elements/${elementId}`);
      fetchElements(selectedMD.id);
    } catch (e) { toast.error('Delete failed'); }
  };

  const handleOpenCreate = (parentId = null) => {
    setModalParentId(parentId);
    setModalElement(null);
    setModalMode('create');
    setShowModal(true);
  };

  const handleOpenEdit = (element) => {
    setModalElement(element);
    setModalMode('edit');
    setShowModal(true);
  };

  const handleSave = async (formData) => {
    try {
      if (modalMode === 'create') {
        await axios.post(`${API}/message-descriptions/${selectedMD.id}/elements`, {
          ...formData, parent_id: modalParentId
        });
      } else {
        await axios.put(`${API}/message-descriptions/${selectedMD.id}/elements/${modalElement.id}`, formData);
      }
      setShowModal(false);
      fetchElements(selectedMD.id);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Save failed');
    }
  };

  return (
    <Layout>
      <div style={{
        minHeight: 'calc(100vh - 100px)',
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
        padding: '2rem', marginTop: '-2rem', marginLeft: '-2rem', marginRight: '-2rem',
      }}>
        <div style={{ maxWidth: '1400px', margin: '0 auto' }}>

          <WorkflowSteps current="md" />

          {/* Header */}
          <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}
            style={{ marginBottom: '2rem', textAlign: 'center' }}>
            <h1 style={{
              fontSize: '2.5rem', fontWeight: '800',
              background: 'linear-gradient(135deg, #06b6d4 0%, #667eea 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', marginBottom: '0.5rem'
            }}>
              📋 Message Description
            </h1>
            <p style={{ color: '#a0a0a0', fontSize: '1rem' }}>
              Step 1 — Upload a sample file, Generate MD, then Approve it as the reference for this message type
            </p>
          </motion.div>

          {/* Pending approvals — admin-only, shown above the upload zone
              so the sidebar notification badge actually leads somewhere
              (previously this page had no way to browse an existing MD
              at all, only upload a new one). */}
          {!selectedMD && user?.is_admin && loadingPending && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ marginBottom: '1.5rem' }}>
              <GlassCard>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {[0, 1].map(i => (
                    <div key={i} style={{
                      height: '52px', borderRadius: '10px',
                      background: 'linear-gradient(90deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.07) 50%, rgba(255,255,255,0.03) 100%)',
                      backgroundSize: '200% 100%', animation: 'shimmer 1.4s ease-in-out infinite'
                    }} />
                  ))}
                </div>
              </GlassCard>
            </motion.div>
          )}

          {!selectedMD && user?.is_admin && !loadingPending && pendingList.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              style={{ marginBottom: '1.5rem' }}>
              <GlassCard>
                <div style={{ color: '#f59e0b', fontWeight: '700', fontSize: '0.95rem', marginBottom: '1rem' }}>
                  🔔 {pendingList.length} pending approval{pendingList.length > 1 ? 's' : ''}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '50vh', overflowY: 'auto' }}>
                  <AnimatePresence>
                    {pendingList.map((md, i) => (
                      <motion.div key={md.id}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 10 }}
                        transition={{ delay: i * 0.04 }}
                        whileHover={{ background: 'rgba(245,158,11,0.12)', borderColor: 'rgba(245,158,11,0.4)', x: 2 }}
                        whileTap={{ scale: 0.99 }}
                        onClick={() => setSelectedMD(md)}
                        style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                          padding: '0.75rem 1rem', borderRadius: '10px', cursor: 'pointer',
                          background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.2)',
                          transition: 'border-color 0.15s'
                        }}>
                        <div>
                          <span style={{ color: 'white', fontWeight: '600', fontSize: '0.9rem' }}>{md.file_name}</span>
                          <span style={{ color: '#6b7280', fontSize: '0.8rem', marginLeft: '0.75rem' }}>
                            {md.mt_type || md.file_type} {md.iso_target ? `→ ${md.iso_target}` : ''}
                          </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ color: '#6b7280', fontSize: '0.78rem' }}>
                            proposed by {md.proposed_by_username || '—'}
                          </span>
                          <ChevronRight size={14} color="#6b7280" />
                        </div>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              </GlassCard>
            </motion.div>
          )}

          {/* Approved references — browsable by everyone, so a non-admin
              can actually find one to view, or to use "Request Access"
              on (see the modal below). Loading skeleton mirrors the
              pending-approvals one above. */}
          {!selectedMD && loadingApproved && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ marginBottom: '1.5rem' }}>
              <GlassCard>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {[0, 1].map(i => (
                    <div key={i} style={{
                      height: '52px', borderRadius: '10px',
                      background: 'linear-gradient(90deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.07) 50%, rgba(255,255,255,0.03) 100%)',
                      backgroundSize: '200% 100%', animation: 'shimmer 1.4s ease-in-out infinite'
                    }} />
                  ))}
                </div>
              </GlassCard>
            </motion.div>
          )}

          {!selectedMD && !loadingApproved && approvedList.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              style={{ marginBottom: '1.5rem' }}>
              <GlassCard>
                <div style={{ color: '#10b981', fontWeight: '700', fontSize: '0.95rem', marginBottom: '1rem' }}>
                  ✅ {approvedList.length} approved reference{approvedList.length > 1 ? 's' : ''}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '50vh', overflowY: 'auto' }}>
                  {approvedList.map((md, i) => (
                    <motion.div key={md.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.03 }}
                      whileHover={{ background: 'rgba(16,185,129,0.12)', borderColor: 'rgba(16,185,129,0.4)', x: 2 }}
                      whileTap={{ scale: 0.99 }}
                      onClick={() => setSelectedMD(md)}
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '0.75rem 1rem', borderRadius: '10px', cursor: 'pointer',
                        background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.2)',
                        transition: 'border-color 0.15s'
                      }}>
                      <div>
                        <span style={{ color: 'white', fontWeight: '600', fontSize: '0.9rem' }}>{md.file_name}</span>
                        <span style={{ color: '#6b7280', fontSize: '0.8rem', marginLeft: '0.75rem' }}>
                          {md.mt_type || md.file_type} {md.iso_target ? `→ ${md.iso_target}` : ''}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ color: '#6b7280', fontSize: '0.78rem' }}>
                          approved by {md.approved_by_username || '—'}
                        </span>
                        <ChevronRight size={14} color="#6b7280" />
                      </div>
                    </motion.div>
                  ))}
                </div>
              </GlassCard>
            </motion.div>
          )}

          {/* Upload Zone — shown when no file selected */}
          {!selectedMD && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
              <GlassCard>
                <div
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    border: `2px dashed ${dragOver ? '#06b6d4' : 'rgba(6,182,212,0.3)'}`,
                    borderRadius: '16px', padding: '4rem 2rem', textAlign: 'center',
                    cursor: 'pointer',
                    background: dragOver ? 'rgba(6,182,212,0.05)' : 'transparent',
                    transition: 'all 0.2s'
                  }}
                >
                  <input ref={fileInputRef} type="file" accept=".txt,.xml,.csv,.json,.xlsx,.xls"
                    style={{ display: 'none' }}
                    onChange={e => handleFileUpload(e.target.files[0])} />
                  {uploading ? (
                    <div style={{ color: '#06b6d4' }}>
                      <div className="spinner" style={{ margin: '0 auto 1rem', width: '32px', height: '32px', borderWidth: '3px' }} />
                      <div style={{ fontSize: '1.1rem', fontWeight: '600' }}>Generating {uploadedFile}...</div>
                    </div>
                  ) : (
                    <>
                      <Upload size={48} color="#06b6d4" style={{ margin: '0 auto 1rem' }} />
                      <div style={{ color: 'white', fontSize: '1.3rem', fontWeight: '700', marginBottom: '0.5rem' }}>
                        Upload SWIFT MT or ISO 20022 XML File
                      </div>
                      <div style={{ color: '#6b7280', fontSize: '0.9rem' }}>
                        Drop your file here or click to browse
                      </div>
                      <div style={{ color: '#4b5563', fontSize: '0.8rem', marginTop: '0.5rem' }}>
                        SWIFT MT (.txt) and ISO 20022 XML both build a full Message Description — either direction works. Also supports plain .csv .json .xlsx .xls for generic column mapping.
                      </div>
                    </>
                  )}
                </div>
              </GlassCard>

              {/* "My last request" — lets the proposer jump straight back
                  to their own most recent submission (pending or approved)
                  instead of having no way to find it again once they've
                  navigated away from the confirmation they saw right after
                  uploading. */}
              {myLastRequest && (
                <div style={{ textAlign: 'center', marginTop: '1rem' }}>
                  <button
                    onClick={() => setSelectedMD(myLastRequest)}
                    style={{
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.12)',
                      borderRadius: '10px',
                      padding: '0.6rem 1.25rem',
                      color: '#d1d5db',
                      fontSize: '0.85rem',
                      fontWeight: '600',
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.6rem'
                    }}
                  >
                    {myLastRequest.approved === true
                      ? <Check size={14} color="#10b981" />
                      : <Clock size={14} color="#f59e0b" />}
                    View my last request — "{myLastRequest.file_name}"
                    <span style={{ color: myLastRequest.approved === true ? '#10b981' : '#f59e0b', fontWeight: '700' }}>
                      {myLastRequest.approved === true ? 'approved' : 'pending approval'}
                    </span>
                  </button>
                </div>
              )}
            </motion.div>
          )}

          {/* File loaded — show tree */}
          {selectedMD && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
              <GlassCard>
                {/* Toolbar */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    {/* File info */}
                    <div style={{
                      padding: '6px 14px',
                      background: 'rgba(6,182,212,0.1)',
                      border: '1px solid rgba(6,182,212,0.3)',
                      borderRadius: '8px',
                      display: 'flex', alignItems: 'center', gap: '8px'
                    }}>
                      <FileText size={14} color="#06b6d4" />
                      {/* Badge order reflects what was actually uploaded, not
                          always "MT -> ISO": an XML_ISO20022 upload is the
                          ISO side, so it's shown first with the MT type as
                          the arrow target — the reverse of an MT/text
                          upload. Otherwise this always displayed
                          "MT202 -> pacs.009.001.08" even when the user
                          uploaded the pacs.009 XML itself. */}
                      <span style={{ color: '#06b6d4', fontWeight: '700', fontSize: '14px' }}>
                        {selectedMD.file_type === 'XML_ISO20022'
                          ? (selectedMD.iso_target || selectedMD.file_name)
                          : (selectedMD.mt_type || selectedMD.file_name)}
                      </span>
                      {selectedMD.file_type === 'XML_ISO20022' ? (
                        selectedMD.mt_type && (
                          <span style={{ color: '#4b5563', fontSize: '11px' }}>
                            → {selectedMD.mt_type}
                          </span>
                        )
                      ) : (
                        selectedMD.iso_target && (
                          <span style={{ color: '#4b5563', fontSize: '11px' }}>
                            → {selectedMD.iso_target}
                          </span>
                        )
                      )}
                    </div>

                    {/* Approval status — only meaningful once there's a
                        generated structure to approve or not. */}
                    {elements.length > 0 && (
                      selectedMD.approved ? (
                        <div style={{
                          padding: '6px 14px', background: 'rgba(16,185,129,0.1)',
                          border: '1px solid rgba(16,185,129,0.3)', borderRadius: '8px',
                          display: 'flex', alignItems: 'center', gap: '6px'
                        }}>
                          <Check size={14} color="#10b981" />
                          <span style={{ color: '#10b981', fontWeight: '700', fontSize: '13px' }}>Approved</span>
                        </div>
                      ) : (
                        <div style={{
                          padding: '6px 14px', background: 'rgba(245,158,11,0.1)',
                          border: '1px solid rgba(245,158,11,0.3)', borderRadius: '8px',
                          color: '#f59e0b', fontWeight: '700', fontSize: '13px'
                        }}>
                          ⏳ Pending Approval
                        </div>
                      )
                    )}

                    {/* Maker-checker: who proposed vs who approved — and,
                        while pending, a heads-up that the proposer can't
                        also be the approver, before they hit the button
                        and get a 403. */}
                    {elements.length > 0 && selectedMD.proposed_by_username && (
                      <div style={{ color: '#6b7280', fontSize: '11px', marginTop: '4px' }}>
                        Proposed by <strong>{selectedMD.proposed_by_username}</strong>
                        {selectedMD.approved && selectedMD.approved_by_username && (
                          <> · Approved by <strong>{selectedMD.approved_by_username}</strong></>
                        )}
                        {!selectedMD.approved && !user?.is_admin && user?.username === selectedMD.proposed_by_username && (
                          <span style={{ color: '#f59e0b' }}> — you proposed this, an admin must approve it</span>
                        )}
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {/* Generate MD button */}
                    <ActionBtn
                      icon={<RefreshCw size={14} />}
                      label={importing ? 'Generating...' : 'Generate MD'}
                      color="#06b6d4"
                      onClick={handleGenerate}
                      disabled={importing}
                    />
                    {/* Sync Validation Rules — regenerates rules from the
                        elements as they are NOW (picks up any Reference
                        Category tag) without wiping/rebuilding the tree,
                        unlike Generate MD. Click after editing an element. */}
                    {elements.length > 0 && (
                      <ActionBtn
                        icon={<Shield size={14} />}
                        label={settingStandard ? 'Syncing...' : 'Sync Validation Rules'}
                        color="#a78bfa"
                        onClick={handleSyncValidationRules}
                        disabled={settingStandard}
                      />
                    )}
                    {/* Approve / Reject — the explicit save-or-discard gate:
                        elements are already persisted the moment Generate MD
                        runs, so "reject" doesn't prevent a DB write, it
                        undoes one — deleting the MD and its elements so
                        nothing unapproved lingers as a selectable reference
                        elsewhere (New Mapping, Validate, Generate Elements). */}
                    {/* Approve is admin-only (maker-checker, enforced server-side
                        too) — showing it to anyone else just means a click
                        that always 403s. Reject/discard is available to the
                        proposer themselves as well as an admin (see the
                        matching ownership check in delete_message_description);
                        anyone else viewing someone else's pending draft gets
                        neither button, since they have no rights over it. */}
                    {elements.length > 0 && !selectedMD.approved && user?.is_admin && (
                      <ActionBtn
                        icon={<Check size={14} />}
                        label={approving ? 'Working...' : 'Approve'}
                        color="#10b981"
                        onClick={handleApprove}
                        disabled={approving}
                      />
                    )}
                    {elements.length > 0 && !selectedMD.approved && (user?.is_admin || user?.id === selectedMD.user_id) && (
                      <ActionBtn
                        icon={<X size={14} />}
                        label={approving ? 'Working...' : 'Reject'}
                        color="#ef4444"
                        onClick={handleReject}
                        disabled={approving}
                      />
                    )}
                    {/* Delete — for an MD already approved. Approve/Reject
                        above only appear pre-approval (Reject IS the
                        discard action at that stage); once approved, this
                        is the equivalent "remove it from the database"
                        action for changing your mind afterward. */}
                    {elements.length > 0 && selectedMD.approved && user?.is_admin && (
                      <ActionBtn
                        icon={<Trash2 size={14} />}
                        label={approving ? 'Working...' : 'Delete'}
                        color="#ef4444"
                        onClick={handleDeleteMD}
                        disabled={approving}
                      />
                    )}
                    {/* Non-admins can't act on an approved reference
                        directly — see the access-grant gate in
                        message_descriptions.py — so instead of Delete
                        they get a way to ask an admin for it. */}
                    {elements.length > 0 && selectedMD.approved && !user?.is_admin && (
                      <ActionBtn
                        icon={<KeyRound size={14} />}
                        label="Request Access"
                        color="#06b6d4"
                        onClick={() => setShowAccessRequestModal(true)}
                        disabled={approving}
                      />
                    )}
                    {/* Add Element */}
                    <ActionBtn
                      icon={<Plus size={14} />}
                      label="Add Element"
                      color="#667eea"
                      onClick={() => handleOpenCreate(null)}
                    />

                    {/* New File */}
                    <ActionBtn
                      icon={<Upload size={14} />}
                      label="New File"
                      color="#f59e0b"
                      onClick={handleNewFile}
                    />
                  </div>
                </div>

                {/* Back — returns to the browse view (approved
                    references / pending approvals list) without implying
                    "upload something new" the way the button above does.
                    Same reset under the hood, different intent. */}
                <div style={{ marginTop: '0.75rem' }}>
                  <ActionBtn
                    icon={<ArrowLeft size={14} />}
                    label="Back"
                    color="#6b7280"
                    onClick={handleNewFile}
                  />
                </div>

                {/* Tree */}
                {loading ? (
                  <div style={{ textAlign: 'center', color: '#6b7280', padding: '3rem' }}>
                    <div className="spinner" style={{ margin: '0 auto 1rem' }} />
                    Loading...
                  </div>
                ) : elements.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '3rem' }}>
                    <Layers size={48} color="#374151" style={{ margin: '0 auto 1rem' }} />
                    <p style={{ color: '#6b7280', marginBottom: '0.5rem' }}>No elements yet</p>
                    <p style={{ color: '#4b5563', fontSize: '0.85rem' }}>
                      Click <strong style={{ color: '#06b6d4' }}>Generate MD</strong> to generate elements automatically.
                    </p>
                  </div>
                ) : (
                  <div style={{ fontFamily: 'monospace' }}>
                    {elements.map(el => (
                      <TreeNode key={el.id} element={el} depth={0}
                        onEdit={handleOpenEdit} onDelete={handleDelete} onAddChild={handleOpenCreate} />
                    ))}
                  </div>
                )}
              </GlassCard>
            </motion.div>
          )}
        </div>

        <style>{`
          .spinner {
            width: 18px; height: 18px;
            border: 2px solid rgba(6,182,212,0.3);
            border-top-color: #06b6d4;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            display: inline-block;
          }
          @keyframes spin { to { transform: rotate(360deg); } }
          @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
        `}</style>
      </div>

      <AnimatePresence>
        {showModal && (
          <ElementModal mode={modalMode} element={modalElement}
            onSave={handleSave} onClose={() => setShowModal(false)} />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showAccessRequestModal && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            style={{
              position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 3000
            }}
            onClick={e => e.target === e.currentTarget && setShowAccessRequestModal(false)}>
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
              style={{
                background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '16px', padding: '1.75rem', width: '420px', maxWidth: '90vw'
              }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1.25rem' }}>
                <KeyRound size={20} color="#06b6d4" />
                <span style={{ color: 'white', fontWeight: '700', fontSize: '1.1rem' }}>Request Access</span>
              </div>
              <p style={{ color: '#9ca3af', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
                "{selectedMD?.file_name}" is already approved. An admin needs to grant you
                one-time permission before you can act on it.
              </p>

              <label style={{ color: '#9ca3af', fontSize: '0.8rem', display: 'block', marginBottom: '6px' }}>
                What do you want to do?
              </label>
              <div style={{ display: 'flex', gap: '8px', marginBottom: '1rem' }}>
                {['update', 'delete'].map(a => (
                  <button key={a} onClick={() => setAccessRequestAction(a)} style={{
                    flex: 1, padding: '8px', borderRadius: '8px', cursor: 'pointer',
                    fontWeight: '700', fontSize: '0.85rem', textTransform: 'capitalize',
                    background: accessRequestAction === a ? 'rgba(6,182,212,0.15)' : 'rgba(255,255,255,0.04)',
                    border: `1px solid ${accessRequestAction === a ? '#06b6d4' : 'rgba(255,255,255,0.1)'}`,
                    color: accessRequestAction === a ? '#06b6d4' : '#9ca3af'
                  }}>{a}</button>
                ))}
              </div>

              <label style={{ color: '#9ca3af', fontSize: '0.8rem', display: 'block', marginBottom: '6px' }}>
                Reason (optional)
              </label>
              <textarea value={accessRequestReason} onChange={e => setAccessRequestReason(e.target.value)}
                placeholder="Why do you need this?"
                style={{
                  width: '100%', minHeight: '70px', padding: '0.6rem', borderRadius: '8px',
                  background: '#0f0f23', border: '1px solid rgba(255,255,255,0.1)',
                  color: 'white', fontSize: '0.85rem', resize: 'vertical', boxSizing: 'border-box'
                }} />

              <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '1.25rem' }}>
                <button onClick={() => setShowAccessRequestModal(false)} style={{
                  padding: '8px 16px', background: 'transparent', border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '8px', color: '#9ca3af', cursor: 'pointer'
                }}>Cancel</button>
                <button onClick={handleRequestAccess} disabled={requestingAccess} style={{
                  padding: '8px 18px', background: 'linear-gradient(135deg, #06b6d4, #0891b2)',
                  border: 'none', borderRadius: '8px', color: 'white', fontWeight: '700',
                  cursor: 'pointer', opacity: requestingAccess ? 0.6 : 1
                }}>{requestingAccess ? 'Sending...' : 'Send Request'}</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </Layout>
  );
};

// ── Tree Node ─────────────────────────────────────────────────────────────────
const TreeNode = ({ element, depth, onEdit, onDelete, onAddChild }) => {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = element.children && element.children.length > 0;
  const isHeader = element.field_tag?.startsWith('{');

  return (
    <div>
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: '0.4rem',
          paddingLeft: `${depth * 20}px`, paddingTop: '4px', paddingBottom: '4px',
          borderRadius: '6px', marginBottom: '2px', transition: 'background 0.15s',
          background: isHeader ? 'rgba(16,185,129,0.05)' : 'transparent',
          borderLeft: isHeader ? '2px solid rgba(16,185,129,0.3)' : '2px solid transparent',
        }}
        onMouseEnter={e => e.currentTarget.style.background = isHeader ? 'rgba(16,185,129,0.08)' : 'rgba(255,255,255,0.04)'}
        onMouseLeave={e => e.currentTarget.style.background = isHeader ? 'rgba(16,185,129,0.05)' : 'transparent'}
      >
        <span onClick={() => setExpanded(!expanded)}
          style={{ color: '#4b5563', cursor: 'pointer', width: '14px', flexShrink: 0, fontSize: '12px' }}>
          {hasChildren ? (expanded ? '▾' : '▸') : '•'}
        </span>

        {hasChildren && (
          <span style={{ fontSize: '12px', flexShrink: 0 }}>
            {expanded ? '📂' : '📁'}
          </span>
        )}

        {element.field_tag && (
          <span style={{
            padding: '1px 7px',
            background: isHeader ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)',
            color: isHeader ? '#10b981' : '#f59e0b',
            borderRadius: '4px', fontSize: '11px', fontWeight: '700', flexShrink: 0
          }}>
            {element.field_tag}
          </span>
        )}

        <span style={{ color: isHeader ? '#6ee7b7' : '#e2e8f0', fontSize: '13px', flex: 1 }}>
          {element.name === element.field_tag ? null : element.name}
          {element.description && element.description !== element.name && (
            <span style={{ color: '#4b5563', fontSize: '10px', marginLeft: '6px' }}>
              — {element.description}
            </span>
          )}
        </span>

        {(element.min_length || element.max_length) && (
          <span style={{ color: '#374151', fontSize: '10px', flexShrink: 0 }}>
            {element.min_length ?? '?'}–{element.max_length ?? '?'}
          </span>
        )}

        {element.fin_format && (
          <span style={{
            padding: '1px 5px', background: 'rgba(245,158,11,0.1)',
            color: '#d97706', borderRadius: '4px', fontSize: '10px',
            flexShrink: 0, fontFamily: 'monospace'
          }}>
            {element.fin_format}
          </span>
        )}

        {element.element_type && (
          <span style={{
            padding: '1px 6px',
            background: element.element_type === 'COMPOSITE' ? 'rgba(6,182,212,0.15)' : 'rgba(102,126,234,0.15)',
            color: element.element_type === 'COMPOSITE' ? '#06b6d4' : '#818cf8',
            borderRadius: '4px', fontSize: '10px', flexShrink: 0
          }}>
            {element.element_type}
          </span>
        )}

        {element.example_value && !hasChildren && (
          <span style={{
            color: '#a5f3fc', fontSize: '10px', fontFamily: 'monospace',
            maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis',
            whiteSpace: 'nowrap', flexShrink: 0
          }}>
            = {element.example_value}
          </span>
        )}

        <div style={{ display: 'flex', gap: '3px', flexShrink: 0 }}>
          <IconBtn icon={<Plus size={11} />} color="#06b6d4" onClick={() => onAddChild(element.id)} title="Add child" />
          <IconBtn icon={<Edit2 size={11} />} color="#667eea" onClick={() => onEdit(element)} title="Edit" />
          <IconBtn icon={<Trash2 size={11} />} color="#ef4444" onClick={() => onDelete(element.id)} title="Delete" />
        </div>
      </div>

      {hasChildren && expanded && (
        <div style={{ borderLeft: '1px dashed rgba(255,255,255,0.06)', marginLeft: `${depth * 20 + 8}px` }}>
          {element.children.map(child => (
            <TreeNode key={child.id} element={child} depth={depth + 1}
              onEdit={onEdit} onDelete={onDelete} onAddChild={onAddChild} />
          ))}
        </div>
      )}
    </div>
  );
};

// ── Element Modal ─────────────────────────────────────────────────────────────
const ElementModal = ({ mode, element, onSave, onClose }) => {
  const [form, setForm] = useState({
    name: element?.name || '',
    element_type: element?.element_type || 'STRING',
    field_tag: element?.field_tag || '',
    fin_format: element?.fin_format || '',
    min_length: element?.min_length ?? '',
    max_length: element?.max_length ?? '',
    min_occurs: element?.min_occurs ?? 1,
    max_occurs: element?.max_occurs ?? '',
    mandatory: element?.mandatory ?? true,
    pattern: element?.pattern || '',
    precision: element?.precision ?? '',
    prefix: element?.prefix || '',
    suffix: element?.suffix || '',
    separator: element?.separator || '',
    mandatory_separator: element?.mandatory_separator ?? false,
    description: element?.description || '',
    example_value: element?.example_value || '',
    reference_category: element?.reference_category || '',
  });
  const [refCategories, setRefCategories] = useState([]);

  useEffect(() => {
    axios.get(`${API}/reference-data/categories`).then(r => setRefCategories(r.data)).catch(() => {});
  }, []);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const selectStyle = {
    width: '100%', padding: '8px 12px', background: '#16213e',
    border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px',
    color: 'white', fontSize: '13px', boxSizing: 'border-box', cursor: 'pointer'
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}
      onClick={onClose}>
      <motion.div initial={{ scale: 0.9 }} animate={{ scale: 1 }} exit={{ scale: 0.9 }}
        style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)', border: '1px solid rgba(6,182,212,0.3)', borderRadius: '16px', padding: '2rem', width: '100%', maxWidth: '720px', maxHeight: '90vh', overflowY: 'auto' }}
        onClick={e => e.stopPropagation()}>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h2 style={{ color: 'white', margin: 0, fontSize: '1.1rem' }}>
            Field Value Description: <span style={{ color: '#06b6d4' }}>{form.name || 'New Element'}</span>
          </h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <FormField label="* Value Type">
            <select value={form.element_type} onChange={e => set('element_type', e.target.value)} style={selectStyle}>
              {ELEMENT_TYPES.map(t => <option key={t} value={t} style={{ background: '#16213e' }}>{t}</option>)}
            </select>
          </FormField>
          <FormField label="* Name">
            <input value={form.name} onChange={e => set('name', e.target.value)} style={inputStyle} placeholder="ApplicationIdentifier" />
          </FormField>
          <FormField label="* Min Length">
            <input type="number" value={form.min_length} onChange={e => set('min_length', e.target.value)} style={inputStyle} placeholder="1" />
          </FormField>
          <FormField label="Max Length">
            <input type="number" value={form.max_length} onChange={e => set('max_length', e.target.value)} style={inputStyle} placeholder="35" />
          </FormField>
          <FormField label="* Min Occurs">
            <input type="number" value={form.min_occurs} onChange={e => set('min_occurs', e.target.value)} style={inputStyle} placeholder="1" />
          </FormField>
          <FormField label="* Pattern">
            <select value={form.pattern} onChange={e => set('pattern', e.target.value)} style={selectStyle}>
              <option value="" style={{ background: '#16213e' }}>— Select —</option>
              {PATTERNS.map(p => <option key={p} value={p} style={{ background: '#16213e' }}>{p}</option>)}
            </select>
          </FormField>
          <FormField label="Fin Format">
            <input value={form.fin_format} onChange={e => set('fin_format', e.target.value)} style={inputStyle} placeholder="1!a" />
          </FormField>
          <FormField label="Precision">
            <input type="number" value={form.precision} onChange={e => set('precision', e.target.value)} style={inputStyle} />
          </FormField>
          <FormField label="Prefix">
            <input value={form.prefix} onChange={e => set('prefix', e.target.value)} style={inputStyle} />
          </FormField>
          <FormField label="Suffix">
            <input value={form.suffix} onChange={e => set('suffix', e.target.value)} style={inputStyle} />
          </FormField>
          <FormField label="Separator">
            <input value={form.separator} onChange={e => set('separator', e.target.value)} style={inputStyle} />
          </FormField>
          <FormField label="Example">
            <input value={form.example_value} onChange={e => set('example_value', e.target.value)} style={inputStyle} placeholder="F" />
          </FormField>
          <FormField label="Field Tag">
            <input value={form.field_tag} onChange={e => set('field_tag', e.target.value)} style={inputStyle} placeholder=":20:" />
          </FormField>
          <FormField label="Reference Category">
            <select value={form.reference_category} onChange={e => set('reference_category', e.target.value)} style={selectStyle}>
              <option value="" style={{ background: '#16213e' }}>— None —</option>
              {refCategories.map(c => <option key={c} value={c} style={{ background: '#16213e' }}>{c}</option>)}
            </select>
          </FormField>
          <FormField label="Mandatory Separator">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', paddingTop: '0.5rem' }}>
              <input type="checkbox" checked={form.mandatory_separator}
                onChange={e => set('mandatory_separator', e.target.checked)}
                style={{ width: '16px', height: '16px', cursor: 'pointer' }} />
              <span style={{ color: '#9ca3af', fontSize: '0.85rem' }}>Required</span>
            </div>
          </FormField>
          <div style={{ gridColumn: '1 / -1' }}>
            <FormField label="Description">
              <textarea value={form.description} onChange={e => set('description', e.target.value)}
                rows={3} style={{ ...inputStyle, resize: 'vertical' }} />
            </FormField>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem', justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{ padding: '0.75rem 1.5rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: 'white', cursor: 'pointer', fontSize: '0.9rem' }}>
            Close
          </button>
          <button onClick={() => {
            if (!form.name) { toast.error('Name is required'); return; }
            onSave({
              ...form,
              min_length: form.min_length !== '' ? parseInt(form.min_length) : null,
              max_length: form.max_length !== '' ? parseInt(form.max_length) : null,
              min_occurs: parseInt(form.min_occurs) || 1,
              max_occurs: form.max_occurs !== '' ? parseInt(form.max_occurs) : null,
              precision: form.precision !== '' ? parseInt(form.precision) : null,
            });
          }} style={{ padding: '0.75rem 1.5rem', background: 'linear-gradient(135deg, #06b6d4 0%, #667eea 100%)', border: 'none', borderRadius: '8px', color: 'white', cursor: 'pointer', fontSize: '0.9rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Check size={16} /> OK
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
};

// ── Shared ────────────────────────────────────────────────────────────────────
const GlassCard = ({ children }) => (
  <div style={{ background: 'rgba(255,255,255,0.05)', backdropFilter: 'blur(10px)', borderRadius: '20px', padding: '1.5rem', border: '1px solid rgba(255,255,255,0.1)', boxShadow: '0 8px 32px rgba(0,0,0,0.3)' }}>
    {children}
  </div>
);

const ActionBtn = ({ icon, label, color, onClick, disabled }) => (
  <button onClick={onClick} disabled={disabled} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 14px', background: `${color}20`, border: `1px solid ${color}40`, borderRadius: '8px', color, fontSize: '12px', fontWeight: '600', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.6 : 1, transition: 'all 0.2s' }}>
  {icon} {label}
  </button>
);

const IconBtn = ({ icon, color, onClick, title }) => (
  <button onClick={onClick} title={title} style={{ background: 'none', border: 'none', cursor: 'pointer', color, padding: '3px', borderRadius: '4px', display: 'flex', alignItems: 'center', opacity: 0.4, transition: 'opacity 0.15s' }}
    onMouseEnter={e => e.currentTarget.style.opacity = '1'}
    onMouseLeave={e => e.currentTarget.style.opacity = '0.4'}>
    {icon}
  </button>
);

const FormField = ({ label, children }) => (
  <div>
    <label style={{ display: 'block', color: '#9ca3af', fontSize: '12px', marginBottom: '6px' }}>{label}</label>
    {children}
  </div>
);

const inputStyle = {
  width: '100%', padding: '8px 12px', background: 'rgba(255,255,255,0.05)',
  border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px',
  color: 'white', fontSize: '13px', boxSizing: 'border-box'
};

export default MessageDescriptionPage;