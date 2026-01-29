import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import Layout from '../components/Layout';
import Card from '../components/Card';
import axios from 'axios';
import { FileText, GitBranch, Sparkles, TrendingUp, Upload, Link2, FileOutput, Zap } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const DashboardPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    messageDescriptions: 0,
    mappingFormulas: 0,
    outputs: 0
  });
  const [loading, setLoading] = useState(true);

  // Mock data for chart
  const chartData = [
    { name: 'Mon', files: 4 },
    { name: 'Tue', files: 7 },
    { name: 'Wed', files: 5 },
    { name: 'Thu', files: 9 },
    { name: 'Fri', files: 12 },
    { name: 'Sat', files: 8 },
    { name: 'Sun', files: 6 },
  ];

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const [msgDesc, mappings, outputs] = await Promise.all([
        axios.get('http://localhost:8000/api/message-descriptions/'),
        axios.get('http://localhost:8000/api/mapping-formulas/'),
        axios.get('http://localhost:8000/api/transform/outputs')
      ]);

      setStats({
        messageDescriptions: msgDesc.data.length,
        mappingFormulas: mappings.data.length,
        outputs: outputs.data.total_outputs
      });
    } catch (error) {
      console.error('Failed to load stats:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div>
        {/* Welcome Header */}
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
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '1.5rem',
          marginBottom: '2rem'
        }}>
          <StatCard
            icon={<FileText size={32} />}
            title="Files Analyzed"
            value={loading ? '...' : stats.messageDescriptions}
            change="+12%"
            color="#667eea"
            delay={0}
          />
          <StatCard
            icon={<GitBranch size={32} />}
            title="Mapping Formulas"
            value={loading ? '...' : stats.mappingFormulas}
            change="+8%"
            color="#764ba2"
            delay={0.1}
          />
          <StatCard
            icon={<Sparkles size={32} />}
            title="Outputs Generated"
            value={loading ? '...' : stats.outputs}
            change="+24%"
            color="#48bb78"
            delay={0.2}
          />
        </div>

        {/* Activity Chart */}
        <Card title="Weekly Activity" icon={<TrendingUp size={24} />} style={{ marginBottom: '2rem' }}>
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
                dataKey="files"
                stroke="#667eea"
                strokeWidth={3}
                fillOpacity={1}
                fill="url(#colorFiles)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        {/* Quick Actions */}
        <Card title="Quick Actions" icon={<Zap size={24} />}>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
            gap: '1.5rem'
          }}>
            <ActionButton
              icon={<Upload size={28} />}
              title="Upload & Analyze"
              description="Upload a new file for AI analysis"
              onClick={() => navigate('/upload')}
              gradient="linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
            />
            <ActionButton
              icon={<Link2 size={28} />}
              title="Create Mapping"
              description="Define transformation rules"
              onClick={() => navigate('/mappings')}
              gradient="linear-gradient(135deg, #f093fb 0%, #f5576c 100%)"
            />
            <ActionButton
              icon={<FileOutput size={28} />}
              title="View Outputs"
              description="Browse generated files"
              onClick={() => navigate('/outputs')}
              gradient="linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)"
            />
          </div>
        </Card>
      </div>
    </Layout>
  );
};

const StatCard = ({ icon, title, value, change, color, delay }) => (
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
    {/* Glow effect */}
    <div style={{
      position: 'absolute',
      top: '-50%',
      right: '-50%',
      width: '200px',
      height: '200px',
      background: `radial-gradient(circle, ${color}30 0%, transparent 70%)`,
      animation: 'float 6s ease-in-out infinite'
    }} />

    <div style={{ position: 'relative', zIndex: 1 }}>
      <div style={{ color, marginBottom: '1rem', opacity: 0.9 }}>
        {icon}
      </div>
      <div style={{
        fontSize: '2.5rem',
        fontWeight: '800',
        color: 'white',
        marginBottom: '0.5rem',
        letterSpacing: '-1px'
      }}>
        {value}
      </div>
      <div style={{
        color: '#a0a0a0',
        fontSize: '0.95rem',
        marginBottom: '0.5rem',
        fontWeight: '500'
      }}>
        {title}
      </div>
      <div style={{
        display: 'inline-block',
        padding: '0.25rem 0.75rem',
        background: 'rgba(72, 187, 120, 0.2)',
        color: '#48bb78',
        borderRadius: '20px',
        fontSize: '0.85rem',
        fontWeight: '600'
      }}>
        {change} this week
      </div>
    </div>
  </motion.div>
);

const ActionButton = ({ icon, title, description, onClick, gradient }) => (
  <motion.button
    whileHover={{ scale: 1.03, y: -3 }}
    whileTap={{ scale: 0.98 }}
    onClick={onClick}
    style={{
      background: gradient,
      color: 'white',
      border: 'none',
      borderRadius: '16px',
      padding: '2rem',
      cursor: 'pointer',
      textAlign: 'left',
      transition: 'all 0.3s ease',
      boxShadow: '0 10px 30px rgba(0, 0, 0, 0.3)',
      position: 'relative',
      overflow: 'hidden'
    }}
  >
    <div style={{ position: 'relative', zIndex: 1 }}>
      <div style={{ marginBottom: '1rem', opacity: 0.9 }}>
        {icon}
      </div>
      <div style={{
        fontWeight: '700',
        fontSize: '1.2rem',
        marginBottom: '0.5rem',
        letterSpacing: '-0.3px'
      }}>
        {title}
      </div>
      <div style={{
        fontSize: '0.9rem',
        opacity: 0.9,
        lineHeight: '1.5'
      }}>
        {description}
      </div>
    </div>

    {/* Shine effect */}
    <motion.div
      initial={{ x: '-100%' }}
      whileHover={{ x: '100%' }}
      transition={{ duration: 0.5 }}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent)',
        pointerEvents: 'none'
      }}
    />
  </motion.button>
);

export default DashboardPage;