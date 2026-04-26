import { useState } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';

const MTBlockReview = ({ analysisResult, onConfirmed, onRegenerate }) => {
  const [blocks, setBlocks] = useState(analysisResult.mt_blocks || {});
  const [editingBlock, setEditingBlock] = useState(null);
  const [editValues, setEditValues] = useState({});
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const handleAcceptAll = async () => {
    setSaving(true);
    try {
      await axios.put(
        `http://localhost:8000/api/files/${analysisResult.id}/mt-blocks`,
        blocks
      );
      onConfirmed(blocks);
    } catch (e) {
      alert('Failed to save blocks');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteBlock = (tag) => {
    const updated = { ...blocks };
    delete updated[tag];
    setBlocks(updated);
  };

  const handleEditBlock = (tag) => {
    setEditingBlock(tag);
    const block = blocks[tag];
    if (block.type === 'string') {
      setEditValues({ value: block.value || '' });
    } else {
      const subVals = {};
      Object.entries(block.sub_fields || {}).forEach(([k, v]) => {
        subVals[k] = v.value || '';
      });
      setEditValues(subVals);
    }
  };

  const handleSaveEdit = (tag) => {
    const block = blocks[tag];
    let updated;
    if (block.type === 'string') {
      updated = { ...block, value: editValues.value };
    } else {
      const newSubFields = { ...block.sub_fields };
      Object.keys(editValues).forEach(k => {
        newSubFields[k] = { ...newSubFields[k], value: editValues[k] };
      });
      updated = { ...block, sub_fields: newSubFields };
    }
    setBlocks(prev => ({ ...prev, [tag]: updated }));
    setEditingBlock(null);
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      // Save current blocks first
      await axios.put(
        `http://localhost:8000/api/files/${analysisResult.id}/mt-blocks`,
        blocks
      );
      // Regenerate suggestions
      const resp = await axios.post(
        `http://localhost:8000/api/files/${analysisResult.id}/regenerate-mt`
      );
      onRegenerate(resp.data);
    } catch (e) {
      alert('Failed to regenerate suggestions');
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <div style={{
      background: 'rgba(255,255,255,0.05)',
      borderRadius: '20px',
      padding: '2rem',
      border: '1px solid rgba(245,158,11,0.3)',
      marginBottom: '2rem'
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '1.5rem' }}>🏦</span>
        <div style={{ flex: 1 }}>
          <h2 style={{ color: 'white', margin: 0, fontSize: '1.4rem' }}>
            Review MT Blocks — {analysisResult.mt_type}
          </h2>
          <p style={{ color: '#a0a0a0', margin: 0, fontSize: '0.85rem' }}>
            Target: {analysisResult.iso_target} · {Object.keys(blocks).length} blocks detected
          </p>
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            style={{
              padding: '8px 16px',
              background: 'rgba(102,126,234,0.2)',
              color: '#667eea',
              border: '1px solid rgba(102,126,234,0.4)',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontWeight: '600'
            }}
          >
            {regenerating ? '⏳ Regenerating...' : '🔄 Re-generate'}
          </button>

          <button
            onClick={handleAcceptAll}
            disabled={saving}
            style={{
              padding: '8px 20px',
              background: 'linear-gradient(135deg, #22c55e, #16a34a)',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontWeight: '600'
            }}
          >
            {saving ? '⏳ Saving...' : '✅ Accept All & Continue'}
          </button>
        </div>
      </div>

      {/* Blocks Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1rem' }}>
        <AnimatePresence>
          {Object.entries(blocks).map(([tag, block]) => (
            <motion.div
              key={tag}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              style={{
                background: 'rgba(245,158,11,0.05)',
                border: '1px solid rgba(245,158,11,0.2)',
                borderRadius: '12px',
                padding: '1rem',
                position: 'relative'
              }}
            >
              {/* Block Header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <span style={{
                  padding: '2px 10px',
                  background: 'rgba(245,158,11,0.2)',
                  color: '#f59e0b',
                  borderRadius: '6px',
                  fontFamily: 'monospace',
                  fontWeight: '700',
                  fontSize: '0.9rem'
                }}>
                  {tag}
                </span>
                <span style={{ color: '#e2e8f0', fontSize: '0.85rem', flex: 1 }}>{block.name}</span>
                <span style={{
                  padding: '1px 6px',
                  background: block.type === 'map' ? 'rgba(6,182,212,0.2)' : 'rgba(102,126,234,0.2)',
                  color: block.type === 'map' ? '#06b6d4' : '#667eea',
                  borderRadius: '4px',
                  fontSize: '0.7rem',
                  fontWeight: '600'
                }}>
                  {block.type}
                </span>
              </div>

              <div style={{ fontSize: '0.7rem', color: '#6b7280', marginBottom: '0.5rem' }}>
                format: <span style={{ color: '#9ca3af', fontFamily: 'monospace' }}>{block.format}</span>
              </div>

              {/* Edit mode */}
              {editingBlock === tag ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '8px' }}>
                  {block.type === 'string' ? (
                    <input
                      value={editValues.value}
                      onChange={e => setEditValues({ value: e.target.value })}
                      style={inputStyle}
                      placeholder="Value"
                    />
                  ) : (
                    Object.keys(block.sub_fields || {}).map(subName => (
                      <div key={subName} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ color: '#06b6d4', fontSize: '0.75rem', minWidth: '70px', fontFamily: 'monospace' }}>
                          {subName}
                        </span>
                        <input
                          value={editValues[subName] || ''}
                          onChange={e => setEditValues(prev => ({ ...prev, [subName]: e.target.value }))}
                          style={{ ...inputStyle, flex: 1 }}
                          placeholder={subName}
                        />
                      </div>
                    ))
                  )}
                  <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                    <button onClick={() => handleSaveEdit(tag)} style={saveBtnStyle}>💾 Save</button>
                    <button onClick={() => setEditingBlock(null)} style={cancelBtnStyle}>✕ Cancel</button>
                  </div>
                </div>
              ) : (
                /* View mode */
                <div style={{ marginBottom: '8px' }}>
                  {block.type === 'string' && block.value && (
                    <div style={valueStyle}>{block.value}</div>
                  )}
                  {block.type === 'map' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                      {Object.entries(block.sub_fields || {}).map(([subName, subField]) => (
                        <div key={subName} style={{
                          display: 'flex', alignItems: 'center', gap: '6px',
                          padding: '3px 8px', background: 'rgba(0,0,0,0.2)',
                          borderRadius: '4px', fontSize: '0.75rem'
                        }}>
                          <span style={{ color: '#06b6d4', minWidth: '70px', fontFamily: 'monospace' }}>{subName}</span>
                          <span style={{ color: '#6b7280', fontSize: '0.7rem' }}>{subField.format}</span>
                          {subField.value && (
                            <span style={{ color: '#a5f3fc', fontFamily: 'monospace', marginLeft: 'auto' }}>
                              {subField.value}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Action buttons */}
              {editingBlock !== tag && (
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button onClick={() => handleEditBlock(tag)} style={editBtnStyle}>✏️ Edit</button>
                  <button onClick={() => handleDeleteBlock(tag)} style={deleteBtnStyle}>🗑️ Remove</button>
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
};

const inputStyle = {
  background: 'rgba(255,255,255,0.08)',
  border: '1px solid rgba(255,255,255,0.15)',
  borderRadius: '6px',
  padding: '4px 8px',
  color: 'white',
  fontSize: '0.8rem',
  fontFamily: 'monospace',
  width: '100%',
  boxSizing: 'border-box'
};

const valueStyle = {
  padding: '4px 8px',
  background: 'rgba(0,0,0,0.2)',
  borderRadius: '6px',
  fontSize: '0.8rem',
  color: '#a5f3fc',
  fontFamily: 'monospace',
  marginBottom: '6px'
};

const editBtnStyle = {
  padding: '4px 10px',
  background: 'rgba(102,126,234,0.2)',
  color: '#667eea',
  border: '1px solid rgba(102,126,234,0.3)',
  borderRadius: '6px',
  cursor: 'pointer',
  fontSize: '0.75rem',
  fontWeight: '600'
};

const deleteBtnStyle = {
  padding: '4px 10px',
  background: 'rgba(239,68,68,0.15)',
  color: '#ef4444',
  border: '1px solid rgba(239,68,68,0.3)',
  borderRadius: '6px',
  cursor: 'pointer',
  fontSize: '0.75rem',
  fontWeight: '600'
};

const saveBtnStyle = {
  padding: '4px 10px',
  background: 'rgba(34,197,94,0.2)',
  color: '#22c55e',
  border: '1px solid rgba(34,197,94,0.3)',
  borderRadius: '6px',
  cursor: 'pointer',
  fontSize: '0.75rem',
  fontWeight: '600'
};

const cancelBtnStyle = {
  padding: '4px 10px',
  background: 'rgba(255,255,255,0.05)',
  color: '#9ca3af',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '6px',
  cursor: 'pointer',
  fontSize: '0.75rem'
};

export default MTBlockReview;