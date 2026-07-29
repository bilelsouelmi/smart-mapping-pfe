import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

/**
 * Password <input> with a show/hide eye toggle. Takes the same style
 * object every page already uses for its plain text inputs — just adds
 * right-padding for the icon and wraps it in a relative container,
 * rather than each page reimplementing this.
 */
const PasswordInput = ({ value, onChange, placeholder, style, required, iconColor = '#9ca3af', autoComplete, ...rest }) => {
  const [visible, setVisible] = useState(false);

  return (
    <div style={{ position: 'relative' }}>
      <input
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        autoComplete={autoComplete}
        style={{ ...style, paddingRight: '40px', width: '100%', boxSizing: 'border-box' }}
        {...rest}
      />
      <button
        type="button"
        onClick={() => setVisible(v => !v)}
        tabIndex={-1}
        style={{
          position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
          background: 'none', border: 'none', cursor: 'pointer', padding: '4px',
          display: 'flex', alignItems: 'center', color: iconColor
        }}
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
};

export default PasswordInput;
