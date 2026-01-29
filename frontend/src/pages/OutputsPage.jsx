import { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import Card from '../components/Card';
import axios from 'axios';
import { toast } from 'react-toastify';

const OutputsPage = () => {
  const [outputs, setOutputs] = useState([]);
  const [messageDescriptions, setMessageDescriptions] = useState([]);
  const [selectedMsgDesc, setSelectedMsgDesc] = useState('');
  const [loading, setLoading] = useState(true);
  const [transforming, setTransforming] = useState(false);


  
  const handleDownload = async (filename) => {
  try {
    const response = await axios.get(
      `http://localhost:8000/api/transform/download/${filename}`,
      {
        responseType: 'blob' // Important pour télécharger des fichiers
      }
    );

    // Créer un lien de téléchargement
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
    console.error('Download error:', error);
  }
};

  useEffect(() => {
    loadData();
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
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleTransform = async () => {
    if (!selectedMsgDesc) {
      toast.error('Please select a file');
      return;
    }

    setTransforming(true);

    try {
      const response = await axios.post(
        `http://localhost:8000/api/transform/apply-mapping/${selectedMsgDesc}`
      );

      toast.success(`Transformed ${response.data.rows_transformed} rows!`);
      loadData(); // Reload outputs
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Transformation failed');
      console.error(error);
    } finally {
      setTransforming(false);
    }
  };

  if (loading) {
    return <Layout><div>Loading...</div></Layout>;
  }

  return (
    <Layout>
      <h1 style={{ marginBottom: '2rem', color: '#2d3748' }}>
        ✨ Generated Outputs
      </h1>

      {/* Transform Section */}
      <Card title="🚀 Generate New Output" style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>Select File to Transform</label>
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
            disabled={!selectedMsgDesc || transforming}
            style={{
              ...buttonStyle,
              opacity: (!selectedMsgDesc || transforming) ? 0.5 : 1,
              cursor: (!selectedMsgDesc || transforming) ? 'not-allowed' : 'pointer'
            }}
          >
            {transforming ? '⏳ Transforming...' : '🚀 Transform & Generate'}
          </button>
        </div>
      </Card>

      {/* Outputs List */}
      <Card title="📂 Generated Files">
        {outputs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: '#718096' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📭</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 'bold', marginBottom: '0.5rem' }}>
              No outputs yet
            </div>
            <div>Transform a file above to generate your first output!</div>
          </div>
        ) : (
          <div style={{ display: 'grid', gap: '1rem' }}>
            {outputs.map((output, idx) => (
              <div key={idx} style={outputCardStyle}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <div style={iconStyle}>📄</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 'bold', color: '#2d3748', marginBottom: '0.25rem' }}>
                      {output.filename}
                    </div>
                    <div style={{ fontSize: '0.85rem', color: '#718096' }}>
                      Size: {(output.size / 1024).toFixed(2)} KB
                      {' • '}
                      Created: {new Date(output.created * 1000).toLocaleString()}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDownload(output.filename)}
                    style={downloadButtonStyle}
                  >
                    ⬇️ Download
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Stats */}
      {outputs.length > 0 && (
        <Card title="📊 Statistics" style={{ marginTop: '2rem' }}>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '1rem'
          }}>
            <StatBox
              icon="📁"
              label="Total Outputs"
              value={outputs.length}
            />
            <StatBox
              icon="💾"
              label="Total Size"
              value={`${(outputs.reduce((sum, o) => sum + o.size, 0) / 1024).toFixed(2)} KB`}
            />
            <StatBox
              icon="📅"
              label="Latest"
              value={outputs.length > 0 ? new Date(Math.max(...outputs.map(o => o.created * 1000))).toLocaleDateString() : '-'}
            />
          </div>
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

const inputStyle = {
  width: '100%',
  padding: '0.75rem',
  border: '2px solid #e2e8f0',
  borderRadius: '8px',
  fontSize: '1rem',
  boxSizing: 'border-box'
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
  whiteSpace: 'nowrap'
};

const outputCardStyle = {
  padding: '1rem',
  border: '2px solid #e2e8f0',
  borderRadius: '8px',
  transition: 'all 0.3s'
};

const iconStyle = {
  fontSize: '2rem',
  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  width: '60px',
  height: '60px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  borderRadius: '10px'
};

const downloadButtonStyle = {
  padding: '0.5rem 1rem',
  background: '#48bb78',
  color: 'white',
  border: 'none',
  borderRadius: '5px',
  cursor: 'pointer',
  fontSize: '0.9rem',
  fontWeight: 'bold'
};

const StatBox = ({ icon, label, value }) => (
  <div style={{
    padding: '1.5rem',
    background: '#f7fafc',
    borderRadius: '10px',
    textAlign: 'center'
  }}>
    <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>{icon}</div>
    <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#667eea', marginBottom: '0.25rem' }}>
      {value}
    </div>
    <div style={{ color: '#718096', fontSize: '0.85rem' }}>{label}</div>
  </div>
);

export default OutputsPage;