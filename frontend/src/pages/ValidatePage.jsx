import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, CheckCircle, XCircle, AlertTriangle, FileText, Shield, ChevronDown, ChevronRight } from 'lucide-react';
import Layout from '../components/Layout';

const API = 'http://localhost:8000/api';

const ValidatePage = () => {
  const [file, setFile] = useState(null);
  const [validating, setValidating] = useState(false);
  const [result, setResult] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  // Restore from sessionStorage
  useEffect(() => {
    const saved = sessionStorage.getItem('validate_page_state');
    if (saved) {
      try { setResult(JSON.parse(saved)); } catch (e) {}
    }
  }, []);

  const handleFileUpload = async (selectedFile) => {
    if (!selectedFile) return;
    setFile(selectedFile);
    setResult(null);
    sessionStorage.removeItem('validate_page_state');
  };

  const handleValidate = async () => {
    if (!file) return;
    setValidating(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await axios.post(`${API}/validation/validate`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResult(res.data);
      sessionStorage.setItem('validate_page_state', JSON.stringify(res.data));
    } catch (e) {
      const msg = e.response?.data?.detail || 'Validation failed';
      alert('❌ ' + msg);
    } finally {
      setValidating(false);
    }
  };

  const handleNewFile = () => {
    setFile(null);
    setResult(null);
    sessionStorage.removeItem('validate_page_state');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // Group errors/passed by block
  const groupByBlock = (items) => {
    const groups = {};
    items.forEach(item => {
      const block = item.block || 'Unknown';
      if (!groups[block]) groups[block] = [];
      groups[block].push(item);
    });
    return groups;
  };

  return (
    <Layout>
      <div style={{
        minHeight: 'calc(100vh - 100px)',
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
        padding: '2rem', marginTop: '-2rem', marginLeft: '-2rem', marginRight: '-2rem',
      }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>

          {/* Header */}
          <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}
            style={{ marginBottom: '2rem', textAlign: 'center' }}>
            <h1 style={{
              fontSize: '2.5rem', fontWeight: '800',
              background: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', marginBottom: '0.5rem'
            }}>
              🛡️ SWIFT File Validation
            </h1>
            <p style={{ color: '#a0a0a0', fontSize: '1rem' }}>
              Validate client SWIFT files against standard rules
            </p>
          </motion.div>

          {/* Upload Zone */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <GlassCard>
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFileUpload(e.dataTransfer.files[0]); }}
                onClick={() => fileInputRef.current?.click()}
                style={{
                  border: `2px dashed ${dragOver ? '#10b981' : 'rgba(16,185,129,0.3)'}`,
                  borderRadius: '12px', padding: '2rem', textAlign: 'center', cursor: 'pointer',
                  background: dragOver ? 'rgba(16,185,129,0.05)' : 'transparent', transition: 'all 0.2s'
                }}
              >
                <input ref={fileInputRef} type="file" accept=".txt,.xml"
                  style={{ display: 'none' }}
                  onChange={e => handleFileUpload(e.target.files[0])} />
                <Upload size={36} color="#10b981" style={{ margin: '0 auto 0.75rem' }} />
                <div style={{ color: 'white', fontWeight: '600', marginBottom: '0.25rem' }}>
                  {file ? file.name : 'Upload Client SWIFT File'}
                </div>
                <div style={{ color: '#6b7280', fontSize: '0.85rem' }}>
                  {file ? `${(file.size / 1024).toFixed(1)} KB · Click to change` : 'Drop .txt or .xml SWIFT file'}
                </div>
              </div>

              {file && (
                <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
                  <button onClick={handleValidate} disabled={validating} style={{
                    flex: 1, padding: '0.75rem',
                    background: validating ? 'rgba(16,185,129,0.3)' : 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
                    border: 'none', borderRadius: '8px', color: 'white',
                    fontWeight: '700', fontSize: '1rem', cursor: validating ? 'not-allowed' : 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem'
                  }}>
                    {validating ? <><div className="spinner" /> Validating...</> : <><Shield size={18} /> Validate</>}
                  </button>
                  <button onClick={handleNewFile} style={{
                    padding: '0.75rem 1.25rem',
                    background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '8px', color: '#9ca3af', cursor: 'pointer', fontSize: '0.9rem'
                  }}>
                    New File
                  </button>
                </div>
              )}
            </GlassCard>
          </motion.div>

          {/* Results */}
          <AnimatePresence>
            {result && (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                style={{ marginTop: '1.5rem' }}>

                {/* Summary */}
                <GlassCard>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
                    {result.is_valid
                      ? <CheckCircle size={40} color="#10b981" />
                      : <XCircle size={40} color="#ef4444" />
                    }
                    <div>
                      <div style={{
                        fontSize: '1.4rem', fontWeight: '800',
                        color: result.is_valid ? '#10b981' : '#ef4444'
                      }}>
                        {result.is_valid ? '✅ File is VALID' : '❌ File is INVALID'}
                      </div>
                      <div style={{ color: '#6b7280', fontSize: '0.9rem' }}>
                        {result.file_name} · MT type: {result.mt_type}
                      </div>
                    </div>
                    <div style={{ marginLeft: 'auto', display: 'flex', gap: '1rem' }}>
                      <StatBadge label="Passed" value={result.summary.passed} color="#10b981" />
                      <StatBadge label="Failed" value={result.summary.failed} color="#ef4444" />
                      <StatBadge label="Warnings" value={result.summary.warnings} color="#f59e0b" />
                      <StatBadge label="Total Rules" value={result.summary.total_rules} color="#06b6d4" />
                    </div>
                  </div>

                  {/* Errors */}
                  {result.errors.length > 0 && (
                    <div style={{ marginBottom: '1.5rem' }}>
                      <div style={{ color: '#ef4444', fontWeight: '700', marginBottom: '0.75rem', fontSize: '0.95rem' }}>
                        ❌ Errors ({result.errors.length})
                      </div>
                      {Object.entries(groupByBlock(result.errors)).map(([block, items]) => (
                        <BlockGroup key={block} block={block} items={items} type="error" />
                      ))}
                    </div>
                  )}

                  {/* Warnings */}
                  {result.warnings.length > 0 && (
                    <div style={{ marginBottom: '1.5rem' }}>
                      <div style={{ color: '#f59e0b', fontWeight: '700', marginBottom: '0.75rem', fontSize: '0.95rem' }}>
                        ⚠️ Warnings ({result.warnings.length})
                      </div>
                      {result.warnings.map((w, i) => (
                        <div key={i} style={{
                          padding: '8px 12px', background: 'rgba(245,158,11,0.08)',
                          border: '1px solid rgba(245,158,11,0.2)', borderRadius: '6px',
                          marginBottom: '4px', fontSize: '13px'
                        }}>
                          <span style={{ color: '#f59e0b', fontFamily: 'monospace', marginRight: '8px' }}>{w.field}</span>
                          <span style={{ color: '#9ca3af' }}>{w.message}</span>
                          {w.value && <span style={{ color: '#a5f3fc', marginLeft: '8px', fontFamily: 'monospace' }}>= {w.value}</span>}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Passed */}
                  {result.passed.length > 0 && (
                    <CollapsibleSection title={`✅ Passed Fields (${result.passed.length})`} color="#10b981">
                      {Object.entries(groupByBlock(result.passed)).map(([block, items]) => (
                        <BlockGroup key={block} block={block} items={items} type="passed" />
                      ))}
                    </CollapsibleSection>
                  )}
                </GlassCard>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <style>{`
          .spinner { width: 18px; height: 18px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block; }
          @keyframes spin { to { transform: rotate(360deg); } }
        `}</style>
      </div>
    </Layout>
  );
};

// ── Block Group ───────────────────────────────────────────────────────────────
const BlockGroup = ({ block, items, type }) => {
  const [expanded, setExpanded] = useState(true);
  const isError = type === 'error';
  const color = isError ? '#ef4444' : '#10b981';
  const bg = isError ? 'rgba(239,68,68,0.05)' : 'rgba(16,185,129,0.05)';
  const border = isError ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)';

  return (
    <div style={{ marginBottom: '8px', background: bg, border: `1px solid ${border}`, borderRadius: '8px', overflow: 'hidden' }}>
      <div onClick={() => setExpanded(!expanded)} style={{
        padding: '8px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px'
      }}>
        {expanded ? <ChevronDown size={14} color={color} /> : <ChevronRight size={14} color={color} />}
        <span style={{ color, fontWeight: '700', fontSize: '12px', fontFamily: 'monospace' }}>{block}</span>
        <span style={{ color: '#6b7280', fontSize: '11px' }}>{items.length} field{items.length > 1 ? 's' : ''}</span>
      </div>
      {expanded && (
        <div style={{ padding: '0 12px 8px' }}>
          {items.map((item, i) => (
            <FieldRow key={i} item={item} type={type} />
          ))}
        </div>
      )}
    </div>
  );
};

// ── Field Row ─────────────────────────────────────────────────────────────────
const FieldRow = ({ item, type }) => {
  const isError = type === 'error';
  return (
    <div style={{
      padding: '6px 8px', marginBottom: '4px',
      background: 'rgba(0,0,0,0.2)', borderRadius: '6px',
      fontSize: '12px'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: isError ? '4px' : 0 }}>
        {isError ? <XCircle size={12} color="#ef4444" /> : <CheckCircle size={12} color="#10b981" />}
        <span style={{ color: '#f59e0b', fontFamily: 'monospace', fontWeight: '700' }}>
          {item.field || item.field_name}
        </span>
        <span style={{ color: '#6b7280' }}>{item.field_name}</span>
        {item.value && (
          <span style={{ marginLeft: 'auto', color: '#a5f3fc', fontFamily: 'monospace', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            = {item.value}
          </span>
        )}
      </div>
      {isError && item.errors && item.errors.map((err, i) => (
        <div key={i} style={{ color: '#fca5a5', paddingLeft: '20px', fontSize: '11px' }}>
          → {err}
        </div>
      ))}
    </div>
  );
};

// ── Collapsible Section ───────────────────────────────────────────────────────
const CollapsibleSection = ({ title, color, children }) => {
  const [expanded, setExpanded] = useState(false);
  return (
    <div>
      <button onClick={() => setExpanded(!expanded)} style={{
        background: 'none', border: 'none', cursor: 'pointer', color,
        fontWeight: '700', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '6px', padding: 0, marginBottom: '0.5rem'
      }}>
        {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        {title}
      </button>
      {expanded && <div>{children}</div>}
    </div>
  );
};

// ── Stat Badge ────────────────────────────────────────────────────────────────
const StatBadge = ({ label, value, color }) => (
  <div style={{ textAlign: 'center' }}>
    <div style={{ fontSize: '1.5rem', fontWeight: '800', color }}>{value}</div>
    <div style={{ fontSize: '11px', color: '#6b7280' }}>{label}</div>
  </div>
);

// ── Glass Card ────────────────────────────────────────────────────────────────
const GlassCard = ({ children }) => (
  <div style={{
    background: 'rgba(255,255,255,0.05)', backdropFilter: 'blur(10px)',
    borderRadius: '16px', padding: '1.5rem',
    border: '1px solid rgba(255,255,255,0.1)',
    boxShadow: '0 8px 32px rgba(0,0,0,0.3)'
  }}>
    {children}
  </div>
);

export default ValidatePage;    