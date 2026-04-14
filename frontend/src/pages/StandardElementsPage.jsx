import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import Layout from '../components/Layout';
import Card from '../components/Card';
import axios from 'axios';
import { toast } from 'react-toastify';
import { Search, Filter, Database, Layers, FileCode, Tag } from 'lucide-react';

const StandardElementsPage = () => {
  const [elements, setElements] = useState([]);
  const [filteredElements, setFilteredElements] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Filtres
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedStructureType, setSelectedStructureType] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Modal
  const [selectedElement, setSelectedElement] = useState(null);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    loadElements();
    loadCategories();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [elements, selectedCategory, selectedStructureType, searchQuery]);

  const loadElements = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/standard-elements/');
      setElements(response.data);
      setFilteredElements(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error loading elements:', error);
      toast.error('Failed to load standard elements');
      setLoading(false);
    }
  };

  const loadCategories = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/standard-elements/categories');
      setCategories(response.data);
    } catch (error) {
      console.error('Error loading categories:', error);
    }
  };

  const applyFilters = () => {
    let filtered = [...elements];

    // Filtre catégorie
    if (selectedCategory !== 'all') {
      filtered = filtered.filter(el => el.category === selectedCategory);
    }

    // Filtre structure type
    if (selectedStructureType !== 'all') {
      filtered = filtered.filter(el => el.structure_type === selectedStructureType);
    }

    // Recherche
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(el =>
        el.element_name.toLowerCase().includes(query) ||
        el.element_id.toLowerCase().includes(query) ||
        el.description?.toLowerCase().includes(query) ||
        el.source_path?.toLowerCase().includes(query)
      );
    }

    setFilteredElements(filtered);
  };

  const structureTypeColors = {
    simple: '#48bb78',
    map: '#667eea',
    hmap: '#764ba2',
    array: '#f6ad55',
    object: '#fc8181'
  };

  const structureTypeIcons = {
    simple: '📄',
    map: '🗺️',
    hmap: '🔀',
    array: '📋',
    object: '📦'
  };

  if (loading) {
    return (
      <Layout>
        <div style={{ textAlign: 'center', padding: '4rem' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>⏳</div>
          <div style={{ color: '#a0a0a0' }}>Loading standard elements...</div>
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '0.5rem' }}>
            <Database size={36} color="#667eea" />
            <h1 style={{
              fontSize: '2.5rem',
              fontWeight: '800',
              margin: 0,
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent'
            }}>
              Standard Elements
            </h1>
          </div>
          <p style={{ color: '#a0a0a0', fontSize: '1.1rem', margin: 0 }}>
            ISO 20022 pain.001.001.12 - Customer Credit Transfer Initiation
          </p>
        </motion.div>

        {/* Stats Cards */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem',
          marginBottom: '2rem'
        }}>
          <StatCard
            icon={<Layers size={24} />}
            label="Total Elements"
            value={elements.length}
            color="#667eea"
          />
          <StatCard
            icon={<Filter size={24} />}
            label="Filtered"
            value={filteredElements.length}
            color="#764ba2"
          />
          <StatCard
            icon={<Tag size={24} />}
            label="Categories"
            value={categories.length}
            color="#48bb78"
          />
          <StatCard
            icon={<FileCode size={24} />}
            label="Structure Types"
            value={[...new Set(elements.map(e => e.structure_type))].length}
            color="#f6ad55"
          />
        </div>

        {/* Filters */}
        <Card style={{ marginBottom: '2rem' }}>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
            gap: '1.5rem'
          }}>
            {/* Search */}
            <div>
              <label style={{
                display: 'block',
                marginBottom: '0.5rem',
                color: '#a0a0a0',
                fontSize: '0.9rem',
                fontWeight: '600'
              }}>
                <Search size={16} style={{ verticalAlign: 'middle', marginRight: '0.5rem' }} />
                Search
              </label>
              <input
                type="text"
                placeholder="Search by name, ID, description..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: '#1a1a2e',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '8px',
                  color: 'white',
                  fontSize: '0.95rem'
                }}
              />
            </div>

            {/* Category Filter */}
            <div>
              <label style={{
                display: 'block',
                marginBottom: '0.5rem',
                color: '#a0a0a0',
                fontSize: '0.9rem',
                fontWeight: '600'
              }}>
                <Filter size={16} style={{ verticalAlign: 'middle', marginRight: '0.5rem' }} />
                Category
              </label>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: '#1a1a2e',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '8px',
                  color: 'white',
                  fontSize: '0.95rem',
                  cursor: 'pointer'
                }}
              >
                <option value="all">All Categories</option>
                {categories.map(cat => (
                  <option key={cat.category} value={cat.category}>
                    {cat.category} ({cat.count})
                  </option>
                ))}
              </select>
            </div>

            {/* Structure Type Filter */}
            <div>
              <label style={{
                display: 'block',
                marginBottom: '0.5rem',
                color: '#a0a0a0',
                fontSize: '0.9rem',
                fontWeight: '600'
              }}>
                <Layers size={16} style={{ verticalAlign: 'middle', marginRight: '0.5rem' }} />
                Structure Type
              </label>
              <select
                value={selectedStructureType}
                onChange={(e) => setSelectedStructureType(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: '#1a1a2e',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '8px',
                  color: 'white',
                  fontSize: '0.95rem',
                  cursor: 'pointer'
                }}
              >
                <option value="all">All Types</option>
                <option value="simple">📄 Simple</option>
                <option value="map">🗺️ MAP</option>
                <option value="hmap">🔀 HMAP</option>
                <option value="array">📋 Array</option>
                <option value="object">📦 Object</option>
              </select>
            </div>
          </div>
        </Card>

        {/* Elements List */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))',
          gap: '1.5rem'
        }}>
          {filteredElements.map((element, index) => (
            <ElementCard
              key={element.id}
              element={element}
              index={index}
              structureTypeColors={structureTypeColors}
              structureTypeIcons={structureTypeIcons}
              onClick={() => {
                setSelectedElement(element);
                setShowModal(true);
              }}
            />
          ))}
        </div>

        {/* No Results */}
        {filteredElements.length === 0 && (
          <Card style={{ textAlign: 'center', padding: '3rem' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🔍</div>
            <div style={{ color: '#a0a0a0', fontSize: '1.1rem' }}>
              No elements found matching your filters
            </div>
          </Card>
        )}

        {/* Modal */}
        {showModal && selectedElement && (
          <ElementModal
            element={selectedElement}
            onClose={() => setShowModal(false)}
            structureTypeColors={structureTypeColors}
            structureTypeIcons={structureTypeIcons}
          />
        )}
      </div>
    </Layout>
  );
};

