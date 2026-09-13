import React, { useState, useEffect } from 'react';
import { 
  Activity, CheckCircle2, XCircle, AlertTriangle, RefreshCw, 
  FileText, Calendar, Clock, Terminal, ChevronDown, ChevronUp, Layers 
} from 'lucide-react';
import { API_BASE_URL } from '../constants/tables';

export default function IngestionMonitoringPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [expandedLogId, setExpandedLogId] = useState(null);

  const fetchStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/ingestion-status`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load ingestion health`);
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const latestByRetailer = data?.latest_by_retailer || [];
  const recentLogs = data?.recent_logs || [];

  const filteredLogs = recentLogs.filter((log) => {
    if (statusFilter === 'ALL') return true;
    return log.status === statusFilter;
  });

  // Diagnostic helper: provides homelab recommendations based on error keywords
  const diagnoseError = (errorMessage) => {
    if (!errorMessage) return null;
    const msg = errorMessage.toLowerCase();

    if (msg.includes('rate limit') || msg.includes('429') || msg.includes('quota')) {
      return {
        title: 'Gemini API Rate Limit / Quota Exceeded',
        advice: 'Reduce batch size in pdf_extractor.py (e.g., 2 pages/batch) or wait for your hourly token window to reset.',
      };
    }
    if (msg.includes('poppler') || msg.includes('pdftoppm')) {
      return {
        title: 'Poppler Dependency Missing or Out of Memory',
        advice: 'Ensure poppler-utils is installed in the ingestion container. Allocate at least 2GB RAM to Docker.',
      };
    }
    if (msg.includes('json') || msg.includes('schema') || msg.includes('parse')) {
      return {
        title: 'Gemini Schema Validation Failure',
        advice: 'The AI model returned text that does not match FLYER_DATA_SCHEMA. Check system instructions in pdf_extractor.py.',
      };
    }
    if (msg.includes('403') || msg.includes('cloudflare') || msg.includes('captcha')) {
      return {
        title: 'Retailer Web Scraper Blocked',
        advice: 'Your homelab IP was flagged by Cloudflare/Akamai bot detection. Update user-agents or run via residential proxy.',
      };
    }
    return {
      title: 'General Execution Exception',
      advice: 'Inspect Docker container logs with: docker compose logs ingestion',
    };
  };

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.6rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Activity style={{ color: '#4ade80' }} /> Flyer Ingestion Health & Monitoring
          </h1>
          <p style={{ opacity: 0.7, margin: '0.2rem 0 0 0', fontSize: '0.85rem' }}>
            Real-time diagnostics for automated flyer discovery, vision extraction, and database loading
          </p>
        </div>
        <button onClick={fetchStatus} disabled={loading} className="outline" style={{ padding: '0.4rem 0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Check Status
        </button>
      </div>

      {loading && <p>Querying ingestion worker status...</p>}
      {error && <article style={{ borderColor: '#f87171', color: '#f87171' }}>Error: {error}</article>}

      {data && (
        <>
          {/* Retailer Flyer Status Cards */}
          <h2 style={{ fontSize: '1.15rem', marginBottom: '0.8rem' }}>Latest Weekly Processing by Chain</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '1rem', marginBottom: '2.5rem' }}>
            {latestByRetailer.map((retailer) => {
              const isOk = retailer.status === 'SUCCESS';
              return (
                <div
                  key={retailer.retailer_code}
                  style={{
                    background: 'var(--pico-card-background-color)',
                    borderRadius: '10px',
                    padding: '1.2rem',
                    borderLeft: `5px solid ${isOk ? '#4ade80' : '#f87171'}`,
                    borderTop: '1px solid rgba(255,255,255,0.05)',
                    borderRight: '1px solid rgba(255,255,255,0.05)',
                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <strong style={{ fontSize: '1.1rem' }}>{retailer.retailer_code.toUpperCase()}</strong>
                    <span
                      className="badge"
                      style={{
                        background: isOk ? 'rgba(74, 222, 128, 0.15)' : 'rgba(248, 113, 113, 0.15)',
                        color: isOk ? '#4ade80' : '#f87171',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.3rem',
                      }}
                    >
                      {isOk ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
                      {retailer.status}
                    </span>
                  </div>

                  <p style={{ margin: '0.4rem 0', fontSize: '0.9rem' }}>
                    Extracted <strong>{retailer.offer_count || 0}</strong> offers across <strong>{retailer.page_count || 0}</strong> pages
                  </p>

                  <div style={{ fontSize: '0.75rem', opacity: 0.6, display: 'flex', flexDirection: 'column', gap: '0.2rem', marginTop: '0.6rem' }}>
                    <span><Calendar size={11} style={{ marginRight: '4px' }} /> Last run: {retailer.attempted_at ? new Date(retailer.attempted_at).toLocaleString() : 'Never'}</span>
                    <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}><FileText size={11} style={{ marginRight: '4px' }} /> {retailer.file_name || 'No file recorded'}</span>
                  </div>

                  {retailer.error_message && (
                    <div style={{ marginTop: '0.8rem', padding: '0.5rem', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '6px', fontSize: '0.75rem', color: '#f87171' }}>
                      <strong>Last Error:</strong> {retailer.error_message.slice(0, 90)}...
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Historical Logs & Diagnostics */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.8rem' }}>
            <h2 style={{ fontSize: '1.15rem', margin: 0 }}>Detailed Ingestion Run Logs</h2>
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              {['ALL', 'SUCCESS', 'FAILED'].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className="outline"
                  style={{
                    padding: '0.2rem 0.6rem',
                    fontSize: '0.75rem',
                    background: statusFilter === st ? 'rgba(255,255,255,0.1)' : 'transparent',
                    margin: 0,
                  }}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Retailer</th>
                  <th>Status</th>
                  <th>Flyer PDF File</th>
                  <th>Offers</th>
                  <th>Pages</th>
                  <th>Timestamp</th>
                  <th>Diagnostics</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((log) => {
                  const isOk = log.status === 'SUCCESS';
                  const isExpanded = expandedLogId === log.id;
                  const diagnosis = log.error_message ? diagnoseError(log.error_message) : null;

                  return (
                    <React.Fragment key={log.id}>
                      <tr>
                        <td><strong>{log.retailer_code.toUpperCase()}</strong></td>
                        <td>
                          <span
                            className="badge"
                            style={{
                              background: isOk ? 'rgba(74, 222, 128, 0.15)' : 'rgba(248, 113, 113, 0.15)',
                              color: isOk ? '#4ade80' : '#f87171',
                            }}
                          >
                            {log.status}
                          </span>
                        </td>
                        <td><code style={{ fontSize: '0.75rem' }}>{log.file_name}</code></td>
                        <td><strong>{log.offer_count ?? 0}</strong></td>
                        <td>{log.page_count ?? '—'}</td>
                        <td style={{ fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                          {log.attempted_at ? new Date(log.attempted_at).toLocaleString() : '—'}
                        </td>
                        <td>
                          {log.error_message ? (
                            <button
                              onClick={() => setExpandedLogId(isExpanded ? null : log.id)}
                              className="outline"
                              style={{
                                padding: '0.2rem 0.5rem',
                                fontSize: '0.7rem',
                                borderColor: '#f87171',
                                color: '#f87171',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.2rem',
                                margin: 0,
                              }}
                            >
                              Inspect Error {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                            </button>
                          ) : (
                            <span style={{ color: '#4ade80', fontSize: '0.75rem' }}>Clean Run</span>
                          )}
                        </td>
                      </tr>

                      {/* Expandable Error Details Row */}
                      {isExpanded && log.error_message && (
                        <tr>
                          <td colSpan={7} style={{ background: 'rgba(0,0,0,0.3)', padding: '1.2rem' }}>
                            {diagnosis && (
                              <div style={{ marginBottom: '0.8rem', padding: '0.8rem', background: 'rgba(239,68,68,0.15)', borderLeft: '4px solid #ef4444', borderRadius: '4px' }}>
                                <strong style={{ color: '#fca5a5', display: 'block', marginBottom: '0.2rem' }}>
                                  <AlertTriangle size={14} style={{ verticalAlign: 'middle', marginRight: '6px' }} />
                                  Detected Issue: {diagnosis.title}
                                </strong>
                                <span style={{ fontSize: '0.8rem', opacity: 0.9 }}>{diagnosis.advice}</span>
                              </div>
                            )}

                            <strong style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.4rem' }}>
                              <Terminal size={14} /> Full Exception Stack Trace:
                            </strong>
                            <pre style={{
                              background: '#090d16',
                              padding: '0.8rem',
                              borderRadius: '6px',
                              fontSize: '0.75rem',
                              color: '#f87171',
                              overflowX: 'auto',
                              whiteSpace: 'pre-wrap',
                              margin: 0,
                            }}>
                              {log.error_message}
                            </pre>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}