import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { toast } from 'react-toastify';
import { Layers, Upload, X, Play, Check, Lock, AlertTriangle, Download } from 'lucide-react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout';
import API_BASE_URL from '../config/api';

const API = `${API_BASE_URL}/api`;

const STATUS_META = {
  success: { label: 'Success', color: '#10b981', icon: Check },
  held: { label: 'Held', color: '#f59e0b', icon: Lock },
  failed: { label: 'Failed', color: '#ef4444', icon: AlertTriangle },
};

const BatchTransformPage = () => {
  const [mappings, setMappings] = useState([]);
  const [mappingId, setMappingId] = useState('');
  const [files, setFiles] = useState([]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    axios.get(`${API}/mappings/`).then(r => setMappings(r.data)).catch(() => {});
  }, []);

  // Takes a plain array, never a live FileList — see handleFileInputChange's
  // comment for why that distinction is the whole fix.
  const addFiles = (fileArray) => {
    setFiles(prev => [...prev, ...fileArray]);
  };

  // e.target.files is a LIVE FileList tied to the <input> element, not a
  // snapshot. setFiles(prev => ...Array.from(fileList)) defers reading
  // that FileList until React actually runs the updater — by which point
  // e.target.value = '' (below) has already cleared it back to empty,
  // so the update silently applied zero files. Whether that landed before
  // or after React's flush was timing-dependent, which is exactly why
  // this was intermittent rather than consistently broken. Fix: convert
  // to a plain array HERE, synchronously, before the input is reset.
  const handleFileInputChange = (e) => {
    const selected = Array.from(e.target.files || []);
    e.target.value = '';
    if (selected.length > 0) addFiles(selected);
  };

  const removeFile = (idx) => {
    setFiles(prev => prev.filter((_, i) => i !== idx));
  };

  const clearBatch = () => {
    setFiles([]);
    setResult(null);
  };

  // Without these three handlers, the browser's default drop behavior
  // takes over — which for a plain (non-input) element typically only
  // opens/navigates to the FIRST dropped file and ignores the rest, so
  // dropping several files at once silently added just one. preventDefault
  // on both dragover and drop is what disables that fallback.
  const handleDragOver = (e) => { e.preventDefault(); setDragActive(true); };
  const handleDragLeave = (e) => { e.preventDefault(); setDragActive(false); };
  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    const dropped = Array.from(e.dataTransfer.files || []);
    if (dropped.length > 0) addFiles(dropped);
  };

  const runBatch = async () => {
    if (!mappingId) { toast.error('Select a mapping first'); return; }
    if (files.length === 0) { toast.error('Add at least one file'); return; }
    setRunning(true);
    setResult(null);
    try {
      const formData = new FormData();
      files.forEach(f => formData.append('files', f));
      const res = await axios.post(`${API}/transform/mapping/${mappingId}/batch`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResult(res.data);
      toast.success(`Batch complete — ${res.data.summary.success} succeeded, ${res.data.summary.held} held, ${res.data.summary.failed} failed`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Batch failed');
    } finally {
      setRunning(false);
    }
  };

  const downloadOutput = async (filename) => {
    try {
      const res = await axios.get(`${API}/transform/download/${encodeURIComponent(filename)}`, { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url; a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error('Download failed');
    }
  };

  return (
    <Layout>
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{
            fontSize: '2.5rem', fontWeight: '800', margin: 0,
            background: 'linear-gradient(135deg, #f472b6 0%, #667eea 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
          }}>
            📦 Batch Processing
          </h1>
          <p style={{ color: '#a0a0a0', marginTop: '0.5rem', maxWidth: '760px' }}>
            Upload multiple files at once and run each through the exact same transform pipeline as a single upload —
            same validation, same sanctions/PEP/duplicate checks, same holds. One file's failure doesn't stop the rest of the batch.
          </p>
        </div>

        <div style={{
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '16px', padding: '1.5rem', marginBottom: '1.5rem'
        }}>
          <label style={labelStyle}>Mapping</label>
          <select value={mappingId} onChange={e => setMappingId(e.target.value)} style={{ ...inputStyle, width: '100%', marginBottom: '1.25rem' }}>
            <option value="">Select a mapping...</option>
            {mappings.map(m => (
              <option key={m.id} value={m.id}>{m.name} ({m.source} → {m.target})</option>
            ))}
          </select>

          <label style={labelStyle}>Files</label>
          {/* htmlFor opens the dialog natively (no JS click() needed) —
              purely cosmetic vs. a ref-based click(), kept since it's the
              simpler standard pattern. The actual multi-file bug was in
              the onChange handler reading a live FileList too late; see
              handleFileInputChange. */}
          <label
            htmlFor="batch-file-input"
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            style={{
              display: 'block',
              border: `2px dashed ${dragActive ? '#a78bfa' : 'rgba(255,255,255,0.15)'}`,
              background: dragActive ? 'rgba(167,139,250,0.08)' : 'transparent',
              borderRadius: '12px', padding: '1.5rem',
              textAlign: 'center', marginBottom: '1rem', cursor: 'pointer',
              transition: 'border-color 0.15s, background 0.15s'
            }}>
            <Upload size={28} color={dragActive ? '#a78bfa' : '#6b7280'} style={{ margin: '0 auto 0.5rem' }} />
            <div style={{ color: '#9ca3af', fontSize: '0.85rem' }}>
              {dragActive ? 'Drop them here' : 'Click to add files, or drag and drop several at once'}
            </div>
            <input
              id="batch-file-input"
              ref={fileInputRef}
              type="file"
              multiple
              style={{ display: 'none' }}
              onChange={handleFileInputChange}
            />
          </label>

          {files.length > 0 && (
            <div style={{ marginBottom: '1.25rem' }}>
              {files.map((f, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '0.5rem 0.85rem', background: 'rgba(255,255,255,0.03)',
                  borderRadius: '8px', marginBottom: '0.4rem'
                }}>
                  <span style={{ color: '#d1d5db', fontSize: '0.82rem' }}>{f.name}</span>
                  <button onClick={() => removeFile(i)} style={iconBtnStyle('#ef4444')}><X size={13} /></button>
                </div>
              ))}
            </div>
          )}

          <button onClick={runBatch} disabled={running} style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '11px 20px', background: 'rgba(16,185,129,0.15)',
            border: '1px solid rgba(16,185,129,0.3)', borderRadius: '10px',
            color: '#10b981', cursor: running ? 'not-allowed' : 'pointer', fontWeight: '700',
            opacity: running ? 0.6 : 1
          }}>
            <Play size={16} /> {running ? 'Running...' : `Run Batch (${files.length} file${files.length === 1 ? '' : 's'})`}
          </button>
        </div>

        {result && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h2 style={{ margin: 0, color: 'white', fontSize: '1.15rem', fontWeight: '700' }}>Results</h2>
              <button onClick={clearBatch} title="Clear results and start a new batch" style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '6px 12px', background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px',
                color: '#9ca3af', cursor: 'pointer', fontSize: '0.8rem', fontWeight: '600'
              }}>
                <X size={13} /> Clear
              </button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
              <StatCard label="Total" value={result.summary.total} color="#9ca3af" />
              <StatCard label="Success" value={result.summary.success} color="#10b981" />
              <StatCard label="Held" value={result.summary.held} color="#f59e0b" />
              <StatCard label="Failed" value={result.summary.failed} color="#ef4444" />
            </div>

            <div style={{
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '16px', overflow: 'hidden'
            }}>
              <div style={{ maxHeight: '55vh', overflowY: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                      {['File', 'Status', 'Detail', 'Actions'].map(h => (
                        <th key={h} style={{ textAlign: 'left', padding: '0.85rem 1rem', color: '#6b7280', fontSize: '0.78rem', textTransform: 'uppercase', position: 'sticky', top: 0, background: '#1a1a2e' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.results.map((r, i) => {
                      const meta = STATUS_META[r.status];
                      const Icon = meta.icon;
                      return (
                        <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                          <td style={{ padding: '0.75rem 1rem', color: 'white', fontWeight: '600', fontSize: '0.85rem' }}>{r.filename}</td>
                          <td style={{ padding: '0.75rem 1rem' }}>
                            <span style={{
                              padding: '2px 10px', borderRadius: '999px', fontSize: '0.72rem', fontWeight: '700',
                              background: `${meta.color}20`, color: meta.color,
                              display: 'inline-flex', alignItems: 'center', gap: '4px', whiteSpace: 'nowrap'
                            }}>
                              <Icon size={11} /> {meta.label}
                            </span>
                          </td>
                          <td style={{ padding: '0.75rem 1rem', color: '#9ca3af', fontSize: '0.8rem', maxWidth: '420px' }}>
                            {r.status === 'success' ? r.output_filename : (r.message || r.detail)}
                          </td>
                          <td style={{ padding: '0.75rem 1rem' }}>
                            {r.status === 'success' && (
                              <button onClick={() => downloadOutput(r.output_filename)} style={iconBtnStyle('#06b6d4')} title="Download">
                                <Download size={13} />
                              </button>
                            )}
                            {r.status === 'held' && (
                              <Link to="/pending-transactions" style={{ color: '#f59e0b', fontSize: '0.78rem', textDecoration: 'none', fontWeight: '600' }}>
                                View in queue →
                              </Link>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </motion.div>
    </Layout>
  );
};

const StatCard = ({ label, value, color }) => (
  <div style={{
    background: 'rgba(255,255,255,0.03)', border: `1px solid ${color}30`,
    borderRadius: '14px', padding: '1.1rem', textAlign: 'center'
  }}>
    <div style={{ fontSize: '1.6rem', fontWeight: '800', color }}>{value}</div>
    <div style={{ color: '#6b7280', fontSize: '0.78rem', fontWeight: '600', textTransform: 'uppercase' }}>{label}</div>
  </div>
);

const labelStyle = {
  display: 'block', color: '#6b7280', fontSize: '0.78rem', fontWeight: '600',
  textTransform: 'uppercase', marginBottom: '6px'
};

const inputStyle = {
  padding: '9px 14px', background: '#1e2a3a', border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '10px', color: 'white', fontSize: '0.85rem'
};

const iconBtnStyle = (color) => ({
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: '26px', height: '26px', borderRadius: '6px',
  border: `1px solid ${color}40`, background: `${color}15`,
  color, cursor: 'pointer'
});

export default BatchTransformPage;
