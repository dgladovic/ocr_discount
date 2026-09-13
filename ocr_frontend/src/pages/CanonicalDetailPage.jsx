import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, Edit3, RotateCcw, Bookmark, BookmarkCheck, Trash2 
} from 'lucide-react';

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
  const [deleting, setDeleting] = useState(false);

  // Watchlist state
  const [isWatched, setIsWatched] = useState(false);
  const [watchLoading, setWatchLoading] = useState(false);

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

  // Check if this canonical item is currently on the user's watchlist
  const checkWatchlistStatus = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/watchlist`);
      if (res.ok) {
        const data = await res.json();
        const allItems = [...(data.on_sale || []), ...(data.no_deals || [])];
        const exists = allItems.some((item) => item.canonical_id === id);
        setIsWatched(exists);
      }
    } catch (e) {
      console.error('Failed to check watchlist status:', e);
    }
  };

  useEffect(() => {
    fetchDetails();
    checkWatchlistStatus();
  }, [id]);

  // Toggle Watch / Bookmark with optimistic UI update and error rollback
  const handleToggleWatch = async () => {
    const nextState = !isWatched;
    setIsWatched(nextState);
    setWatchLoading(true);

    try {
      const method = nextState ? 'POST' : 'DELETE';
      const res = await fetch(`${API_BASE_URL}/watchlist/${id}`, { method });
      if (!res.ok) throw new Error(`Status ${res.status}: Failed to update watchlist`);
    } catch (err) {
      setIsWatched(!nextState); // Rollback on failure
      alert(`Watchlist Error: ${err.message}`);
    } finally {
      setWatchLoading(false);
    }
  };

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

  // Permanently delete canonical product
  const handleDeleteProduct = async () => {
    const confirmed = window.confirm(
      `Are you sure you want to permanently delete "${canonical.display_name}"?\n\nAll linked store products will be unlinked and this product will be removed from the catalog.`
    );
    if (!confirmed) return;

    setDeleting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/canonical-products/${id}`, {
        method: 'DELETE',
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}: Failed to delete product`);
      }

      // Navigate back to the catalog view
      navigate('/catalog');
    } catch (err) {
      alert(`Delete Error: ${err.message}`);
      setDeleting(false);
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.8rem' }}>
        <button onClick={() => navigate(-1)} className="outline" style={{ padding: '0.35rem 0.75rem', margin: 0 }}>
          <ArrowLeft size={16} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> Back
        </button>

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Watchlist Toggle Button */}
          <button
            onClick={handleToggleWatch}
            disabled={watchLoading || deleting}
            className="outline"
            style={{
              padding: '0.35rem 0.75rem',
              margin: 0,
              color: isWatched ? '#4ade80' : 'inherit',
              borderColor: isWatched ? '#4ade80' : 'var(--pico-border-color)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '0.85rem'
            }}
          >
            {isWatched ? <BookmarkCheck size={15} /> : <Bookmark size={15} />}
            {isWatched ? 'Watched' : 'Watch Product'}
          </button>

          {/* Edit Product Override */}
          <button 
            onClick={() => setIsEditing(true)} 
            disabled={deleting}
            className="outline" 
            style={{ padding: '0.35rem 0.75rem', margin: 0, fontSize: '0.85rem' }}
          >
            <Edit3 size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> Edit
          </button>

          {/* Revert AI Lock if edited */}
          {canonical.is_manually_edited && (
            <button
              onClick={handleRevertOverride}
              disabled={submitting || deleting}
              className="outline"
              style={{ padding: '0.35rem 0.75rem', margin: 0, borderColor: '#f87171', color: '#f87171', fontSize: '0.85rem' }}
            >
              <RotateCcw size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> Reset to AI
            </button>
          )}

          {/* Permanent Delete Button */}
          <button
            onClick={handleDeleteProduct}
            disabled={deleting}
            className="outline"
            title="Permanently delete this canonical product"
            style={{ 
              padding: '0.35rem 0.75rem', 
              margin: 0, 
              borderColor: '#f87171', 
              color: '#f87171', 
              fontSize: '0.85rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <Trash2 size={14} />
            {deleting ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>

      {/* Modular Product Sections */}
      <ProductHero canonical={canonical} />
      <ActiveOffersSection activeOffers={activeOffers} />
      <LinkedStoreProducts priceHistory={priceHistory} />
      <PriceHistoryTable priceHistory={priceHistory} />

      {/* Override Modal */}
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