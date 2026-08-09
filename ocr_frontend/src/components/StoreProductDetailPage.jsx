import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Layers, FileText } from 'lucide-react';
import { API_BASE_URL } from '../constants/tables';

export default function StoreProductDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchProduct = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE_URL}/store-products/${id}`);
        if (!res.ok) throw new Error(`Store product details not found (Status ${res.status})`);
        const json = await res.json();
        setProduct(json);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchProduct();
  }, [id]);

  if (loading) return <div className="page-container"><p>Loading store product details...</p></div>;
  if (error) return (
    <div className="page-container">
      <button onClick={() => navigate(-1)} className="back-btn outline"><ArrowLeft size={16} /> Back</button>
      <article style={{ borderColor: 'var(--pico-del-color)' }}>Error: {error}</article>
    </div>
  );

  const rawUrl = product.image_url ? String(product.image_url).replace(/\\/g, '/') : null;
  const imageUrl = rawUrl
    ? (rawUrl.startsWith('http') ? rawUrl : `${API_BASE_URL}/${rawUrl.replace(/^\//, '')}`)
    : null;

  // Construct PDF deep-link URL
  const pdfFullUrl = product.flyer_pdf_url 
    ? `${API_BASE_URL}/${product.flyer_pdf_url}`
    : null;

  return (
    <div className="page-container" style={{ maxWidth: '800px' }}>
      <button onClick={() => navigate(-1)} className="back-btn outline">
        <ArrowLeft size={16} /> Back
      </button>

      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.5rem', marginTop: '1rem' }}>
        <span className="badge">{product.retailer_name || product.retailer_code}</span>
        {product.canonical_id ? (
          <Link to={`/canonical/${product.canonical_id}`} className="badge badge-yes" style={{ textDecoration: 'none' }}>
            <Layers size={12} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
            Linked to Canonical Item
          </Link>
        ) : (
          <span className="badge" style={{ background: 'rgba(255,255,255,0.1)' }}>Unlinked Product</span>
        )}
      </div>

      <h1 style={{ margin: '0.2rem 0 1rem 0' }}>{product.product_name_raw}</h1>

      <div className="product-hero">
        <div className="hero-img-box">
          {imageUrl ? (
            <img src={imageUrl} alt={product.product_name_raw} className="hero-img" />
          ) : (
            <div style={{ color: '#888' }}>No Image Available</div>
          )}
        </div>

        <div>
          <h3>Price & Offer Details</h3>
          {product.current_price ? (
            <div style={{ margin: '0.5rem 0 1.5rem 0' }}>
              <span style={{ fontSize: '2rem', fontWeight: 800, color: '#2e7d32' }}>
                €{Number(product.current_price).toFixed(2)}
              </span>
              {product.original_price && (
                <span className="big-old-price" style={{ fontSize: '1.2rem', marginLeft: '0.5rem' }}>
                  €{Number(product.original_price).toFixed(2)}
                </span>
              )}
              {product.discount_percent && (
                <span className="badge" style={{ background: '#d32f2f', color: '#fff', marginLeft: '0.5rem' }}>
                  -{product.discount_percent}% OFF
                </span>
              )}
            </div>
          ) : (
            <p style={{ opacity: 0.6 }}>No current price offer recorded.</p>
          )}

          {/* Action Buttons: PDF Deep-Link & Canonical Link */}
          <div style={{ display: 'flex', gap: '0.8rem', flexWrap: 'wrap', margin: '1.5rem 0' }}>
            {pdfFullUrl && (
              <a
                href={pdfFullUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="button outline"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none', color: '#4ade80', borderColor: '#4ade80' }}
              >
                <FileText size={16} /> View in Flyer {product.flyer_page_number ? `(Page ${product.flyer_page_number})` : ''}
              </a>
            )}

            {product.canonical_id && (
              <Link to={`/canonical/${product.canonical_id}`} className="button" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                <Layers size={16} /> View Canonical Product ({product.canonical_display_name})
              </Link>
            )}
          </div>

          <h4>Raw Attributes</h4>
          <p style={{ fontSize: '0.9rem', opacity: 0.8, lineHeight: 1.6 }}>
            Category Raw: <strong>{product.category_raw || '—'}</strong><br />
            Product Type Raw: <strong>{product.product_type_raw || '—'}</strong><br />
            Brand Raw: <strong>{product.brand_raw || '—'}</strong><br />
            Unit Size Raw: <strong>{product.unit_size_raw || '—'}</strong>
          </p>
        </div>
      </div>
    </div>
  );
}