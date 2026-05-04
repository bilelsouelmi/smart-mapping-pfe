import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronRight, Plus, Edit2, Trash2, RefreshCw, FileText, Layers, X, Check, Upload, Shield } from 'lucide-react';
import Layout from '../components/Layout';

const API = 'http://localhost:8000/api';

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
  const fileInputRef = useRef(null);

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
        alert('❌ ' + errMsg);
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

  const handleParse = async () => {
    if (!selectedMD) return;
    setImporting(true);
    const isSWIFT = selectedMD.mt_type || selectedMD.file_type === 'XML_MT';
    const endpoint = isSWIFT
      ? `${API}/message-descriptions/${selectedMD.id}/elements/import-from-blocks`
      : `${API}/message-descriptions/${selectedMD.id}/elements/import-from-columns`;
    try {
      await axios.post(endpoint);
      await fetchElements(selectedMD.id);
    } catch (e) {
      alert(e.response?.data?.detail || 'Parse failed');
    } finally { setImporting(false); }
  };

  const handleSetAsStandard = async () => {
    if (!selectedMD) return;
    if (!window.confirm(`Set ${selectedMD.mt_type || selectedMD.file_name} as the standard reference for validation?`)) return;
    setSettingStandard(true);
    try {
      const r = await axios.post(`${API}/validation/validation-rules/import-from-md/${selectedMD.id}`);
      alert(`✅ ${r.data.message}`);
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to set as standard');
    } finally { setSettingStandard(false); }
  };

  const handleNewFile = () => {
    setSelectedMD(null);
    setElements([]);
    setUploadedFile(null);
    sessionStorage.removeItem('md_page_state');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDelete = async (elementId) => {
    if (!window.confirm('Delete this element and all its children?')) return;
    try {
      await axios.delete(`${API}/message-descriptions/${selectedMD.id}/elements/${elementId}`);
      fetchElements(selectedMD.id);
    } catch (e) { alert('Delete failed'); }
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
      alert(e.response?.data?.detail || 'Save failed');
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
              Hierarchical field structure of SWIFT MT messages
            </p>
          </motion.div>

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
                  <input ref={fileInputRef} type="file" accept=".txt,.xml,.csv,.json,.xlsx"
                    style={{ display: 'none' }}
                    onChange={e => handleFileUpload(e.target.files[0])} />
                  {uploading ? (
                    <div style={{ color: '#06b6d4' }}>
                      <div className="spinner" style={{ margin: '0 auto 1rem', width: '32px', height: '32px', borderWidth: '3px' }} />
                      <div style={{ fontSize: '1.1rem', fontWeight: '600' }}>Parsing {uploadedFile}...</div>
                    </div>
                  ) : (
                    <>
                      <Upload size={48} color="#06b6d4" style={{ margin: '0 auto 1rem' }} />
                      <div style={{ color: 'white', fontSize: '1.3rem', fontWeight: '700', marginBottom: '0.5rem' }}>
                        Upload SWIFT File
                      </div>
                      <div style={{ color: '#6b7280', fontSize: '0.9rem' }}>
                        Drop your file here or click to browse
                      </div>
                      <div style={{ color: '#4b5563', fontSize: '0.8rem', marginTop: '0.5rem' }}>
                        Supports .txt .xml .csv .json .xlsx
                      </div>
                    </>
                  )}
                </div>
              </GlassCard>
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
                      <span style={{ color: '#06b6d4', fontWeight: '700', fontSize: '14px' }}>
                        {selectedMD.mt_type || selectedMD.file_name}
                      </span>
                      {selectedMD.iso_target && (
                        <span style={{ color: '#4b5563', fontSize: '11px' }}>
                          → {selectedMD.iso_target}
                        </span>
                      )}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {/* Parse button */}
                    <ActionBtn
                      icon={<RefreshCw size={14} />}
                      label={importing ? 'Parsing...' : 'Parse'}
                      color="#06b6d4"
                      onClick={handleParse}
                      disabled={importing}
                    />
                    {/* Add Element */}
                    <ActionBtn
                      icon={<Plus size={14} />}
                      label="Add Element"
                      color="#667eea"
                      onClick={() => handleOpenCreate(null)}
                    />
                    {/* Set as Standard */}
                    <ActionBtn
                      icon={<Shield size={14} />}
                      label={settingStandard ? 'Setting...' : 'Set as Standard'}
                      color="#10b981"
                      onClick={handleSetAsStandard}
                      disabled={settingStandard || elements.length === 0}
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
                      Click <strong style={{ color: '#06b6d4' }}>Parse</strong> to generate elements automatically.
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
        `}</style>
      </div>

      <AnimatePresence>
        {showModal && (
          <ElementModal mode={modalMode} element={modalElement}
            onSave={handleSave} onClose={() => setShowModal(false)} />
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
          {element.name}
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
  });

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
            if (!form.name) { alert('Name is required'); return; }
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