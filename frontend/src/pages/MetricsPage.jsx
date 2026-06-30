/**
 * Metrics dashboard page — system analytics and KPIs.
 *
 * Features:
 *   - Metric cards: total queries, avg latency, docs, chunks, cost
 *   - Queries-per-day bar chart (Recharts)
 *   - Top queried documents list
 */

import { useState, useEffect } from 'react';
import { adminApi } from '../api/client';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import {
  BarChart3,
  Clock,
  FileText,
  Layers,
  DollarSign,
  Zap,
  TrendingUp,
} from 'lucide-react';

/**
 * Custom tooltip for the queries-per-day chart.
 * Styled to match the dark glassmorphism design system.
 */
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: 'rgba(15, 23, 42, 0.95)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: 8,
        padding: '8px 12px',
        fontSize: 12,
        color: '#f1f5f9',
        boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
      }}
    >
      <div style={{ color: '#94a3b8', marginBottom: 2 }}>{label}</div>
      <div style={{ fontWeight: 600 }}>
        {payload[0].value} {payload[0].value === 1 ? 'query' : 'queries'}
      </div>
    </div>
  );
}

export default function MetricsPage() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMetrics();
  }, []);

  const loadMetrics = async () => {
    try {
      const data = await adminApi.getMetrics();
      setMetrics(data);
    } catch (err) {
      /* metrics load failure handled by empty state below */
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="empty-state" style={{ paddingTop: 120 }}>
        <div className="spinner" style={{ margin: '0 auto' }} />
        <p style={{ marginTop: 12 }}>Loading metrics…</p>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="empty-state">
        <BarChart3 size={40} />
        <p>Failed to load metrics.</p>
      </div>
    );
  }

  /* Format date labels for the chart — show "Jun 5" style */
  const chartData = metrics.queries_per_day.map((d) => ({
    ...d,
    label: new Date(d.date + 'T00:00:00').toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    }),
  }));

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">System Metrics</h1>
          <p className="page-subtitle">Last 30 days analytics</p>
        </div>
      </div>

      {/* KPI cards */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-icon purple">
            <Zap size={20} />
          </div>
          <div className="metric-value">{metrics.total_queries_30d.toLocaleString()}</div>
          <div className="metric-label">Total Queries</div>
        </div>

        <div className="metric-card">
          <div className="metric-icon blue">
            <Clock size={20} />
          </div>
          <div className="metric-value">{metrics.avg_latency_ms.toFixed(0)}<span style={{ fontSize: 14, color: 'var(--text-muted)' }}>ms</span></div>
          <div className="metric-label">Avg Latency</div>
        </div>

        <div className="metric-card">
          <div className="metric-icon green">
            <FileText size={20} />
          </div>
          <div className="metric-value">{metrics.total_documents}</div>
          <div className="metric-label">Documents</div>
        </div>

        <div className="metric-card">
          <div className="metric-icon cyan">
            <Layers size={20} />
          </div>
          <div className="metric-value">{metrics.total_chunks.toLocaleString()}</div>
          <div className="metric-label">Total Chunks</div>
        </div>

        <div className="metric-card">
          <div className="metric-icon amber">
            <DollarSign size={20} />
          </div>
          <div className="metric-value">${metrics.cost_30d_usd.toFixed(2)}</div>
          <div className="metric-label">API Cost (30d)</div>
        </div>
      </div>

      <div className="grid-2">
        {/* Queries per day chart — Recharts */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <TrendingUp size={16} style={{ display: 'inline', marginRight: 8, verticalAlign: -2 }} />
              Queries Per Day
            </span>
          </div>
          <div className="card-body">
            {chartData.length === 0 ? (
              <div className="empty-state" style={{ padding: 20 }}>
                <p>No query data yet.</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.9} />
                      <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.7} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.04)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 10, fill: '#64748b' }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
                    tickLine={false}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: '#64748b' }}
                    axisLine={false}
                    tickLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                  <Bar
                    dataKey="count"
                    fill="url(#barGradient)"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={40}
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Top queried documents */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <FileText size={16} style={{ display: 'inline', marginRight: 8, verticalAlign: -2 }} />
              Top Queried Documents
            </span>
          </div>
          <div className="card-body">
            {metrics.top_queried_documents.length === 0 ? (
              <div className="empty-state" style={{ padding: 20 }}>
                <p>No query data yet.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {metrics.top_queried_documents.map((doc, i) => {
                  const maxCount = metrics.top_queried_documents[0].query_count;
                  const pct = (doc.query_count / maxCount) * 100;
                  return (
                    <div key={i}>
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          marginBottom: 4,
                          fontSize: 13,
                        }}
                      >
                        <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                          {doc.title}
                        </span>
                        <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                          {doc.query_count}
                        </span>
                      </div>
                      <div
                        style={{
                          height: 6,
                          background: 'var(--bg-input)',
                          borderRadius: 3,
                          overflow: 'hidden',
                        }}
                      >
                        <div
                          style={{
                            height: '100%',
                            width: `${pct}%`,
                            background: 'var(--gradient-primary)',
                            borderRadius: 3,
                            transition: 'width 0.5s ease',
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
