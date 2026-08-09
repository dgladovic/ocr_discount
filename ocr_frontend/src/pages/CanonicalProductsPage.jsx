import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Layers, RefreshCw, ArrowRight, ChevronLeft, ChevronRight, ArrowUpDown } from 'lucide-react';
import { API_BASE_URL } from '../constants/tables';

export default function CanonicalProductsPage() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [retailers, setRetailers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filter & Pagination States
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedRetailer, setSelectedRetailer] = useState('');
  const [sortBy, setSortBy] = useState('updated_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);

  const navigate = useNavigate();

  // Categories list
  const CATEGORIES = [
    'Bread & Bakery', 'Dairy & Eggs', 'Meat & Poultry', 'Fish & Seafood',
    'Fruit & Vegetables', 'Frozen Foods', 'Drinks & Beverages', 'Beer, Wine & Spirits',
    'Snacks & Confectionery', 'Pantry & Cooking', 'Breakfast & Cereals',
    'Baby & Kids', 'Household & Cleaning', 'Personal Care & Beauty', 'Pet Supplies'
  ];

  const fetchRetailers = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/retailers`);
      if (res.ok) setRetailers(await res.json());
    } catch (e) {
      console.error('Failed to load retailers:', e);
    }
  };

  const fetchProducts = async () => {
    setLoading(true);
    setError(null);
    try {
      const offset = (page - 1) * limit;
      const params = new URLSearchParams({
        limit,
        offset,
        sort_by: sortBy,
        sort_order: sortOrder,
      });

      if (searchTerm.trim()) params.append('search', searchTerm.trim());
      if (selectedCategory) params.append('category', selectedCategory);
      if (selectedRetailer) params.append('retailer_code', selectedRetailer);

      const res = await fetch(`${API_BASE_URL}/canonical-products?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch catalog`);

      const json = await res.json();
      setItems(json.items || []);
      setTotal(json.total || 0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRetailers();
  }, []);

  // Fetch when filters/page change
  useEffect(() => {
    fetchProducts();
  }, [page, limit, selectedCategory, selectedRetailer, sortBy, sortOrder]);

  // Handle Search submit / enter
  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    fetchProducts();
  };

  const totalPages = Math.ceil(total / limit) || 1;

  return (
    <div style={{ padding: '0.5rem 0' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.6rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Layers style={{ color: '#2e7d32' }} /> Canonical Products Catalog
          </h1>
          <p style={{ opacity: 0.7, margin: '0.3rem 0 0 0', fontSize: '0.88rem' }}>
            Server-side paginated master product catalog
          </p>
        </div>
        <button onClick={fetchProducts} disabled={loading} className="outline" style={{ width: 'auto', padding: '0.4rem 0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </header>

      {/* Filter Controls Bar */}
      <form onSubmit={handleSearchSubmit} style={{ background: 'var(--pico-card-background-color)', padding: '1rem', borderRadius: '12px', marginBottom: '1.5rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', alignItems: 'center' }}>
        
        {/* Search Input */}
        <div style={{ position: 'relative' }}>
          <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', opacity: 0.5 }} />
          <input
            type="text"
            placeholder="Search name/brand..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ paddingLeft: '2.2rem', margin: 0, fontSize: '0.88rem' }}
          />
        </div>

        {/* Category Filter */}
        <div>
          <select
            value={selectedCategory}
            onChange={(e) => { setSelectedCategory(e.target.value); setPage(1); }}
            style={{ margin: 0, fontSize: '0.88rem' }}
          >
            <option value="">All Categories</option>
            {CATEGORIES.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>

        {/* Retailer Filter */}
        <div>
          <select
            value={selectedRetailer}
            onChange={(e) => { setSelectedRetailer(e.target.value); setPage(1); }}
            style={{ margin: 0, fontSize: '0.88rem' }}
          >
            <option value="">All Retailers</option>
            {retailers.map(r => (
              <option key={r.id} value={r.code}>{r.name}</option>
            ))}
          </select>
        </div>

        {/* Sort By */}
        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          <select
            value={sortBy}
            onChange={(e) => { setSortBy(e.target.value); setPage(1); }}
            style={{ margin: 0, fontSize: '0.88rem' }}
          >
            <option value="updated_at">Sort: Updated At</option>
            <option value="display_name">Sort: Name</option>
            <option value="brand">Sort: Brand</option>
            <option value="category">Sort: Category</option>
          </select>

          <button
            type="button"
            className="outline"
            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
            style={{ margin: 0, padding: '0.45rem', width: 'auto' }}
            title={`Toggle Order (${sortOrder.toUpperCase()})`}
          >
            <ArrowUpDown size={16} />
          </button>
        </div>
      </form>

      {/* Pagination & Count Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', fontSize: '0.85rem' }}>
        <span style={{ opacity: 0.8 }}>
          Showing <strong>{items.length}</strong> of <strong>{total}</strong> products (Page {page} of {totalPages})
        </span>

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <select
            value={limit}
            onChange={(e) => { setLimit(Number(e.target.value)); setPage(1); }}
            style={{ margin: 0, padding: '0.2rem 0.5rem', fontSize: '0.8rem', width: 'auto' }}
          >
            <option value={20}>20 per page</option>
            <option value={50}>50 per page</option>
            <option value={100}>100 per page</option>
          </select>

          <button
            disabled={page <= 1 || loading}
            onClick={() => setPage(p => Math.max(p - 1, 1))}
            className="outline"
            style={{ padding: '0.2rem 0.5rem', margin: 0 }}
          >
            <ChevronLeft size={16} />
          </button>

          <button
            disabled={page >= totalPages || loading}
            onClick={() => setPage(p => p + 1)}
            className="outline"
            style={{ padding: '0.2rem 0.5rem', margin: 0 }}
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* Product Cards Grid */}
      {loading ? (
        <p>Loading products from backend...</p>
      ) : error ? (
        <article style={{ borderColor: 'var(--pico-del-color)' }}>Error: {error}</article>
      ) : items.length === 0 ? (
        <p style={{ opacity: 0.7 }}>No products found matching current criteria.</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '1.2rem' }}>
          {items.map(product => {
            const rawUrl = product.image_url ? String(product.image_url).replace(/\\/g, '/') : null;
            const fullImageUrl = rawUrl
              ? (rawUrl.startsWith('http') ? rawUrl : `${API_BASE_URL}/${rawUrl.replace(/^\//, '')}`)
              : null;

            return (
              <div
                key={product.id}
                onClick={() => navigate(`/canonical/${product.id}`)}
                style={{
                  background: 'var(--pico-card-background-color)',
                  borderRadius: '12px',
                  padding: '1.2rem',
                  cursor: 'pointer',
                  border: '1px solid rgba(255,255,255,0.08)',
                  display: 'flex',
                  flexDirection: 'column',
                  justify: 'space-between',
                  transition: 'transform 0.15s ease, border-color 0.15s ease'
                }}
              >
                <div>
                  <div style={{ height: '140px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', marginBottom: '1rem', overflow: 'hidden' }}>
                    {fullImageUrl ? (
                      <img
                        src={fullImageUrl}
                        alt={product.display_name}
                        style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }}
                        onError={(e) => { e.target.style.display = 'none'; }}
                      />
                    ) : (
                      <div style={{ opacity: 0.4, fontSize: '0.8rem' }}>No Image</div>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
                    <span className="badge" style={{ fontSize: '0.7rem' }}>{product.category}</span>
                    {product.brand && <span className="badge badge-yes" style={{ fontSize: '0.7rem' }}>{product.brand}</span>}
                  </div>

                  <h3 style={{ fontSize: '1.05rem', margin: '0.2rem 0 0.5rem 0', lineHeight: 1.3 }}>
                    {product.display_name}
                  </h3>
                </div>

                <div style={{ marginTop: '1rem', paddingTop: '0.8rem', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem' }}>
                  <span style={{ opacity: 0.7 }}>
                    {product.unit_size ? `${product.unit_size} ${product.unit_measurement || ''}` : 'Standard Pack'}
                  </span>
                  <span style={{ color: '#4ade80', display: 'flex', alignItems: 'center', gap: '0.2rem', fontWeight: 600 }}>
                    Details <ArrowRight size={14} />
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}