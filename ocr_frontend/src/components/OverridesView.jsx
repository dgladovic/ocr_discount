import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Edit3, RotateCcw, ExternalLink } from 'lucide-react';
import { API_BASE_URL } from '../constants/tables';

export default function OverridesView() {
  const [overrides, setOverrides] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const fetchOverrides = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/product-overrides`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch product overrides`);
      const json = await res.json();
      setOverrides(json);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOverrides();
  }, []);

  const handleRevert = async (canonicalId) => {
    if (!window.confirm('Are you sure you want to revert all overrides for this product? AI pipeline updates will be unlocked.')) return;

    try {
      const res = await fetch(`${API_BASE_URL}/canonical-products/${canonicalId}/override`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error('Failed to revert override');
      await fetchOverrides();
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };

  if (loading) return <p>Loading overrides...</p>;
  if (error) return <article style={{ borderColor: 'var(--pico-del-color)' }}>Error: {error}</article>;
  if (overrides.length === 0) return <p style={{ opacity: 0.7 }}>No active product overrides recorded.</p>;

  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            <th>Canonical Product</th>
            <th>Overridden Field</th>
            <th>New Override Value</th>
            <th>Edited By</th>
            <th>Edited At</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {overrides.map((row) => (
            <tr key={row.id}>
              <td>
                <strong
                  onClick={() => navigate(`/canonical/${row.canonical_id}`)}
                  style={{ cursor: 'pointer', color: '#4ade80', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
                >
                  {row.canonical_display_name} <ExternalLink size={12} />
                </strong>
              </td>
              <td><code>{row.field_name}</code></td>
              <td><strong>{row.override_value}</strong></td>
              <td><small>{row.edited_by}</small></td>
              <td><small>{new Date(row.edited_at).toLocaleString()}</small></td>
              <td>
                <div style={{ display: 'flex', gap: '0.4rem' }}>
                  <button
                    onClick={() => navigate(`/canonical/${row.canonical_id}`)}
                    className="outline"
                    style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', margin: 0 }}
                  >
                    View
                  </button>
                  <button
                    onClick={() => handleRevert(row.canonical_id)}
                    className="outline"
                    style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', margin: 0, color: '#f87171', borderColor: '#f87171' }}
                  >
                    Revert
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}