// Composant StatCard
const StatCard = ({ icon, label, value, color }) => (
  <motion.div
    initial={{ opacity: 0, scale: 0.9 }}
    animate={{ opacity: 1, scale: 1 }}
    whileHover={{ scale: 1.05, y: -3 }}
    style={{
      background: 'rgba(26, 26, 46, 0.6)',
      backdropFilter: 'blur(20px)',
      borderRadius: '16px',
      padding: '1.5rem',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      borderLeft: `4px solid ${color}`,
      cursor: 'pointer'
    }}
  >
    <div style={{ color, marginBottom: '0.5rem' }}>{icon}</div>
    <div style={{
      fontSize: '2rem',
      fontWeight: '800',
      color: 'white',
      marginBottom: '0.25rem'
    }}>
      {value}
    </div>
    <div style={{ color: '#a0a0a0', fontSize: '0.9rem' }}>{label}</div>
  </motion.div>
);

// Composant ElementCard
const ElementCard = ({ element, index, structureTypeColors, structureTypeIcons, onClick }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: index * 0.05 }}
    whileHover={{ y: -5, boxShadow: '0 20px 40px rgba(102, 126, 234, 0.3)' }}
    onClick={onClick}
    style={{
      background: 'rgba(26, 26, 46, 0.6)',
      backdropFilter: 'blur(20px)',
      borderRadius: '16px',
      padding: '1.5rem',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      cursor: 'pointer',
      transition: 'all 0.3s ease'
    }}
  >
    {/* Header */}
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      marginBottom: '1rem'
    }}>
      <div>
        <div style={{
          display: 'inline-block',
          padding: '0.25rem 0.75rem',
          background: structureTypeColors[element.structure_type] + '30',
          color: structureTypeColors[element.structure_type],
          borderRadius: '12px',
          fontSize: '0.75rem',
          fontWeight: '700',
          marginBottom: '0.5rem'
        }}>
          {structureTypeIcons[element.structure_type]} {element.structure_type?.toUpperCase() || 'UNKNOWN'}
        </div>
        <div style={{
          fontSize: '0.85rem',
          color: '#667eea',
          fontWeight: '600',
          fontFamily: 'monospace'
        }}>
          {element.element_id}
        </div>
      </div>
      <div style={{
        padding: '0.25rem 0.75rem',
        background: 'rgba(102, 126, 234, 0.2)',
        color: '#667eea',
        borderRadius: '12px',
        fontSize: '0.75rem',
        fontWeight: '600'
      }}>
        {element.category}
      </div>
    </div>

    {/* Name */}
    <h3 style={{
      margin: '0 0 0.75rem 0',
      fontSize: '1.1rem',
      fontWeight: '700',
      color: 'white'
    }}>
      {element.element_name}
    </h3>

    {/* Description */}
    {element.description && (
      <p style={{
        margin: '0 0 1rem 0',
        color: '#a0a0a0',
        fontSize: '0.85rem',
        lineHeight: '1.5',
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
        overflow: 'hidden'
      }}>
        {element.description}
      </p>
    )}

    {/* Paths */}
    <div style={{ fontSize: '0.8rem', color: '#888' }}>
      {element.source_path && (
        <div style={{ marginBottom: '0.25rem' }}>
          <span style={{ color: '#667eea' }}>Source:</span> {element.source_path}
        </div>
      )}
      {element.target_path && (
        <div>
          <span style={{ color: '#764ba2' }}>Target:</span> {element.target_path}
        </div>
      )}
    </div>

    {/* Tags */}
    {element.tags && element.tags.length > 0 && (
      <div style={{
        display: 'flex',
        gap: '0.5rem',
        flexWrap: 'wrap',
        marginTop: '1rem'
      }}>
        {element.tags.slice(0, 3).map((tag, idx) => (
          <span
            key={idx}
            style={{
              padding: '0.25rem 0.5rem',
              background: 'rgba(255, 255, 255, 0.1)',
              borderRadius: '8px',
              fontSize: '0.7rem',
              color: '#a0a0a0'
            }}
          >
            {tag}
          </span>
        ))}
      </div>
    )}
  </motion.div>
);

