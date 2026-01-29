import { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import Card from '../components/Card';
import axios from 'axios';
import { toast } from 'react-toastify';

const MappingsPage = () => {
  const [messageDescriptions, setMessageDescriptions] = useState([]);
  const [mappings, setMappings] = useState([]);
  const [selectedMsgDesc, setSelectedMsgDesc] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [loading, setLoading] = useState(true);

  const [formData, setFormData] = useState({
    name: '',
    source_column: '',
    target_column: '',
    transformation_type: 'direct',
    transformation_rule: '',
    example_input: '',
    example_output: ''
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [msgDescResp, mappingsResp] = await Promise.all([
        axios.get('http://localhost:8000/api/message-descriptions/'),
        axios.get('http://localhost:8000/api/mapping-formulas/')
      ]);

      setMessageDescriptions(msgDescResp.data);
      setMappings(mappingsResp.data);
    } catch (error) {
      toast.error('Failed to load data');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!selectedMsgDesc) {
      toast.error('Please select a file');
      return;
    }

    try {
      await axios.post('http://localhost:8000/api/mapping-formulas/', {
        ...formData,
        message_description_id: parseInt(selectedMsgDesc)
      });

      toast.success('Mapping created successfully!');
      setShowCreateForm(false);
      setFormData({
        name: '',
        source_column: '',
        target_column: '',
        transformation_type: 'direct',
        transformation_rule: '',
        example_input: '',
        example_output: ''
      });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create mapping');
    }
  };

  if (loading) {
    return <Layout><div>Loading...</div></Layout>;
  }

  return (
    <Layout>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 style={{ margin: 0, color: '#2d3748' }}>🔗 Mapping Formulas</h1>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          style={buttonStyle}
        >
          {showCreateForm ? '❌ Cancel' : '➕ Create Mapping'}
        </button>
      </div>

      {showCreateForm && (
        <Card title="Create New Mapping" style={{ marginBottom: '2rem' }}>
          <form onSubmit={handleSubmit}>
            <div style={formGridStyle}>
              <div>
                <label style={labelStyle}>Select File</label>
                <select
                  value={selectedMsgDesc}
                  onChange={(e) => setSelectedMsgDesc(e.target.value)}
                  required
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

              <div>
                <label style={labelStyle}>Mapping Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                  style={inputStyle}
                  placeholder="e.g., Map ID to ClientID"
                />
              </div>

              <div>
                <label style={labelStyle}>Source Column</label>
                <input
                  type="text"
                  value={formData.source_column}
                  onChange={(e) => setFormData({ ...formData, source_column: e.target.value })}
                  required
                  style={inputStyle}
                  placeholder="e.g., hhh"
                />
              </div>

              <div>
                <label style={labelStyle}>Target Column</label>
                <input
                  type="text"
                  value={formData.target_column}
                  onChange={(e) => setFormData({ ...formData, target_column: e.target.value })}
                  required
                  style={inputStyle}
                  placeholder="e.g., client_id"
                />
              </div>

              <div>
                <label style={labelStyle}>Transformation Type</label>
                <select
                  value={formData.transformation_type}
                  onChange={(e) => setFormData({ ...formData, transformation_type: e.target.value })}
                  style={inputStyle}
                >
                  <option value="direct">Direct Copy</option>
                  <option value="date_format">Date Format</option>
                  <option value="name_split">Name Split</option>
                  <option value="phone_format">Phone Format</option>
                  <option value="concatenate">Concatenate</option>
                  <option value="substring">Substring</option>
                  <option value="case_conversion">Case Conversion</option>
                  <option value="custom">Custom</option>
                </select>
              </div>

              <div>
                <label style={labelStyle}>Transformation Rule</label>
                <input
                  type="text"
                  value={formData.transformation_rule}
                  onChange={(e) => setFormData({ ...formData, transformation_rule: e.target.value })}
                  required
                  style={inputStyle}
                  placeholder="e.g., Direct copy"
                />
              </div>
            </div>

            <button type="submit" style={{ ...buttonStyle, marginTop: '1rem' }}>
              ✅ Create Mapping
            </button>
          </form>
        </Card>
      )}

      <Card title="📋 Existing Mappings">
        {mappings.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#718096' }}>
            No mappings yet. Create your first mapping above!
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={thStyle}>Name</th>
                  <th style={thStyle}>Source → Target</th>
                  <th style={thStyle}>Type</th>
                  <th style={thStyle}>Rule</th>
                  <th style={thStyle}>Success Rate</th>
                </tr>
              </thead>
              <tbody>
                {mappings.map(mapping => (
                  <tr key={mapping.id} style={trStyle}>
                    <td style={tdStyle}>{mapping.name}</td>
                    <td style={tdStyle}>
                      <strong>{mapping.source_column}</strong> → {mapping.target_column}
                    </td>
                    <td style={tdStyle}>
                      <span style={badgeStyle}>{mapping.transformation_type}</span>
                    </td>
                    <td style={tdStyle}>{mapping.transformation_rule}</td>
                    <td style={tdStyle}>{(mapping.success_rate * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </Layout>
  );
};

const labelStyle = {
  display: 'block',
  marginBottom: '0.5rem',
  fontWeight: 'bold',
  color: '#2d3748',
  fontSize: '0.9rem'
};

const inputStyle = {
  width: '100%',
  padding: '0.75rem',
  border: '2px solid #e2e8f0',
  borderRadius: '8px',
  fontSize: '1rem',
  boxSizing: 'border-box'
};

const formGridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
  gap: '1rem'
};

const buttonStyle = {
  padding: '0.75rem 1.5rem',
  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  color: 'white',
  border: 'none',
  borderRadius: '8px',
  fontSize: '1rem',
  fontWeight: 'bold',
  cursor: 'pointer'
};

const tableStyle = {
  width: '100%',
  borderCollapse: 'collapse'
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

export default MappingsPage;