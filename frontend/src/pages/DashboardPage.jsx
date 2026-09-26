import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import Layout from '../components/Layout';
import Card from '../components/Card';
import axios from 'axios';
import { FileText, GitBranch, Sparkles, TrendingUp, Zap, CheckCircle, Award, Target } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const DashboardPage = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState({
    messageDescriptions: 0,
    mtFiles: 0,
    approvedRefs: 0,
    mappingsTotal: 0,
    mappingsActive: 0,
    mappingElements: 0,
    mappedElements: 0,
    avgMappingCompletion: 0,
    outputs: 0
  });
  const [loading, setLoading] = useState(true);
  const [recentFiles, setRecentFiles] = useState([]);
  // Activité réelle des 7 derniers jours, alimentée par la piste d'audit
  const [chartData, setChartData] = useState([]);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const [summary, files] = await Promise.all([
        axios.get('http://localhost:8000/api/files/dashboard-stats'),
        axios.get('http://localhost:8000/api/files/')
      ]);

      const s = summary.data;
      setStats({
        messageDescriptions: s.message_descriptions,
        mtFiles: s.mt_files,
        approvedRefs: s.approved_refs,
        mappingsTotal: s.mappings_total,
        mappingsActive: s.mappings_active,
        mappingElements: s.mapping_elements,
        mappedElements: s.mapped_elements,
        avgMappingCompletion: s.avg_mapping_completion,
        outputs: s.outputs
      });
      setChartData(s.activity || []);

      const allFiles = files.data.files || files.data || [];
      setRecentFiles([...allFiles].sort((a, b) => b.id - a.id).slice(0, 5));
    } catch (error) {
      console.error('Failed to load stats:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div>
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ marginBottom: '2rem' }}
        >
          <h1 style={{
            fontSize: '2.5rem',
            fontWeight: '800',
            marginBottom: '0.5rem',
            background: 'linear-gradient(135deg, #fff 0%, #a0a0a0 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            letterSpacing: '-1px'
          }}>
            Welcome back, {user?.full_name || user?.username}! 👋
          </h1>
          <p style={{ color: '#a0a0a0', fontSize: '1.1rem' }}>
            Here's what's happening with your data transformations today.
          </p>
        </motion.div>

        {/* Stats Cards */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '1.5rem',
          marginBottom: '2rem'
        }}>
          <StatCard
            icon={<FileText size={32} />}
            title="Files Analyzed"
            value={loading ? '...' : stats.messageDescriptions}
            sub={`${stats.mtFiles} SWIFT MT`}
            color="#667eea"
            delay={0}
          />
          <StatCard
            icon={<GitBranch size={32} />}
            title="Mappings"
            value={loading ? '...' : stats.mappingsTotal}
            sub={`${stats.mappingsActive} active`}
            color="#764ba2"
            delay={0.1}
          />
          <StatCard
            icon={<Sparkles size={32} />}
            title="Outputs Generated"
            value={loading ? '...' : stats.outputs}
            sub="ISO 20022 files"
            color="#48bb78"
            delay={0.2}
          />
          <StatCard
            icon={<CheckCircle size={32} />}
            title="Approved References"
            value={loading ? '...' : stats.approvedRefs}
            sub="Standards de référence"
            color="#f59e0b"
            delay={0.3}
          />
          <StatCard
            icon={<Award size={32} />}
            title="Mapped Elements"
            value={loading ? '...' : stats.mappedElements}
            sub={`sur ${stats.mappingElements} éléments`}
            color="#06b6d4"
            delay={0.4}
          />
          <StatCard
            icon={<Target size={32} />}
            title="Avg Mapping Completion"
            value={loading ? '...' : `${stats.avgMappingCompletion}%`}
            sub="Éléments mappés"
            color="#f43f5e"
            delay={0.5}
          />
        </div>

        {/* ── NOUVEAU : Recent Files Status ──────────────────────────────────── */}
        {recentFiles.length > 0 && (
          <Card title="Recent Files" icon={<FileText size={24} />} style={{ marginBottom: '2rem' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {recentFiles.map(file => (
                <div key={file.id} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '1rem',
                  padding: '0.75rem 1rem',
                  background: 'rgba(255,255,255,0.03)',
                  borderRadius: '8px',
                  border: '1px solid rgba(255,255,255,0.06)'
                }}>
                  <span style={{ fontSize: '1.2rem' }}>
                    {file.file_type === 'XML_MT' ? '🏦' : '📄'}
                  </span>
                  <span style={{ color: '#e2e8f0', flex: 1, fontSize: '0.9rem' }}>
                    {file.file_name}
                    {file.mt_type && (
                      <span style={{
                        marginLeft: '8px',
                        padding: '1px 6px',
                        background: 'rgba(245,158,11,0.2)',
                        color: '#f59e0b',
                        borderRadius: '4px',
                        fontSize: '0.7rem',
                        fontWeight: '600'
                      }}>
                        {file.mt_type}
                      </span>
                    )}
                  </span>
                  <span style={{
                    padding: '2px 10px',
                    borderRadius: '20px',
                    fontSize: '0.75rem',
                    fontWeight: '600',
                    background: file.status === 'validated' ? 'rgba(34,197,94,0.2)'
                      : file.status === 'in_progress' ? 'rgba(59,130,246,0.2)'
                      : 'rgba(107,114,128,0.2)',
                    color: file.status === 'validated' ? '#22c55e'
                      : file.status === 'in_progress' ? '#3b82f6'
                      : '#9ca3af'
                  }}>
                    {file.status || 'draft'}
                  </span>
                  {file.mapping_completion > 0 && (
                    <span style={{ color: '#a0a0a0', fontSize: '0.8rem', minWidth: '45px', textAlign: 'right' }}>
                      {file.mapping_completion}%
                    </span>
                  )}
                  {file.quality_score > 0 && (
                    <span style={{
                      color: file.quality_score >= 80 ? '#22c55e' : file.quality_score >= 60 ? '#f59e0b' : '#ef4444',
                      fontSize: '0.8rem',
                      fontWeight: '700',
                      minWidth: '45px',
                      textAlign: 'right'
                    }}>
                      Q:{file.quality_score}%
                    </span>
                  )}
                </div>
              ))}
            </div>
          </Card>
        )}
        {/* ── FIN NOUVEAU ──────────────────────────────────────────────────────── */}

        {/* Activity Chart */}
        <Card title="Activité des 7 derniers jours" icon={<TrendingUp size={24} />} style={{ marginBottom: '2rem' }}>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorFiles" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#667eea" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#667eea" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="name" stroke="#a0a0a0" />
              <YAxis stroke="#a0a0a0" />
              <Tooltip
                contentStyle={{
                  background: 'rgba(26, 26, 46, 0.95)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '10px',
                  backdropFilter: 'blur(10px)'
                }}
              />
              <Area
                type="monotone"
                dataKey="events"
                name="Événements"
                stroke="#667eea"
                strokeWidth={3}
                fillOpacity={1}
                fill="url(#colorFiles)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </Card>


      </div>
    </Layout>
  );
};

