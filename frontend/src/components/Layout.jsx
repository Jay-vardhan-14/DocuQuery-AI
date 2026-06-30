/**
 * App layout with sidebar navigation.
 *
 * Wraps authenticated pages with a sidebar containing navigation links,
 * user info, and a logout button.
 */

import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  MessageSquare,
  FileText,
  Shield,
  LogOut,
  BarChart3,
} from 'lucide-react';

export default function Layout() {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const initials = user?.full_name
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || '??';

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="sidebar-logo-icon">D</div>
            <div>
              <div className="sidebar-logo-text">DocuQuery AI</div>
              <div className="sidebar-logo-version">v1.0.0</div>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <NavLink
            to="/chat"
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            <MessageSquare />
            Ask a Question
          </NavLink>

          <NavLink
            to="/documents"
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            <FileText />
            Documents
          </NavLink>

          {isAdmin && (
            <>
              <NavLink
                to="/admin"
                className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
              >
                <Shield />
                Admin Panel
              </NavLink>
              <NavLink
                to="/metrics"
                className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
              >
                <BarChart3 />
                Metrics
              </NavLink>
            </>
          )}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="sidebar-avatar">{initials}</div>
            <div className="sidebar-user-info">
              <div className="sidebar-user-name">{user?.full_name}</div>
              <div className="sidebar-user-role">{user?.role}</div>
            </div>
            <button
              className="sidebar-logout"
              onClick={handleLogout}
              title="Sign out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <div className="page-container">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
