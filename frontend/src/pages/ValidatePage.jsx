import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, CheckCircle, XCircle, AlertTriangle, FileText, Shield, ChevronDown, ChevronRight, Database } from 'lucide-react';
import Layout from '../components/Layout';
import WorkflowSteps from '../components/WorkflowSteps';

const API = 'http://localhost:8000/api';

const ValidatePage = () => {
  const [file, setFile] = useState(null);
  const [validating, setValidating] = useState(false);
  const [result, setResult] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  // MD reference selector
  const [mdList, setMdList] = useState([]);
  const [selectedMdId, setSelectedMdId] = useState('');
  const [loadingMds, setLoadingMds] = useState(false);

  useEffect(() => {
    const fetchMds = async () => {
      setLoadingMds(true);
      try {
        const res = await axios.get(`${API}/files/`);
        const files = res.data.files || [];
        // Deduplicate by (mt_type, file_type) — keep latest (highest id) per
        // combination. mt_type alone isn't enough: an ISO 20022 XML upload
        // and a genuine SWIFT MT text upload can share the same mt_type
        // (e.g. both "MT103" — one detected FROM the XML content, the
        // other from the MT text itself), but they're structurally
        // different files that need different validation rule sets. Keying
        // on mt_type alone meant any newer upload of either kind silently
        // evicted the other from the dropdown entirely, even though both
        // are legitimate, independently useful reference standards.
        const seen = {};
        const deduped = [];
        // Prefer entries that actually have elements (i.e. "Generate MD"
        // was run) over the literal newest upload — the same file gets
        // re-uploaded often enough (testing, drag-drop retries) that
        // "highest id" alone regularly lands on a duplicate that was never
        // processed. Picking that one as the reference means "import rules
        // from MD" silently produces zero rules (no error at that step),
        // and the real failure only surfaces later as a confusing "no
        // rules found" when actually validating a file against it. Within
        // each (has-elements, id) tier, still prefer the newest.
        const sorted = [...files].sort((a, b) => {
          const aHas = (a.element_count || 0) > 0;
          const bHas = (b.element_count || 0) > 0;
          if (aHas !== bHas) return aHas ? -1 : 1;
          return b.id - a.id;
        });
        for (const md of sorted) {
          const key = md.mt_type ? `${md.mt_type}|${md.file_type || ''}` : md.file_name;
          if (!seen[key]) {
            seen[key] = true;
            deduped.push(md);
          }
        }
        setMdList(deduped);
      } catch (e) {
        console.error('Failed to load MDs', e);
      } finally {
        setLoadingMds(false);
      }
    };
    fetchMds();
  }, []);

  useEffect(() => {
    const saved = sessionStorage.getItem('validate_page_state');
    if (saved) {
      try { setResult(JSON.parse(saved)); } catch (e) {}
    }
  }, []);

  useEffect(() => {
    const handleReset = () => {
      setResult(null);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    };
    window.addEventListener('validate-reset', handleReset);
    return () => window.removeEventListener('validate-reset', handleReset);
  }, []);

  const handleFileUpload = async (selectedFile) => {
    if (!selectedFile) return;
    setFile(selectedFile);
    setResult(null);
    sessionStorage.removeItem('validate_page_state');
  };

  const handleValidate = async () => {
    if (!file) return;
    if (!selectedMdId) {
      alert('⚠️ Please select a reference standard from the dropdown before validating.');
      return;
    }

    // Check MT type match between reference and uploaded file
    const selectedMd = mdList.find(md => String(md.id) === String(selectedMdId));
    if (selectedMd && selectedMd.mt_type) {
      // Detect MT type from file name as a quick pre-check
      const fileName = file.name.toLowerCase();
      const refMtType = selectedMd.mt_type.toLowerCase();
      // Extract MT number from reference (e.g. MT103 -> 103)
      const refMtNum = refMtType.replace('mt', '');
      // Check if filename contains the MT number of the reference
      // Only block if filename explicitly contains a different MT number
      const mtNumbers = ['103', '202', '900', '910', '940', '950'];
      const fileContainsMt = mtNumbers.find(n => fileName.includes(n) || fileName.includes(`mt${n}`));
      if (fileContainsMt && fileContainsMt !== refMtNum) {
        alert(`⚠️ MT type mismatch!

Reference standard: ${selectedMd.mt_type}
File appears to be: MT${fileContainsMt}

Please select the correct reference standard for this file.`);
        return;
      }
    }

    try {
      await axios.post(`${API}/validation/validation-rules/import-from-md/${selectedMdId}`);
    } catch (e) {
      alert('Failed to load reference: ' + (e.response?.data?.detail || e.message));
      return;
    }
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

          <WorkflowSteps current="validate" />

          <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}
            style={{ marginBottom: '2rem', textAlign: 'center' }}>
            <h1 style={{
              fontSize: '2.5rem', fontWeight: '800',
              background: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', marginBottom: '0.5rem'
            }}>
              🛡️ File Validation
            </h1>
            <p style={{ color: '#a0a0a0', fontSize: '1rem' }}>
              Check any file against an approved reference standard — this also runs automatically before every Transform
            </p>
          </motion.div>

          {/* Reference Standard Selector */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            style={{ marginBottom: '1rem' }}>
            <GlassCard>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <Database size={18} color="#06b6d4" />
                <span style={{ color: '#a0a0a0', fontSize: '0.9rem', whiteSpace: 'nowrap' }}>
                  Reference standard:
                </span>
                <select
                  value={selectedMdId}
                  onChange={e => setSelectedMdId(e.target.value)}
                  style={{
                    flex: 1, padding: '0.5rem 0.75rem',
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(255,255,255,0.15)',
                    borderRadius: '8px', color: 'white', fontSize: '0.9rem',
                    cursor: 'pointer', outline: 'none'
                  }}
                >
                  <option value="" style={{ background: '#1a1a2e' }}>
                    {loadingMds ? 'Loading...' : '── Select a reference standard ──'}
                  </option>
                  {mdList.map(md => (
                    <option key={md.id} value={md.id} style={{ background: '#1a1a2e' }}>
                      {md.file_name}{md.mt_type ? ` (${md.mt_type})` : ''}{md.file_type ? ` · ${md.file_type}` : ''}
                    </option>
                  ))}
                </select>
              </div>
              {selectedMdId && (
                <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#06b6d4', paddingLeft: '1.75rem' }}>
                  ✓ Will validate against selected reference
                </div>
              )}
            </GlassCard>
          </motion.div>

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
                <input ref={fileInputRef} type="file" accept=".txt,.xml,.csv,.json,.xlsx,.xls"
                  style={{ display: 'none' }}
                  onChange={e => handleFileUpload(e.target.files[0])} />
                <Upload size={36} color="#10b981" style={{ margin: '0 auto 0.75rem' }} />
                <div style={{ color: 'white', fontWeight: '600', marginBottom: '0.25rem' }}>
                  {file ? file.name : 'Upload Client File'}
                </div>
                <div style={{ color: '#6b7280', fontSize: '0.85rem' }}>
                  {file ? `${(file.size / 1024).toFixed(1)} KB · Click to change` : 'Drop .txt .xml .csv .json .xlsx file'}
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

          <AnimatePresence>
            {result && (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                style={{ marginTop: '1.5rem' }}>
                <GlassCard>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
                    {result.is_valid
                      ? <CheckCircle size={40} color="#10b981" />
                      : <XCircle size={40} color="#ef4444" />
                    }
                    <div>
                      <div style={{ fontSize: '1.4rem', fontWeight: '800', color: result.is_valid ? '#10b981' : '#ef4444' }}>
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
          select option { background: #1a1a2e; color: white; }
        `}</style>
      </div>
    </Layout>
  );
};

const BlockGroup = ({ block, items, type }) => {
  const [expanded, setExpanded] = useState(true);
  const isError = type === 'error';
  const color = isError ? '#ef4444' : '#10b981';
  const bg = isError ? 'rgba(239,68,68,0.05)' : 'rgba(16,185,129,0.05)';
  const border = isError ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)';
  return (
    <div style={{ marginBottom: '8px', background: bg, border: `1px solid ${border}`, borderRadius: '8px', overflow: 'hidden' }}>
      <div onClick={() => setExpanded(!expanded)} style={{ padding: '8px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}>
        {expanded ? <ChevronDown size={14} color={color} /> : <ChevronRight size={14} color={color} />}
        <span style={{ color, fontWeight: '700', fontSize: '12px', fontFamily: 'monospace' }}>{block}</span>
        <span style={{ color: '#6b7280', fontSize: '11px' }}>{items.length} field{items.length > 1 ? 's' : ''}</span>
      </div>
      {expanded && (
        <div style={{ padding: '0 12px 8px' }}>
          {items.map((item, i) => <FieldRow key={i} item={item} type={type} />)}
        </div>
      )}
    </div>
  );
};

const FieldRow = ({ item, type }) => {
  const isError = type === 'error';
  return (
    <div style={{ padding: '6px 8px', marginBottom: '4px', background: 'rgba(0,0,0,0.2)', borderRadius: '6px', fontSize: '12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: isError ? '4px' : 0 }}>
        {isError ? <XCircle size={12} color="#ef4444" /> : <CheckCircle size={12} color="#10b981" />}
        <span style={{ color: '#f59e0b', fontFamily: 'monospace', fontWeight: '700' }}>{item.field || item.field_name}</span>
        <span style={{ color: '#6b7280' }}>{item.field_name}</span>
        {item.value && (
          <span style={{ marginLeft: 'auto', color: '#a5f3fc', fontFamily: 'monospace', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            = {item.value}
          </span>
        )}
      </div>
      {isError && item.errors && item.errors.map((err, i) => (
        <div key={i} style={{ color: '#fca5a5', paddingLeft: '20px', fontSize: '11px' }}>→ {err}</div>
      ))}
    </div>
  );
};

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

const StatBadge = ({ label, value, color }) => (
  <div style={{ textAlign: 'center' }}>
    <div style={{ fontSize: '1.5rem', fontWeight: '800', color }}>{value}</div>
    <div style={{ fontSize: '11px', color: '#6b7280' }}>{label}</div>
  </div>
);

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