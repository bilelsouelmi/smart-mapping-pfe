import { motion } from 'framer-motion';

const Card = ({ title, children, style, icon }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      whileHover={{ y: -5, boxShadow: '0 20px 60px rgba(102, 126, 234, 0.3)' }}
      style={{
        background: 'rgba(26, 26, 46, 0.6)',
        backdropFilter: 'blur(20px)',
        borderRadius: '20px',
        padding: '2rem',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
        transition: 'all 0.3s ease',
        ...style
      }}
    >
      {title && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          marginBottom: '1.5rem',
          paddingBottom: '1rem',
          borderBottom: '2px solid rgba(102, 126, 234, 0.3)'
        }}>
          {icon && <span style={{ fontSize: '1.5rem' }}>{icon}</span>}
          <h2 style={{
            margin: 0,
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            fontSize: '1.5rem',
            fontWeight: '700',
            letterSpacing: '-0.5px'
          }}>
            {title}
          </h2>
        </div>
      )}
      {children}
    </motion.div>
  );
};

export default Card;