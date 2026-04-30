import { useAuth } from '../contexts/AuthContext';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Home, Upload, Link2, FileOutput, LogOut, Sparkles, Database, Search, Layers } from 'lucide-react';

const Layout = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { path: '/dashboard', icon: Home, label: 'Dashboard' },
    { path: '/upload', icon: Upload, label: 'Upload' },
    { path: '/standard-elements', icon: Database, label: 'Elements' },
    { path: '/message-descriptions', icon: Layers, label: 'Message Desc' },
    { path: '/mappings', icon: Link2, label: 'Mappings' },
    { path: '/outputs', icon: FileOutput, label: 'Outputs' },
    { path: '/rag-search', icon: Search, label: 'RAG Search' },
  ];

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0f0f23 0%, #1a1a2e 50%, #16213e 100%)',
      position: 'relative',
      overflow: 'hidden'
    }}>
      <div style={{
        position: 'absolute', width: '500px', height: '500px', borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(102,126,234,0.1) 0%, transparent 70%)',
        top: '-250px', right: '-250px', animation: 'float 6s ease-in-out infinite'
      }} />
      <div style={{
        position: 'absolute', width: '400px', height: '400px', borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(118,75,162,0.1) 0%, transparent 70%)',
        bottom: '-200px', left: '-200px', animation: 'float 8s ease-in-out infinite', animationDelay: '2s'
      }} />

      <motion.nav
        initial={{ y: -100 }} animate={{ y: 0 }} transition={{ type: 'spring', stiffness: 100 }}
        style={{
          background: 'rgba(26, 26, 46, 0.8)', backdropFilter: 'blur(20px)',
          padding: '1rem 2rem', display: 'flex', justifyContent: 'space-between',
          alignItems: 'center', borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
          position: 'sticky', top: 0, zIndex: 1000, boxShadow: '0 4px 30px rgba(0, 0, 0, 0.3)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
          <motion.div whileHover={{ scale: 1.05 }} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Sparkles size={28} color="#667eea" />
            <h1 style={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              margin: 0, fontSize: '1.5rem', fontWeight: '800', letterSpacing: '-0.5px'
            }}>
              Smart Mapping
            </h1>
          </motion.div>

          <div style={{ display: 'flex', gap: '0.4rem' }}>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link key={item.path} to={item.path} style={{ textDecoration: 'none' }}>
                  <motion.div
                    whileHover={{ scale: 1.05, y: -2 }} whileTap={{ scale: 0.95 }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '0.4rem',
                      padding: '0.6rem 1rem', borderRadius: '12px',
                      background: isActive ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : 'rgba(255, 255, 255, 0.05)',
                      color: 'white', border: '1px solid',
                      borderColor: isActive ? 'transparent' : 'rgba(255, 255, 255, 0.1)',
                      transition: 'all 0.3s ease', cursor: 'pointer',
                      boxShadow: isActive ? '0 4px 20px rgba(102, 126, 234, 0.4)' : 'none'
                    }}
                  >
                    <Icon size={16} />
                    <span style={{ fontWeight: '600', fontSize: '0.8rem' }}>{item.label}</span>
                  </motion.div>
                </Link>
              );
            })}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            padding: '0.5rem 1rem', background: 'rgba(255, 255, 255, 0.05)',
            borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.1)'
          }}>
            <span style={{ color: '#a0a0a0', fontSize: '0.85rem' }}>👤</span>
            <span style={{ color: 'white', marginLeft: '0.5rem', fontWeight: '600' }}>{user?.username}</span>
          </div>
          <motion.button
            whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={handleLogout}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              padding: '0.75rem 1.25rem', background: 'rgba(239, 68, 68, 0.1)',
              color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: '10px', cursor: 'pointer', fontWeight: '600',
              fontSize: '0.9rem', transition: 'all 0.3s ease'
            }}
          >
            <LogOut size={18} />
            Logout
          </motion.button>
        </div>
      </motion.nav>

      <main style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto', position: 'relative', zIndex: 1 }}>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          {children}
        </motion.div>
      </main>
    </div>
  );
};

export default Layout;