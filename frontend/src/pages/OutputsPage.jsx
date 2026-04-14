import { useState, useEffect, useRef } from 'react';
import Layout from '../components/Layout';
import Card from '../components/Card';
import axios from 'axios';
import { toast } from 'react-toastify';
import { motion, AnimatePresence } from 'framer-motion';

const OutputsPage = () => {
  const [outputs, setOutputs] = useState([]);
  const [messageDescriptions, setMessageDescriptions] = useState([]);
  const [selectedMsgDesc, setSelectedMsgDesc] = useState('');
  const [loading, setLoading] = useState(true);
  const [activeJob, setActiveJob] = useState(null);
  const [jobs, setJobs] = useState([]);
  const pollingRef = useRef(null);

  useEffect(() => {
    loadData();
    loadJobs();
    return () => clearInterval(pollingRef.current);
  }, []);

  const loadData = async () => {
    try {
      const [outputsResp, msgDescResp] = await Promise.all([
        axios.get('http://localhost:8000/api/transform/outputs'),
        axios.get('http://localhost:8000/api/message-descriptions/')
      ]);
      setOutputs(outputsResp.data.files || []);
      setMessageDescriptions(msgDescResp.data);
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const loadJobs = async () => {
    try {
      const resp = await axios.get('http://localhost:8000/api/transform/jobs');
      setJobs(resp.data.jobs || []);
    } catch (error) {
      console.error('Failed to load jobs:', error);
    }
  };

  const pollJobStatus = (jobId) => {
    pollingRef.current = setInterval(async () => {
      try {
        const resp = await axios.get(`http://localhost:8000/api/transform/job/${jobId}`);
        const job = resp.data;
        setActiveJob(job);

        if (job.status === 'completed' || job.status === 'failed') {
          clearInterval(pollingRef.current);
          loadData();
          loadJobs();
          if (job.status === 'completed') {
            toast.success('✅ Transformation completed!');
          } else {
            toast.error(`❌ Job failed: ${job.error_message}`);
          }
        }
      } catch (error) {
        clearInterval(pollingRef.current);
      }
    }, 1500);
  };

  const handleTransform = async () => {
    if (!selectedMsgDesc) {
      toast.error('Please select a file');
      return;
    }
    try {
      const response = await axios.post(
        `http://localhost:8000/api/transform/apply-mapping/${selectedMsgDesc}`
      );
      const { job_id } = response.data;
      toast.info(`🚀 Job #${job_id} started`);

      // Start polling
      const initialJob = { job_id, status: 'pending', progress: 0, validation_report: null };
      setActiveJob(initialJob);
      pollJobStatus(job_id);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Transformation failed');
    }
  };

  const handleDownload = async (filename) => {
    try {
      const response = await axios.get(
        `http://localhost:8000/api/transform/download/${filename}`,
        { responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('File downloaded!');
    } catch (error) {
      toast.error('Download failed');
    }
  };

  const getQualityColor = (quality) => {
    const map = {
      EXCELLENT: '#22c55e',
      GOOD: '#3b82f6',
      ACCEPTABLE: '#f59e0b',
      POOR: '#ef4444'
    };
    return map[quality] || '#9ca3af';
  };

  const getQualityEmoji = (quality) => {
    const map = { EXCELLENT: '🏆', GOOD: '✅', ACCEPTABLE: '⚠️', POOR: '❌' };
    return map[quality] || '❓';
  };

  const getStatusColor = (status) => {
    const map = {
      pending: '#f59e0b',
      running: '#3b82f6',
      completed: '#22c55e',
      failed: '#ef4444'
    };
    return map[status] || '#9ca3af';
  };

  if (loading) {
    return (
      <Layout>
        <div style={{ textAlign: 'center', padding: '4rem', color: '#a0a0a0' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>⏳</div>
          Loading...
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>

        {/* Header */}
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{
            fontSize: '2.5rem',
            fontWeight: '800',
            margin: 0,
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}>
            🚀 Transformation & Validation
          </h1>
          <p style={{ color: '#a0a0a0', marginTop: '0.5rem' }}>
            Apply mappings, track jobs, and view validation reports
          </p>
        </div>

        {/* Transform Section */}
        <Card style={{ marginBottom: '2rem' }}>
          <h2 style={{ color: 'white', marginBottom: '1.5rem', fontSize: '1.3rem' }}>
            ⚡ Launch Transformation Job
          </h2>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '200px' }}>
              <label style={labelStyle}>Select File</label>
              <select
                value={selectedMsgDesc}
                onChange={(e) => setSelectedMsgDesc(e.target.value)}
                style={inputStyle}
              >
                <option value="">Choose a file...</option>
                {messageDescriptions.map(md => (
                  <option key={md.id} value={md.id}>
                    {md.file_name} (ID: {md.id})
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={handleTransform}
              disabled={!selectedMsgDesc || (activeJob && activeJob.status === 'running')}
              style={{
                padding: '0.75rem 1.5rem',
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                color: 'white',
                border: 'none',
                borderRadius: '10px',
                fontSize: '1rem',
                fontWeight: '600',
                cursor: 'pointer',
                opacity: (!selectedMsgDesc || (activeJob && activeJob.status === 'running')) ? 0.5 : 1,
                whiteSpace: 'nowrap'
              }}
            >
              🚀 Transform & Validate
            </button>
          </div>
        </Card>

        {/* Active Job Monitor */}
        <AnimatePresence>
          {activeJob && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              style={{ marginBottom: '2rem' }}
            >
              <Card>
                <h2 style={{ color: 'white', marginBottom: '1.5rem', fontSize: '1.3rem' }}>
                  📊 Job #{activeJob.job_id} — Status
                </h2>

                {/* Progress Bar */}
                <div style={{ marginBottom: '1.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <span style={{ color: '#a0a0a0', fontSize: '0.9rem' }}>{activeJob.job_name || 'Processing...'}</span>
                    <span style={{ color: getStatusColor(activeJob.status), fontWeight: '700' }}>
                      {activeJob.status?.toUpperCase()} {activeJob.progress ? `— ${activeJob.progress}%` : ''}
                    </span>
                  </div>
                  <div style={{ background: 'rgba(255,255,255,0.1)', borderRadius: '999px', height: '8px', overflow: 'hidden' }}>
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${activeJob.progress || 0}%` }}
                      transition={{ duration: 0.5 }}
                      style={{
                        height: '100%',
                        borderRadius: '999px',
                        background: `linear-gradient(90deg, ${getStatusColor(activeJob.status)}, ${getStatusColor(activeJob.status)}88)`
                      }}
                    />
                  </div>
                </div>

                {/* Validation Report */}
                {activeJob.validation_report && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                    <div style={{
                      background: 'rgba(255,255,255,0.03)',
                      borderRadius: '12px',
                      padding: '1.5rem',
                      border: `1px solid ${getQualityColor(activeJob.validation_report.overall_quality)}40`
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
                        <span style={{ fontSize: '2rem' }}>
                          {getQualityEmoji(activeJob.validation_report.overall_quality)}
                        </span>
                        <div>
                          <div style={{
                            fontSize: '1.5rem',
                            fontWeight: '800',
                            color: getQualityColor(activeJob.validation_report.overall_quality)
                          }}>
                            {activeJob.validation_report.overall_quality}
                          </div>
                          <div style={{ color: '#a0a0a0', fontSize: '0.9rem' }}>
                            {activeJob.validation_report.recommendation}
                          </div>
                        </div>
                        <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
                          <div style={{
                            fontSize: '2.5rem',
                            fontWeight: '900',
                            color: getQualityColor(activeJob.validation_report.overall_quality)
                          }}>
                            {activeJob.validation_report.accuracy_percentage}%
                          </div>
                          <div style={{ color: '#a0a0a0', fontSize: '0.8rem' }}>Accuracy</div>
                        </div>
                      </div>

                      {/* Stats Grid */}
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1rem' }}>
                        {[
                          { label: 'Total Cells', value: activeJob.validation_report.total_cells, color: '#a0a0a0' },
                          { label: 'Matching', value: activeJob.validation_report.matching_cells, color: '#22c55e' },
                          { label: 'Differing', value: activeJob.validation_report.differing_cells, color: '#ef4444' },
                          { label: 'Row Match', value: activeJob.validation_report.row_count_match ? '✅' : '❌', color: '#3b82f6' }
                        ].map(stat => (
                          <div key={stat.label} style={{
                            background: 'rgba(255,255,255,0.05)',
                            borderRadius: '8px',
                            padding: '0.75rem',
                            textAlign: 'center'
                          }}>
                            <div style={{ fontSize: '1.5rem', fontWeight: '700', color: stat.color }}>{stat.value}</div>
                            <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.25rem' }}>{stat.label}</div>
                          </div>
                        ))}
                      </div>

                      {/* Differences */}
                      {activeJob.validation_report.differences && activeJob.validation_report.differences.length > 0 && (
                        <div>
                          <div style={{ fontSize: '0.85rem', color: '#f59e0b', fontWeight: '600', marginBottom: '0.5rem' }}>
                            ⚠️ Differences detected:
                          </div>
                          <div style={{ maxHeight: '150px', overflowY: 'auto' }}>
                            {activeJob.validation_report.differences.map((diff, i) => (
                              <div key={i} style={{
                                fontSize: '0.8rem',
                                color: '#9ca3af',
                                padding: '4px 8px',
                                borderBottom: '1px solid rgba(255,255,255,0.05)',
                                fontFamily: 'monospace'
                              }}>
                                Row {diff.row_number} / {diff.column_name}: 
                                <span style={{ color: '#ef4444' }}> "{diff.expected_value}"</span>
                                {' → '}
                                <span style={{ color: '#22c55e' }}>"{diff.generated_value}"</span>
                                <span style={{ color: '#f59e0b', marginLeft: '0.5rem' }}>({diff.difference_type})</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}

                {activeJob.error_message && (
                  <div style={{
                    background: 'rgba(239,68,68,0.1)',
                    border: '1px solid rgba(239,68,68,0.3)',
                    borderRadius: '8px',
                    padding: '1rem',
                    color: '#ef4444',
                    fontSize: '0.9rem'
                  }}>
                    ❌ {activeJob.error_message}
                  </div>
                )}
              </Card>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Jobs History */}
        {jobs.length > 0 && (
          <Card style={{ marginBottom: '2rem' }}>
            <h2 style={{ color: 'white', marginBottom: '1.5rem', fontSize: '1.3rem' }}>
              📋 Recent Jobs
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {jobs.map(job => (
                <div key={job.job_id} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '1rem',
                  padding: '0.75rem 1rem',
                  background: 'rgba(255,255,255,0.03)',
                  borderRadius: '8px',
                  border: '1px solid rgba(255,255,255,0.06)'
                }}>
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: '999px',
                    fontSize: '0.75rem',
                    fontWeight: '700',
                    background: `${getStatusColor(job.status)}20`,
                    color: getStatusColor(job.status)
                  }}>
                    {job.status?.toUpperCase()}
                  </span>
                  <span style={{ color: '#e2e8f0', fontSize: '0.9rem', flex: 1 }}>{job.job_name}</span>
                  <span style={{ color: '#6b7280', fontSize: '0.8rem' }}>
                    {job.created_at ? new Date(job.created_at).toLocaleString() : ''}
                  </span>
                  <button
                    onClick={async () => {
                      const resp = await axios.get(`http://localhost:8000/api/transform/job/${job.job_id}`);
                      setActiveJob(resp.data);
                    }}
                    style={{
                      padding: '4px 10px',
                      background: 'rgba(102,126,234,0.2)',
                      color: '#667eea',
                      border: '1px solid rgba(102,126,234,0.3)',
                      borderRadius: '6px',
                      fontSize: '0.75rem',
                      cursor: 'pointer'
                    }}
                  >
                    View
                  </button>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Output Files */}
        <Card>
          <h2 style={{ color: 'white', marginBottom: '1.5rem', fontSize: '1.3rem' }}>
            📂 Generated Files ({outputs.length})
          </h2>
          {outputs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#a0a0a0' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📭</div>
              <div>No outputs yet. Launch a transformation above!</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {outputs.map((output, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '1rem',
                    padding: '1rem',
                    background: 'rgba(255,255,255,0.03)',
                    borderRadius: '10px',
                    border: '1px solid rgba(255,255,255,0.08)'
                  }}
                >
                  <div style={{
                    fontSize: '1.5rem',
                    width: '40px',
                    height: '40px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'rgba(102,126,234,0.15)',
                    borderRadius: '8px'
                  }}>
                    📄
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ color: 'white', fontWeight: '600', fontSize: '0.9rem' }}>{output.filename}</div>
                    <div style={{ color: '#6b7280', fontSize: '0.8rem', marginTop: '2px' }}>
                      {(output.size / 1024).toFixed(2)} KB • {new Date(output.created * 1000).toLocaleString()}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDownload(output.filename)}
                    style={{
                      padding: '6px 14px',
                      background: 'linear-gradient(135deg, #22c55e, #16a34a)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '0.85rem',
                      fontWeight: '600',
                      cursor: 'pointer'
                    }}
                  >
                    ⬇️ Download
                  </button>
                </motion.div>
              ))}
            </div>
          )}
        </Card>
      </motion.div>
    </Layout>
  );
};

const labelStyle = {
  display: 'block',
  marginBottom: '0.5rem',
  fontWeight: '600',
  color: '#a0a0a0',
  fontSize: '0.9rem'
};

const inputStyle = {
  width: '100%',
  padding: '0.75rem',
  background: '#1a1a2e',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '8px',
  fontSize: '0.95rem',
  color: 'white',
  boxSizing: 'border-box'
};

export default OutputsPage;