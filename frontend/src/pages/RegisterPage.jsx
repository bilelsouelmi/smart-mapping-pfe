import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'react-toastify';
import PasswordInput from '../components/PasswordInput';

const RegisterPage = () => {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    full_name: ''
  });
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    const result = await register(formData);
    
    if (result.success) {
      toast.success('Account created! Please login.');
      navigate('/login');
    } else {
      toast.error(result.error);
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
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem'
    }}>
      <style>{`
        .auth-input::placeholder { color: rgba(255,255,255,0.55); }
        .auth-input:focus { outline: none; border-color: rgba(255,255,255,0.6) !important; }
      `}</style>
      <div style={{
        background: 'rgba(255,255,255,0.06)',
        backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid rgba(255,255,255,0.3)',
        borderRadius: '20px',
        padding: '3rem',
        width: '100%',
        maxWidth: '450px',
        boxShadow: '0 20px 60px rgba(0,0,0,0.45)'
      }}>
        <h1 style={{ textAlign: 'center', marginBottom: '0.5rem', color: 'white' }}>
          Create Account
        </h1>
        <p style={{ textAlign: 'center', color: 'rgba(255,255,255,0.75)', marginBottom: '2rem' }}>
          Join Smart Mapping Platform
        </p>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1rem' }}>
            <label style={labelStyle}>Full Name</label>
            <input
              type="text"
              name="full_name"
              value={formData.full_name}
              onChange={handleChange}
              required
              style={inputStyle}
              placeholder="John Doe"
              className="auth-input"
            />
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={labelStyle}>Username</label>
            <input
              type="text"
              name="username"
              value={formData.username}
              onChange={handleChange}
              required
              style={inputStyle}
              placeholder="johndoe"
              className="auth-input"
            />
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={labelStyle}>Email</label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              pattern=".+@vermeg\.com$"
              title="Only @vermeg.com email addresses are allowed"
              style={inputStyle}
              placeholder="john@vermeg.com"
              className="auth-input"
            />
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={labelStyle}>Password</label>
            <PasswordInput
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              minLength={8}
              maxLength={72}
              style={inputStyle}
              placeholder="Min 8 characters"
              autoComplete="new-password"
              iconColor="rgba(255,255,255,0.75)"
              className="auth-input"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              ...buttonStyle,
              opacity: loading ? 0.7 : 1,
              cursor: loading ? 'not-allowed' : 'pointer'
            }}
          >
            {loading ? 'Creating Account...' : 'Register'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: '1.5rem', color: 'rgba(255,255,255,0.75)' }}>
          Already have an account?{' '}
          <Link to="/login" style={{ color: '#c4b5fd', fontWeight: 'bold' }}>
            Login here
          </Link>
        </p>
      </div>
    </div>
  );
};

const labelStyle = {
  display: 'block',
  marginBottom: '0.5rem',
  color: 'rgba(255,255,255,0.9)',
  fontWeight: '500',
  fontSize: '0.9rem'
};

const inputStyle = {
  width: '100%',
  padding: '0.75rem',
  background: 'rgba(255,255,255,0.1)',
  color: 'white',
  border: '1px solid rgba(255,255,255,0.3)',
  borderRadius: '8px',
  fontSize: '1rem',
  transition: 'border-color 0.3s',
  boxSizing: 'border-box'
};

const buttonStyle = {
  width: '100%',
  padding: '0.75rem',
  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  color: 'white',
  border: 'none',
  borderRadius: '8px',
  fontSize: '1rem',
  fontWeight: 'bold',
  cursor: 'pointer',
  transition: 'transform 0.2s'
};

export default RegisterPage;