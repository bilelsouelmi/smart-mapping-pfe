import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Plus, Edit2, Trash2, Link2, X, Check, Zap, Upload, FileText,
  Sparkles, ChevronDown, ChevronUp, ArrowLeftRight, Download
} from 'lucide-react';
import Layout from '../components/Layout';
import WorkflowSteps from '../components/WorkflowSteps';
import SuggestionCard from '../components/SuggestionCard';
import MTBlockReview from '../components/MTBlockReview';
import { useAuth } from '../contexts/AuthContext';
import API_BASE_URL from '../config/api';

const API = `${API_BASE_URL}/api`;

const STATUSES = ['draft', 'active', 'inactive'];
const ELEMENT_STATUSES = ['pending', 'mapped', 'skipped'];

const isMtType = (v) => (v || '').toUpperCase().startsWith('MT');

const MappingWorkspacePage = () => {
  const { user } = useAuth();
  // ── Mapping list / elements state ──────────────────────────────────────────
  const [mappings, setMappings] = useState([]);
  const [selectedMapping, setSelectedMapping] = useState(null);
  const [elements, setElements] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showMappingModal, setShowMappingModal] = useState(false);
  const [showElementModal, setShowElementModal] = useState(false);
  const [modalMode, setModalMode] = useState('create');
  const [modalElement, setModalElement] = useState(null);
  const [modalMapping, setModalMapping] = useState(null);
  const [sources, setSources] = useState([]);
  const [targets, setTargets] = useState([]);
  const [msgDescs, setMsgDescs] = useState([]);
  const [generatingElements, setGeneratingElements] = useState(false);

  // ── Step 1 (optional formulas) state ───────────────────────────────────────
  const [showFormulaStep, setShowFormulaStep] = useState(false);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [mtBlocksConfirmed, setMtBlocksConfirmed] = useState(false);
  const [acceptingAll, setAcceptingAll] = useState(false);
  const [acceptedColumns, setAcceptedColumns] = useState(new Set());

  // ── Transform (both directions, auto-detected) state ──────────────────────
  const [showTransformPanel, setShowTransformPanel] = useState(false);
  const [transformFile, setTransformFile] = useState(null);
  const [transforming, setTransforming] = useState(false);
  const [transformResult, setTransformResult] = useState(null);
  const [transformHeld, setTransformHeld] = useState(null);
  const [transformError, setTransformError] = useState('');

  useEffect(() => {
    fetchMappings();
    fetchSourcesTargets();
    fetchMsgDescs();
  }, []);

  useEffect(() => {
    if (selectedMapping) fetchElements(selectedMapping.id);
  }, [selectedMapping]);

  // ── Fetchers ────────────────────────────────────────────────────────────────
  const fetchMappings = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/mappings/`);
      setMappings(r.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const fetchElements = async (mappingId) => {
    try {
      const r = await axios.get(`${API}/mappings/${mappingId}/elements`);
      setElements(r.data);
    } catch (e) { console.error(e); }
  };

  const fetchSourcesTargets = async () => {
    try {
      const r = await axios.get(`${API}/mappings/sources-targets/available`);
      setSources(r.data.sources || []);
      setTargets(r.data.targets || []);
    } catch (e) { console.error(e); }
  };

  const fetchMsgDescs = async () => {
    try {
      const r = await axios.get(`${API}/files/`);
      setMsgDescs(r.data.files || []);
    } catch (e) { console.error(e); }
  };

  // ── Mapping CRUD ────────────────────────────────────────────────────────────
  const [activating, setActivating] = useState(false);
  const handleActivateMapping = async (m) => {
    if (!window.confirm(`Activate "${m.name}"? This makes it usable for real Transforms.`)) return;
    setActivating(true);
    try {
      const r = await axios.put(`${API}/mappings/${m.id}`, { status: 'active' });
      setSelectedMapping(r.data);
      fetchMappings();
    } catch (e) {
      alert('❌ ' + (e.response?.data?.detail || 'Activation failed'));
    } finally {
      setActivating(false);
    }
  };

  const handleDeleteMapping = async (id) => {
    if (!window.confirm('Delete this mapping and all its elements?')) return;
    try {
      await axios.delete(`${API}/mappings/${id}`);
      if (selectedMapping?.id === id) { setSelectedMapping(null); setElements([]); }
      fetchMappings();
    } catch (e) { alert('Delete failed'); }
  };

  const handleDeleteElement = async (elementId) => {
    if (!window.confirm('Delete this element?')) return;
    try {
      await axios.delete(`${API}/mappings/${selectedMapping.id}/elements/${elementId}`);
      fetchElements(selectedMapping.id);
    } catch (e) { alert('Delete failed'); }
  };

  const handleGenerateElements = async () => {
    if (!selectedMapping) return;
    setGeneratingElements(true);
    try {
      const r = await axios.post(`${API}/mappings/${selectedMapping.id}/generate-elements`);
      alert(`✅ ${r.data.message} (${r.data.mapped} mapped, ${r.data.pending} pending)`);
      fetchElements(selectedMapping.id);
      fetchMappings();
    } catch (e) {
      alert('❌ ' + (e.response?.data?.detail || 'Generation failed'));
    } finally {
      setGeneratingElements(false);
    }
  };

  // Runs the actual conversion for the selected mapping's pair, in
  // whichever direction the uploaded file turns out to be (SWIFT MT text
  // or ISO 20022 XML). Uses /transform/mapping/{id} — NOT /transform/auto —
  // since a specific mapping is already selected here: /transform/auto's
  // XML->MT branch bypasses Mapping/MappingElement entirely (calls
  // iso20022_parser/mt_generator directly), so it would never use this
  // mapping's own accepted formulas/pseudocode. transform_with_mapping
  // handles both directions itself (see its is_iso_to_mt branch).
  const handleTransform = async () => {
    if (!transformFile) { setTransformError('Please select a file first'); return; }
    if (!selectedMapping) { setTransformError('No mapping selected'); return; }
    setTransforming(true);
    setTransformError('');
    setTransformResult(null);
    setTransformHeld(null);
    try {
      const formData = new FormData();
      formData.append('file', transformFile);
      const r = await axios.post(`${API}/transform/mapping/${selectedMapping.id}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        responseType: 'blob'
      });

      // Amount above the approval threshold — the endpoint returns 202 +
      // JSON instead of the XML file (see transform_mapping.py's
      // required_approvals hold). responseType:'blob' means axios hands
      // us a Blob either way, so branch on content-type instead of
      // trying to detect it from the (blob) body shape.
      const contentType = r.headers['content-type'] || '';
      if (contentType.includes('application/json')) {
        const heldData = JSON.parse(await r.data.text());
        setTransformHeld(heldData);
        return;
      }

      const blob = new Blob([r.data], { type: r.headers['content-type'] || 'application/octet-stream' });
      const url = URL.createObjectURL(blob);
      const disposition = r.headers['content-disposition'] || '';
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : `output_${Date.now()}`;
      const content = await blob.text();
      let outputValidation = null;
      try {
        const raw = r.headers['x-output-validation'];
        if (raw) outputValidation = JSON.parse(raw);
      } catch { /* ignore */ }
      setTransformResult({
        url, filename, content, size: blob.size,
        detectedType: r.headers['x-message-type'], outputValidation
      });
    } catch (e) {
      let msg = e.message || 'Transformation failed';
      if (e.response?.data instanceof Blob) {
        try {
          const text = await e.response.data.text();
          msg = JSON.parse(text).detail || msg;
        } catch { /* ignore */ }
      } else if (e.response?.data?.detail) {
        msg = e.response.data.detail;
      }
      setTransformError(msg);
    } finally {
      setTransforming(false);
    }
  };

  const handleSaveMapping = async (formData) => {
    try {
      if (modalMode === 'create') {
        const r = await axios.post(`${API}/mappings/`, formData);
        setSelectedMapping(r.data);
      } else {
        await axios.put(`${API}/mappings/${modalMapping.id}`, formData);
        if (selectedMapping?.id === modalMapping.id) {
          const r = await axios.get(`${API}/mappings/${modalMapping.id}`);
          setSelectedMapping(r.data);
        }
      }
      setShowMappingModal(false);
      fetchMappings();
    } catch (e) { alert(e.response?.data?.detail || 'Save failed'); }
  };

  const handleSaveElement = async (formData) => {
    try {
      if (modalMode === 'create') {
        await axios.post(`${API}/mappings/${selectedMapping.id}/elements`, formData);
      } else {
        await axios.put(`${API}/mappings/${selectedMapping.id}/elements/${modalElement.id}`, formData);
      }
      setShowElementModal(false);
      fetchElements(selectedMapping.id);
    } catch (e) { alert(e.response?.data?.detail || 'Save failed'); }
  };

  // ── Step 1: Formula upload / suggestions ────────────────────────────────────
  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setAnalysisResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) { alert('Please select a file first'); return; }
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    // This is a throwaway "just give me column suggestions" call, not an
    // attempt to create a new reference Message Description — re-analyzing
    // a file whose MD is already approved/pending (e.g. re-testing the
    // same sample) must not be blocked by that unrelated duplicate check.
    formData.append('skip_duplicate_check', 'true');
    try {
      const response = await axios.post(`${API}/files/analyze`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setAnalysisResult(response.data);
      setAcceptedColumns(new Set());
    } catch (error) {
      alert(error.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleAcceptAll = async () => {
    if (!analysisResult?.suggestions) return;
    setAcceptingAll(true);
    const suggestions = analysisResult.suggestions;
    let accepted = 0, failed = 0;
    const newlyAccepted = new Set();
    for (const [columnName, columnSuggestions] of Object.entries(suggestions)) {
      if (!columnSuggestions || columnSuggestions.length === 0) continue;
      const suggestion = columnSuggestions[0];
      const sourceLevel = columnName.split('.').length;
      let columnFailed = false;

      // Use the REAL pseudocode/expression from the RAG-enriched suggestion
      // (string, or {pseudocode, expression} object once edited) instead of
      // a placeholder — otherwise every bulk-accepted formula loses its
      // actual transformation logic and Generate Elements has nothing real
      // to evaluate.
      const mf = suggestion.mapping_formula;
      const mfPseudocode = mf && typeof mf === 'object' ? (mf.pseudocode || mf.expression) : (typeof mf === 'string' ? mf : null);
      const formulaText = mfPseudocode || `Auto-accepted (${suggestion.confidence || 50}% confidence)`;

      // A single source field can drive several ISO 20022 targets from one
      // shared formula (e.g. :50K: -> Dbtr.Nm AND DbtrAcct.Id.IBAN) —
      // additional_targets carries the extras beyond the primary
      // target_path, so create one formula per target here too.
      const allTargetPaths = [
        suggestion.target_path || suggestion.element_name,
        ...(suggestion.additional_targets || []).map(t => t.target_path).filter(Boolean)
      ];

      for (const targetPath of allTargetPaths) {
        try {
          const targetLevel = targetPath ? targetPath.split('.').length : 1;
          await axios.post(`${API}/mapping-formulas/`, {
            message_description_id: analysisResult.id,
            name: `${columnName} → ${suggestion.element_name}`,
            source_path: columnName,
            target_path: targetPath,
            source_level: sourceLevel,
            target_level: targetLevel,
            transformation_type: 'direct',
            transformation_rule: formulaText,
            example_input: null,
            example_output: null
          });
          accepted++;
        } catch (e) { failed++; columnFailed = true; }
      }
      if (!columnFailed) newlyAccepted.add(columnName);
    }
    setAcceptedColumns(prev => new Set([...prev, ...newlyAccepted]));
    setAcceptingAll(false);
    alert(`✅ Accepted ${accepted} formulas${failed > 0 ? ` (${failed} failed)` : ''}. You can now use them via "Generate Elements" below.`);
  };

  const handleNewFile = () => {
    setFile(null);
    setAnalysisResult(null);
    setMtBlocksConfirmed(false);
    setAcceptedColumns(new Set());
  };

  const isMT = analysisResult?.file_type === 'XML_MT';
  const showMTReview = isMT && !mtBlocksConfirmed;
  const showSuggestions = !isMT || mtBlocksConfirmed;

  const statusColor = (s) => {
    if (s === 'active') return '#10b981';
    if (s === 'draft') return '#f59e0b';
    return '#6b7280';
  };

  const elementStatusColor = (s) => {
    if (s === 'mapped') return '#10b981';
    if (s === 'pending') return '#f59e0b';
    return '#6b7280';
  };

  return (
    <Layout>
      <div style={{
        minHeight: 'calc(100vh - 100px)',
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
        padding: '2rem', marginTop: '-2rem', marginLeft: '-2rem', marginRight: '-2rem',
      }}>
        <div style={{ maxWidth: '1400px', margin: '0 auto' }}>

          <WorkflowSteps current="mapping" />

          <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}
            style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
            <h1 style={{
              fontSize: '2.5rem', fontWeight: '800',
              background: 'linear-gradient(135deg, #a78bfa 0%, #667eea 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', marginBottom: '0.5rem'
            }}>
              🔗 Mapping
            </h1>
            <p style={{ color: '#a0a0a0', fontSize: '1rem' }}>
              Step 2 — Accept mapping formulas, Generate Elements, then Transform a file (requires an approved Message Description for its type)
            </p>
          </motion.div>

          {/* ── Optional Step 1: Formula suggestions (collapsible) ──────────── */}
          <GlassCard style={{ marginBottom: '1.5rem' }}>
            <button onClick={() => setShowFormulaStep(s => !s)} style={{
              width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              background: 'none', border: 'none', cursor: 'pointer', padding: 0
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <Sparkles size={20} color="#667eea" />
                <div style={{ textAlign: 'left' }}>
                  <div style={{ color: 'white', fontWeight: '700', fontSize: '0.95rem' }}>
                    Optional: AI Formula Suggestions
                  </div>
                  <div style={{ color: '#6b7280', fontSize: '0.78rem' }}>
                    Upload a generic file (CSV/JSON/Excel) for column-level AI suggestions —
                    not needed for standard SWIFT MT mappings, which use "Generate Elements" below.
                  </div>
                </div>
              </div>
              {showFormulaStep ? <ChevronUp size={18} color="#6b7280" /> : <ChevronDown size={18} color="#6b7280" />}
            </button>

            <AnimatePresence>
              {showFormulaStep && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }} style={{ overflow: 'hidden' }}>
                  <div style={{ marginTop: '1.5rem' }}>
                    <div style={{
                      border: '2px dashed rgba(102, 126, 234, 0.3)', borderRadius: '14px',
                      padding: '2rem', textAlign: 'center', background: 'rgba(102, 126, 234, 0.05)',
                    }}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      const droppedFile = e.dataTransfer.files[0];
                      if (droppedFile) { setFile(droppedFile); setAnalysisResult(null); }
                    }}>
                      <input type="file" onChange={handleFileChange} style={{ display: 'none' }}
                        id="formula-file-upload" accept=".csv,.json,.xml,.xlsx,.txt" />
                      <label htmlFor="formula-file-upload" style={{ cursor: 'pointer', display: 'block' }}>
                        <Upload size={40} color="#667eea" style={{ margin: '0 auto 1rem' }} />
                        <div style={{ color: 'white', fontSize: '1.1rem', marginBottom: '0.4rem' }}>
                          Drop your file here or click to browse
                        </div>
                        <div style={{ color: '#a0a0a0', fontSize: '0.85rem' }}>
                          Supports CSV, JSON, XML, Excel, SWIFT TXT
                        </div>
                        {file && (
                          <div style={{
                            marginTop: '1rem', padding: '0.6rem 1rem',
                            background: 'rgba(72, 187, 120, 0.2)', borderRadius: '10px', display: 'inline-block'
                          }}>
                            <FileText size={18} color="#48bb78" style={{ verticalAlign: 'middle', marginRight: '0.4rem' }} />
                            <span style={{ color: '#48bb78', fontWeight: '600' }}>{file.name}</span>
                          </div>
                        )}
                      </label>
                    </div>

                    {file && !analysisResult && (
                      <button onClick={handleUpload} disabled={uploading} style={{
                        width: '100%', marginTop: '1rem', padding: '0.9rem',
                        background: uploading ? 'rgba(102,126,234,0.5)' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        color: 'white', border: 'none', borderRadius: '10px', fontSize: '1rem', fontWeight: '700',
                        cursor: uploading ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center',
                        justifyContent: 'center', gap: '0.5rem'
                      }}>
                        <Sparkles size={18} /> {uploading ? 'Analyzing with AI...' : 'Analyze with AI'}
                      </button>
                    )}

                    {analysisResult && (
                      <div style={{ marginTop: '1.5rem' }}>
                        {showMTReview && analysisResult.mt_blocks && (
                          <MTBlockReview
                            analysisResult={analysisResult}
                            onConfirmed={(confirmedBlocks) => {
                              setAnalysisResult({ ...analysisResult, mt_blocks: confirmedBlocks });
                              setMtBlocksConfirmed(true);
                            }}
                            onRegenerate={(newData) => {
                              setAnalysisResult({ ...analysisResult, suggestions: newData.suggestions });
                              setMtBlocksConfirmed(true);
                            }}
                          />
                        )}

                        {showSuggestions && (
                          <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                              <h3 style={{ color: 'white', margin: 0, fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <Sparkles size={20} color="#667eea" /> AI Suggestions
                              </h3>
                              <div style={{ display: 'flex', gap: '0.5rem' }}>
                                <button onClick={handleAcceptAll} disabled={acceptingAll} style={{
                                  padding: '0.5rem 1rem', background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                                  color: 'white', border: 'none', borderRadius: '8px', fontSize: '0.85rem', fontWeight: '600',
                                  cursor: acceptingAll ? 'not-allowed' : 'pointer'
                                }}>
                                  {acceptingAll ? '⏳ Accepting...' : '✅ Accept All'}
                                </button>
                                <button onClick={handleNewFile} style={{
                                  padding: '0.5rem 1rem', background: 'rgba(255,255,255,0.08)',
                                  color: 'white', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px',
                                  fontSize: '0.85rem', fontWeight: '600', cursor: 'pointer'
                                }}>
                                  <Upload size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> New File
                                </button>
                              </div>
                            </div>
                            <div style={{ display: 'grid', gap: '1rem' }}>
                              {Object.entries(analysisResult.suggestions || {})
                                .filter(([columnName]) => !acceptedColumns.has(columnName))
                                .map(([columnName, columnSuggestions]) => (
                                <SuggestionCard key={columnName} columnName={columnName}
                                  suggestions={columnSuggestions} analysisResult={analysisResult}
                                  onAccepted={() => setAcceptedColumns(prev => new Set(prev).add(columnName))} />
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </GlassCard>

          {/* ── Main mapping workspace ───────────────────────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1.5rem' }}>

            <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
              <GlassCard>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h2 style={{ color: 'white', margin: 0, fontSize: '1rem', fontWeight: '700' }}>
                    Mappings ({mappings.length})
                  </h2>
                  <ActionBtn icon={<Plus size={13} />} label="New" color="#a78bfa"
                    onClick={() => { setModalMode('create'); setShowMappingModal(true); }} />
                </div>

                {loading ? (
                  <div style={{ textAlign: 'center', padding: '2rem', color: '#6b7280' }}>
                    <div className="spinner" style={{ margin: '0 auto 0.5rem' }} /> Loading...
                  </div>
                ) : mappings.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '2rem', color: '#6b7280' }}>
                    <Link2 size={32} style={{ margin: '0 auto 0.5rem', display: 'block', opacity: 0.3 }} />
                    No mappings yet
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '70vh', overflowY: 'auto' }}>
                    {mappings.map(m => (
                      <div key={m.id}
                        onClick={() => setSelectedMapping(m)}
                        style={{
                          padding: '0.75rem 1rem', borderRadius: '10px', cursor: 'pointer',
                          background: selectedMapping?.id === m.id ? 'rgba(167,139,250,0.15)' : 'rgba(255,255,255,0.03)',
                          border: `1px solid ${selectedMapping?.id === m.id ? 'rgba(167,139,250,0.4)' : 'rgba(255,255,255,0.08)'}`,
                          transition: 'all 0.2s'
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ color: 'white', fontWeight: '600', fontSize: '13px' }}>{m.name}</span>
                          <div style={{ display: 'flex', gap: '4px' }}>
                            <IconBtn icon={<Edit2 size={11} />} color="#667eea"
                              onClick={(e) => { e.stopPropagation(); setModalMapping(m); setModalMode('edit'); setShowMappingModal(true); }} />
                            <IconBtn icon={<Trash2 size={11} />} color="#ef4444"
                              onClick={(e) => { e.stopPropagation(); handleDeleteMapping(m.id); }} />
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: '6px', marginTop: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
                          <Badge label={m.source} color={isMtType(m.source) ? '#f59e0b' : '#06b6d4'} />
                          <span style={{ color: '#4b5563', fontSize: '10px' }}>→</span>
                          <Badge label={m.target} color={isMtType(m.target) ? '#f59e0b' : '#06b6d4'} />
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px' }}>
                          <span style={{ fontSize: '10px', color: '#6b7280' }}>{m.element_count || 0} elements</span>
                          <span style={{ fontSize: '10px', color: statusColor(m.status), fontWeight: '600' }}>
                            {m.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </GlassCard>
            </motion.div>

            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
              {!selectedMapping ? (
                <GlassCard>
                  <div style={{ textAlign: 'center', padding: '4rem 2rem', color: '#6b7280' }}>
                    <Link2 size={48} style={{ margin: '0 auto 1rem', display: 'block', opacity: 0.2 }} />
                    <p style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>Select a mapping</p>
                    <p style={{ fontSize: '0.85rem', color: '#4b5563' }}>
                      Choose a mapping from the left panel to view and manage its elements
                    </p>
                  </div>
                </GlassCard>
              ) : (
                <GlassCard>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <div style={{ padding: '6px 14px', background: 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.3)', borderRadius: '8px' }}>
                        <span style={{ color: '#a78bfa', fontWeight: '700', fontSize: '14px' }}>{selectedMapping.name}</span>
                      </div>
                      <Badge label={selectedMapping.source} color={isMtType(selectedMapping.source) ? '#f59e0b' : '#06b6d4'} />
                      <span style={{ color: '#4b5563' }}>→</span>
                      <Badge label={selectedMapping.target} color={isMtType(selectedMapping.target) ? '#f59e0b' : '#06b6d4'} />
                      <span style={{
                        padding: '2px 10px', borderRadius: '20px', fontSize: '10px', fontWeight: '700',
                        background: 'rgba(255,255,255,0.05)', color: '#9ca3af'
                      }}>
                        {isMtType(selectedMapping.source) ? 'MT → ISO 20022' : 'ISO 20022 → MT'}
                      </span>
                      <span style={{
                        padding: '2px 10px', borderRadius: '20px', fontSize: '10px', fontWeight: '700',
                        background: `${statusColor(selectedMapping.status)}20`, color: statusColor(selectedMapping.status)
                      }}>
                        {selectedMapping.status}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      {/* Maker-checker: a draft/inactive mapping isn't
                          usable for Transform yet (see the status check in
                          transform_with_mapping) — only an admin can flip
                          it to active, once someone's actually reviewed
                          its formulas. */}
                      {selectedMapping.status !== 'active' && user?.is_admin && (
                        <ActionBtn icon={<Check size={13} />} label={activating ? 'Activating...' : 'Activate'} color="#10b981"
                          onClick={() => handleActivateMapping(selectedMapping)} disabled={activating} />
                      )}
                      <ActionBtn icon={<Plus size={13} />} label="Add Element" color="#667eea"
                        onClick={() => { setModalMode('create'); setModalElement(null); setShowElementModal(true); }} />
                      <ActionBtn icon={<Zap size={13} />} label="Generate Elements" color="#f472b6"
                        onClick={handleGenerateElements} disabled={generatingElements} />
                      <ActionBtn icon={<ArrowLeftRight size={13} />} label="Transform" color="#10b981"
                        onClick={() => { setShowTransformPanel(v => !v); setTransformResult(null); setTransformError(''); }} />
                    </div>
                  </div>

                  {showTransformPanel && (
                    <div style={{
                      marginBottom: '1.5rem', padding: '1.25rem', borderRadius: '12px',
                      background: 'rgba(16,185,129,0.05)', border: '1px solid rgba(16,185,129,0.2)'
                    }}>
                      <div style={{ color: '#6ee7b7', fontWeight: '700', fontSize: '13px', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <ArrowLeftRight size={14} /> Transform — upload a {isMtType(selectedMapping.source) ? 'SWIFT MT (.txt)' : 'ISO 20022 XML'} file matching this mapping's source ({selectedMapping.source})
                      </div>
                      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
                        <input type="file" accept={isMtType(selectedMapping.source) ? '.txt' : '.xml'}
                          onChange={(e) => { setTransformFile(e.target.files[0]); setTransformResult(null); setTransformError(''); }}
                          style={{ color: '#d1d5db', fontSize: '13px' }} />
                        <button onClick={handleTransform} disabled={transforming || !transformFile} style={{
                          padding: '0.5rem 1rem', background: transforming ? 'rgba(16,185,129,0.4)' : 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                          color: 'white', border: 'none', borderRadius: '8px', fontSize: '0.85rem', fontWeight: '600',
                          cursor: transforming || !transformFile ? 'not-allowed' : 'pointer'
                        }}>
                          {transforming ? '⏳ Transforming...' : '⚡ Run Transform'}
                        </button>
                      </div>
                      {transformError && (
                        <div style={{ marginTop: '0.75rem', color: '#fca5a5', fontSize: '13px' }}>❌ {transformError}</div>
                      )}
                      {transformHeld && (
                        <div style={{
                          marginTop: '1rem', padding: '12px 14px', borderRadius: '8px',
                          background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)'
                        }}>
                          <div style={{ color: '#fbbf24', fontSize: '13px', fontWeight: '700', marginBottom: '4px' }}>
                            🔒 Held for approval
                          </div>
                          <div style={{ color: '#fcd34d', fontSize: '12px', marginBottom: '8px' }}>
                            {transformHeld.message}
                          </div>
                          <Link to="/pending-transactions" style={{
                            display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 10px',
                            background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.3)',
                            borderRadius: '6px', color: '#fbbf24', fontSize: '12px', fontWeight: '600', textDecoration: 'none'
                          }}>
                            View Pending Transactions
                          </Link>
                        </div>
                      )}
                      {transformResult && (
                        <div style={{ marginTop: '1rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                            <span style={{ color: '#10b981', fontSize: '13px', fontWeight: '600' }}>
                              ✅ {transformResult.filename} · {(transformResult.size / 1024).toFixed(1)} KB
                              {transformResult.detectedType ? ` · detected ${transformResult.detectedType}` : ''}
                            </span>
                            <a href={transformResult.url} download={transformResult.filename} style={{
                              display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 10px',
                              background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)',
                              borderRadius: '6px', color: '#6ee7b7', fontSize: '12px', fontWeight: '600', textDecoration: 'none'
                            }}>
                              <Download size={12} /> Download
                            </a>
                          </div>
                          {transformResult.outputValidation && (
                            <div style={{
                              marginBottom: '0.5rem', fontSize: '12px',
                              color: transformResult.outputValidation.is_valid ? '#6ee7b7' : '#fcd34d'
                            }}>
                              {transformResult.outputValidation.is_valid
                                ? `✅ Output validated: ${transformResult.outputValidation.total_rules} rule(s) checked, all passed`
                                : `⚠️ Output validation: ${transformResult.outputValidation.failed} field(s) failed against the reference standard (file still generated — this is informational only)`}
                            </div>
                          )}
                          <pre style={{
                            background: 'rgba(0,0,0,0.3)', borderRadius: '8px', padding: '10px 12px',
                            color: '#a5f3fc', fontSize: '11px', maxHeight: '260px', overflow: 'auto',
                            whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0
                          }}>{transformResult.content}</pre>
                        </div>
                      )}
                    </div>
                  )}

                  {elements.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>
                      <p>No elements yet</p>
                      <p style={{ fontSize: '0.85rem', color: '#4b5563' }}>
                        Click <strong style={{ color: '#f472b6' }}>Generate Elements</strong> for automatic RAG-based mapping,
                        or <strong style={{ color: '#667eea' }}>Add Element</strong> to map fields manually
                      </p>
                    </div>
                  ) : (
                    <div style={{ overflowX: 'auto' }}>
                      <div style={{ minWidth: '620px' }}>
                      <div style={{
                        display: 'grid', gridTemplateColumns: '1fr 1fr 2fr 80px 80px',
                        gap: '0.5rem', padding: '8px 12px', marginBottom: '4px',
                        color: '#6b7280', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.5px'
                      }}>
                        <span>Source Field</span>
                        <span>Target Field</span>
                        <span>Expression</span>
                        <span>Status</span>
                        <span>Actions</span>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxHeight: '55vh', overflowY: 'auto' }}>
                        {elements.map(el => (
                          <div key={el.id} style={{
                            display: 'grid', gridTemplateColumns: '1fr 1fr 2fr 80px 80px',
                            gap: '0.5rem', padding: '10px 12px',
                            background: 'rgba(255,255,255,0.03)',
                            border: '1px solid rgba(255,255,255,0.06)',
                            borderRadius: '8px', alignItems: 'center'
                          }}>
                            <span style={{
                              color: '#f59e0b', fontFamily: 'monospace', fontSize: '12px', fontWeight: '600',
                              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                              display: 'block', minWidth: 0
                            }} title={el.source_field}>
                              {el.source_field}
                            </span>
                            <span style={{
                              color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px',
                              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                              display: 'block', minWidth: 0
                            }} title={el.target_field}>
                              {el.target_field || '—'}
                            </span>
                            <span style={{
                              color: '#a5f3fc', fontFamily: 'monospace', fontSize: '11px',
                              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                              display: 'block', minWidth: 0
                            }} title={el.expression}>
                              {el.expression || '—'}
                            </span>
                            <span style={{
                              padding: '2px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: '700',
                              background: `${elementStatusColor(el.status)}20`,
                              color: elementStatusColor(el.status),
                              textAlign: 'center', minWidth: 0
                            }}>
                              {el.status}
                            </span>
                            <div style={{ display: 'flex', gap: '4px', minWidth: 0 }}>
                              <IconBtn icon={<Edit2 size={11} />} color="#667eea"
                                onClick={() => { setModalElement(el); setModalMode('edit'); setShowElementModal(true); }} />
                              <IconBtn icon={<Trash2 size={11} />} color="#ef4444"
                                onClick={() => handleDeleteElement(el.id)} />
                            </div>
                          </div>
                        ))}
                      </div>
                      </div>
                    </div>
                  )}
                </GlassCard>
              )}
            </motion.div>
          </div>
        </div>

        <style>{`
          .spinner { width: 18px; height: 18px; border: 2px solid rgba(167,139,250,0.3); border-top-color: #a78bfa; border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block; }
          @keyframes spin { to { transform: rotate(360deg); } }
        `}</style>
      </div>

      <AnimatePresence>
        {showMappingModal && (
          <MappingModal mode={modalMode} mapping={modalMapping} sources={sources} targets={targets} msgDescs={msgDescs}
            isAdmin={user?.is_admin} onSave={handleSaveMapping} onClose={() => setShowMappingModal(false)} />
        )}
        {showElementModal && (
          <ElementModal mode={modalMode} element={modalElement} mappingId={selectedMapping?.id}
            onSave={handleSaveElement} onClose={() => setShowElementModal(false)} />
        )}
      </AnimatePresence>
    </Layout>
  );
};

// ── Mapping Modal ─────────────────────────────────────────────────────────────
const MappingModal = ({ mode, mapping, sources, targets, msgDescs, isAdmin, onSave, onClose }) => {
  const [form, setForm] = useState({
    name: mapping?.name || '',
    source: mapping?.source || '',
    target: mapping?.target || '',
    status: mapping?.status || 'draft',
    message_description_id: mapping?.message_description_id || '',
  });

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  return (
    <Modal title={mode === 'create' ? '🔗 New Mapping' : '✏️ Edit Mapping'} onClose={onClose}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <div style={{ gridColumn: '1 / -1' }}>
          <FormField label="* Name">
            <input value={form.name} onChange={e => set('name', e.target.value)} style={inputStyle} placeholder="MT103 to pacs.008 Mapping" />
          </FormField>
        </div>
        <FormField label="* Message Description">
          <select value={form.message_description_id} onChange={e => {
            set('message_description_id', parseInt(e.target.value));
            const md = msgDescs.find(m => m.id === parseInt(e.target.value));
            if (md) {
              // Which side is "source" depends on what was actually
              // uploaded, not just which mt_type/iso_target pair it
              // belongs to: an XML_ISO20022 file (a real ISO 20022 XML
              // upload) means the user wants to convert FROM that XML,
              // i.e. source=iso_target/target=mt_type (the XML->MT
              // direction this mapping engine now fully supports) — the
              // reverse of an XML_MT/TXT (SWIFT MT text) upload, where
              // source=mt_type/target=iso_target is correct. Defaulting
              // to MT->ISO unconditionally meant selecting an XML upload
              // here silently pre-filled the wrong direction, forcing a
              // manual Source/Target swap below every time.
              if (md.file_type === 'XML_ISO20022') {
                set('source', md.iso_target || ''); set('target', md.mt_type || '');
              } else {
                set('source', md.mt_type || ''); set('target', md.iso_target || '');
              }
            }
          }} style={selectStyle}>
            <option value="" style={{ background: '#16213e' }}>— Select MD —</option>
            {msgDescs.map(md => (
              <option key={md.id} value={md.id} style={{ background: '#16213e' }}>
                {md.file_name} {md.mt_type ? `(${md.mt_type})` : ''} {md.file_type === 'XML_ISO20022' ? '— XML→MT' : md.mt_type ? '— MT→XML' : ''}
              </option>
            ))}
          </select>
        </FormField>
        <FormField label={isAdmin ? 'Status' : 'Status (admin-only — new mappings start as draft)'}>
          <select value={form.status} disabled={!isAdmin}
            onChange={e => set('status', e.target.value)}
            style={{ ...selectStyle, opacity: isAdmin ? 1 : 0.5, cursor: isAdmin ? 'pointer' : 'not-allowed' }}>
            {STATUSES.map(s => <option key={s} value={s} style={{ background: '#16213e' }}>{s}</option>)}
          </select>
        </FormField>

        <FormField label="* Source">
          <select value={form.source} onChange={e => set('source', e.target.value)} style={selectStyle}>
            <option value="" style={{ background: '#16213e' }}>— Select Source —</option>
            <optgroup label="SWIFT MT">
              {sources.filter(s => isMtType(s)).map(s => (
                <option key={s} value={s} style={{ background: '#16213e' }}>{s}</option>
              ))}
            </optgroup>
            <optgroup label="ISO 20022">
              {sources.filter(s => !isMtType(s)).map(s => (
                <option key={s} value={s} style={{ background: '#16213e' }}>{s}</option>
              ))}
            </optgroup>
          </select>
        </FormField>

        <FormField label="* Target">
          <select value={form.target} onChange={e => set('target', e.target.value)} style={selectStyle}>
            <option value="" style={{ background: '#16213e' }}>— Select Target —</option>
            <optgroup label="ISO 20022">
              {targets.filter(t => !isMtType(t)).map(t => (
                <option key={t} value={t} style={{ background: '#16213e' }}>{t}</option>
              ))}
            </optgroup>
            <optgroup label="SWIFT MT">
              {targets.filter(t => isMtType(t)).map(t => (
                <option key={t} value={t} style={{ background: '#16213e' }}>{t}</option>
              ))}
            </optgroup>
          </select>
        </FormField>
      </div>
      <ModalFooter onClose={onClose} onSave={() => {
        if (!form.name || !form.source || !form.target || !form.message_description_id) {
          alert('Please fill all required fields'); return;
        }
        onSave(form);
      }} />
    </Modal>
  );
};

// ── Element Modal ─────────────────────────────────────────────────────────────
const ElementModal = ({ mode, element, mappingId, onSave, onClose }) => {
  const [form, setForm] = useState({
    mapping_id: mappingId,
    source_field: element?.source_field || '',
    source_xpath: element?.source_xpath || '',
    target_field: element?.target_field || '',
    target_xpath: element?.target_xpath || '',
    expression: element?.expression || '',
    is_mandatory: element?.is_mandatory ?? false,
    default_value: element?.default_value || '',
    status: element?.status || 'pending',
    msg_desc_element_id: element?.msg_desc_element_id || null,
    mapping_formula_id: element?.mapping_formula_id || null,
  });

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  return (
    <Modal title={mode === 'create' ? '➕ New Mapping Element' : '✏️ Edit Mapping Element'} onClose={onClose} wide>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <FormField label="* Source Field">
          <input value={form.source_field} onChange={e => set('source_field', e.target.value)} style={inputStyle} placeholder=":20" />
        </FormField>
        <FormField label="* Target Field">
          <input value={form.target_field} onChange={e => set('target_field', e.target.value)} style={inputStyle} placeholder="GrpHdr/MsgId" />
        </FormField>
        <FormField label="Source XPath">
          <input value={form.source_xpath} onChange={e => set('source_xpath', e.target.value)} style={inputStyle} placeholder="block4/:20" />
        </FormField>
        <FormField label="Target XPath">
          <input value={form.target_xpath} onChange={e => set('target_xpath', e.target.value)} style={inputStyle} placeholder="Document/FIToFICstmrCdtTrf/GrpHdr/MsgId" />
        </FormField>
        <FormField label="Status">
          <select value={form.status} onChange={e => set('status', e.target.value)} style={selectStyle}>
            {ELEMENT_STATUSES.map(s => <option key={s} value={s} style={{ background: '#16213e' }}>{s}</option>)}
          </select>
        </FormField>
        <FormField label="Default Value">
          <input value={form.default_value} onChange={e => set('default_value', e.target.value)} style={inputStyle} />
        </FormField>
        <div style={{ gridColumn: '1 / -1' }}>
          <FormField label="Expression (Pseudocode)">
            <textarea value={form.expression} onChange={e => set('expression', e.target.value)}
              rows={5} style={{ ...inputStyle, resize: 'vertical', fontFamily: 'monospace', fontSize: '12px', color: '#a5f3fc' }}
              placeholder={'mt103_ref = source.field_20\nmsg_id = mt103_ref + "_" + timestamp()\nreturn msg_id'} />
          </FormField>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', paddingTop: '1.5rem' }}>
          <input type="checkbox" checked={form.is_mandatory} onChange={e => set('is_mandatory', e.target.checked)}
            style={{ width: '16px', height: '16px', cursor: 'pointer' }} />
          <span style={{ color: '#9ca3af', fontSize: '13px' }}>Mandatory field</span>
        </div>
      </div>
      <ModalFooter onClose={onClose} onSave={() => {
        if (!form.source_field || !form.target_field) {
          alert('Source field and target field are required'); return;
        }
        onSave(form);
      }} />
    </Modal>
  );
};

// ── Shared Components ─────────────────────────────────────────────────────────
const GlassCard = ({ children, style }) => (
  <div style={{ background: 'rgba(255,255,255,0.05)', backdropFilter: 'blur(10px)', borderRadius: '20px', padding: '1.5rem', border: '1px solid rgba(255,255,255,0.1)', boxShadow: '0 8px 32px rgba(0,0,0,0.3)', ...style }}>
    {children}
  </div>
);

const Modal = ({ title, children, onClose, wide }) => (
  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
    style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}
    onClick={onClose}>
    <motion.div initial={{ scale: 0.9 }} animate={{ scale: 1 }} exit={{ scale: 0.9 }}
      style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)', border: '1px solid rgba(167,139,250,0.3)', borderRadius: '16px', padding: '2rem', width: '100%', maxWidth: wide ? '820px' : '600px', maxHeight: '90vh', overflowY: 'auto' }}
      onClick={e => e.stopPropagation()}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ color: 'white', margin: 0, fontSize: '1.1rem' }}>{title}</h2>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer' }}><X size={20} /></button>
      </div>
      {children}
    </motion.div>
  </motion.div>
);

const ModalFooter = ({ onClose, onSave }) => (
  <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem', justifyContent: 'flex-end' }}>
    <button onClick={onClose} style={{ padding: '0.75rem 1.5rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: 'white', cursor: 'pointer', fontSize: '0.9rem' }}>
      Cancel
    </button>
    <button onClick={onSave} style={{ padding: '0.75rem 1.5rem', background: 'linear-gradient(135deg, #a78bfa 0%, #667eea 100%)', border: 'none', borderRadius: '8px', color: 'white', cursor: 'pointer', fontSize: '0.9rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <Check size={16} /> Save
    </button>
  </div>
);

const ActionBtn = ({ icon, label, color, onClick, disabled }) => (
  <button onClick={onClick} disabled={disabled} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 14px', background: `${color}20`, border: `1px solid ${color}40`, borderRadius: '8px', color, fontSize: '12px', fontWeight: '600', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.6 : 1, transition: 'all 0.2s' }}>
    {icon} {label}
  </button>
);

const IconBtn = ({ icon, color, onClick }) => (
  <button onClick={onClick} style={{ background: 'none', border: 'none', cursor: 'pointer', color, padding: '3px', borderRadius: '4px', display: 'flex', alignItems: 'center', opacity: 0.4, transition: 'opacity 0.15s' }}
    onMouseEnter={e => e.currentTarget.style.opacity = '1'}
    onMouseLeave={e => e.currentTarget.style.opacity = '0.4'}>
    {icon}
  </button>
);

const Badge = ({ label, color }) => (
  <span style={{ padding: '2px 8px', background: `${color}20`, color, border: `1px solid ${color}40`, borderRadius: '4px', fontSize: '10px', fontWeight: '700', fontFamily: 'monospace' }}>
    {label}
  </span>
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

const selectStyle = {
  width: '100%', padding: '8px 12px', background: '#16213e',
  border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px',
  color: 'white', fontSize: '13px', boxSizing: 'border-box', cursor: 'pointer'
};

export default MappingWorkspacePage;