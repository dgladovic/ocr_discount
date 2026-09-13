import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { 
  BookmarkCheck, Flame, Trash2, ExternalLink, Calendar, 
  Tag, RefreshCw, ShoppingBag, ArrowRight, FileText 
} from 'lucide-react';
import { API_BASE_URL } from '../constants/tables';
import { buildAssetUrl, isFlyerAvailable } from '../utils/formatters';

export default function WatchlistPage() {
  const [data, setData] = useState({ on_sale: [], no_deals: [], total_watched: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const fetchWatchlist = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/watchlist`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load watchlist`);
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWatchlist();
  }, []);

  const handleRemove = async (canonicalId, displayName) => {
    if (!window.confirm(`Remove "${displayName}" from your watchlist?`)) return;

    try {
      const res = await fetch(`${API_BASE_URL}/watchlist/${canonicalId}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error('Failed to remove item');
      // Instant optimistic UI update
      setData((prev) => ({
        ...prev,
        total_watched: prev.total_watched - 1,
        on_sale: prev.on_sale.filter((item) => item.canonical_id !== canonicalId),
        no_deals: prev.no_deals.filter((item) => item.canonical_id !== canonicalId),
      }));
    } catch (err) {
      alert(err.message);
    }
  };

  if (loading) return <div className="page-container"><p>Checking flyer deals for your watched items...</p></div>;
  if (error) return <article style={{ borderColor: '#f87171' }}>Error: {error}</article>;

  const { on_sale = [], no_deals = [], total_watched = 0 } = data;

  return (
    <div className="page-container" style={{ maxWidth: '1000px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.6rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <BookmarkCheck style={{ color: '#4ade80' }} /> My Product Watchlist
          </h1>
          <p style={{ opacity: 0.7, margin: '0.2rem 0 0 0', fontSize: '0.85rem' }}>
            Track your favorite items and check real-time flyer discounts across all supermarket chains
          </p>
        </div>
        <button onClick={fetchWatchlist} disabled={loading} className="outline" style={{ padding: '0.4rem 0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Check Deals
        </button>
      </div>

      {/* Summary KPI Banner */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <article style={{ margin: 0, padding: '1rem', textAlign: 'center' }}>
          <small style={{ opacity: 0.6 }}>Watched Products</small>
          <h2 style={{ margin: '0.2rem 0 0', fontSize: '2rem' }}>{total_watched}</h2>
        </article>

        <article style={{ margin: 0, padding: '1rem', textAlign: 'center', borderLeft: '4px solid #ef4444' }}>
          <small style={{ opacity: 0.8, color: '#ef4444', fontWeight: 600 }}>🔥 Deals Active This Week</small>
          <h2 style={{ margin: '0.2rem 0 0', fontSize: '2rem', color: '#ef4444' }}>{on_sale.length}</h2>
        </article>

        <article style={{ margin: 0, padding: '1rem', textAlign: 'center' }}>
          <small style={{ opacity: 0.6 }}>Regular Price / No Deals</small>
          <h2 style={{ margin: '0.2rem 0 0', fontSize: '2rem', opacity: 0.7 }}>{no_deals.length}</h2>
        </article>
      </div>

      {total_watched === 0 ? (
        <article style={{ textAlign: 'center', padding: '3rem 1rem' }}>
          <ShoppingBag size={48} style={{ opacity: 0.3, marginBottom: '1rem' }} />
          <h3>Your watchlist is empty</h3>
          <p style={{ opacity: 0.7 }}>Browse the master catalog or active flyer deals and click the bookmark button to watch products.</p>
          <Link to="/catalog" className="button" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
            Browse Catalog <ArrowRight size={16} />
          </Link>
        </article>
      ) : (
        <>
          {/* 1. ON SALE SECTION */}
          <section style={{ marginBottom: '3rem' }}>
            <h2 style={{ fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#ef4444' }}>
              <Flame size={22} /> On Sale This Week ({on_sale.length})
            </h2>

            {on_sale.length === 0 ? (
              <p style={{ opacity: 0.6, fontSize: '0.9rem' }}>None of your watched items have active flyer promotions this week.</p>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))', gap: '1.2rem' }}>
                {on_sale.map((item) => {
                  const masterImg = buildAssetUrl(item.image_url);
                  const bestOffer = item.active_offers[0]; // first active promotion

                  return (
                    <article
                      key={item.canonical_id}
                      style={{
                        margin: 0,
                        padding: '1.2rem',
                        border: '1px solid #ef4444',
                        borderRadius: '12px',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        {/* Top badges */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
                          <span className="badge">{bestOffer.retailer_name}</span>
                          {item.best_discount_percent && (
                            <span className="badge" style={{ background: '#ef4444', color: '#fff', fontWeight: 700 }}>
                              -{Math.round(item.best_discount_percent)}% OFF
                            </span>
                          )}
                        </div>

                        {/* Image & Title */}
                        <div style={{ display: 'flex', gap: '0.8rem', alignItems: 'center', marginBottom: '0.8rem' }}>
                          <div style={{ width: '60px', height: '60px', borderRadius: '6px', overflow: 'hidden', background: 'rgba(0,0,0,0.1)', flexShrink: 0 }}>
                            {masterImg ? (
                              <img src={masterImg} alt={item.display_name} style={{ width: '100%', height: '100%', objectFit: 'contain' }} onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                            ) : null}
                          </div>
                          <div>
                            <h3 style={{ fontSize: '1rem', margin: '0 0 0.2rem 0', lineHeight: 1.2 }}>{item.display_name}</h3>
                            <small style={{ opacity: 0.6 }}>{item.brand ? `${item.brand} • ` : ''}{item.unit_size} {item.unit_measurement || ''}</small>
                          </div>
                        </div>

                        {/* Price Display */}
                        <div style={{ margin: '0.6rem 0', display: 'flex', alignItems: 'baseline', gap: '0.6rem' }}>
                          <span style={{ fontSize: '1.8rem', fontWeight: 800, color: '#4ade80' }}>
                            €{Number(item.best_current_price).toFixed(2)}
                          </span>
                          {bestOffer.original_price && (
                            <span className="big-old-price" style={{ fontSize: '1.1rem' }}>
                              €{Number(bestOffer.original_price).toFixed(2)}
                            </span>
                          )}
                        </div>

                        <small style={{ opacity: 0.7, display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <Calendar size={13} /> Valid until: {bestOffer.week_end}
                        </small>
                      </div>

                      {/* Footer Actions */}
                      <div style={{ marginTop: '1rem', paddingTop: '0.8rem', borderTop: '1px solid var(--pico-border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Link to={`/canonical/${item.canonical_id}`} style={{ fontSize: '0.85rem', color: '#4ade80', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          View All Deals ({item.active_offers.length}) <ExternalLink size={12} />
                        </Link>

                        <button
                          onClick={() => handleRemove(item.canonical_id, item.display_name)}
                          className="outline"
                          title="Remove from watchlist"
                          style={{ padding: '0.2rem 0.5rem', margin: 0, borderColor: '#f87171', color: '#f87171' }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>

          {/* 2. NO DEALS THIS WEEK SECTION */}
          <section>
            <h2 style={{ fontSize: '1.15rem', opacity: 0.8, marginBottom: '0.8rem' }}>
              Regular Price / No Active Promotions ({no_deals.length})
            </h2>

            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Category</th>
                    <th>Size</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {no_deals.map((item) => (
                    <tr key={item.canonical_id}>
                      <td>
                        <strong
                          onClick={() => navigate(`/canonical/${item.canonical_id}`)}
                          style={{ cursor: 'pointer', color: '#4ade80' }}
                        >
                          {item.display_name}
                        </strong>
                        {item.brand && <small style={{ opacity: 0.6, display: 'block' }}>Brand: {item.brand}</small>}
                      </td>
                      <td><span className="badge">{item.category}</span></td>
                      <td>{item.unit_size ? `${item.unit_size} ${item.unit_measurement || ''}` : '—'}</td>
                      <td><small style={{ opacity: 0.5 }}>Waiting for promo</small></td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.4rem' }}>
                          <button
                            onClick={() => navigate(`/canonical/${item.canonical_id}`)}
                            className="outline"
                            style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', margin: 0 }}
                          >
                            Price History
                          </button>
                          <button
                            onClick={() => handleRemove(item.canonical_id, item.display_name)}
                            className="outline"
                            style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', margin: 0, color: '#f87171', borderColor: '#f87171' }}
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}