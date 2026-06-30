/**
 * Documents page — upload, view, and manage documents.
 *
 * Features:
 *   - Document list with access level badges and status indicators
 *   - Upload modal with drag-and-drop zone
 *   - Delete confirmation
 *   - Admin-only upload/delete actions
 */

import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { documentsApi } from '../api/client';
import toast from 'react-hot-toast';
import {
  Upload,
  FileText,
  Trash2,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Clock,
  XCircle,
  X,
} from 'lucide-react';

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

const STATUS_ICONS = {
  completed: <CheckCircle size={14} />,
  processing: <RefreshCw size={14} className="spin-slow" />,
  pending: <Clock size={14} />,
  failed: <XCircle size={14} />,
};

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const { isAdmin } = useAuth();

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const docs = await documentsApi.list();
      setDocuments(docs);
    } catch (err) {
      toast.error('Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const handleDelete = async (docId, title) => {
    if (!confirm(`Delete "${title}" and all its chunks? This cannot be undone.`)) {
      return;
    }
    try {
      await documentsApi.remove(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      toast.success(`"${title}" deleted successfully`);
    } catch (err) {
      toast.error('Delete failed: ' + err.message);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Documents</h1>
          <p className="page-subtitle">
            {documents.length} document{documents.length !== 1 ? 's' : ''} in your corpus
          </p>
        </div>
        {isAdmin && (
          <button
            className="btn btn-primary"
            onClick={() => setShowUpload(true)}
          >
            <Upload size={16} />
            Upload Document
          </button>
        )}
      </div>

      {/* Document table */}
      <div className="card">
        <div className="table-container">
          {loading ? (
            <div className="empty-state">
              <div className="spinner" style={{ margin: '0 auto' }} />
              <p style={{ marginTop: 12 }}>Loading documents…</p>
            </div>
          ) : documents.length === 0 ? (
            <div className="empty-state">
              <FileText size={40} />
              <p>No documents found.</p>
              {isAdmin && (
                <p style={{ fontSize: 12, marginTop: 4 }}>
                  Upload your first document to get started.
                </p>
              )}
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Access Level</th>
                  <th>Status</th>
                  <th>Chunks</th>
                  <th>Size</th>
                  <th>Uploaded</th>
                  {isAdmin && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <FileText size={16} style={{ color: 'var(--accent-purple)', flexShrink: 0 }} />
                        <div>
                          <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                            {doc.title}
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            {doc.filename}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className={`badge badge-${doc.access_level}`}>
                        {doc.access_level}
                      </span>
                    </td>
                    <td>
                      <span
                        className={`badge badge-${doc.processing_status}`}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
                      >
                        {STATUS_ICONS[doc.processing_status]}
                        {doc.processing_status}
                      </span>
                    </td>
                    <td>{doc.total_chunks}</td>
                    <td>{formatBytes(doc.file_size_bytes)}</td>
                    <td>{formatDate(doc.created_at)}</td>
                    {isAdmin && (
                      <td>
                        <button
                          className="btn btn-danger btn-sm btn-icon"
                          onClick={() => handleDelete(doc.id, doc.title)}
                          title="Delete"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Upload Modal */}
      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onUploaded={() => {
            setShowUpload(false);
            loadDocuments();
          }}
        />
      )}
    </div>
  );
}

function UploadModal({ onClose, onUploaded }) {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState('');
  const [accessLevel, setAccessLevel] = useState('public');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) {
      setFile(dropped);
      if (!title) setTitle(dropped.name.replace(/\.[^.]+$/, ''));
    }
  };

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected) {
      setFile(selected);
      if (!title) setTitle(selected.name.replace(/\.[^.]+$/, ''));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !title) return;
    setError('');
    setUploading(true);
    try {
      await documentsApi.upload(file, title, accessLevel);
      toast.success('Document uploaded successfully!');
      onUploaded();
    } catch (err) {
      const msg = err.message || 'Upload failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 className="modal-title">Upload Document</h2>
          <button className="btn btn-icon" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {error && <div className="auth-error" style={{ marginBottom: 16 }}>{error}</div>}

        <form onSubmit={handleSubmit}>
          {/* Drop zone */}
          <div
            className={`dropzone${dragActive ? ' active' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
            <div className="dropzone-icon">
              <Upload size={28} />
            </div>
            {file ? (
              <div className="dropzone-text" style={{ color: 'var(--accent-green)' }}>
                {file.name} ({formatBytes(file.size)})
              </div>
            ) : (
              <>
                <div className="dropzone-text">Drop a file here or click to browse</div>
                <div className="dropzone-hint">PDF or DOCX, max 20MB</div>
              </>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 20 }}>
            <div className="form-group">
              <label className="form-label" htmlFor="doc-title">Document Title</label>
              <input
                id="doc-title"
                className="form-input"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Enter a descriptive title"
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="doc-access">Access Level</label>
              <select
                id="doc-access"
                className="form-select"
                value={accessLevel}
                onChange={(e) => setAccessLevel(e.target.value)}
              >
                <option value="public">Public — All users</option>
                <option value="internal">Internal — Employees and above</option>
                <option value="confidential">Confidential — Managers and above</option>
                <option value="restricted">Restricted — Admins only</option>
              </select>
            </div>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={!file || !title || uploading}
            >
              {uploading ? (
                <>
                  <span className="spinner" />
                  Uploading…
                </>
              ) : (
                <>
                  <Upload size={16} />
                  Upload & Process
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
