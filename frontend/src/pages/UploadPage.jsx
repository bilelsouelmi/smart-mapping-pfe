import { useState } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, Database, TrendingUp, Sparkles, Zap } from 'lucide-react';
import Layout from '../components/Layout';
import SuggestionCard from '../components/SuggestionCard';

const UploadPage = () => {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setAnalysisResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      alert('Please select a file first');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('http://localhost:8000/api/files/analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setAnalysisResult(response.data);
      alert('🎉 File analyzed successfully!');
    } catch (error) {
      console.error('Upload error:', error);
      alert(error.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleNewFile = () => {
    setFile(null);
    setAnalysisResult(null);
    const fileInput = document.getElementById('file-upload');
    if (fileInput) fileInput.value = '';
    console.log('🔄 Reset: Ready for new upload');
  };

  return (
    <Layout>
      <div style={{ 
        minHeight: 'calc(100vh - 100px)',
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
        padding: '2rem',
        marginTop: '-2rem',
        marginLeft: '-2rem',
        marginRight: '-2rem',
        borderRadius: '0'
      }}>
        <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            style={{ marginBottom: '3rem', textAlign: 'center' }}
          >
            <h1 style={{
              fontSize: '3rem',
              fontWeight: '800',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              marginBottom: '1rem'
            }}>
              🧠 AI-Powered File Analysis
            </h1>
            <p style={{ fontSize: '1.2rem', color: '#a0a0a0' }}>
              Upload your file and let AI suggest intelligent mappings
            </p>
          </motion.div>

          {/* Upload Section */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.1 }}
          >
            <Card>
              <div style={{
                border: '3px dashed rgba(102, 126, 234, 0.3)',
                borderRadius: '16px',
                padding: '3rem',
                textAlign: 'center',
                background: 'rgba(102, 126, 234, 0.05)',
                cursor: 'pointer',
                transition: 'all 0.3s ease'
              }}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const droppedFile = e.dataTransfer.files[0];
                if (droppedFile) {
                  setFile(droppedFile);
                  setAnalysisResult(null);
                }
              }}>
                <input
                  type="file"
                  onChange={handleFileChange}
                  style={{ display: 'none' }}
                  id="file-upload"
                  accept=".csv,.json,.xml,.xlsx"
                />
                <label htmlFor="file-upload" style={{ cursor: 'pointer', display: 'block' }}>
                  <Upload size={64} color="#667eea" style={{ margin: '0 auto 1.5rem' }} />
                  <h3 style={{ color: 'white', fontSize: '1.5rem', marginBottom: '0.5rem' }}>
                    Drop your file here or click to browse
                  </h3>
                  <p style={{ color: '#a0a0a0', fontSize: '1rem' }}>
                    Supports CSV, JSON, XML, Excel
                  </p>
                  {file && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      style={{
                        marginTop: '1.5rem',
                        padding: '1rem',
                        background: 'rgba(72, 187, 120, 0.2)',
                        borderRadius: '12px',
                        display: 'inline-block'
                      }}
                    >
                      <FileText size={24} color="#48bb78" style={{ verticalAlign: 'middle', marginRight: '0.5rem' }} />
                      <span style={{ color: '#48bb78', fontWeight: '600', fontSize: '1.1rem' }}>
                        {file.name}
                      </span>
                    </motion.div>
                  )}
                </label>
              </div>

              {file && !analysisResult && (
                <motion.button
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={handleUpload}
                  disabled={uploading}
                  style={{
                    width: '100%',
                    marginTop: '2rem',
                    padding: '1.25rem',
                    background: uploading 
                      ? 'rgba(102, 126, 234, 0.5)'
                      : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '12px',
                    fontSize: '1.2rem',
                    fontWeight: '700',
                    cursor: uploading ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.75rem'
                  }}
                >
                  {uploading ? (
                    <>
                      <div className="spinner" />
                      Analyzing with AI...
                    </>
                  ) : (
                    <>
                      <Sparkles size={24} />
                      Analyze with AI
                    </>
                  )}
                </motion.button>
              )}
            </Card>
          </motion.div>

          {/* Analysis Results */}
          <AnimatePresence>
            {analysisResult && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ delay: 0.2 }}
                style={{ marginTop: '3rem' }}
              >
                {/* Stats Grid */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
                  gap: '1.5rem',
                  marginBottom: '2rem'
                }}>
                  <StatsCard
                    icon={<FileText size={32} />}
                    label="File Type"
                    value={analysisResult.file_type}
                    color="#667eea"
                  />
                  <StatsCard
                    icon={<Database size={32} />}
                    label="Columns Detected"
                    value={analysisResult.column_structure?.length || 0}
                    color="#48bb78"
                  />
                  <StatsCard
                    icon={<TrendingUp size={32} />}
                    label="Business Domain"
                    value={analysisResult.business_domain || 'Unknown'}
                    color="#ed8936"
                  />
                  <StatsCard
                    icon={<Zap size={32} />}
                    label="AI Suggestions"
                    value={Object.keys(analysisResult.suggestions || {}).length}
                    color="#f56565"
                  />
                </div>

                {/* Suggestions Section */}
                <Card>
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '2rem',
                    flexWrap: 'wrap',
                    gap: '1rem'
                  }}>
                    <h2 style={{
                      color: 'white',
                      fontSize: '2rem',
                      margin: 0,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '1rem'
                    }}>
                      <Sparkles size={32} color="#667eea" />
                      AI Mapping Suggestions
                    </h2>

                    <motion.button
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={handleNewFile}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.75rem',
                        padding: '0.75rem 1.5rem',
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '12px',
                        fontSize: '1rem',
                        fontWeight: '600',
                        cursor: 'pointer',
                        boxShadow: '0 4px 20px rgba(102, 126, 234, 0.4)'
                      }}
                    >
                      <Upload size={20} />
                      New File
                    </motion.button>
                  </div>

                  <div style={{ display: 'grid', gap: '2rem' }}>
                    {Object.entries(analysisResult.suggestions || {}).map(([columnName, columnSuggestions]) => (
                      <SuggestionCard
                        key={columnName}
                        columnName={columnName}
                        suggestions={columnSuggestions}
                        analysisResult={analysisResult}
                      />
                    ))}
                  </div>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <style>{`
          .spinner {
            width: 24px;
            height: 24px;
            border: 3px solid rgba(255, 255, 255, 0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
          }

          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    </Layout>
  );
};

// Card Component
const Card = ({ children, style }) => (
  <motion.div
    whileHover={{ y: -5 }}
    style={{
      background: 'rgba(255, 255, 255, 0.05)',
      backdropFilter: 'blur(10px)',
      borderRadius: '20px',
      padding: '2rem',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
      ...style
    }}
  >
    {children}
  </motion.div>
);

// Stats Card Component
const StatsCard = ({ icon, label, value, color }) => (
  <motion.div
    whileHover={{ scale: 1.05 }}
    style={{
      background: `linear-gradient(135deg, ${color}15 0%, ${color}05 100%)`,
      borderRadius: '16px',
      padding: '1.5rem',
      border: `2px solid ${color}40`,
      display: 'flex',
      alignItems: 'center',
      gap: '1rem'
    }}
  >
    <div style={{ color }}>{icon}</div>
    <div>
      <div style={{ color: '#a0a0a0', fontSize: '0.9rem', marginBottom: '0.25rem' }}>
        {label}
      </div>
      <div style={{ color: 'white', fontSize: '1.5rem', fontWeight: '700' }}>
        {value}
      </div>
    </div>
  </motion.div>
);

export default UploadPage;