// Composant Modal
const ElementModal = ({ element, onClose, structureTypeColors, structureTypeIcons }) => (
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    onClick={onClose}
    style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.8)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      padding: '2rem'
    }}
  >
    <motion.div
      initial={{ scale: 0.9, y: 20 }}
      animate={{ scale: 1, y: 0 }}
      onClick={(e) => e.stopPropagation()}
      style={{
        background: 'rgba(26, 26, 46, 0.95)',
        backdropFilter: 'blur(20px)',
        borderRadius: '20px',
        padding: '2rem',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        maxWidth: '600px',
        width: '100%',
        maxHeight: '80vh',
        overflow: 'auto'
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: '1.5rem'
      }}>
        <div>
          <div style={{
            display: 'inline-block',
            padding: '0.35rem 1rem',
            background: structureTypeColors[element.structure_type] + '30',
            color: structureTypeColors[element.structure_type],
            borderRadius: '12px',
            fontSize: '0.85rem',
            fontWeight: '700',
            marginBottom: '0.75rem'
          }}>
            {structureTypeIcons[element.structure_type]} {element.structure_type?.toUpperCase() || 'UNKNOWN'}
          </div>
          <h2 style={{
            margin: 0,
            fontSize: '1.8rem',
            fontWeight: '800',
            color: 'white'
          }}>
            {element.element_name}
          </h2>
          <div style={{
            color: '#667eea',
            fontFamily: 'monospace',
            fontSize: '0.95rem',
            marginTop: '0.5rem'
          }}>
            {element.element_id}
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'rgba(239, 68, 68, 0.2)',
            color: '#ef4444',
            border: 'none',
            borderRadius: '8px',
            padding: '0.5rem 1rem',
            cursor: 'pointer',
            fontWeight: '600'
          }}
        >
          ✕ Close
        </button>
      </div>

      {/* Details */}
      <div style={{ display: 'grid', gap: '1.5rem' }}>
        <DetailRow label="Category" value={element.category} />
        <DetailRow label="Business Domain" value={element.business_domain} />
        <DetailRow label="Data Type" value={element.data_type} />
        
        {element.description && (
          <DetailRow label="Description" value={element.description} />
        )}
        
        {element.source_path && (
          <DetailRow label="Source Path" value={element.source_path} mono />
        )}
        
        {element.target_path && (
          <DetailRow label="Target Path" value={element.target_path} mono />
        )}
        
        {element.iso20022_path && (
          <DetailRow label="ISO 20022 Path" value={element.iso20022_path} mono />
        )}
        
        {element.example_value && (
          <DetailRow label="Example" value={element.example_value} />
        )}
        
        <DetailRow 
          label="Required" 
          value={element.is_required ? '✅ Yes' : '❌ No'} 
        />
        
        {element.tags && element.tags.length > 0 && (
          <div>
            <div style={{
              color: '#a0a0a0',
              fontSize: '0.85rem',
              marginBottom: '0.5rem',
              fontWeight: '600'
            }}>
              Tags
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {element.tags.map((tag, idx) => (
                <span
                  key={idx}
                  style={{
                    padding: '0.35rem 0.75rem',
                    background: 'rgba(102, 126, 234, 0.2)',
                    color: '#667eea',
                    borderRadius: '8px',
                    fontSize: '0.8rem',
                    fontWeight: '600'
                  }}
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  </motion.div>
);

// Composant DetailRow
const DetailRow = ({ label, value, mono }) => (
  <div>
    <div style={{
      color: '#a0a0a0',
      fontSize: '0.85rem',
      marginBottom: '0.35rem',
      fontWeight: '600'
    }}>
      {label}
    </div>
    <div style={{
      color: 'white',
      fontSize: '0.95rem',
      fontFamily: mono ? 'monospace' : 'inherit',
      padding: mono ? '0.5rem' : '0',
      background: mono ? 'rgba(255, 255, 255, 0.05)' : 'transparent',
      borderRadius: mono ? '6px' : '0'
    }}>
      {value}
    </div>
  </div>
);

export default StandardElementsPage;