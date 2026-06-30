/**
 * Application root component with routing.
 *
 * Routes:
 *   /login    — Login page (public)
 *   /register — Registration page (public)
 *   /chat     — Chat Q&A page (authenticated)
 *   /documents — Document management (authenticated)
 *   /admin    — Admin panel (admin only)
 *   /metrics  — Metrics dashboard (admin only)
 */

import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ChatPage from './pages/ChatPage';
import DocumentsPage from './pages/DocumentsPage';
import AdminPage from './pages/AdminPage';
import MetricsPage from './pages/MetricsPage';

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <div className="auth-page"><div className="spinner" /></div>;
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function AdminRoute({ children }) {
  const { isAdmin, loading } = useAuth();
  if (loading) return <div className="auth-page"><div className="spinner" /></div>;
  return isAdmin ? children : <Navigate to="/chat" replace />;
}

function PublicRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <div className="auth-page"><div className="spinner" /></div>;
  return isAuthenticated ? <Navigate to="/chat" replace /> : children;
}

export default function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
      <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />

      {/* Authenticated routes */}
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/admin" element={<AdminRoute><AdminPage /></AdminRoute>} />
        <Route path="/metrics" element={<AdminRoute><MetricsPage /></AdminRoute>} />
      </Route>

      {/* Default redirect */}
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}
