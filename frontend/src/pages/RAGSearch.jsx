import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import ragService from '../services/ragService';
import RAGResultCard from '../components/RAGResultCard';
import Layout from '../components/Layout';

const RAGSearch = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [filters, setFilters] = useState({
    chunk_type: '',
    mapping_id: '',
    n_results: 5
  });

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const data = await ragService.getStats();
      setStats(data.stats);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    
    if (!query.trim()) return;

    setLoading(true);
    try {
      const data = await ragService.query(query, {
        n_results: filters.n_results,
        filter_chunk_type: filters.chunk_type || null,
        filter_mapping_id: filters.mapping_id || null
      });

      setResults(data.results || []);
    } catch (error) {
      console.error('Search failed:', error);
      alert('Search failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setFilters({ chunk_type: '', mapping_id: '', n_results: 5 });
    setResults([]);
    setQuery('');
  };

  // ── MODIFIÉ : ajout de GLOBAL_VARIABLES ──────────────────────────────────
  const chunkTypes = [
    { value: '', label: 'All Types' },
    { value: 'FIELD_MAPPING', label: 'Field Mapping' },
    { value: 'SOURCE_FIELD', label: 'Source Field' },
    { value: 'TARGET_FIELD', label: 'Target Field' },
    { value: 'GENERAL_INFO', label: 'General Info' },
    { value: 'USE_CASE', label: 'Use Case' },
    { value: 'GLOBAL_VARIABLES', label: 'Global Variables' },  // ← NOUVEAU
  ];
  // ── FIN MODIFIÉ ───────────────────────────────────────────────────────────

  const styles = {
    container: {
      minHeight: 'calc(100vh - 100px)',
      padding: '2rem'
    },
    header: {
      marginBottom: '2rem'
    },
    title: {
      fontSize: '2rem',
      fontWeight: 'bold',
      color: 'white',
      marginBottom: '0.5rem'
    },
    subtitle: {
      color: '#a0a0a0',
      fontSize: '1rem'
    },
    statsBar: {
      background: 'rgba(255, 255, 255, 0.05)',
      backdropFilter: 'blur(10px)',
      borderRadius: '12px',
      padding: '1.5rem',
      marginBottom: '2rem',
      border: '1px solid rgba(255, 255, 255, 0.1)'
    },
    statItem: {
      display: 'inline-block',
      marginRight: '3rem'
    },
    statLabel: {
      fontSize: '0.875rem',
      color: '#a0a0a0',
      marginBottom: '0.25rem'
    },
    statValue: {
      fontSize: '1.5rem',
      fontWeight: 'bold',
      color: '#667eea'
    },
    searchForm: {
      background: 'rgba(255, 255, 255, 0.05)',
      backdropFilter: 'blur(10px)',
      borderRadius: '12px',
      padding: '2rem',
      marginBottom: '2rem',
      border: '1px solid rgba(255, 255, 255, 0.1)'
    },
    inputGroup: {
      marginBottom: '1.5rem'
    },
    label: {
      display: 'block',
      fontSize: '0.875rem',
      fontWeight: '500',
      color: 'white',
      marginBottom: '0.5rem'
    },
    searchContainer: {
      display: 'flex',
      gap: '0.75rem'
    },
    input: {
      flex: 1,
      padding: '0.875rem 1rem',
      background: 'rgba(255, 255, 255, 0.08)',
      border: '1px solid rgba(255, 255, 255, 0.2)',
      borderRadius: '8px',
      color: 'white',
      fontSize: '1rem',
      outline: 'none'
    },
    button: {
      padding: '0.875rem 2rem',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      color: 'white',
      border: 'none',
      borderRadius: '8px',
      fontWeight: '600',
      cursor: 'pointer',
      fontSize: '1rem',
      transition: 'transform 0.2s'
    },
    buttonDisabled: {
      background: '#444',
      cursor: 'not-allowed'
    },
    filtersGrid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(3, 1fr)',
      gap: '1rem'
    },
    select: {
      width: '100%',
      padding: '0.75rem',
      background: '#2a2a3e',
      border: '1px solid rgba(255, 255, 255, 0.3)',
      borderRadius: '8px',
      color: 'white',
      fontSize: '0.9rem',
      outline: 'none',
      cursor: 'pointer',
      WebkitAppearance: 'none',
      MozAppearance: 'none',
      appearance: 'none'
    },
    resultsHeader: {
      fontSize: '1.25rem',
      fontWeight: 'bold',
      color: 'white',
      marginBottom: '1.5rem'
    },
    resultsContainer: {
      display: 'flex',
      flexDirection: 'column',
      gap: '1.5rem'
    },
    emptyState: {
      background: 'rgba(255, 255, 255, 0.05)',
      backdropFilter: 'blur(10px)',
      borderRadius: '12px',
      padding: '4rem 2rem',
      textAlign: 'center',
      border: '1px solid rgba(255, 255, 255, 0.1)'
    },
    emptyIcon: {
      fontSize: '4rem',
      marginBottom: '1rem'
    },
    emptyTitle: {
      fontSize: '1.25rem',
      fontWeight: '600',
      color: 'white',
      marginBottom: '0.5rem'
    },
    emptyText: {
      color: '#a0a0a0',
      marginBottom: '1.5rem'
    },
    exampleButtons: {
      display: 'flex',
      flexWrap: 'wrap',
      justifyContent: 'center',
      gap: '0.5rem'
    },
    exampleButton: {
      padding: '0.5rem 1rem',
      background: 'rgba(255, 255, 255, 0.1)',
      color: '#a0a0a0',
      border: 'none',
      borderRadius: '8px',
      cursor: 'pointer',
      fontSize: '0.875rem',
      transition: 'all 0.2s'
    }
  };

  return (
    <Layout>
      <div style={styles.container}>
        {/* Header */}
        <div style={styles.header}>
          <h1 style={styles.title}>🔍 RAG Search</h1>
          <p style={styles.subtitle}>
            Search for field mappings using semantic similarity
          </p>
        </div>

        {/* Stats Bar */}
        {stats && (
          <div style={styles.statsBar}>
            <div style={styles.statItem}>
              <div style={styles.statLabel}>Total Chunks</div>
              <div style={styles.statValue}>{stats.total_chunks}</div>
            </div>
            <div style={styles.statItem}>
              <div style={styles.statLabel}>Collection</div>
              <div style={{ fontSize: '1.125rem', fontWeight: '600', color: 'white' }}>
                {stats.collection_name}
              </div>
            </div>
            <div style={styles.statItem}>
              <div style={styles.statLabel}>Status</div>
              <span style={{
                display: 'inline-block',
                padding: '0.25rem 0.75rem',
                background: 'rgba(34, 197, 94, 0.2)',
                color: '#22c55e',
                borderRadius: '999px',
                fontSize: '0.875rem',
                fontWeight: '600'
              }}>
                {stats.status}
              </span>
            </div>
            {/* ── NOUVEAU : breakdown des chunk types dans la stats bar ── */}
            {stats.chunk_types && (
              <div style={{ ...styles.statItem, marginTop: '0.5rem' }}>
                <div style={styles.statLabel}>Chunk Types</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.25rem' }}>
                  {Object.entries(stats.chunk_types).map(([type, count]) => (
                    <span key={type} style={{
                      padding: '0.2rem 0.6rem',
                      background: 'rgba(102, 126, 234, 0.15)',
                      color: '#667eea',
                      borderRadius: '6px',
                      fontSize: '0.75rem',
                      fontWeight: '600',
                      border: '1px solid rgba(102, 126, 234, 0.3)'
                    }}>
                      {type}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {/* ── FIN NOUVEAU ─────────────────────────────────────────── */}
          </div>
        )}

        {/* Search Form */}
        <form onSubmit={handleSearch} style={styles.searchForm}>
          <div style={styles.inputGroup}>
            <label style={styles.label}>Search Query</label>
            <div style={styles.searchContainer}>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g., What are the GDPR implications? What global variables control the MT103 mapping?"
                style={styles.input}
              />
              <button
                type="submit"
                disabled={loading || !query.trim()}
                style={{
                  ...styles.button,
                  ...(loading || !query.trim() ? styles.buttonDisabled : {})
                }}
              >
                {loading ? 'Searching...' : 'Search'}
              </button>
            </div>
          </div>

          {/* Filters */}
          <div style={styles.filtersGrid}>
            <div>
              <label style={styles.label}>Chunk Type</label>
              <select
                value={filters.chunk_type}
                onChange={(e) => setFilters({ ...filters, chunk_type: e.target.value })}
                style={styles.select}
              >
                {chunkTypes.map(type => (
                  <option 
                    key={type.value} 
                    value={type.value}
                    style={{ background: '#2a2a3e', color: 'white' }}
                  >
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={styles.label}>Results Count</label>
              <input
                type="number"
                min="1"
                max="20"
                value={filters.n_results}
                onChange={(e) => setFilters({ ...filters, n_results: parseInt(e.target.value) })}
                style={styles.input}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button
                type="button"
                onClick={handleReset}
                style={{
                  ...styles.button,
                  background: 'rgba(255, 255, 255, 0.1)',
                  width: '100%'
                }}
              >
                Reset Filters
              </button>
            </div>
          </div>
        </form>

        {/* Results */}
        {results.length > 0 && (
          <div>
            <h2 style={styles.resultsHeader}>Results ({results.length})</h2>
            <div style={styles.resultsContainer}>
              {results.map((result, index) => (
                <RAGResultCard
                  key={result.chunk_id}
                  result={result}
                  rank={index + 1}
                />
              ))}
            </div>
          </div>
        )}

        {/* No Results */}
        {!loading && results.length === 0 && query && (
          <div style={styles.emptyState}>
            <div style={styles.emptyIcon}>🔍</div>
            <h3 style={styles.emptyTitle}>No results found</h3>
            <p style={styles.emptyText}>Try adjusting your search query or filters</p>
          </div>
        )}

        {/* Empty State */}
        {!loading && results.length === 0 && !query && (
          <div style={styles.emptyState}>
            <div style={styles.emptyIcon}>🚀</div>
            <h3 style={styles.emptyTitle}>Start Your Search</h3>
            <p style={styles.emptyText}>
              Enter a query to find relevant field mappings using AI-powered semantic search
            </p>
            <div style={styles.exampleButtons}>
              <button onClick={() => setQuery('How to convert Field 20C?')} style={styles.exampleButton}>
                Field 20C conversion
              </button>
              <button onClick={() => setQuery('Settlement amount validation rules')} style={styles.exampleButton}>
                Validation rules
              </button>
              <button onClick={() => setQuery('Critical mappings MT202 to MT500')} style={styles.exampleButton}>
                Critical mappings
              </button>
              {/* ── NOUVEAU : exemples pour les nouveaux champs ── */}
              <button onClick={() => setQuery('What are the GDPR and data privacy implications?')} style={styles.exampleButton}>
                GDPR & Data Privacy
              </button>
              <button onClick={() => setQuery('What compliance regulations apply to this mapping?')} style={styles.exampleButton}>
                Compliance requirements
              </button>
              <button onClick={() => setQuery('What global variables control the MT103 mapping?')} style={styles.exampleButton}>
                Global variables
              </button>
              <button onClick={() => setQuery('What needs to be audited in the settlement process?')} style={styles.exampleButton}>
                Audit requirements
              </button>
              <button onClick={() => setQuery('Migration notes and challenges')} style={styles.exampleButton}>
                Migration notes
              </button>
              {/* ── FIN NOUVEAU ────────────────────────────────── */}
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default RAGSearch;