import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { 
  ArrowLeft, Tag, Calendar, ShieldCheck, DollarSign, 
  ShoppingBag, ExternalLink, FileText 
} from 'lucide-react';
import { API_BASE_URL } from '../constants/tables';

export default function CanonicalDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDetails = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE_URL}/canonical-products/${id}/details`);
        if (!res.ok) throw new Error(`Canonical product details not found (Status ${res.status})`);
        const json = await res.json();
        setDetails(json);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchDetails();
  }, [id]);

  if (loading) return <div className="page-container"><p>Loading canonical product details & price history...</p></div>;
  if (error) return (
    <div className="page-container">
      <Link to="/" className="back-btn outline button"><ArrowLeft size={16} /> Back to Catalog</Link>
      <article style={{ borderColor: 'var(--pico-del-color)' }}>Error: {error}</article>
    </div>
  );

  const canonical = details?.canonical || {};
  const activeOffers = details?.active_offers || [];
  const priceHistory = details?.price_history || [];

  // Extract distinct linked store products per retailer with image URLs
  const linkedStoreProductsMap = {};
  priceHistory.forEach(item => {
    if (item.store_product_id && !linkedStoreProductsMap[item.store_product_id]) {
      const imgRaw = item.store_product_image_url ? String(item.store_product_image_url).replace(/\\/g, '/') : null;
      const imgFull = imgRaw 
        ? (imgRaw.startsWith('http') ? imgRaw : `${API_BASE_URL}/${imgRaw.replace(/^\//, '')}`)
        : null;

      linkedStoreProductsMap[item.store_product_id] = {
        id: item.store_product_id,
        name_raw: item.product_name_raw,
        retailer_name: item.retailer_name,
        retailer_code: item.retailer_code,
        image_url: imgFull
      };
    }
  });
  const linkedStoreProducts = Object.values(linkedStoreProductsMap);

  const rawUrl = canonical.image_url ? String(canonical.image_url).replace(/\\/g, '/') : null;
  const fullImageUrl = rawUrl
    ? (rawUrl.startsWith('http') ? rawUrl : `${API_BASE_URL}/${rawUrl.replace(/^\//, '')}`)
    : null;

  return (
    <div className="page-container" style={{ maxWidth: '1000px', margin: '0 auto', padding: '1.5rem' }}>
      <button onClick={() => navigate(-1)} className="back-btn outline" style={{ marginBottom: '1rem' }}>
        <ArrowLeft size={16} /> Back
      </button>

      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.5rem' }}>
        <span className="badge badge-yes">Canonical Master Item</span>
        <small style={{ opacity: 0.7 }}>{canonical.category} › {canonical.product_type}</small>
      </div>

      <h1 style={{ margin: '0.2rem 0 0.5rem 0' }}>{canonical.display_name}</h1>
      {canonical.brand && <p style={{ opacity: 0.7, margin: 0 }}>Brand: <strong>{canonical.brand}</strong></p>}

      {/* Hero Specifications Card */}
      <div className="product-hero" style={{ marginTop: '1.5rem' }}>
        <div className="hero-img-box">
          {fullImageUrl ? (
            <img src={fullImageUrl} alt={canonical.display_name} className="hero-img" />
          ) : (
            <div style={{ color: '#888' }}>No Master Image Available</div>
          )}
        </div>

        <div>
          <h3>Product Specifications</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1.5rem' }}>
            {canonical.unit_size && (
              <span className="attribute-pill">
                Size: {canonical.unit_size} {canonical.unit_measurement || ''}
              </span>
            )}
            {canonical.fat_percent && <span className="attribute-pill">Fat: {canonical.fat_percent}%</span>}
            {canonical.organic && <span className="attribute-pill">Organic: {canonical.organic}</span>}
          </div>

          <p style={{ fontSize: '0.85rem', opacity: 0.7 }}>
            <ShieldCheck size={14} style={{ verticalAlign: 'middle', marginRight: '6px' }} />
            Canonical Product ID: <code>{canonical.id}</code>
          </p>
        </div>
      </div>

      {/* 1. Currently Active Offers per Retailer */}
      <div style={{ marginTop: '2.5rem' }}>
        <h2 style={{ fontSize: '1.3rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Tag size={20} style={{ color: '#2e7d32' }} /> Currently Active Flyer Offers by Retailer
        </h2>

        {activeOffers.length === 0 ? (
          <p style={{ opacity: 0.7 }}>No active flyer deals available for this product this week.</p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
            {activeOffers.map((offer) => {
              const pdfFullUrl = offer.flyer_pdf_url ? `${API_BASE_URL}/${offer.flyer_pdf_url}` : null;

              return (
                <div
                  key={offer.offer_id}
                  style={{
                    background: 'var(--pico-card-background-color)',
                    border: '1px solid #2e7d32',
                    borderRadius: '10px',
                    padding: '1.2rem',
                    display: 'flex',
                    flexDirection: 'column',
                    justify: 'space-between'
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <strong style={{ fontSize: '1.1rem', color: '#2e7d32' }}>{offer.retailer_name}</strong>
                      {offer.discount_percent && (
                        <span className="badge" style={{ background: '#d32f2f', color: '#fff' }}>
                          -{offer.discount_percent}% OFF
                        </span>
                      )}
                    </div>

                    <div style={{ margin: '0.5rem 0' }}>
                      <span style={{ fontSize: '1.8rem', fontWeight: 800, color: '#2e7d32' }}>
                        €{Number(offer.current_price || 0).toFixed(2)}
                      </span>
                      {offer.original_price && (
                        <span className="big-old-price" style={{ fontSize: '1.1rem', marginLeft: '0.5rem' }}>
                          €{Number(offer.original_price).toFixed(2)}
                        </span>
                      )}
                    </div>

                    <p style={{ fontSize: '0.85rem', margin: '0.4rem 0', opacity: 0.8 }}>
                      <Calendar size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
                      {offer.week_start} to {offer.week_end}
                    </p>
                    <p style={{ fontSize: '0.8rem', margin: 0, opacity: 0.6 }}>
                      Store Product Name: <strong>{offer.product_name_raw}</strong>
                    </p>
                  </div>

                  {/* Flyer PDF Deep-Link Button */}
                  {pdfFullUrl && (
                    <div style={{ marginTop: '1rem', paddingTop: '0.8rem', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                      <a
                        href={pdfFullUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="button outline"
                        style={{
                          fontSize: '0.8rem',
                          padding: '0.35rem 0.7rem',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.4rem',
                          textDecoration: 'none',
                          color: '#4ade80',
                          borderColor: '#4ade80',
                          margin: 0
                        }}
                      >
                        <FileText size={14} /> Open in Flyer {offer.flyer_page_number ? `(Page ${offer.flyer_page_number})` : ''}
                      </a>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 2. Linked Retailer Store Products */}
      <div style={{ marginTop: '2.5rem' }}>
        <h2 style={{ fontSize: '1.3rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <ShoppingBag size={20} /> Linked Retailer Store Items
        </h2>

        {linkedStoreProducts.length === 0 ? (
          <p style={{ opacity: 0.7 }}>No linked store products recorded.</p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '1rem' }}>
            {linkedStoreProducts.map(sp => (
              <div
                key={sp.id}
                onClick={() => navigate(`/products/${sp.id}`)}
                style={{
                  background: 'var(--pico-card-background-color)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '8px',
                  padding: '1rem',
                  cursor: 'pointer',
                  display: 'flex',
                  gap: '0.8rem',
                  alignItems: 'center',
                  justify: 'space-between'
                }}
              >
                {/* Store Product Crop Thumbnail */}
                {sp.image_url && (
                  <div style={{ width: '50px', height: '50px', borderRadius: '6px', overflow: 'hidden', background: 'rgba(0,0,0,0.2)', flexShrink: 0 }}>
                    <img src={sp.image_url} alt={sp.name_raw} style={{ width: '100%', height: '100%', objectFit: 'contain' }} onError={(e) => { e.target.style.display = 'none'; }} />
                  </div>
                )}

                <div style={{ flexGrow: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.2rem' }}>
                    <span className="badge">{sp.retailer_name}</span>
                    <ExternalLink size={12} style={{ opacity: 0.5 }} />
                  </div>
                  <strong style={{ fontSize: '0.88rem', display: 'block', lineHeight: 1.2 }}>
                    {sp.name_raw}
                  </strong>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 3. Historical Price Offers */}
      <div style={{ marginTop: '2.5rem' }}>
        <h2 style={{ fontSize: '1.3rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <DollarSign size={20} /> Historical Price Offers
        </h2>

        {priceHistory.length === 0 ? (
          <p style={{ opacity: 0.7 }}>No historical price records found.</p>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Retailer</th>
                  <th>Week Start</th>
                  <th>Week End</th>
                  <th>Current Price</th>
                  <th>Original Price</th>
                  <th>Discount</th>
                  <th>Type</th>
                  <th>Flyer PDF</th>
                </tr>
              </thead>
              <tbody>
                {priceHistory.map((h) => {
                  const pdfUrl = h.flyer_pdf_url ? `${API_BASE_URL}/${h.flyer_pdf_url}` : null;

                  return (
                    <tr key={h.offer_id}>
                      <td><strong>{h.retailer_name}</strong></td>
                      <td>{h.week_start}</td>
                      <td>{h.week_end}</td>
                      <td><strong style={{ color: '#2e7d32' }}>€{Number(h.current_price || 0).toFixed(2)}</strong></td>
                      <td>{h.original_price ? `€${Number(h.original_price).toFixed(2)}` : '—'}</td>
                      <td>{h.discount_percent ? `-${h.discount_percent}%` : '—'}</td>
                      <td><span className="badge">{h.offer_type || 'WEEKLY_SPECIAL'}</span></td>
                      <td>
                        {pdfUrl ? (
                          <a href={pdfUrl} target="_blank" rel="noopener noreferrer" style={{ color: '#4ade80', fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                            <FileText size={12} /> Page {h.flyer_page_number || '—'}
                          </a>
                        ) : (
                          '—'
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}