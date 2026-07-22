import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import MappingWorkspacePage from './pages/MappingWorkspacePage';
import ConfigPage from './pages/ConfigPage';
import ConsommationPage from './pages/ConsommationPage';
import OutputsPage from './pages/OutputsPage';
import MessageDescriptionPage from './pages/MessageDescriptionPage';
import ValidatePage from './pages/ValidatePage';
import AdminPage from './pages/AdminPage';
import AuditLogPage from './pages/AuditLogPage';

// ── Protected route: must be authenticated ────────────────────────────────────
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
      Loading...
    </div>
  );
  return isAuthenticated ? children : <Navigate to="/login" />;
};

// ── Admin route: must be authenticated AND is_admin = true ───────────────────
const AdminRoute = ({ children }) => {
  const { isAuthenticated, loading, user } = useAuth();
  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
      Loading...
    </div>
  );
  if (!isAuthenticated) return <Navigate to="/login" />;
  if (!user?.is_admin) return <Navigate to="/dashboard" />;
  return children;
};

function App() {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/login"    element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected routes — any authenticated user */}
          <Route path="/dashboard"           element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/mappings"            element={<ProtectedRoute><MappingWorkspacePage /></ProtectedRoute>} />
          <Route path="/config"              element={<ProtectedRoute><ConfigPage /></ProtectedRoute>} />
          <Route path="/pipeline"            element={<ProtectedRoute><ConsommationPage /></ProtectedRoute>} />
          <Route path="/outputs"             element={<ProtectedRoute><OutputsPage /></ProtectedRoute>} />
          <Route path="/message-descriptions" element={<ProtectedRoute><MessageDescriptionPage /></ProtectedRoute>} />
          <Route path="/validate"            element={<ProtectedRoute><ValidatePage /></ProtectedRoute>} />

          {/* Legacy redirects: standalone transform pages merged into /mappings
              (Mapping Workspace's "Transform" button, auto-detects direction) */}
          <Route path="/upload" element={<Navigate to="/mappings" />} />
          <Route path="/transform" element={<Navigate to="/mappings" />} />
          <Route path="/generate-mt" element={<Navigate to="/mappings" />} />

          {/* Admin-only routes */}
          <Route path="/admin" element={<AdminRoute><AdminPage /></AdminRoute>} />
          <Route path="/audit-log" element={<AdminRoute><AuditLogPage /></AdminRoute>} />

          {/* Default redirect */}
          <Route path="/" element={<Navigate to="/dashboard" />} />
        </Routes>
        <ToastContainer position="top-right" autoClose={3000} hideProgressBar={false}
          newestOnTop closeOnClick rtl={false} pauseOnFocusLoss draggable pauseOnHover />
      </AuthProvider>
    </Router>
  );
}

export default App;