import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Copy, Check } from 'lucide-react';

const RAGResultCard = ({ result, rank }) => {
  const { chunk_id, content, metadata, similarity_score } = result;
  const [copied, setCopied] = useState(false);
  const [showFullContent, setShowFullContent] = useState(false);
  const [showFullFormula, setShowFullFormula] = useState(false);

  const handleCopyId = () => {
    navigator.clipboard.writeText(chunk_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // ── Helper : extraire depuis mapping_formula (objet ou string) ────────────
  const getMappingFormula = (mf) => {
    if (!mf) return null;
    if (typeof mf === 'string') return mf;
    if (typeof mf === 'object') return mf.pseudocode || mf.expression || null;
    return null;
  };

  const getExpression = (mf) => {
    if (!mf) return null;
    if (typeof mf === 'object') return mf.expression || null;
    return null;
  };

  const getGlobalVars = (mf) => {
    if (!mf || typeof mf !== 'object') return null;
    return mf.details?.global_variables || null;
  };

  const getConditions = (mf) => {
    if (!mf || typeof mf !== 'object') return null;
    return mf.details?.conditions || null;
  };

  const formulaPseudocode = getMappingFormula(metadata?.mapping_formula);
  const formulaExpression = getExpression(metadata?.mapping_formula);
  const formulaGlobalVars = getGlobalVars(metadata?.mapping_formula);
  const formulaConditions = getConditions(metadata?.mapping_formula);
  // ── FIN Helper ────────────────────────────────────────────────────────────

  const styles = {
    card: {
      background: 'rgba(255, 255, 255, 0.05)',
      backdropFilter: 'blur(10px)',
      borderRadius: '12px',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      overflow: 'hidden',
      transition: 'all 0.3s ease'
    },
    cardHover: {
      boxShadow: '0 8px 32px rgba(102, 126, 234, 0.2)',
      transform: 'translateY(-2px)'
    },
    header: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '1.5rem',
      background: 'rgba(0, 0, 0, 0.2)',
      borderBottom: '1px solid rgba(255, 255, 255, 0.1)'
    },
    leftHeader: {
      display: 'flex',
      alignItems: 'center',
      gap: '1rem',
      flex: 1
    },
    rank: {
      fontSize: '1.5rem',
      fontWeight: 'bold',
      color: '#667eea',
      minWidth: '40px'
    },
    titleContainer: {
      flex: 1
    },
    title: {
      fontSize: '1.125rem',
      fontWeight: '600',
      color: 'white',
      marginBottom: '0.25rem'
    },
    chunkIdContainer: {
      display: 'flex',
      alignItems: 'center',
      gap: '0.5rem'
    },
    chunkId: {
      fontSize: '0.8rem',
      color: '#888',
      fontFamily: 'monospace'
    },
    copyButton: {
      background: 'rgba(255, 255, 255, 0.1)',
      border: '1px solid rgba(255, 255, 255, 0.2)',
      borderRadius: '4px',
      padding: '0.25rem 0.5rem',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      gap: '0.25rem',
      fontSize: '0.75rem',
      color: '#888',
      transition: 'all 0.2s'
    },
    scoreBadge: {
      padding: '0.5rem 1rem',
      borderRadius: '6px',
      fontSize: '0.875rem',
      fontWeight: '600',
      background: 'rgba(102, 126, 234, 0.2)',
      color: '#667eea',
      border: '1px solid rgba(102, 126, 234, 0.3)'
    },
    section: {
      padding: '1.5rem'
    },
    sectionTitle: {
      fontSize: '0.875rem',
      fontWeight: '600',
      color: '#a0a0a0',
      marginBottom: '1rem',
      display: 'flex',
      alignItems: 'center',
      gap: '0.5rem'
    },
    payloadGrid: {
      display: 'grid',
      gridTemplateColumns: '200px 1fr',
      gap: '0.75rem',
      fontSize: '0.875rem'
    },
    payloadKey: {
      color: '#888',
      fontFamily: 'monospace',
      display: 'flex',
      alignItems: 'flex-start',
      gap: '0.5rem',
      paddingTop: '0.1rem'
    },
    payloadValue: {
      color: 'white',
      fontFamily: 'monospace',
      wordBreak: 'break-word'
    },
    sourceField: {
      color: '#3b82f6',
      fontWeight: 'bold',
      fontSize: '0.95rem'
    },
    targetField: {
      color: '#22c55e',
      fontWeight: 'bold',
      fontSize: '0.95rem'
    },
    enrichedValue: {
      color: '#e2e8f0',
      fontSize: '0.85rem',
      lineHeight: '1.5',
      wordBreak: 'break-word',
      background: 'rgba(0,0,0,0.2)',
      borderRadius: '6px',
      padding: '0.5rem 0.75rem',
      borderLeft: '3px solid'
    },
    auditStyle: { borderLeftColor: '#f59e0b' },
    complianceStyle: { borderLeftColor: '#3b82f6' },
    privacyStyle: { borderLeftColor: '#8b5cf6' },
    migrationStyle: { borderLeftColor: '#06b6d4' },
    cachingStyle: { borderLeftColor: '#10b981' },
    globalVarsStyle: { borderLeftColor: '#f97316' },
    globalVarsContainer: {
      background: 'rgba(249, 115, 22, 0.08)',
      borderRadius: '8px',
      padding: '1rem',
      border: '1px solid rgba(249, 115, 22, 0.2)'
    },
    globalVarItem: {
      display: 'flex',
      alignItems: 'center',
      gap: '0.5rem',
      padding: '0.3rem 0',
      fontSize: '0.8rem',
      color: '#fbd38d',
      fontFamily: 'monospace'
    },
    flagBadge: {
      padding: '0.15rem 0.5rem',
      borderRadius: '4px',
      fontSize: '0.7rem',
      fontWeight: '600',
      background: 'rgba(34, 197, 94, 0.2)',
      color: '#22c55e',
      border: '1px solid rgba(34, 197, 94, 0.3)'
    },
    formulaBox: {
      background: 'rgba(0, 0, 0, 0.4)',
      borderRadius: '8px',
      padding: '1rem',
      fontSize: '0.8rem',
      color: '#a5f3fc',
      fontFamily: 'monospace',
      lineHeight: '1.7',
      whiteSpace: 'pre-wrap',
      overflow: 'auto',
      border: '1px solid rgba(102, 126, 234, 0.2)',
      borderLeft: '3px solid #667eea'
    },
    contentBox: {
      background: 'rgba(0, 0, 0, 0.3)',
      borderRadius: '8px',
      padding: '1rem',
      fontSize: '0.875rem',
      color: '#ddd',
      fontFamily: 'monospace',
      lineHeight: '1.6',
      whiteSpace: 'pre-wrap',
      maxHeight: '200px',
      overflow: 'auto'
    },
    vectorInfo: {
      display: 'flex',
      alignItems: 'center',
      gap: '1rem',
      fontSize: '0.875rem',
      color: '#888',
      fontFamily: 'monospace'
    },
    badge: {
      padding: '0.25rem 0.5rem',
      borderRadius: '4px',
      fontSize: '0.75rem',
      fontWeight: '500',
      background: 'rgba(102, 126, 234, 0.2)',
      color: '#667eea',
      border: '1px solid rgba(102, 126, 234, 0.3)'
    },
    divider: {
      height: '1px',
      background: 'rgba(255, 255, 255, 0.1)',
      margin: '0'
    },
    icon: {
      fontSize: '0.875rem'
    },
    showMoreBtn: {
      background: 'none',
      border: '1px solid rgba(255,255,255,0.2)',
      color: '#a0a0a0',
      borderRadius: '6px',
      padding: '0.3rem 0.75rem',
      fontSize: '0.75rem',
      cursor: 'pointer',
      marginTop: '0.5rem'
    }
  };

  const getScoreColor = (score) => {
    if (score > 0.8) return { background: 'rgba(34, 197, 94, 0.2)', color: '#22c55e', border: '1px solid rgba(34, 197, 94, 0.3)' };
    if (score > 0.6) return { background: 'rgba(234, 179, 8, 0.2)', color: '#eab308', border: '1px solid rgba(234, 179, 8, 0.3)' };
    return { background: 'rgba(156, 163, 175, 0.2)', color: '#9ca3af', border: '1px solid rgba(156, 163, 175, 0.3)' };
  };

  const getCriticalityStyle = (criticality) => {
    if (criticality === 'HIGH' || criticality === 'CRITICAL') return { color: '#ef4444', fontWeight: 'bold' };
    if (criticality === 'MEDIUM') return { color: '#f97316', fontWeight: 'bold' };
    return { color: '#22c55e', fontWeight: 'bold' };
  };

  const [isHovered, setIsHovered] = useState(false);
  const [isCopyHovered, setIsCopyHovered] = useState(false);

  const isGlobalVars = metadata?.chunk_type === 'GLOBAL_VARIABLES';

  const extractSection = (text, label) => {
    const start = text.indexOf(label);
    if (start === -1) return null;
    const valueStart = start + label.length + 1;
    const nextSection = text.indexOf('\n\n', valueStart);
    return text.substring(valueStart, nextSection === -1 ? undefined : nextSection).trim();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: rank * 0.05 }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        ...styles.card,
        ...(isHovered ? styles.cardHover : {})
      }}
    >
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.leftHeader}>
          <span style={styles.rank}>#{rank}</span>
          <div style={styles.titleContainer}>
            <h3 style={styles.title}>
              {isGlobalVars ? '⚙️ ' : ''}
              {metadata?.mapping_name || 'Mapping Result'}
            </h3>
            <div style={styles.chunkIdContainer}>
              <p style={styles.chunkId}>{chunk_id}</p>
              <button
                onClick={handleCopyId}
                onMouseEnter={() => setIsCopyHovered(true)}
                onMouseLeave={() => setIsCopyHovered(false)}
                style={{
                  ...styles.copyButton,
                  ...(isCopyHovered ? { background: 'rgba(255,255,255,0.2)', color: '#22c55e' } : {})
                }}
              >
                {copied ? (
                  <><Check size={12} /><span>Copied!</span></>
                ) : (
                  <><Copy size={12} /><span>Copy</span></>
                )}
              </button>
            </div>
          </div>
        </div>
        <span style={{ ...styles.scoreBadge, ...getScoreColor(similarity_score) }}>
          Score: {(similarity_score * 100).toFixed(1)}%
        </span>
      </div>

      {/* Payload Section */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <span style={styles.icon}>📋</span> Payload:
        </div>
        <div style={styles.payloadGrid}>
          <div style={styles.payloadKey}><span style={styles.icon}>🆔</span> chunk_id</div>
          <div style={styles.payloadValue}>{chunk_id}</div>

          {metadata?.chunk_type && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>📦</span> chunk_type</div>
              <div style={styles.payloadValue}>{metadata.chunk_type}</div>
            </>
          )}

          {metadata?.field_id && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>🔢</span> field_id</div>
              <div style={styles.payloadValue}>{metadata.field_id}</div>
            </>
          )}

          {/* ── source / target (nouveau format) ─────────────────────────── */}
          {metadata?.source && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>📤</span> source</div>
              <div style={{ ...styles.payloadValue, ...styles.sourceField }}>{metadata.source}</div>
            </>
          )}

          {metadata?.target && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>📥</span> target</div>
              <div style={{ ...styles.payloadValue, ...styles.targetField }}>{metadata.target}</div>
            </>
          )}

          {metadata?.element_id && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>🔑</span> element_id</div>
              <div style={styles.payloadValue}>{metadata.element_id}</div>
            </>
          )}

          {metadata?.field_name && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>🏷️</span> field_name</div>
              <div style={styles.payloadValue}>{metadata.field_name}</div>
            </>
          )}

          {metadata?.field_tag && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>🔖</span> field_tag</div>
              <div style={styles.payloadValue}>{metadata.field_tag}</div>
            </>
          )}

          {metadata?.mapping_id && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>🗺️</span> mapping_id</div>
              <div style={styles.payloadValue}>{metadata.mapping_id}</div>
            </>
          )}

          {metadata?.mapping_name && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>📝</span> mapping_name</div>
              <div style={styles.payloadValue}>{metadata.mapping_name}</div>
            </>
          )}

          {metadata?.message_type && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>💬</span> message_type</div>
              <div style={styles.payloadValue}>{metadata.message_type}</div>
            </>
          )}

          {metadata?.side && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>↔️</span> side</div>
              <div style={styles.payloadValue}>{metadata.side}</div>
            </>
          )}

          {metadata?.criticality && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>⚠️</span> criticality</div>
              <div style={{ ...styles.payloadValue, ...getCriticalityStyle(metadata.criticality) }}>
                {metadata.criticality}
              </div>
            </>
          )}

          {metadata?.formula_type && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>🧮</span> formula_type</div>
              <div style={styles.payloadValue}>{metadata.formula_type}</div>
            </>
          )}

          {metadata?.performance_impact && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>⚡</span> performance_impact</div>
              <div style={styles.payloadValue}>{metadata.performance_impact}</div>
            </>
          )}

          {(metadata?.has_audit_requirement || metadata?.has_compliance_requirement || metadata?.has_migration_note) && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>🏷️</span> flags</div>
              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                {metadata.has_audit_requirement && (
                  <span style={{ ...styles.flagBadge, background: 'rgba(245,158,11,0.2)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)' }}>
                    ✓ Audit
                  </span>
                )}
                {metadata.has_compliance_requirement && (
                  <span style={{ ...styles.flagBadge, background: 'rgba(59,130,246,0.2)', color: '#3b82f6', border: '1px solid rgba(59,130,246,0.3)' }}>
                    ✓ Compliance
                  </span>
                )}
                {metadata.has_migration_note && (
                  <span style={{ ...styles.flagBadge, background: 'rgba(6,182,212,0.2)', color: '#06b6d4', border: '1px solid rgba(6,182,212,0.3)' }}>
                    ✓ Migration Note
                  </span>
                )}
              </div>
            </>
          )}

          {metadata?.variables_count && (
            <>
              <div style={styles.payloadKey}><span style={styles.icon}>⚙️</span> variables_count</div>
              <div style={styles.payloadValue}>{metadata.variables_count} variables</div>
            </>
          )}
        </div>
      </div>

      <div style={styles.divider}></div>

      {/* ── Section Mapping Formula (PseudoCode + Expression + Details) ────── */}
      {formulaPseudocode && (
        <>
          <div style={styles.section}>
            <div style={styles.sectionTitle}>
              <span style={styles.icon}>🧮</span> Mapping Formula:
            </div>

            {/* PseudoCode */}
            <div style={{ marginBottom: '0.75rem' }}>
              <div style={{ fontSize: '0.75rem', color: '#667eea', fontWeight: '600', marginBottom: '0.4rem' }}>
                PSEUDOCODE
              </div>
              <div style={{
                ...styles.formulaBox,
                maxHeight: showFullFormula ? 'none' : '180px'
              }}>
                {formulaPseudocode}
              </div>
              {formulaPseudocode.length > 200 && (
                <button
                  onClick={() => setShowFullFormula(!showFullFormula)}
                  style={styles.showMoreBtn}
                >
                  {showFullFormula ? '▲ Show less' : '▼ Show full formula'}
                </button>
              )}
            </div>

            {/* Expression */}
            {formulaExpression && (
              <div style={{
                marginBottom: '0.75rem',
                fontSize: '0.75rem',
                color: '#9ca3af',
                fontFamily: 'monospace',
                padding: '0.5rem 0.75rem',
                background: 'rgba(255,255,255,0.03)',
                borderRadius: '6px',
                border: '1px solid rgba(255,255,255,0.08)'
              }}>
                <span style={{ color: '#667eea', fontWeight: '600' }}>Expression: </span>
                {formulaExpression}
              </div>
            )}

            {/* Global Variables */}
            {formulaGlobalVars && Object.keys(formulaGlobalVars).length > 0 && (
              <div style={{ marginBottom: '0.75rem' }}>
                <div style={{ fontSize: '0.75rem', color: '#f97316', fontWeight: '600', marginBottom: '0.4rem' }}>
                  ⚙️ GLOBAL VARIABLES
                </div>
                <div style={styles.globalVarsContainer}>
                  {Object.entries(formulaGlobalVars).map(([name, value]) => (
                    <div key={name} style={styles.globalVarItem}>
                      <span style={{ color: '#fb923c' }}>{name}</span>
                      {value && <><span style={{ color: '#6b7280' }}>=</span><span style={{ color: '#fde68a' }}>{value}</span></>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Conditions */}
            {formulaConditions && Object.keys(formulaConditions).length > 0 && (
              <div>
                <div style={{ fontSize: '0.75rem', color: '#06b6d4', fontWeight: '600', marginBottom: '0.4rem' }}>
                  🔀 CONDITIONS
                </div>
                <div style={{
                  background: 'rgba(6, 182, 212, 0.05)',
                  borderRadius: '8px',
                  padding: '0.75rem',
                  border: '1px solid rgba(6, 182, 212, 0.2)'
                }}>
                  {Object.entries(formulaConditions).map(([key, expr]) => (
                    <div key={key} style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '0.5rem',
                      padding: '0.35rem 0',
                      fontSize: '0.8rem',
                      fontFamily: 'monospace',
                      borderBottom: '1px solid rgba(6,182,212,0.08)'
                    }}>
                      <span style={{ color: '#06b6d4', minWidth: '90px', flexShrink: 0 }}>{key}:</span>
                      <span style={{ color: '#e2e8f0', wordBreak: 'break-word', lineHeight: '1.5' }}>
                        {expr}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          <div style={styles.divider}></div>
        </>
      )}
      {/* ── FIN Section Mapping Formula ──────────────────────────────────────── */}

      {/* Enriched Information Section */}
      {metadata?.chunk_type && content && (() => {
        const hasAudit = content.includes('Audit Requirement:');
        const hasCompliance = content.includes('Compliance Requirement:');
        const hasPrivacy = content.includes('Data Privacy (GDPR):');
        const hasMigration = content.includes('Migration Note:');
        const hasCaching = content.includes('Caching Strategy:');

        if (!hasAudit && !hasCompliance && !hasPrivacy && !hasMigration && !hasCaching) return null;

        return (
          <>
            <div style={styles.section}>
              <div style={styles.sectionTitle}>
                <span style={styles.icon}>🔍</span> Enriched Information:
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>

                {hasAudit && (
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#f59e0b', fontWeight: '600', marginBottom: '0.3rem' }}>
                      📋 AUDIT REQUIREMENT
                    </div>
                    <div style={{ ...styles.enrichedValue, ...styles.auditStyle }}>
                      {extractSection(content, 'Audit Requirement:')}
                    </div>
                  </div>
                )}

                {hasCompliance && (
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#3b82f6', fontWeight: '600', marginBottom: '0.3rem' }}>
                      ⚖️ COMPLIANCE REQUIREMENT
                    </div>
                    <div style={{ ...styles.enrichedValue, ...styles.complianceStyle }}>
                      {extractSection(content, 'Compliance Requirement:')}
                    </div>
                  </div>
                )}

                {hasPrivacy && (
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#8b5cf6', fontWeight: '600', marginBottom: '0.3rem' }}>
                      🔒 DATA PRIVACY (GDPR)
                    </div>
                    <div style={{ ...styles.enrichedValue, ...styles.privacyStyle }}>
                      {extractSection(content, 'Data Privacy (GDPR):')}
                    </div>
                  </div>
                )}

                {hasMigration && (
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#06b6d4', fontWeight: '600', marginBottom: '0.3rem' }}>
                      🚀 MIGRATION NOTE
                    </div>
                    <div style={{ ...styles.enrichedValue, ...styles.migrationStyle }}>
                      {extractSection(content, 'Migration Note:')}
                    </div>
                  </div>
                )}

                {hasCaching && (
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: '600', marginBottom: '0.3rem' }}>
                      💾 CACHING STRATEGY
                    </div>
                    <div style={{ ...styles.enrichedValue, ...styles.cachingStyle }}>
                      {extractSection(content, 'Caching Strategy:')}
                    </div>
                  </div>
                )}

              </div>
            </div>
            <div style={styles.divider}></div>
          </>
        );
      })()}

      {/* Content Section */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <span style={styles.icon}>📄</span> Content:
        </div>
        <div style={styles.contentBox}>
          {showFullContent
            ? content
            : content.length > 500 ? content.substring(0, 500) + '...' : content
          }
        </div>
        {content.length > 500 && (
          <button
            onClick={() => setShowFullContent(!showFullContent)}
            style={styles.showMoreBtn}
          >
            {showFullContent ? '▲ Show less' : '▼ Show full content'}
          </button>
        )}
      </div>

      <div style={styles.divider}></div>

      {/* Vectors Section */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <span style={styles.icon}>📊</span> Vectors:
        </div>
        <div style={styles.vectorInfo}>
          <span>Default vector</span>
          <span style={styles.badge}>Length: 768</span>
        </div>
      </div>
    </motion.div>
  );
};

export default RAGResultCard;