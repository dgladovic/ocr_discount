import React from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';

export default function IngestionStatusView({ data }) {
  if (!data) return null;

  const { latest_by_retailer = [], recent_logs = [] } = data;

  return (
    <div>
      {/* Latest Run Cards Per Retailer */}
      <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem', opacity: 0.8 }}>Latest Run Per Retailer</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        {latest_by_retailer.map((log) => {
          const isSuccess = log.status === 'SUCCESS';
          const retailerCode = (log.retailer_code || 'unknown').toUpperCase();

          return (
            <article
              key={log.id || log.retailer_code}
              style={{
                padding: '1rem',
                borderRadius: '0.75rem',
                borderLeft: `4px solid ${isSuccess ? '#4ade80' : '#f87171'}`,
                background: 'var(--pico-card-background-color)',
                margin: 0,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                {isSuccess ? (
                  <CheckCircle2 size={18} style={{ color: '#4ade80', flexShrink: 0 }} />
                ) : (
                  <XCircle size={18} style={{ color: '#f87171', flexShrink: 0 }} />
                )}
                <strong style={{ fontSize: '1rem' }}>{retailerCode}</strong>
              </div>

              <div style={{ fontSize: '0.85rem', opacity: 0.8, margin: '0.4rem 0' }}>
                <strong>{log.offer_count ?? 0}</strong> offers extracted across <strong>{log.page_count ?? 0}</strong> pages
              </div>

              <small style={{ opacity: 0.6, fontSize: '0.75rem' }}>
                File: <code>{log.file_name}</code>
              </small>
              <br />
              <small style={{ opacity: 0.5, fontSize: '0.75rem' }}>
                {log.attempted_at ? new Date(log.attempted_at).toLocaleString() : '—'}
              </small>

              {log.error_message && (
                <details style={{ marginTop: '0.5rem' }}>
                  <summary style={{ fontSize: '0.75rem', color: '#f87171', cursor: 'pointer' }}>Error Details</summary>
                  <pre style={{ fontSize: '0.7rem', whiteSpace: 'pre-wrap', margin: '0.25rem 0 0' }}>{log.error_message}</pre>
                </details>
              )}
            </article>
          );
        })}
      </div>

      {/* Recent Ingestion Logs Table */}
      <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem', opacity: 0.8 }}>Recent Ingestion Logs</h3>
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Retailer</th>
              <th>File Name</th>
              <th>Status</th>
              <th>Pages</th>
              <th>Offers Extracted</th>
              <th>Attempted At</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {recent_logs.map((log, idx) => {
              const isSuccess = log.status === 'SUCCESS';
              return (
                <tr key={log.id || idx}>
                  <td><strong>{(log.retailer_code || '—').toUpperCase()}</strong></td>
                  <td><code style={{ fontSize: '0.75rem' }}>{log.file_name || '—'}</code></td>
                  <td>
                    <span
                      className={`badge ${isSuccess ? 'badge-yes' : ''}`}
                      style={!isSuccess ? { background: 'rgba(248,113,113,0.15)', color: '#f87171' } : {}}
                    >
                      {log.status}
                    </span>
                  </td>
                  <td>{log.page_count ?? '—'}</td>
                  <td><strong>{log.offer_count ?? '—'}</strong></td>
                  <td style={{ whiteSpace: 'nowrap', fontSize: '0.8rem' }}>
                    {log.attempted_at ? new Date(log.attempted_at).toLocaleString() : '—'}
                  </td>
                  <td style={{ maxWidth: '260px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.75rem', color: '#f87171' }}>
                    {log.error_message || '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}