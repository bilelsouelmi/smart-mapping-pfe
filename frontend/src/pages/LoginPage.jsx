import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'react-toastify';
import { Clock } from 'lucide-react';
import PasswordInput from '../components/PasswordInput';

const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [pendingApproval, setPendingApproval] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setPendingApproval(false);

    const result = await login(email, password);

    if (result.success) {
      toast.success('Welcome back!');
      navigate('/dashboard');
    } else {
      if (result.error === 'PENDING_APPROVAL') {
        setPendingApproval(true);
      } else {
        toast.error(result.error);
      }
    }

    setLoading(false);
  };

  return (
    <div style={{
      minHeight: '100vh',
      backgroundImage: 'linear-gradient(rgba(20,10,40,0.35), rgba(20,10,40,0.55)), url(/vermeg-bg.png)',
      backgroundSize: 'cover',
      backgroundPosition: 'center',
      backgroundRepeat: 'no-repeat',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem'
    }}>
      <style>{`
        .auth-input::placeholder { color: rgba(255,255,255,0.55); }
        .auth-input:focus { outline: none; border-color: rgba(255,255,255,0.6) !important; }
      `}</style>
      <div style={{
        background: 'rgba(255,255,255,0.06)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid rgba(255,255,255,0.3)',
        borderRadius: '20px', padding: '3rem',
        width: '100%', maxWidth: '450px',
        boxShadow: '0 20px 60px rgba(0,0,0,0.45)'
      }}>
        <h1 style={{ textAlign: 'center', marginBottom: '0.5rem', color: 'white' }}>
          🎯 Smart Mapping
        </h1>
        <p style={{ textAlign: 'center', color: 'rgba(255,255,255,0.75)', marginBottom: '2rem' }}>
          AI-Powered Data Transformation
        </p>

        {/* Pending approval message */}
        {pendingApproval && (
          <div style={{
            background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.5)',
            borderRadius: '12px', padding: '1rem 1.25rem',
            marginBottom: '1.5rem', display: 'flex', gap: '0.75rem', alignItems: 'flex-start'
          }}>
            <Clock size={20} color="#fbbf24" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <div style={{ fontWeight: '700', color: '#fde68a', fontSize: '0.9rem' }}>
                Account pending approval
              </div>
              <div style={{ color: '#fef3c7', fontSize: '0.82rem', marginTop: '2px' }}>
                Your account has been created successfully but requires administrator
                approval before you can log in. Please contact your administrator.
              </div>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={labelStyle}>Email</label>
            <input
              type="email" value={email}
              onChange={(e) => setEmail(e.target.value)}
              required style={inputStyle} placeholder="you@vermeg.com"
              className="auth-input"
            />
          </div>
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={labelStyle}>Password</label>
            <PasswordInput
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required style={inputStyle} placeholder="Enter your password"
              iconColor="rgba(255,255,255,0.75)" autoComplete="current-password"
              className="auth-input"
            />
          </div>
          <button type="submit" disabled={loading} style={{
            ...buttonStyle,
            opacity: loading ? 0.7 : 1,
            cursor: loading ? 'not-allowed' : 'pointer'
          }}>
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: '1.5rem', color: 'rgba(255,255,255,0.75)' }}>
          Don't have an account?{' '}
          <Link to="/register" style={{ color: '#c4b5fd', fontWeight: 'bold' }}>
            Register here
          </Link>
        </p>
      </div>
    </div>
  );
};

const labelStyle = {
  display: 'block', marginBottom: '0.5rem', color: 'rgba(255,255,255,0.9)', fontWeight: '500'
};

const inputStyle = {
  width: '100%', padding: '0.75rem',
  background: 'rgba(255,255,255,0.1)', color: 'white',
  border: '1px solid rgba(255,255,255,0.3)', borderRadius: '8px',
  fontSize: '1rem', transition: 'border-color 0.3s', boxSizing: 'border-box'
};

const buttonStyle = {
  width: '100%', padding: '0.75rem',
  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  color: 'white', border: 'none', borderRadius: '8px',
  fontSize: '1rem', fontWeight: 'bold', cursor: 'pointer', transition: 'transform 0.2s'
};

export default LoginPage;