const StatCard = ({ icon, title, value, sub, color, delay }) => (
  <motion.div
    initial={{ opacity: 0, scale: 0.8 }}
    animate={{ opacity: 1, scale: 1 }}
    transition={{ delay, type: 'spring', stiffness: 100 }}
    whileHover={{ scale: 1.05, y: -5 }}
    style={{
      background: 'rgba(26, 26, 46, 0.6)',
      backdropFilter: 'blur(20px)',
      borderRadius: '20px',
      padding: '2rem',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      borderLeft: `4px solid ${color}`,
      cursor: 'pointer',
      transition: 'all 0.3s ease',
      position: 'relative',
      overflow: 'hidden'
    }}
  >
    <div style={{
      position: 'absolute',
      top: '-50%',
      right: '-50%',
      width: '200px',
      height: '200px',
      background: `radial-gradient(circle, ${color}30 0%, transparent 70%)`,
    }} />
    <div style={{ position: 'relative', zIndex: 1 }}>
      <div style={{ color, marginBottom: '1rem', opacity: 0.9 }}>{icon}</div>
      <div style={{ fontSize: '2.5rem', fontWeight: '800', color: 'white', marginBottom: '0.5rem', letterSpacing: '-1px' }}>
        {value}
      </div>
      <div style={{ color: '#a0a0a0', fontSize: '0.95rem', marginBottom: '0.5rem', fontWeight: '500' }}>
        {title}
      </div>
      <div style={{
        display: 'inline-block',
        padding: '0.25rem 0.75rem',
        background: `${color}20`,
        color: color,
        borderRadius: '20px',
        fontSize: '0.85rem',
        fontWeight: '600'
      }}>
        {sub}
      </div>
    </div>
  </motion.div>
);

export default DashboardPage;