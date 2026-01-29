import { useState } from 'react';
import Layout from '../components/Layout';
import Card from '../components/Card';
import axios from 'axios';
import { toast } from 'react-toastify';
import { useNavigate } from 'react-router-dom';

const UploadPage = () => {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const navigate = useNavigate();

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      toast.error('Please select a file');
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(
        'http://localhost:8000/api/files/analyze',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        }
      );

      setResult(response.data);
      toast.success('File analyzed successfully!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Upload failed');
      console.error('Upload error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <Card title="📤 Upload & Analyze File">
        <div style={{ marginBottom: '1.5rem' }}>
          <label style={labelStyle}>
            Select File (CSV, XML, JSON, Excel)
          </label>
          <input
            type="file"
            accept=".csv,.xml,.json,.xlsx,.xls"
            onChange={handleFileChange}
            style={fileInputStyle}
          />
          {file && (
            <div style={fileInfoStyle}>
              📄 {file.name} ({(file.size / 1024).toFixed(2)} KB)
            </div>
          )}
        </div>

        <button
          onClick={handleUpload}
          disabled={!file || loading}
          style={{
            ...buttonStyle,
            opacity: (!file || loading) ? 0.5 : 1,
            cursor: (!file || loading) ? 'not-allowed' : 'pointer'
          }}
        >
          {loading ? '⏳ Analyzing with AI...' : '🚀 Upload & Analyze'}
        </button>
      </Card>

      {result && (
        <Card title="✅ Analysis Result" style={{ marginTop: '2rem' }}>
          <div style={resultContainerStyle}>
            <div style={{...resultItemStyle, background: '#667eea', color: 'white', fontWeight: 'bold'}}>
                <strong>📋 ID:</strong> {result.id}
                </div>
              <div style={resultItemStyle}>
                <strong>File:</strong> {result.file_name}
            </div>
            <div style={resultItemStyle}>
              <strong>Type:</strong> {result.file_type}
            </div>
            <div style={resultItemStyle}>
              <strong>Domain:</strong> {result.business_domain || 'Not detected'}
            </div>
            <div style={resultItemStyle}>
              <strong>Columns:</strong> {result.column_structure?.length || 0}
            </div>
          </div>

          <h3 style={{ marginTop: '1.5rem', marginBottom: '1rem' }}>
            📊 Detected Columns
          </h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={thStyle}>Column Name</th>
                  <th style={thStyle}>Type</th>
                  <th style={thStyle}>Format</th>
                  <th style={thStyle}>Sample Values</th>
                </tr>
              </thead>
              <tbody>
                {result.column_structure?.map((col, idx) => (
                  <tr key={idx} style={trStyle}>
                    <td style={tdStyle}>{col.name}</td>
                    <td style={tdStyle}>
                      <span style={badgeStyle}>{col.detected_type}</span>
                    </td>
                    <td style={tdStyle}>{col.format || '-'}</td>
                    <td style={tdStyle}>
                      {col.sample_values?.join(', ') || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button
            onClick={() => navigate('/mappings')}
            style={{ ...buttonStyle, marginTop: '1.5rem' }}
          >
            🔗 Create Mappings
          </button>
        </Card>
      )}
    </Layout>
  );
};

const labelStyle = {
  display: 'block',
  marginBottom: '0.5rem',
  fontWeight: 'bold',
  color: '#2d3748'
};

const fileInputStyle = {
  width: '100%',
  padding: '0.75rem',
  border: '2px dashed #cbd5e0',
  borderRadius: '8px',
  cursor: 'pointer'
};

const fileInfoStyle = {
  marginTop: '0.5rem',
  padding: '0.5rem',
  background: '#f7fafc',
  borderRadius: '5px',
  color: '#2d3748'
};

const buttonStyle = {
  padding: '0.75rem 1.5rem',
  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  color: 'white',
  border: 'none',
  borderRadius: '8px',
  fontSize: '1rem',
  fontWeight: 'bold',
  cursor: 'pointer',
  transition: 'transform 0.2s'
};

const resultContainerStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
  gap: '1rem',
  marginBottom: '1rem'
};

const resultItemStyle = {
  padding: '1rem',
  background: '#f7fafc',
  borderRadius: '8px'
};

const tableStyle = {
  width: '100%',
  borderCollapse: 'collapse',
  marginTop: '0.5rem'
};

const thStyle = {
  background: '#667eea',
  color: 'white',
  padding: '0.75rem',
  textAlign: 'left',
  fontWeight: 'bold'
};

const tdStyle = {
  padding: '0.75rem',
  borderBottom: '1px solid #e2e8f0'
};

const trStyle = {
  transition: 'background 0.2s'
};

const badgeStyle = {
  background: '#764ba2',
  color: 'white',
  padding: '0.25rem 0.5rem',
  borderRadius: '5px',
  fontSize: '0.85rem'
};

export default UploadPage;