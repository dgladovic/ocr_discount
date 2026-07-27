import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useParams, Link } from 'react-router-dom';
import {
  Tag, ShoppingBag, Layers, Link2, DollarSign,
  Megaphone, Edit3, Users, Eye, RefreshCw, ArrowLeft, Calendar, ShieldCheck
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const TABLES = [
  { id: 'store-products', label: 'Store Products', icon: ShoppingBag, endpoint: '/store-products' },
  { id: 'price-offers', label: 'Price Offers', icon: DollarSign, endpoint: '/price-offers' },
  { id: 'canonical-products', label: 'Canonical Products', icon: Layers, endpoint: '/canonical-products' },
  { id: 'store-product-links', label: 'Product Links', icon: Link2, endpoint: '/store-product-links' },
  { id: 'retailers', label: 'Retailers', icon: Tag, endpoint: '/retailers' },
  { id: 'category-announcements', label: 'Announcements', icon: Megaphone, endpoint: '/category-announcements' },
  { id: 'product-overrides', label: 'Overrides', icon: Edit3, endpoint: '/product-overrides' },
  { id: 'users', label: 'Users', icon: Users, endpoint: '/users' },
  { id: 'watchlist-items', label: 'Watchlist', icon: Eye, endpoint: '/watchlist-items' },
];

// --- 1. DASHBOARD COMPONENT ---
function Dashboard() {
  const [activeTable, setActiveTable] = useState(TABLES[0]);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const fetchData = async (table) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}${table.endpoint}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch ${table.label}`);
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err.message);
      setData([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(activeTable);
  }, [activeTable]);

  const handleRowClick = (row) => {
    const productId = row.store_product_id || row.id;
    if (activeTable.id === 'store-products' || activeTable.id === 'price-offers') {
      navigate(`/products/${productId}`);
    }
  };

  const formatCellValue = (key, value) => {
    if (value === null || value === undefined) return <span style={{ opacity: 0.3 }}>—</span>;
    if (typeof value === 'boolean') return <span className={`badge ${value ? 'badge-yes' : ''}`}>{value ? 'Yes' : 'No'}</span>;
    
    if (key.includes('image_url') || key.includes('imageUrl')) {
      if (!value) return <span style={{ opacity: 0.3 }}>—</span>;
      const fullImageUrl = value.startsWith('http') ? value : `${API_BASE_URL}/${value.replace(/^\//, '')}`;
      return <img src={fullImageUrl} alt="Product" className="product-img" onError={(e) => e.target.style.display = 'none'} />;
    }

    if (key.includes('price') && typeof value === 'number') return <strong>€{value.toFixed(2)}</strong>;
    if (typeof value === 'object') return <pre style={{ margin: 0, fontSize: '0.7rem' }}>{JSON.stringify(value)}</pre>;
    return String(value);
  };

  return (
    <div className="app-container">
      <aside className="sidebar">
        <h2><ShoppingBag size={22} /> Retail Dashboard</h2>
        <ul className="nav-list">
          {TABLES.map((t) => {
            const Icon = t.icon;
            return (
              <li
                key={t.id}
                className={`nav-item ${activeTable.id === t.id ? 'active' : ''}`}
                onClick={() => setActiveTable(t)}
              >
                <Icon size={16} /> {t.label}
              </li>
            );
          })}
        </ul>
      </aside>

      <main className="main-content">
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.5rem' }}>{activeTable.label}</h1>
            <small style={{ opacity: 0.7 }}>Endpoint: <code>{activeTable.endpoint}</code></small>
          </div>
          <button
            onClick={() => fetchData(activeTable)}
            disabled={loading}
            className="outline"
            style={{ width: 'auto', padding: '0.4rem 0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
          </button>
        </header>

        {loading && <p>Loading data...</p>}
        {error && <article style={{ borderColor: 'var(--pico-del-color)' }}>Error: {error}</article>}

        {!loading && !error && data.length > 0 && (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  {Object.keys(data[0]).map((col) => (
                    <th key={col}>{col.replace(/_/g, ' ').toUpperCase()}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.map((row, idx) => (
                  <tr 
                    key={row.id || idx} 
                    onClick={() => handleRowClick(row)}
                    className={activeTable.id === 'store-products' || activeTable.id === 'price-offers' ? 'clickable-row' : ''}
                  >
                    {Object.entries(row).map(([key, val], i) => (
                      <td key={i}>{formatCellValue(key, val)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}

// --- 2. DEDICATED FULL PRODUCT PAGE ---
function ProductDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchProductDetails = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE_URL}/store-products/${id}`);
        if (!res.ok) throw new Error(`Product not found (Status ${res.status})`);
        const data = await res.json();
        setProduct(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchProductDetails();
  }, [id]);

  if (loading) return <div className="page-container"><p>Loading product details...</p></div>;
  if (error) return (
    <div className="page-container">
      <Link to="/" className="back-btn outline button"><ArrowLeft size={16} /> Back to Dashboard</Link>
      <article style={{ borderColor: 'var(--pico-del-color)' }}>Error: {error}</article>
    </div>
  );

  const fullImageUrl = product.image_url 
    ? `${API_BASE_URL}/${product.image_url.replace(/^\//, '')}`
    : null;

  return (
    <div className="page-container">
      <button onClick={() => navigate(-1)} className="back-btn outline">
        <ArrowLeft size={16} /> Back
      </button>

      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.5rem' }}>
        <span className="badge badge-yes">{product.retailer_name}</span>
        <small style={{ opacity: 0.7 }}>{product.category} › {product.product_type}</small>
      </div>

      <h1 style={{ margin: '0.2rem 0 0.5rem 0' }}>{product.product_name_raw}</h1>
      {product.brand && <p style={{ opacity: 0.7, margin: 0 }}>Brand: <strong>{product.brand}</strong></p>}

      <div className="product-hero">
        <div className="hero-img-box">
          {fullImageUrl ? (
            <img src={fullImageUrl} alt={product.product_name_raw} className="hero-img" />
          ) : (
            <div style={{ color: '#888' }}>No Image Available</div>
          )}
        </div>

        <div>
          {/* Price Box */}
          <div className="big-price-card">
            <div>
              <span className="big-price">€{Number(product.current_price || 0).toFixed(2)}</span>
              {product.original_price && (
                <span className="big-old-price">€{Number(product.original_price).toFixed(2)}</span>
              )}
              {product.discount_percent && (
                <span className="badge" style={{ background: '#d32f2f', color: '#fff', marginLeft: '0.8rem' }}>
                  -{product.discount_percent}% OFF
                </span>
              )}
            </div>
            {product.effective_unit_price && (
              <small style={{ display: 'block', marginTop: '0.4rem', opacity: 0.8 }}>
                Effective Unit Price: <strong>€{product.effective_unit_price} / unit</strong>
              </small>
            )}
          </div>

          {/* Metadata */}
          <p style={{ fontSize: '0.9rem', marginBottom: '0.5rem' }}>
            <Calendar size={15} style={{ verticalAlign: 'middle', marginRight: '6px' }} />
            Offer Valid: <strong>{product.week_start || 'N/A'}</strong> to <strong>{product.week_end || 'N/A'}</strong>
          </p>

          <p style={{ fontSize: '0.9rem', marginBottom: '1rem' }}>
            Offer Type: <span className="badge">{product.offer_type || 'WEEKLY_SPECIAL'}</span>
          </p>

          {/* Attributes */}
          <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--pico-border-color)' }}>
            <h4 style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>Product Attributes</h4>
            <div>
              {product.volume_ml && <span className="attribute-pill">Volume: {product.volume_ml} ml</span>}
              {product.weight_g && <span className="attribute-pill">Weight: {product.weight_g} g</span>}
              {product.fat_percent && <span className="attribute-pill">Fat: {product.fat_percent}%</span>}
              {product.organic && <span className="attribute-pill">Organic: {product.organic}</span>}
            </div>
          </div>

          {product.canonical_display_name && (
            <div style={{ marginTop: '1.5rem', padding: '0.75rem', background: 'rgba(255,255,255,0.04)', borderRadius: '8px', fontSize: '0.85rem' }}>
              <ShieldCheck size={14} style={{ verticalAlign: 'middle', marginRight: '6px' }} />
              Canonical Product: <strong>{product.canonical_display_name}</strong>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// --- 3. MAIN ROUTER APP ---
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/products/:id" element={<ProductDetailPage />} />
      </Routes>
    </BrowserRouter>
  );
}