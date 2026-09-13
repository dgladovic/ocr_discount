import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Edit3, RotateCcw } from 'lucide-react';

import { API_BASE_URL } from '../constants/tables';
import ProductHero from '../components/canonical/ProductHero';
import ActiveOffersSection from '../components/canonical/ActiveOffersSection';
import LinkedStoreProducts from '../components/canonical/LinkedStoreProducts';
import PriceHistoryTable from '../components/canonical/PriceHistoryTable';
import EditOverrideModal from '../components/canonical/EditOverrideModal';

export default function CanonicalDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const fetchDetails = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/canonical-products/${id}/details`);
      if (!res.ok) throw new Error(`Status ${res.status}: Product details not found`);
      const json = await res.json();
      setDetails(json);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetails();
  }, [id]);

  const handleSaveOverride = async (payload) => {
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/canonical-products/${id}/override`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Failed to save override (Status ${res.status})`);
      setIsEditing(false);
      await fetchDetails();
    } catch (err) {
      alert(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRevertOverride = async () => {
    if (!window.confirm('Revert all overrides and unlock this product for AI updates?')) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/canonical-products/${id}/override`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error('Failed to revert override');
      await fetchDetails();
    } catch (err) {
      alert(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="page-container"><p>Loading details...</p></div>;
  if (error) return (
    <div className="page-container">
      <button onClick={() => navigate(-1)} className="outline back-btn"><ArrowLeft size={16} /> Back</button>
      <article style={{ borderColor: '#f87171' }}>Error: {error}</article>
    </div>
  );

  const canonical = details?.canonical || {};
  const activeOffers = details?.active_offers || [];
  const priceHistory = details?.price_history || [];

  return (
    <div className="page-container" style={{ maxWidth: '960px', margin: '0 auto', padding: '1rem' }}>
      {/* Top Navigation & Actions Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button onClick={() => navigate(-1)} className="outline" style={{ padding: '0.35rem 0.75rem', margin: 0 }}>
          <ArrowLeft size={16} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> Back
        </button>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button onClick={() => setIsEditing(true)} className="outline" style={{ padding: '0.35rem 0.75rem', margin: 0 }}>
            <Edit3 size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> Edit
          </button>
          {canonical.is_manually_edited && (
            <button
              onClick={handleRevertOverride}
              disabled={submitting}
              className="outline"
              style={{ padding: '0.35rem 0.75rem', margin: 0, borderColor: '#f87171', color: '#f87171' }}
            >
              <RotateCcw size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> Reset to AI
            </button>
          )}
        </div>
      </div>

      {/* Modular Sections */}
      <ProductHero canonical={canonical} />
      <ActiveOffersSection activeOffers={activeOffers} />
      <LinkedStoreProducts priceHistory={priceHistory} />
      <PriceHistoryTable priceHistory={priceHistory} />

      {/* Modal Dialog */}
      {isEditing && (
        <EditOverrideModal
          canonical={canonical}
          onSave={handleSaveOverride}
          onCancel={() => setIsEditing(false)}
          submitting={submitting}
        />
      )}
    </div>
  );
}