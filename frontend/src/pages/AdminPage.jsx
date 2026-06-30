/**
 * Admin page — user management and audit log viewer.
 *
 * Features:
 *   - Users tab: list all users, update roles, toggle active status
 *   - Audit Logs tab: paginated audit log viewer
 */

import { useState, useEffect } from 'react';
import { adminApi } from '../api/client';
import toast from 'react-hot-toast';
import { Users, ScrollText, ChevronLeft, ChevronRight } from 'lucide-react';

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState('users');

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Admin Panel</h1>
          <p className="page-subtitle">Manage users and review audit logs</p>
        </div>
      </div>

      <div className="tabs">
        <button
          className={`tab${activeTab === 'users' ? ' active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          <Users size={14} style={{ display: 'inline', marginRight: 6 }} />
          Users
        </button>
        <button
          className={`tab${activeTab === 'audit' ? ' active' : ''}`}
          onClick={() => setActiveTab('audit')}
        >
          <ScrollText size={14} style={{ display: 'inline', marginRight: 6 }} />
          Audit Logs
        </button>
      </div>

      {activeTab === 'users' ? <UsersPanel /> : <AuditPanel />}
    </div>
  );
}

function UsersPanel() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const data = await adminApi.listUsers();
      setUsers(data);
    } catch (err) {
      toast.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const handleRoleChange = async (userId, newRole) => {
    try {
      const updated = await adminApi.updateUser(userId, { role: newRole });
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, ...updated } : u))
      );
      toast.success(`Role updated to ${newRole}`);
    } catch (err) {
      toast.error('Failed to update role: ' + err.message);
    }
  };

  const handleToggleActive = async (userId, currentActive) => {
    try {
      const updated = await adminApi.updateUser(userId, {
        is_active: !currentActive,
      });
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, ...updated } : u))
      );
      toast.success(`User ${!currentActive ? 'activated' : 'deactivated'}`);
    } catch (err) {
      toast.error('Failed to update status: ' + err.message);
    }
  };

  if (loading) {
    return (
      <div className="card">
        <div className="empty-state">
          <div className="spinner" style={{ margin: '0 auto' }} />
          <p style={{ marginTop: 12 }}>Loading users…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Joined</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                  {user.full_name}
                </td>
                <td>{user.email}</td>
                <td>
                  <select
                    className="form-select"
                    value={user.role}
                    onChange={(e) => handleRoleChange(user.id, e.target.value)}
                    style={{ padding: '4px 28px 4px 8px', fontSize: 12, minWidth: 110 }}
                  >
                    <option value="employee">Employee</option>
                    <option value="manager">Manager</option>
                    <option value="admin">Admin</option>
                  </select>
                </td>
                <td>
                  <span
                    className={`badge ${user.is_active ? 'badge-completed' : 'badge-failed'}`}
                  >
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td>{formatDate(user.created_at)}</td>
                <td>
                  <button
                    className={`btn btn-sm ${user.is_active ? 'btn-danger' : 'btn-secondary'}`}
                    onClick={() => handleToggleActive(user.id, user.is_active)}
                  >
                    {user.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AuditPanel() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const pageSize = 15;

  useEffect(() => {
    loadLogs();
  }, [page]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const data = await adminApi.getAuditLogs({ page, pageSize });
      setLogs(data);
    } catch (err) {
      toast.error('Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="card">
        <div className="empty-state">
          <div className="spinner" style={{ margin: '0 auto' }} />
          <p style={{ marginTop: 12 }}>Loading audit logs…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="table-container">
        {logs.length === 0 ? (
          <div className="empty-state">
            <ScrollText size={40} />
            <p>No audit log entries yet.</p>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Query</th>
                <th>User</th>
                <th>Latency</th>
                <th>Tokens</th>
                <th>Cost</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id}>
                  <td>
                    <div
                      style={{
                        maxWidth: 300,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        color: 'var(--text-primary)',
                      }}
                      title={log.query_text}
                    >
                      {log.query_text}
                    </div>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                    {log.user_id.slice(0, 8)}…
                  </td>
                  <td>{log.latency_ms}ms</td>
                  <td>{log.total_tokens_used || '—'}</td>
                  <td>
                    {log.estimated_cost_usd
                      ? `$${parseFloat(log.estimated_cost_usd).toFixed(4)}`
                      : '—'}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>{formatDate(log.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {logs.length > 0 && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            gap: 8,
            padding: 16,
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          <button
            className="btn btn-secondary btn-sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            <ChevronLeft size={14} />
            Previous
          </button>
          <span
            style={{
              display: 'flex',
              alignItems: 'center',
              fontSize: 13,
              color: 'var(--text-muted)',
              padding: '0 12px',
            }}
          >
            Page {page}
          </span>
          <button
            className="btn btn-secondary btn-sm"
            disabled={logs.length < pageSize}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
            <ChevronRight size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
