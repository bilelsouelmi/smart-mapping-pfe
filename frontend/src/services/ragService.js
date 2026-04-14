import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class RAGService {
  /**
   * Query the RAG system
   */
  async query(queryText, options = {}) {
    try {
      const response = await axios.post(`${API_URL}/api/rag/query`, {
        query: queryText,
        n_results: options.n_results || 5,
        filter_mapping_id: options.filter_mapping_id || null,
        filter_chunk_type: options.filter_chunk_type || null
      });
      return response.data;
    } catch (error) {
      console.error('RAG query error:', error);
      throw error;
    }
  }

  /**
   * Search with GET method
   */
  async search(queryText, options = {}) {
    try {
      const params = new URLSearchParams({
        query: queryText,
        limit: options.limit || 5
      });
      
      if (options.mapping_id) params.append('mapping_id', options.mapping_id);
      if (options.chunk_type) params.append('chunk_type', options.chunk_type);

      const response = await axios.get(`${API_URL}/api/rag/search?${params}`);
      return response.data;
    } catch (error) {
      console.error('RAG search error:', error);
      throw error;
    }
  }

  /**
   * Get RAG statistics
   */
  async getStats() {
    try {
      const response = await axios.get(`${API_URL}/api/rag/stats`);
      return response.data;
    } catch (error) {
      console.error('RAG stats error:', error);
      throw error;
    }
  }

  /**
   * Find mapping by field
   */
  async findMapping(sourceField, targetField = null, nResults = 3) {
    try {
      const params = new URLSearchParams({
        source_field: sourceField,
        n_results: nResults
      });
      
      if (targetField) params.append('target_field', targetField);

      const response = await axios.get(`${API_URL}/api/rag/mappings/find?${params}`);
      return response.data;
    } catch (error) {
      console.error('Find mapping error:', error);
      throw error;
    }
  }
}

export default new RAGService();