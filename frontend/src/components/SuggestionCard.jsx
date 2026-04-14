import { useState } from 'react';
import axios from 'axios';
import { ArrowRight, AlertCircle } from 'lucide-react';

const SuggestionCard = ({ columnName, suggestions, analysisResult }) => {
  const [editMode, setEditMode] = useState(false);
  const [editedValues, setEditedValues] = useState(null);
  const [currentSuggestion, setCurrentSuggestion] = useState(suggestions[0]);
  const [showFullFormula, setShowFullFormula] = useState(false); // ── NOUVEAU ──
  const [showConditions, setShowConditions] = useState(false);
  const [showComplianceDetails, setShowComplianceDetails] = useState(false);

  // ── Helpers mapping_formula (objet ou string) ─────────────────────────────
  const getMFPseudocode = (mf) => {
    if (!mf) return null;
    if (typeof mf === 'string') return mf;
    return mf.pseudocode || mf.expression || null;
  };
  const getMFExpression = (mf) => (mf && typeof mf === 'object') ? (mf.expression || null) : null;
  const getMFGlobalVars = (mf) => (mf && typeof mf === 'object') ? (mf.details?.global_variables || null) : null;
  const getMFConditions = (mf) => (mf && typeof mf === 'object') ? (mf.details?.conditions || null) : null;
  // ── FIN Helpers ───────────────────────────────────────────────────────────

  if (!suggestions || suggestions.length === 0) {
    return (
      <Card style={{ opacity: 0.6 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ color: 'white', margin: 0, fontSize: '1.1rem', fontFamily: 'monospace' }}>
              {columnName}
            </h3>
            <p style={{ color: '#a0a0a0', margin: '0.5rem 0 0 0', fontSize: '0.9rem' }}>
              <AlertCircle size={16} style={{ verticalAlign: 'middle', marginRight: '0.5rem' }} />
              No matching StandardElements found
            </p>
          </div>
        </div>
      </Card>
    );
  }

  const getSourceBadge = (source) => {
    const badges = {
      learning: { emoji: '🧠', text: 'Learned from you', color: '#22c55e' },
      element_matcher: { emoji: '📚', text: 'Knowledge Base', color: '#667eea' },
      ai: { emoji: '🤖', text: 'AI Generated', color: '#a855f7' }
    };
    return badges[source] || { emoji: '💡', text: 'Suggestion', color: '#888' };
  };

  const sourceBadge = getSourceBadge(currentSuggestion.suggestion_source);
  const confidence = currentSuggestion.confidence || 50;

  // ── NOUVEAU : vérifie si enrichissement Qdrant disponible ──────────────────
  const ragMF = currentSuggestion.mapping_formula;
  const ragPseudocode = getMFPseudocode(ragMF);
  const ragExpression = getMFExpression(ragMF);
  const ragGlobalVars = getMFGlobalVars(ragMF);
  const ragConditions = getMFConditions(ragMF);

  const hasRagEnrichment = !!(
    currentSuggestion.audit_requirement ||
    currentSuggestion.compliance_requirement ||
    currentSuggestion.data_privacy ||
    currentSuggestion.migration_note ||
    currentSuggestion.caching_strategy ||
    ragPseudocode
  );
  // ── FIN NOUVEAU ────────────────────────────────────────────────────────────

  const handleRecordDecision = async (action, finalValues = null) => {
    try {
      await axios.post('http://localhost:8000/api/ai-learning/record-decision', {
        field_id: columnName,
        field_tag: null,
        suggestion: currentSuggestion.full_suggestion || currentSuggestion,
        user_action: action,
        final_values: finalValues,
        message_description_id: analysisResult.id,
        mapping_formula_id: null
      });
      console.log(`✅ Recorded ${action} for ${columnName}`);
    } catch (error) {
      console.error('Failed to record decision:', error);
    }
  };

  const handleApply = async (suggestionToUse = null) => {
    try {
      const suggestion = suggestionToUse || currentSuggestion;
      const sourceLevel = columnName.split('.').length;
      const targetLevel = suggestion.target_path ? suggestion.target_path.split('.').length : 1;

      await axios.post('http://localhost:8000/api/mapping-formulas/', {
        message_description_id: analysisResult.id,
        name: `${columnName} → ${suggestion.element_name}`,
        source_path: columnName,
        target_path: suggestion.target_path || suggestion.element_name,
        source_level: sourceLevel,
        target_level: targetLevel,
        transformation_type: 'direct',
        transformation_rule: `Auto-suggested (${confidence}% confidence)`,
        example_input: null,
        example_output: null
      });

      await handleRecordDecision('accept', null);
      alert(`✅ Mapping created: ${columnName} → ${suggestion.element_name}`);
    } catch (error) {
      console.error('Error creating mapping:', error);
      alert(error.response?.data?.detail?.[0]?.msg || 'Failed to create mapping');
    }
  };

  const handleEdit = () => {
    const mf = currentSuggestion.mapping_formula;
    const mfPseudo = getMFPseudocode(mf) || '';
    const mfExpr = getMFExpression(mf) || '';
    const mfGlobalVars = getMFGlobalVars(mf) || {};
    const mfConditions = getMFConditions(mf) || {};

    setEditedValues({
      element_id: currentSuggestion.element_id || '',
      element_name: currentSuggestion.element_name || '',
      description: currentSuggestion.element_name || '',
      source: columnName,
      target: currentSuggestion.target_path || '',
      transformation: currentSuggestion.full_suggestion?.transformation || 'DIRECT_COPY',
      criticality: currentSuggestion.full_suggestion?.criticality || 'MEDIUM',
      category: currentSuggestion.category || 'Financial',
      data_type: 'String',
      // ── mapping_formula fields ─────────────────────────────────────────────
      formula_pseudocode: mfPseudo,
      formula_expression: mfExpr,
      formula_global_vars: Object.entries(mfGlobalVars).map(([k, v]) => `${k}=${v}`).join('\n'),
      formula_conditions: Object.entries(mfConditions).map(([k, v]) => `${k}: ${v}`).join('\n'),
    });
    setEditMode(true);
    console.log('✏️ Edit mode activated for:', columnName);
  };

  const handleSaveEdit = async () => {
    // Rebuild mapping_formula object from edited fields
    const globalVarsObj = {};
    (editedValues.formula_global_vars || '').split('\n').forEach(line => {
      const [k, ...rest] = line.split('=');
      if (k?.trim()) globalVarsObj[k.trim()] = rest.join('=').trim();
    });
    const conditionsObj = {};
    (editedValues.formula_conditions || '').split('\n').forEach(line => {
      const [k, ...rest] = line.split(':');
      if (k?.trim()) conditionsObj[k.trim()] = rest.join(':').trim();
    });
    const updatedMappingFormula = {
      pseudocode: editedValues.formula_pseudocode,
      expression: editedValues.formula_expression,
      details: { global_variables: globalVarsObj, conditions: conditionsObj }
    };

    const finalValues = {
      element_id: editedValues.element_id,
      element_name: editedValues.element_name,
      description: editedValues.element_name,
      source: editedValues.source,
      target: editedValues.target,
      transformation: editedValues.transformation,
      criticality: editedValues.criticality,
      category: editedValues.category,
      data_type: editedValues.data_type,
      mapping_formula: updatedMappingFormula
    };

    console.log('💾 Saving edited values:', finalValues);

    const editedSuggestion = {
      ...currentSuggestion,
      element_id: finalValues.element_id,
      element_name: finalValues.element_name,
      target_path: finalValues.target,
      category: finalValues.category,
      mapping_formula: finalValues.mapping_formula,
      full_suggestion: {
        ...currentSuggestion.full_suggestion,
        element_id: finalValues.element_id,
        description: finalValues.description,
        source: finalValues.source,
        target: finalValues.target,
        transformation: finalValues.transformation,
        criticality: finalValues.criticality,
        category: finalValues.category,
        data_type: finalValues.data_type,
        mapping_formula: finalValues.mapping_formula
      }
    };

    try {
      await handleApply(editedSuggestion);
      await handleRecordDecision('edit', finalValues);
      console.log('✅ Edit saved successfully!');
      setCurrentSuggestion(editedSuggestion);
      setEditMode(false);
      alert('💾 Saved and learned from your correction!');
    } catch (error) {
      console.error('❌ Error saving edit:', error);
      alert('❌ Error saving changes. Check console for details.');
    }
  };

  const handleReject = async () => {
    await handleRecordDecision('reject', null);
    alert('❌ Rejected - AI will learn from this');
  };

  return (
    <Card>
      {/* Header */}
      <div style={{ marginBottom: '1.5rem', paddingBottom: '1rem', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
        <h3 style={{
          color: 'white',
          margin: 0,
          fontSize: '1.2rem',
          fontFamily: 'monospace',
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          flexWrap: 'wrap'
        }}>
          <span style={{
            padding: '0.25rem 0.75rem',
            background: 'rgba(102, 126, 234, 0.2)',
            borderRadius: '8px',
            fontSize: '0.9rem'
          }}>
            {columnName}
          </span>
          <ArrowRight size={20} color="#667eea" />

          <span style={{
            padding: '0.25rem 0.75rem',
            background: `${sourceBadge.color}20`,
            color: sourceBadge.color,
            borderRadius: '8px',
            fontSize: '0.75rem',
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            gap: '0.25rem'
          }}>
            <span>{sourceBadge.emoji}</span>
            <span>{sourceBadge.text}</span>
          </span>

          {/* ── NOUVEAU : badge RAG enrichi ──────────────────────────────── */}
          {hasRagEnrichment && (
            <span style={{
              padding: '0.25rem 0.75rem',
              background: 'rgba(6, 182, 212, 0.15)',
              color: '#06b6d4',
              borderRadius: '8px',
              fontSize: '0.75rem',
              fontWeight: '600',
              border: '1px solid rgba(6, 182, 212, 0.3)'
            }}>
              ✨ RAG Enriched
            </span>
          )}
          {/* ── FIN NOUVEAU ─────────────────────────────────────────────── */}
        </h3>
      </div>

      {editMode ? (
        /* EDIT MODE - FORMULAIRE COMPLET - IDENTIQUE À L'ORIGINAL */
        <div
          key="edit-mode"
          style={{
            padding: '1.5rem',
            background: 'rgba(102, 126, 234, 0.1)',
            borderRadius: '12px',
            border: '2px solid rgba(102, 126, 234, 0.3)',
            animation: 'fadeIn 0.2s ease-in'
          }}
        >
          <h4 style={{ color: 'white', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            ✏️ Edit Suggestion
          </h4>

          <div style={{ display: 'grid', gap: '1rem' }}>
            {/* SOURCE */}
            <div>
              <label style={{ display: 'block', color: '#a0a0a0', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                Source
              </label>
              <input
                type="text"
                value={editedValues.source}
                onChange={(e) => setEditedValues({ ...editedValues, source: e.target.value })}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  borderRadius: '8px',
                  color: 'white',
                  fontSize: '0.9rem',
                  fontFamily: 'monospace'
                }}
              />
            </div>

            {/* TARGET PATH */}
            <div>
              <label style={{ display: 'block', color: '#a0a0a0', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                Target Path
              </label>
              <input
                type="text"
                value={editedValues.target}
                onChange={(e) => setEditedValues({ ...editedValues, target: e.target.value })}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  borderRadius: '8px',
                  color: 'white',
                  fontSize: '0.9rem',
                  fontFamily: 'monospace'
                }}
              />
            </div>

            {/* ELEMENT ID */}
            <div>
              <label style={{ display: 'block', color: '#a0a0a0', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                Element ID
              </label>
              <input
                type="text"
                value={editedValues.element_id}
                onChange={(e) => setEditedValues({ ...editedValues, element_id: e.target.value })}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  borderRadius: '8px',
                  color: 'white',
                  fontSize: '0.9rem',
                  fontFamily: 'monospace'
                }}
              />
            </div>

            {/* ELEMENT NAME */}
            <div>
              <label style={{ display: 'block', color: '#a0a0a0', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                Element Name
              </label>
              <input
                type="text"
                value={editedValues.element_name}
                onChange={(e) => setEditedValues({ ...editedValues, element_name: e.target.value })}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  borderRadius: '8px',
                  color: 'white',
                  fontSize: '0.9rem'
                }}
              />
            </div>

            {/* MAPPING FORMULA SECTION */}
            <div style={{
              background: 'rgba(102, 126, 234, 0.05)',
              padding: '1rem',
              borderRadius: '8px',
              border: '1px solid rgba(102, 126, 234, 0.2)'
            }}>
              <div style={{
                fontSize: '0.85rem',
                color: '#667eea',
                marginBottom: '1rem',
                fontWeight: '600',
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}>
                🧮 Mapping Formula
              </div>

              {/* PSEUDOCODE */}
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', color: '#a0a0a0', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                  Pseudocode
                </label>
                <textarea
                  value={editedValues.formula_pseudocode}
                  onChange={(e) => setEditedValues({ ...editedValues, formula_pseudocode: e.target.value })}
                  rows={5}
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid rgba(102, 126, 234, 0.3)',
                    borderRadius: '8px',
                    color: '#a5f3fc',
                    fontSize: '0.8rem',
                    fontFamily: 'monospace',
                    lineHeight: '1.6',
                    resize: 'vertical',
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              {/* EXPRESSION */}
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', color: '#a0a0a0', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                  Expression
                </label>
                <input
                  type="text"
                  value={editedValues.formula_expression}
                  onChange={(e) => setEditedValues({ ...editedValues, formula_expression: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    borderRadius: '8px',
                    color: '#9ca3af',
                    fontSize: '0.85rem',
                    fontFamily: 'monospace'
                  }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                {/* GLOBAL VARIABLES */}
                <div>
                  <label style={{ display: 'block', color: '#f97316', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                    ⚙️ Global Variables
                    <span style={{ color: '#6b7280', fontSize: '0.75rem', marginLeft: '0.5rem' }}>
                      (NAME=value par ligne)
                    </span>
                  </label>
                  <textarea
                    value={editedValues.formula_global_vars}
                    onChange={(e) => setEditedValues({ ...editedValues, formula_global_vars: e.target.value })}
                    rows={4}
                    placeholder={'MAX_MSG_ID_LENGTH=35\nDUPLICATE_WINDOW_DAYS=3'}
                    style={{
                      width: '100%',
                      padding: '0.75rem',
                      background: 'rgba(249, 115, 22, 0.05)',
                      border: '1px solid rgba(249, 115, 22, 0.2)',
                      borderRadius: '8px',
                      color: '#fb923c',
                      fontSize: '0.75rem',
                      fontFamily: 'monospace',
                      lineHeight: '1.6',
                      resize: 'vertical',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>

                {/* CONDITIONS */}
                <div>
                  <label style={{ display: 'block', color: '#06b6d4', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                    🔀 Conditions
                    <span style={{ color: '#6b7280', fontSize: '0.75rem', marginLeft: '0.5rem' }}>
                      (condition_1: expression par ligne)
                    </span>
                  </label>
                  <textarea
                    value={editedValues.formula_conditions}
                    onChange={(e) => setEditedValues({ ...editedValues, formula_conditions: e.target.value })}
                    rows={4}
                    placeholder={'condition_1: source.field != null\ncondition_2: length(source.field) <= 16'}
                    style={{
                      width: '100%',
                      padding: '0.75rem',
                      background: 'rgba(6, 182, 212, 0.05)',
                      border: '1px solid rgba(6, 182, 212, 0.2)',
                      borderRadius: '8px',
                      color: '#67e8f9',
                      fontSize: '0.75rem',
                      fontFamily: 'monospace',
                      lineHeight: '1.6',
                      resize: 'vertical',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>
              </div>
            </div>

            {/* RELATED DETAILS - GRID 2x2 */}
            <div style={{ 
              background: 'rgba(255,255,255,0.03)', 
              padding: '1rem', 
              borderRadius: '8px',
              border: '1px solid rgba(255,255,255,0.1)'
            }}>
              <div style={{ 
                fontSize: '0.85rem', 
                color: '#9ca3af', 
                marginBottom: '1rem',
                fontWeight: '600',
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}>
                Related Details
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                {/* TRANSFORMATION */}
                <div>
                  <label style={{ display: 'block', color: '#a0a0a0', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                    Transformation
                  </label>
                  <select
                    value={editedValues.transformation}
                    onChange={(e) => setEditedValues({ ...editedValues, transformation: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '0.75rem',
                      background: 'rgba(255, 255, 255, 0.05)',
                      border: '1px solid rgba(255, 255, 255, 0.2)',
                      borderRadius: '8px',
                      color: 'white',
                      fontSize: '0.9rem',
                      cursor: 'pointer'
                    }}
                  >
                    <option value="DIRECT_COPY" style={{ background: '#1a1a2e', color: 'white' }}>Direct Copy</option>
                    <option value="DERIVATION" style={{ background: '#1a1a2e', color: 'white' }}>Derivation</option>
                    <option value="EXTRACTION" style={{ background: '#1a1a2e', color: 'white' }}>Extraction</option>
                    <option value="TRANSFORMATION" style={{ background: '#1a1a2e', color: 'white' }}>Transformation</option>
                  </select>
                </div>

                {/* CRITICALITY */}
                <div>
                  <label style={{ display: 'block', color: '#a0a0a0', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                    Criticality
                  </label>
                  <select
                    value={editedValues.criticality}
                    onChange={(e) => setEditedValues({ ...editedValues, criticality: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '0.75rem',
                      background: 'rgba(255, 255, 255, 0.05)',
                      border: '1px solid rgba(255, 255, 255, 0.2)',
                      borderRadius: '8px',
                      color: 'white',
                      fontSize: '0.9rem',
                      cursor: 'pointer'
                    }}
                  >
                    <option value="LOW" style={{ background: '#1a1a2e', color: 'white' }}>Low</option>
                    <option value="MEDIUM" style={{ background: '#1a1a2e', color: 'white' }}>Medium</option>
                    <option value="HIGH" style={{ background: '#1a1a2e', color: 'white' }}>High</option>
                    <option value="CRITICAL" style={{ background: '#1a1a2e', color: 'white' }}>Critical</option>
                  </select>
                </div>

                {/* CATEGORY */}
                <div>
                  <label style={{ display: 'block', color: '#a0a0a0', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                    Category
                  </label>
                  <select
                    value={editedValues.category}
                    onChange={(e) => setEditedValues({ ...editedValues, category: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '0.75rem',
                      background: 'rgba(255, 255, 255, 0.05)',
                      border: '1px solid rgba(255, 255, 255, 0.2)',
                      borderRadius: '8px',
                      color: 'white',
                      fontSize: '0.9rem',
                      cursor: 'pointer'
                    }}
                  >
                    <option value="Financial" style={{ background: '#1a1a2e', color: 'white' }}>Financial</option>
                    <option value="AI Suggestion" style={{ background: '#1a1a2e', color: 'white' }}>AI Suggestion</option>
                    <option value="Payment" style={{ background: '#1a1a2e', color: 'white' }}>Payment</option>
                    <option value="Customer" style={{ background: '#1a1a2e', color: 'white' }}>Customer</option>
                    <option value="Transaction" style={{ background: '#1a1a2e', color: 'white' }}>Transaction</option>
                    <option value="Account" style={{ background: '#1a1a2e', color: 'white' }}>Account</option>
                  </select>
                </div>

                {/* DATA TYPE */}
                <div>
                  <label style={{ display: 'block', color: '#a0a0a0', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                    Data Type
                  </label>
                  <select
                    value={editedValues.data_type}
                    onChange={(e) => setEditedValues({ ...editedValues, data_type: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '0.75rem',
                      background: 'rgba(255, 255, 255, 0.05)',
                      border: '1px solid rgba(255, 255, 255, 0.2)',
                      borderRadius: '8px',
                      color: 'white',
                      fontSize: '0.9rem',
                      cursor: 'pointer'
                    }}
                  >
                    <option value="String" style={{ background: '#1a1a2e', color: 'white' }}>String</option>
                    <option value="Number" style={{ background: '#1a1a2e', color: 'white' }}>Number</option>
                    <option value="Date" style={{ background: '#1a1a2e', color: 'white' }}>Date</option>
                    <option value="Boolean" style={{ background: '#1a1a2e', color: 'white' }}>Boolean</option>
                    <option value="Array" style={{ background: '#1a1a2e', color: 'white' }}>Array</option>
                    <option value="Object" style={{ background: '#1a1a2e', color: 'white' }}>Object</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem' }}>
            <button
              onClick={handleSaveEdit}
              style={{
                flex: 1,
                padding: '0.75rem',
                background: 'linear-gradient(135deg, #48bb78 0%, #38a169 100%)',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontSize: '0.9rem',
                fontWeight: '600',
                cursor: 'pointer'
              }}
            >
              💾 Save & Learn
            </button>
            <button
              onClick={() => setEditMode(false)}
              style={{
                padding: '0.75rem 1.5rem',
                background: 'rgba(255, 255, 255, 0.1)',
                color: 'white',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                borderRadius: '8px',
                fontSize: '0.9rem',
                fontWeight: '600',
                cursor: 'pointer'
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        /* VIEW MODE */
        <div
          key="view-mode"
          style={{
            padding: '1.5rem',
            background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
            borderRadius: '12px',
            border: '1px solid rgba(255,255,255,0.1)'
          }}
        >
          {/* Header avec badges */}
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div
              style={{
                background: sourceBadge.color + '40',
                padding: '6px 12px',
                borderRadius: '20px',
                fontSize: '13px',
                fontWeight: '600',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                color: sourceBadge.color
              }}
            >
              <span>{sourceBadge.emoji}</span>
              <span>{sourceBadge.text}</span>
            </div>

            <div
              style={{
                background: confidence >= 70 ? 'rgba(16, 185, 129, 0.2)' : confidence >= 50 ? 'rgba(251, 191, 36, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                border: `1px solid ${confidence >= 70 ? 'rgba(16, 185, 129, 0.5)' : confidence >= 50 ? 'rgba(251, 191, 36, 0.5)' : 'rgba(239, 68, 68, 0.5)'}`,
                padding: '6px 12px',
                borderRadius: '20px',
                fontSize: '13px',
                fontWeight: '600',
                color: confidence >= 70 ? '#6ee7b7' : confidence >= 50 ? '#fcd34d' : '#fca5a5'
              }}
            >
              ⚡ {confidence}%
            </div>
          </div>

          {/* 1. SOURCE */}
          <div style={{ marginBottom: '12px' }}>
            <div style={{ fontSize: '11px', color: '#9ca3af', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Source
            </div>
            <div style={{ fontSize: '15px', color: '#e5e7eb', fontWeight: '500' }}>
              {columnName}
            </div>
          </div>

          {/* 2. TARGET */}
          <div style={{ marginBottom: '12px' }}>
            <div style={{ fontSize: '11px', color: '#9ca3af', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Target
            </div>
            <div style={{
              fontSize: '14px',
              color: '#60a5fa',
              fontFamily: 'monospace',
              background: 'rgba(59, 130, 246, 0.1)',
              padding: '4px 8px',
              borderRadius: '4px',
              display: 'inline-block'
            }}>
              {currentSuggestion.target_path || currentSuggestion.target || 'N/A'}
            </div>
          </div>

          {/* 3. ELEMENT ID */}
          <div style={{ marginBottom: '12px' }}>
            <div style={{ fontSize: '11px', color: '#9ca3af', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Element ID
            </div>
            <div style={{ fontSize: '13px', color: '#a78bfa', fontFamily: 'monospace' }}>
              {currentSuggestion.element_id || 'N/A'}
            </div>
          </div>



          {/* 5. RELATED DETAILS */}
          <div style={{
            background: 'rgba(255,255,255,0.05)',
            padding: '12px',
            borderRadius: '8px',
            marginBottom: '16px'
          }}>
            <div style={{
              fontSize: '11px',
              color: '#9ca3af',
              marginBottom: '8px',
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
              fontWeight: '600'
            }}>
              Related Details
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <div>
                <div style={{ fontSize: '10px', color: '#6b7280', marginBottom: '2px' }}>Transformation</div>
                <div style={{ fontSize: '12px', color: '#d1d5db' }}>
                  {currentSuggestion.full_suggestion?.transformation || 'DIRECT_COPY'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '10px', color: '#6b7280', marginBottom: '2px' }}>Criticality</div>
                <div style={{ fontSize: '12px', color: '#d1d5db' }}>
                  {currentSuggestion.full_suggestion?.criticality || 'MEDIUM'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '10px', color: '#6b7280', marginBottom: '2px' }}>Category</div>
                <div style={{ fontSize: '12px', color: '#d1d5db' }}>
                  {currentSuggestion.category || 'Financial'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '10px', color: '#6b7280', marginBottom: '2px' }}>Data Type</div>
                <div style={{ fontSize: '12px', color: '#d1d5db' }}>
                  {currentSuggestion.full_suggestion?.data_type || 'String'}
                </div>
              </div>
            </div>

            {/* ── NOUVEAU : flags enrichis ────────────────────────────────── */}
            {(currentSuggestion.has_audit_requirement || currentSuggestion.has_compliance_requirement || currentSuggestion.has_migration_note || currentSuggestion.performance_impact) && (
              <div style={{ marginTop: '10px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {currentSuggestion.has_audit_requirement && (
                  <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '600', background: 'rgba(245,158,11,0.2)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)' }}>
                    📋 Audit
                  </span>
                )}
                {currentSuggestion.has_compliance_requirement && (
                  <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '600', background: 'rgba(59,130,246,0.2)', color: '#3b82f6', border: '1px solid rgba(59,130,246,0.3)' }}>
                    ⚖️ Compliance
                  </span>
                )}
                {currentSuggestion.has_migration_note && (
                  <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '600', background: 'rgba(6,182,212,0.2)', color: '#06b6d4', border: '1px solid rgba(6,182,212,0.3)' }}>
                    🚀 Migration Note
                  </span>
                )}
                {currentSuggestion.performance_impact && (
                  <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '600', background: 'rgba(139,92,246,0.2)', color: '#8b5cf6', border: '1px solid rgba(139,92,246,0.3)' }}>
                    ⚡ {currentSuggestion.performance_impact}
                  </span>
                )}
              </div>
            )}
            {/* ── FIN flags enrichis ─────────────────────────────────────── */}
          </div>

          {/* ── NOUVEAU : Section Compliance & Risk depuis Qdrant ──────────── */}
          {hasRagEnrichment && (
            <div style={{
              background: 'rgba(6, 182, 212, 0.05)',
              border: '1px solid rgba(6, 182, 212, 0.2)',
              borderRadius: '10px',
              padding: '14px',
              marginBottom: '16px'
            }}>
              <div style={{
                fontSize: '11px',
                color: '#06b6d4',
                marginBottom: '10px',
                fontWeight: '700',
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}>
                ✨ Compliance & Risk — from RAG
                {currentSuggestion.rag_mapping_name && (
                  <span style={{ color: '#9ca3af', fontWeight: '400', textTransform: 'none', letterSpacing: 0, fontSize: '10px' }}>
                    ({currentSuggestion.rag_mapping_name} · {Math.round((currentSuggestion.rag_similarity_score || 0) * 100)}% match)
                  </span>
                )}
              </div>

              {/* ── Toggle button ──────────────────────────────────────── */}
              <button
                onClick={() => setShowComplianceDetails(!showComplianceDetails)}
                style={{
                  background: 'none',
                  border: '1px solid rgba(6, 182, 212, 0.3)',
                  color: '#06b6d4',
                  borderRadius: '6px',
                  padding: '4px 12px',
                  fontSize: '11px',
                  cursor: 'pointer',
                  marginBottom: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                {showComplianceDetails ? '▲ Hide details' : '▼ Show details'}
              </button>

              {showComplianceDetails && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>

                {/* ── Mapping Formula (objet imbriqué) ──────────────────────── */}
                {ragPseudocode && (
                  <div>
                    <div style={{ fontSize: '10px', color: '#667eea', fontWeight: '600', marginBottom: '4px' }}>
                      🧮 MAPPING FORMULA (PSEUDOCODE)
                    </div>
                    <div style={{
                      fontSize: '11px', color: '#a5f3fc', fontFamily: 'monospace', lineHeight: '1.7',
                      whiteSpace: 'pre-wrap', background: 'rgba(0,0,0,0.3)', borderRadius: '6px',
                      padding: '8px 12px', borderLeft: '3px solid #667eea',
                      maxHeight: showFullFormula ? 'none' : '100px', overflow: 'hidden'
                    }}>
                      {ragPseudocode}
                    </div>
                    {ragPseudocode.length > 150 && (
                      <button onClick={() => setShowFullFormula(!showFullFormula)}
                        style={{ background: 'none', border: 'none', color: '#667eea', fontSize: '11px', cursor: 'pointer', padding: '2px 0', marginTop: '2px' }}>
                        {showFullFormula ? '▲ Show less' : '▼ Show full formula'}
                      </button>
                    )}
                    {ragExpression && (
                      <div style={{ marginTop: '6px', fontSize: '11px', color: '#9ca3af', fontFamily: 'monospace', padding: '4px 8px', background: 'rgba(255,255,255,0.03)', borderRadius: '4px' }}>
                        <span style={{ color: '#667eea', fontWeight: '600' }}>expr: </span>{ragExpression}
                      </div>
                    )}
                    {ragGlobalVars && Object.keys(ragGlobalVars).length > 0 && (
                      <div style={{ marginTop: '6px' }}>
                        <div style={{ fontSize: '10px', color: '#f97316', fontWeight: '600', marginBottom: '3px' }}>⚙️ GLOBAL VARIABLES</div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                          {Object.entries(ragGlobalVars).map(([name, value]) => (
                            <span key={name} style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '10px', background: 'rgba(249,115,22,0.15)', color: '#fb923c', border: '1px solid rgba(249,115,22,0.3)', fontFamily: 'monospace' }}>
                              {name}{value ? `=${value}` : ''}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {ragConditions && Object.keys(ragConditions).length > 0 && (
                      <div style={{ marginTop: '6px' }}>
                        <div style={{ fontSize: '10px', color: '#06b6d4', fontWeight: '600', marginBottom: '3px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                          onClick={() => setShowConditions(!showConditions)}>
                          🔀 CONDITIONS ({Object.keys(ragConditions).length}) {showConditions ? '▲' : '▼'}
                        </div>
                        {showConditions && (
                          <div style={{ background: 'rgba(6,182,212,0.05)', borderRadius: '6px', padding: '6px 8px', border: '1px solid rgba(6,182,212,0.2)' }}>
                            {Object.entries(ragConditions).map(([key, expr]) => (
                              <div key={key} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', padding: '3px 0', fontSize: '10px', fontFamily: 'monospace', borderBottom: '1px solid rgba(6,182,212,0.08)' }}>
                                <span style={{ color: '#06b6d4', minWidth: '80px', flexShrink: 0 }}>{key}:</span>
                                <span style={{ color: '#e2e8f0', wordBreak: 'break-word', lineHeight: '1.5' }}>{expr}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
                {/* ── FIN Mapping Formula ────────────────────────────────────── */}

                {currentSuggestion.audit_requirement && (
                  <EnrichedField
                    icon="📋"
                    label="AUDIT REQUIREMENT"
                    value={currentSuggestion.audit_requirement}
                    color="#f59e0b"
                    borderColor="rgba(245,158,11,0.4)"
                  />
                )}

                {currentSuggestion.compliance_requirement && (
                  <EnrichedField
                    icon="⚖️"
                    label="COMPLIANCE REQUIREMENT"
                    value={currentSuggestion.compliance_requirement}
                    color="#3b82f6"
                    borderColor="rgba(59,130,246,0.4)"
                  />
                )}

                {currentSuggestion.data_privacy && (
                  <EnrichedField
                    icon="🔒"
                    label="DATA PRIVACY (GDPR)"
                    value={currentSuggestion.data_privacy}
                    color="#8b5cf6"
                    borderColor="rgba(139,92,246,0.4)"
                  />
                )}

                {currentSuggestion.migration_note && (
                  <EnrichedField
                    icon="🚀"
                    label="MIGRATION NOTE"
                    value={currentSuggestion.migration_note}
                    color="#06b6d4"
                    borderColor="rgba(6,182,212,0.4)"
                  />
                )}

                {currentSuggestion.caching_strategy && (
                  <EnrichedField
                    icon="💾"
                    label="CACHING STRATEGY"
                    value={currentSuggestion.caching_strategy}
                    color="#10b981"
                    borderColor="rgba(16,185,129,0.4)"
                  />
                )}

                {currentSuggestion.global_variable_refs && currentSuggestion.global_variable_refs.length > 0 && (
                  <div>
                    <div style={{ fontSize: '10px', color: '#f97316', fontWeight: '600', marginBottom: '4px' }}>
                      ⚙️ GLOBAL VARIABLES USED
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {currentSuggestion.global_variable_refs.map(v => (
                        <span key={v} style={{
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '11px',
                          background: 'rgba(249,115,22,0.15)',
                          color: '#fb923c',
                          border: '1px solid rgba(249,115,22,0.3)',
                          fontFamily: 'monospace'
                        }}>
                          {v}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

              </div>
              )} {/* end showComplianceDetails */}
            </div>
          )}
          {/* ── FIN Section Compliance & Risk ─────────────────────────────── */}

          {/* ── NOUVEAU : Section Web Enrichment ──────────────────────────── */}
          {currentSuggestion.web_search_performed && (
            <div style={{
              background: currentSuggestion.web_enrichment && currentSuggestion.web_enrichment.length > 0
                ? 'rgba(34, 197, 94, 0.05)'
                : 'rgba(239, 68, 68, 0.05)',
              border: `1px solid ${currentSuggestion.web_enrichment && currentSuggestion.web_enrichment.length > 0
                ? 'rgba(34, 197, 94, 0.2)'
                : 'rgba(239, 68, 68, 0.2)'}`,
              borderRadius: '10px',
              padding: '12px 14px',
              marginBottom: '16px'
            }}>
              <div style={{
                fontSize: '11px',
                fontWeight: '700',
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
                marginBottom: '8px',
                color: currentSuggestion.web_enrichment && currentSuggestion.web_enrichment.length > 0
                  ? '#22c55e' : '#ef4444'
              }}>
                🌐 Web Search
                {currentSuggestion.web_enrichment && currentSuggestion.web_enrichment.length > 0
                  ? ` — ${currentSuggestion.web_enrichment.length} result(s) found`
                  : ' — No results found'}
              </div>

              {currentSuggestion.web_enrichment && currentSuggestion.web_enrichment.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {currentSuggestion.web_enrichment.map((result, i) => (
                    <div key={i} style={{
                      background: 'rgba(0,0,0,0.2)',
                      borderRadius: '6px',
                      padding: '8px 10px',
                      borderLeft: '3px solid rgba(34,197,94,0.4)'
                    }}>
                      <div style={{ fontSize: '11px', color: '#22c55e', fontWeight: '600', marginBottom: '3px' }}>
                        📌 {result.source || 'Web'}
                        {result.url && (
                          <a href={result.url} target="_blank" rel="noopener noreferrer"
                            style={{ color: '#60a5fa', marginLeft: '8px', fontSize: '10px' }}>
                            🔗 link
                          </a>
                        )}
                      </div>
                      <div style={{ fontSize: '11px', color: '#e2e8f0', lineHeight: '1.5' }}>
                        {result.snippet}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: '11px', color: '#9ca3af', fontStyle: 'italic' }}>
                  No relevant information found on the web for this field.
                </div>
              )}
            </div>
          )}
          {/* ── FIN Web Enrichment ─────────────────────────────────────────── */}

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              onClick={() => handleApply()}
              style={{
                flex: 1,
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                color: 'white',
                padding: '12px',
                borderRadius: '8px',
                border: 'none',
                fontSize: '14px',
                fontWeight: '600',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                transition: 'transform 0.2s'
              }}
              onMouseEnter={(e) => e.target.style.transform = 'scale(1.02)'}
              onMouseLeave={(e) => e.target.style.transform = 'scale(1)'}
            >
              ✅ Accept
            </button>

            <button
              onClick={handleEdit}
              style={{
                flex: 1,
                background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
                color: 'white',
                padding: '12px',
                borderRadius: '8px',
                border: 'none',
                fontSize: '14px',
                fontWeight: '600',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                transition: 'transform 0.2s'
              }}
              onMouseEnter={(e) => e.target.style.transform = 'scale(1.02)'}
              onMouseLeave={(e) => e.target.style.transform = 'scale(1)'}
            >
              ✏️ Edit
            </button>

            <button
              onClick={handleReject}
              style={{
                flex: 1,
                background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
                color: 'white',
                padding: '12px',
                borderRadius: '8px',
                border: 'none',
                fontSize: '14px',
                fontWeight: '600',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                transition: 'transform 0.2s'
              }}
              onMouseEnter={(e) => e.target.style.transform = 'scale(1.02)'}
              onMouseLeave={(e) => e.target.style.transform = 'scale(1)'}
            >
              ❌ Reject
            </button>
          </div>
        </div>
      )}
    </Card>
  );
};

// ── NOUVEAU : composant réutilisable pour chaque champ enrichi ─────────────────
const EnrichedField = ({ icon, label, value, color, borderColor }) => (
  <div>
    <div style={{ fontSize: '10px', color, fontWeight: '600', marginBottom: '3px' }}>
      {icon} {label}
    </div>
    <div style={{
      fontSize: '12px',
      color: '#e2e8f0',
      lineHeight: '1.5',
      background: 'rgba(0,0,0,0.2)',
      borderRadius: '6px',
      padding: '6px 10px',
      borderLeft: `3px solid ${borderColor}`
    }}>
      {value}
    </div>
  </div>
);
// ── FIN NOUVEAU ────────────────────────────────────────────────────────────────

// Card Component
const Card = ({ children, style }) => (
  <div
    style={{
      background: 'rgba(255, 255, 255, 0.05)',
      backdropFilter: 'blur(10px)',
      borderRadius: '20px',
      padding: '2rem',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
      transition: 'transform 0.3s ease',
      ...style
    }}
    onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-5px)'}
    onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
  >
    {children}
  </div>
);

// Inject CSS animation
if (typeof document !== 'undefined') {
  const styleSheet = document.createElement('style');
  styleSheet.textContent = `
    @keyframes fadeIn {
      from {
        opacity: 0;
      }
      to {
        opacity: 1;
      }
    }
  `;
  if (!document.querySelector('style[data-suggestion-card]')) {
    styleSheet.setAttribute('data-suggestion-card', 'true');
    document.head.appendChild(styleSheet);
  }
}

export default SuggestionCard;