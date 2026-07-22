import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ChevronRight, ShieldCheck } from 'lucide-react';

// The core pipeline a user actually walks through, in order: define a
// reference, map & transform, see what came out. Validate is deliberately
// NOT in this numbered chain — it isn't a step you perform in sequence,
// it's a check that Transform already runs automatically (see the backend
// gate in transform_mapping.py's _run_transform_prechecks), plus a
// standalone tool you can reach any time. Rendering it as step 3 of 4
// implied a manual hop between Mapping and Outputs that isn't how the
// platform actually works, so it's shown separately below instead.
const STEPS = [
  { key: 'md',      path: '/message-descriptions', label: 'Message Description', hint: 'Upload & approve a reference' },
  { key: 'mapping', path: '/mappings',              label: 'Mapping',             hint: 'Map fields & Transform (auto-validates)' },
  { key: 'outputs', path: '/outputs',               label: 'Outputs',             hint: 'View past results' },
];

const WorkflowSteps = ({ current }) => {
  const isValidatePage = current === 'validate';

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        gap: '0.4rem', flexWrap: 'wrap', marginBottom: '1.75rem'
      }}
    >
      {STEPS.map((step, i) => {
        const isActive = step.key === current;
        return (
          <div key={step.key} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Link to={step.path} style={{ textDecoration: 'none' }} title={step.hint}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                padding: '0.45rem 0.9rem', borderRadius: '999px',
                background: isActive ? 'rgba(102,126,234,0.18)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${isActive ? 'rgba(102,126,234,0.5)' : 'rgba(255,255,255,0.08)'}`,
                cursor: 'pointer', transition: 'background 0.2s, border-color 0.2s'
              }}>
                <span style={{
                  width: '20px', height: '20px', borderRadius: '50%',
                  background: isActive ? '#667eea' : 'rgba(255,255,255,0.08)',
                  color: isActive ? 'white' : '#6b7280',
                  fontSize: '0.7rem', fontWeight: '800',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0
                }}>
                  {i + 1}
                </span>
                <span style={{
                  color: isActive ? '#c7d2fe' : '#9ca3af',
                  fontWeight: isActive ? '700' : '500',
                  fontSize: '0.85rem', whiteSpace: 'nowrap'
                }}>
                  {step.label}
                </span>
              </div>
            </Link>
            {i < STEPS.length - 1 && (
              <ChevronRight size={14} color="#4b5563" style={{ flexShrink: 0 }} />
            )}
          </div>
        );
      })}

      {/* Not a numbered step — see comment above. Dashed border + a check
          icon instead of a number visually marks it as a side tool, not
          the next hop in the chain. */}
      <div style={{ width: '1px', height: '20px', background: 'rgba(255,255,255,0.1)', margin: '0 0.3rem' }} />
      <Link to="/validate" style={{ textDecoration: 'none' }}
        title="Check any file against a reference standard — also runs automatically before every Transform">
        <div style={{
          display: 'flex', alignItems: 'center', gap: '0.5rem',
          padding: '0.45rem 0.9rem', borderRadius: '999px',
          background: isValidatePage ? 'rgba(16,185,129,0.15)' : 'rgba(255,255,255,0.03)',
          border: `1px dashed ${isValidatePage ? 'rgba(16,185,129,0.5)' : 'rgba(255,255,255,0.12)'}`,
          cursor: 'pointer', transition: 'background 0.2s, border-color 0.2s'
        }}>
          <ShieldCheck size={14} color={isValidatePage ? '#10b981' : '#6b7280'} />
          <span style={{
            color: isValidatePage ? '#6ee7b7' : '#9ca3af',
            fontWeight: isValidatePage ? '700' : '500',
            fontSize: '0.85rem', whiteSpace: 'nowrap'
          }}>
            Validate a file
          </span>
        </div>
      </Link>
    </motion.div>
  );
};

export default WorkflowSteps;
