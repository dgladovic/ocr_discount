import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { 
  Flame, Search, Tag, Calendar, FileText, ArrowUpDown, 
  ExternalLink, CheckCircle, RefreshCw 
} from 'lucide-react';
import { API_BASE_URL } from '../constants/tables';

export default function ActiveOffersPage() {
  const [offers, setOffers] = useState([]);
  const [retailers, setRetailers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedRetailer, setSelectedRetailer] = useState('');
  const [minDiscount, setMinDiscount] = useState('');
  const [sortBy, setSortBy] = useState('discount_desc');

  const navigate = useNavigate();

  const fetchRetailers = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/retailers`);
      if (res.ok) setRetailers(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  const fetchActiveOffers = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        sort_by: sortBy,
        limit: 60,
      });
      if (searchTerm.trim()) params.append('search', searchTerm.trim());
      if (selectedRetailer) params.append('retailer_code', selectedRetailer);
      if (minDiscount) params.append('min_discount', minDiscount);

      const res = await fetch(`${API_BASE_URL}/active-offers?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load offers`);
      const json = await res.json();
      setOffers(json.items || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRetailers();
  }, []);

  useEffect(() => {
    fetchActiveOffers();
  }, [selectedRetailer, minDiscount, sortBy]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchActiveOffers();
  };

  const buildAssetUrl = (url) => {
    if (!url) return null;
    const normalized = String(url).replace(/\\/g, '/');
    return normalized.startsWith('http') ? normalized : `${API_BASE_URL}/${normalized.replace(/^\/+/, '')}`;
  };

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.6rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Flame style={{ color: '#ef4444' }} /> Current Flyer Offers
          </h1>
          <p style={{ opacity: 0.7, margin: '0.2rem 0 0 0', fontSize: '0.85rem' }}>
            Live promotional deals extracted from active supermarket flyers
          </p>
        </div>
        <button onClick={fetchActiveOffers} disabled={loading} className="outline" style={{ padding: '0.4rem 0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh Deals
        </button>
      </div>

      {/* Filter Bar */}
      <form onSubmit={handleSearchSubmit} style={{
        background: 'var(--pico-card-background-color)',
        padding: '1rem',
        borderRadius: '12px',
        marginBottom: '1.5rem',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
        gap: '0.8rem',
        alignItems: 'center'
      }}>
        <div style={{ position: 'relative' }}>
          <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', opacity: 0.5 }} />
          <input
            type="text"
            placeholder="Search offer or brand..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ paddingLeft: '2.2rem', margin: 0, fontSize: '0.85rem' }}
          />
        </div>

        <select
          value={selectedRetailer}
          onChange={(e) => setSelectedRetailer(e.target.value)}
          style={{ margin: 0, fontSize: '0.85rem' }}
        >
          <option value="">All Retailers</option>
          {retailers.map((r) => (
            <option key={r.id} value={r.code}>{r.name}</option>
          ))}
        </select>

        <select
          value={minDiscount}
          onChange={(e) => setMinDiscount(e.target.value)}
          style={{ margin: 0, fontSize: '0.85rem' }}
        >
          <option value="">Any Discount</option>
          <option value="15">≥ 15% OFF</option>
          <option value="25">≥ 25% OFF</option>
          <option value="33">≥ 33% OFF</option>
          <option value="50">≥ 50% OFF (Half Price)</option>
        </select>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          style={{ margin: 0, fontSize: '0.85rem' }}
        >
          <option value="discount_desc">Highest Discount %</option>
          <option value="price_asc">Lowest Price (€)</option>
          <option value="newest">Ending Soonest</option>
        </select>

        {(searchTerm || selectedRetailer || minDiscount) && (
          <button
            type="button"
            className="outline"
            onClick={() => { setSearchTerm(''); setSelectedRetailer(''); setMinDiscount(''); }}
            style={{ margin: 0, padding: '0.4rem', fontSize: '0.8rem' }}
          >
            Clear
          </button>
        )}
      </form>

      {/* Grid of Offers */}
      {loading ? (
        <p>Loading live offers...</p>
      ) : error ? (
        <article style={{ borderColor: '#f87171', color: '#f87171' }}>Error: {error}</article>
      ) : offers.length === 0 ? (
        <p style={{ opacity: 0.6 }}>No active offers match your current criteria.</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1.2rem' }}>
          {offers.map((offer) => {
            const imgUrl = buildAssetUrl(offer.cropped_image_path);
            const pdfUrl = buildAssetUrl(offer.flyer_pdf_url);

            return (
              <div
                key={offer.offer_id}
                style={{
                  background: 'var(--pico-card-background-color)',
                  borderRadius: '12px',
                  border: '1px solid rgba(255,255,255,0.08)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  overflow: 'hidden',
                }}
              >
                <div style={{ padding: '1.2rem' }}>
                  {/* Retailer & Discount Badge */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.8rem' }}>
                    <span className="badge" style={{ fontWeight: 600 }}>{offer.retailer_name}</span>
                    {offer.discount_percent ? (
                      <span className="badge" style={{ background: '#ef4444', color: '#fff', fontWeight: 700 }}>
                        -{Math.round(offer.discount_percent)}%
                      </span>
                    ) : (
                      <span className="badge" style={{ background: '#2563eb', color: '#fff' }}>
                        {offer.offer_type || 'SPECIAL'}
                      </span>
                    )}
                  </div>

                  {/* Cropped Image */}
                  <div style={{ height: '140px', background: 'rgba(0,0,0,0.25)', borderRadius: '8px', marginBottom: '0.8rem', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                    {imgUrl ? (
                      <img src={imgUrl} alt={offer.product_name_raw} style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }} onError={(e) => { e.target.style.display = 'none'; }} />
                    ) : (
                      <span style={{ opacity: 0.4, fontSize: '0.8rem' }}>No Cropped Image</span>
                    )}
                  </div>

                  {/* Product Details */}
                  <h3 style={{ fontSize: '1rem', margin: '0 0 0.4rem 0', lineHeight: 1.3 }}>{offer.product_name_raw}</h3>
                  <p style={{ opacity: 0.7, fontSize: '0.8rem', margin: 0 }}>
                    {offer.brand && <strong>{offer.brand} • </strong>}
                    {offer.unit_size ? `${offer.unit_size} ${offer.unit_measurement || ''}` : offer.category}
                  </p>

                  {/* Price Row */}
                  <div style={{ marginTop: '0.8rem', display: 'flex', alignItems: 'baseline', gap: '0.6rem' }}>
                    <span style={{ fontSize: '1.8rem', fontWeight: 800, color: '#4ade80' }}>
                      €{Number(offer.current_price).toFixed(2)}
                    </span>
                    {offer.original_price && (
                      <span style={{ fontSize: '1.1rem', textDecoration: 'line-through', opacity: 0.5 }}>
                        €{Number(offer.original_price).toFixed(2)}
                      </span>
                    )}
                  </div>

                  {/* Base Price (Grundpreis) */}
                  {offer.base_price && (
                    <small style={{ opacity: 0.6, fontSize: '0.75rem', display: 'block', marginTop: '0.2rem' }}>
                      €{Number(offer.base_price).toFixed(2)} / {offer.base_price_unit}
                    </small>
                  )}

                  {/* Validity */}
                  <div style={{ marginTop: '0.8rem', fontSize: '0.75rem', opacity: 0.6, display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <Calendar size={13} />
                    <span>Valid until: {offer.week_end}</span>
                  </div>
                </div>

                {/* Footer Buttons */}
                <div style={{ padding: '0.8rem 1.2rem', background: 'rgba(0,0,0,0.15)', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  {offer.canonical_id ? (
                    <Link to={`/canonical/${offer.canonical_id}`} style={{ fontSize: '0.8rem', color: '#4ade80', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                      Price History <ExternalLink size={12} />
                    </Link>
                  ) : (
                    <Link to={`/products/${offer.store_product_id}`} style={{ fontSize: '0.8rem', opacity: 0.8, textDecoration: 'none' }}>
                      Store Item
                    </Link>
                  )}

                  {pdfUrl && (
                    <a href={pdfUrl} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.75rem', color: '#93c5fd', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                      <FileText size={13} /> View Flyer
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}