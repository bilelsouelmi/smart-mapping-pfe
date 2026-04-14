import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import Layout from '../components/Layout';
import Card from '../components/Card';
import axios from 'axios';
import { toast } from 'react-toastify';
import { Link2, Plus, X, TrendingUp, Zap } from 'lucide-react';

const MappingsPage = () => {
  const [messageDescriptions, setMessageDescriptions] = useState([]);
  const [mappings, setMappings] = useState([]);
  const [selectedMsgDesc, setSelectedMsgDesc] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [loading, setLoading] = useState(true);

  const [formData, setFormData] = useState({
    name: '',
    source_path: '',
    target_path: '',
    source_level: 1,
    target_level: 1,
    transformation_type: 'direct',
    transformation_rule: 'Direct copy',
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

      toast.success('✅ Mapping created successfully!');
      setShowCreateForm(false);
      setFormData({
        name: '',
        source_path: '',
        target_path: '',
        source_level: 1,
        target_level: 1,
        transformation_type: 'direct',
        transformation_rule: 'Direct copy',
        example_input: '',
        example_output: ''
      });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create mapping');
    }
  };

  const getSuccessRateColor = (rate) => {
    if (rate >= 80) return '#48bb78';
    if (rate >= 50) return '#f6ad55';
    return '#fc8181';
  };

  if (loading) {
    return (
      <Layout>
        <div style={{ textAlign: 'center', padding: '4rem' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>⏳</div>
          <div style={{ color: '#a0a0a0' }}>Loading mappings...</div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div>
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ marginBottom: '2rem' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <Link2 size={36} color="#667eea" />
              <h1 style={{
                fontSize: '2.5rem',
                fontWeight: '800',
                margin: 0,
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent'
              }}>
                Mapping Formulas
              </h1>
            </div>

            <button
              onClick={() => setShowCreateForm(!showCreateForm)}
              style={{
                padding: '0.75rem 1.5rem',
                background: showCreateForm ? 'rgba(239, 68, 68, 0.2)' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                color: showCreateForm ? '#ef4444' : 'white',
                border: showCreateForm ? '1px solid #ef4444' : 'none',
                borderRadius: '12px',
                fontSize: '1rem',
                fontWeight: '600',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
            >
              {showCreateForm ? (
                <>
                  <X size={20} />
                  Cancel
                </>
              ) : (
                <>
                  <Plus size={20} />
                  Create Mapping
                </>
              )}
            </button>
          </div>
        </motion.div>

        {/* Create Form */}
        {showCreateForm && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card style={{ marginBottom: '2rem' }}>
              <h2 style={{ color: 'white', marginBottom: '1.5rem', fontSize: '1.5rem' }}>
                ➕ Create New Mapping
              </h2>
              <form onSubmit={handleSubmit}>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
                  gap: '1.5rem'
                }}>
                  {/* Select File */}
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

                  {/* Mapping Name */}
                  <div>
                    <label style={labelStyle}>Mapping Name</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      required
                      style={inputStyle}
                      placeholder="e.g., Client ID → Customer ID"
                    />
                  </div>

                  {/* Source Path */}
                  <div>
                    <label style={labelStyle}>Source Path</label>
                    <input
                      type="text"
                      value={formData.source_path}
                      onChange={(e) => {
                        const path = e.target.value;
                        setFormData({
                          ...formData,
                          source_path: path,
                          source_level: path.split('.').length
                        });
                      }}
                      required
                      style={inputStyle}
                      placeholder="e.g., Client.Identity.Name"
                    />
                  </div>

                  {/* Target Path */}
                  <div>
                    <label style={labelStyle}>Target Path</label>
                    <input
                      type="text"
                      value={formData.target_path}
                      onChange={(e) => {
                        const path = e.target.value;
                        setFormData({
                          ...formData,
                          target_path: path,
                          target_level: path.split('.').length
                        });
                      }}
                      required
                      style={inputStyle}
                      placeholder="e.g., PmtInf.Dbtr.Nm"
                    />
                  </div>

                  {/* Transformation Type */}
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

                  {/* Transformation Rule */}
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

                <button
                  type="submit"
                  style={{
                    marginTop: '1.5rem',
                    padding: '0.75rem 2rem',
                    background: 'linear-gradient(135deg, #48bb78 0%, #38a169 100%)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '12px',
                    fontSize: '1rem',
                    fontWeight: '600',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem'
                  }}
                >
                  <Zap size={20} />
                  Create Mapping
                </button>
              </form>
            </Card>
          </motion.div>
        )}

        {/* Existing Mappings */}
        <Card>
          <h2 style={{ color: 'white', marginBottom: '1.5rem', fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            📋 Existing Mappings
            {mappings.length > 0 && (
              <span style={{
                padding: '0.25rem 0.75rem',
                background: 'rgba(102, 126, 234, 0.2)',
                color: '#667eea',
                borderRadius: '8px',
                fontSize: '0.9rem'
              }}>
                {mappings.length}
              </span>
            )}
          </h2>

          {mappings.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#a0a0a0' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📭</div>
              <div style={{ fontSize: '1.1rem' }}>No mappings yet. Create your first mapping above!</div>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{
                      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                      color: 'white',
                      padding: '1rem',
                      textAlign: 'left',
                      fontWeight: '700',
                      fontSize: '0.9rem'
                    }}>
                      Name
                    </th>
                    <th style={{
                      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                      color: 'white',
                      padding: '1rem',
                      textAlign: 'left',
                      fontWeight: '700',
                      fontSize: '0.9rem'
                    }}>
                      Source → Target
                    </th>
                    <th style={{
                      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                      color: 'white',
                      padding: '1rem',
                      textAlign: 'left',
                      fontWeight: '700',
                      fontSize: '0.9rem'
                    }}>
                      Type
                    </th>
                    <th style={{
                      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                      color: 'white',
                      padding: '1rem',
                      textAlign: 'left',
                      fontWeight: '700',
                      fontSize: '0.9rem'
                    }}>
                      Rule
                    </th>
                    <th style={{
                      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                      color: 'white',
                      padding: '1rem',
                      textAlign: 'center',
                      fontWeight: '700',
                      fontSize: '0.9rem'
                    }}>
                      Success Rate
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {mappings.map((mapping, index) => (
                    <motion.tr
                      key={mapping.id}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.05 }}
                      style={{
                        borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
                        transition: 'background 0.2s'
                      }}
                      whileHover={{ background: 'rgba(255, 255, 255, 0.05)' }}
                    >
                      <td style={{ padding: '1rem', color: 'white' }}>
                        {mapping.name}
                      </td>
                      <td style={{ padding: '1rem', color: '#a0a0a0', fontFamily: 'monospace', fontSize: '0.85rem' }}>
                        <span style={{ color: '#667eea' }}>{mapping.source_path}</span>
                        {' → '}
                        <span style={{ color: '#764ba2' }}>{mapping.target_path}</span>
                      </td>
                      <td style={{ padding: '1rem' }}>
                        <span style={{
                          background: 'rgba(118, 75, 162, 0.3)',
                          color: '#b794f4',
                          padding: '0.35rem 0.75rem',
                          borderRadius: '8px',
                          fontSize: '0.85rem',
                          fontWeight: '600'
                        }}>
                          {mapping.transformation_type}
                        </span>
                      </td>
                      <td style={{ padding: '1rem', color: '#a0a0a0', fontSize: '0.9rem' }}>
                        {mapping.transformation_rule}
                      </td>
                      <td style={{ padding: '1rem', textAlign: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                          <TrendingUp size={16} color={getSuccessRateColor(mapping.success_rate)} />
                          <span style={{
                            color: getSuccessRateColor(mapping.success_rate),
                            fontWeight: '700',
                            fontSize: '1rem'
                          }}>
                            {mapping.success_rate.toFixed(0)}%
                          </span>
                        </div>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
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
  border: '1px solid rgba(255, 255, 255, 0.1)',
  borderRadius: '8px',
  fontSize: '0.95rem',
  color: 'white',
  boxSizing: 'border-box'
};

export default MappingsPage;