import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { 
  Search, Layers, RefreshCw, ArrowRight, ChevronLeft, ChevronRight, 
  ArrowUpDown, Edit3, CheckSquare, Square, X, Check 
} from 'lucide-react';
import { API_BASE_URL } from '../constants/tables';

export default function CanonicalProductsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // 1. URL Query State Sync (Never resets on "Back" navigation)
  const page = Number(searchParams.get('page')) || 1;
  const limit = Number(searchParams.get('limit')) || 20;
  const searchTerm = searchParams.get('search') || '';
  const selectedCategory = searchParams.get('category') || '';
  const selectedBrand = searchParams.get('brand') || '';
  const selectedRetailer = searchParams.get('retailer_code') || '';
  const sortBy = searchParams.get('sort_by') || 'updated_at';
  const sortOrder = searchParams.get('sort_order') || 'desc';

  // Local Search Input buffer (allows smooth typing before submit)
  const [searchInput, setSearchInput] = useState(searchTerm);

  // Data states
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [retailers, setRetailers] = useState([]);
  const [brands, setBrands] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Multi-select & Batch Edit states
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [isBatchEditing, setIsBatchEditing] = useState(false);
  const [batchSubmitting, setBatchSubmitting] = useState(false);
  const [batchForm, setBatchForm] = useState({
    category: '',
    product_type: '',
    brand: '',
    organic: '',
  });

  const CATEGORIES = [
    'Bread & Bakery', 'Dairy & Eggs', 'Meat & Poultry', 'Fish & Seafood',
    'Fresh Produce', 'Frozen Foods', 'Drinks & Beverages',
    'Snacks & Confectionery', 'Pantry & Baking',
    'Household & Cleaning', 'Health & Beauty', 'Pet Supplies', 'Miscellaneous'
  ];

  // Helper to update URL search params cleanly
  const updateParams = (newParams) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(newParams).forEach(([k, v]) => {
      if (v === '' || v === null || v === undefined) {
        next.delete(k);
      } else {
        next.set(k, String(v));
      }
    });
    setSearchParams(next);
  };

  // Sync local search input if URL changes externally
  useEffect(() => {
    setSearchInput(searchTerm);
  }, [searchTerm]);

  const fetchRetailers = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/retailers`);
      if (res.ok) setRetailers(await res.json());
    } catch (e) {
      console.error('Failed to load retailers:', e);
    }
  };

  const fetchBrands = async () => {
    try {
      const params = new URLSearchParams();
      if (selectedCategory) params.append('category', selectedCategory);
      if (selectedRetailer) params.append('retailer_code', selectedRetailer);
      if (searchTerm.trim()) params.append('search', searchTerm.trim());

      const res = await fetch(`${API_BASE_URL}/canonical-brands?${params.toString()}`);
      if (res.ok) {
        const brandList = await res.json();
        setBrands(brandList);
        if (selectedBrand && !brandList.includes(selectedBrand)) {
          updateParams({ brand: '' });
        }
      }
    } catch (e) {
      console.error('Failed to load dynamic brands:', e);
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
      if (selectedBrand) params.append('brand', selectedBrand);
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

  useEffect(() => {
    fetchBrands();
  }, [selectedCategory, selectedRetailer, searchTerm]);

  // Refetches whenever URL params change (including browser Back/Forward navigation)
  useEffect(() => {
    fetchProducts();
  }, [searchParams]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    updateParams({ search: searchInput, page: 1 });
  };

  // Checkbox Selection Helpers
  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAllOnPage = () => {
    if (selectedIds.size === items.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(items.map((i) => i.id)));
    }
  };

const handleBatchSave = async (e) => {
    e.preventDefault();
    if (selectedIds.size === 0) return;

    setBatchSubmitting(true);
    try {
      const payload = {
        canonical_ids: Array.from(selectedIds),
        category: batchForm.category || null,       // <-- USE null, NOT None
        product_type: batchForm.product_type || null, // <-- USE null, NOT None
        brand: batchForm.brand || null,             // <-- USE null, NOT None
        organic: batchForm.organic || null,         // <-- USE null, NOT None
        edited_by: 'admin@retailoffers.com',
      };

      const res = await fetch(`${API_BASE_URL}/canonical-products/batch-override`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Failed to apply batch edits');
      }

      setIsBatchEditing(false);
      setSelectedIds(new Set());
      setBatchForm({ category: '', product_type: '', brand: '', organic: '' });
      await fetchProducts();
    } catch (err) {
      alert(`Batch Edit Error: ${err.message}`);
    } finally {
      setBatchSubmitting(false);
    }
  };

  const totalPages = Math.ceil(total / limit) || 1;

  return (
    <div style={{ padding: '0.5rem 0' }}>
      {/* Top Header */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.8rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.6rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Layers style={{ color: '#2e7d32' }} /> Canonical Products Catalog
          </h1>
          <p style={{ opacity: 0.7, margin: '0.3rem 0 0 0', fontSize: '0.88rem' }}>
            Persistent URL filtering, state preservation & batch editing
          </p>
        </div>
        <button onClick={fetchProducts} disabled={loading} className="outline" style={{ width: 'auto', padding: '0.4rem 0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </header>

      {/* Filter Controls Bar */}
      <form onSubmit={handleSearchSubmit} style={{ background: 'var(--pico-card-background-color)', padding: '1rem', borderRadius: '12px', marginBottom: '1.5rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.8rem', alignItems: 'center' }}>
        {/* Search Input */}
        <div style={{ position: 'relative' }}>
          <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', opacity: 0.5 }} />
          <input
            type="text"
            placeholder="Search name/brand..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            style={{ paddingLeft: '2.2rem', margin: 0, fontSize: '0.88rem' }}
          />
        </div>

        {/* Category Filter */}
        <div>
          <select
            value={selectedCategory}
            onChange={(e) => updateParams({ category: e.target.value, page: 1 })}
            style={{ margin: 0, fontSize: '0.88rem' }}
          >
            <option value="">All Categories</option>
            {CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>

        {/* Retailer Filter */}
        <div>
          <select
            value={selectedRetailer}
            onChange={(e) => updateParams({ retailer_code: e.target.value, page: 1 })}
            style={{ margin: 0, fontSize: '0.88rem' }}
          >
            <option value="">All Retailers</option>
            {retailers.map((r) => (
              <option key={r.id} value={r.code}>{r.name}</option>
            ))}
          </select>
        </div>

        {/* Dynamic Cascading Brand Filter */}
        <div>
          <select
            value={selectedBrand}
            onChange={(e) => updateParams({ brand: e.target.value, page: 1 })}
            style={{ margin: 0, fontSize: '0.88rem' }}
          >
            <option value="">
              {selectedRetailer || selectedCategory ? `Brands in Selection (${brands.length})` : `All Brands (${brands.length})`}
            </option>
            {brands.map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
        </div>

        {/* Sort By & Order */}
        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          <select
            value={sortBy}
            onChange={(e) => updateParams({ sort_by: e.target.value, page: 1 })}
            style={{ margin: 0, fontSize: '0.88rem' }}
          >
            <option value="updated_at">Sort: Updated</option>
            <option value="display_name">Sort: Name</option>
            <option value="brand">Sort: Brand</option>
            <option value="category">Sort: Category</option>
          </select>

          <button
            type="button"
            className="outline"
            onClick={() => updateParams({ sort_order: sortOrder === 'asc' ? 'desc' : 'asc' })}
            style={{ margin: 0, padding: '0.45rem', width: 'auto' }}
            title={`Toggle Order (${sortOrder.toUpperCase()})`}
          >
            <ArrowUpDown size={16} />
          </button>
        </div>

        {/* Clear Filters Button */}
        {(searchTerm || selectedCategory || selectedBrand || selectedRetailer) && (
          <button
            type="button"
            onClick={() => {
              setSearchInput('');
              setSearchParams(new URLSearchParams());
            }}
            className="outline"
            style={{ margin: 0, padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}
          >
            Clear Filters
          </button>
        )}
      </form>

      {/* Floating Batch Action Toolbar */}
      {selectedIds.size > 0 && (
        <div style={{
          position: 'sticky',
          top: '1rem',
          zIndex: 90,
          background: 'var(--pico-card-background-color)',
          border: '1px solid #4ade80',
          boxShadow: '0 4px 15px rgba(0,0,0,0.3)',
          borderRadius: '10px',
          padding: '0.8rem 1.2rem',
          marginBottom: '1.2rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.8rem'
        }}>
          <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <CheckSquare size={18} style={{ color: '#4ade80' }} />
            {selectedIds.size} of {items.length} products selected on this page
          </span>

          <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
            <button
              onClick={() => setIsBatchEditing(true)}
              style={{ margin: 0, padding: '0.35rem 0.8rem', fontSize: '0.85rem', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
            >
              <Edit3 size={14} /> Batch Edit Selected
            </button>

            <button
              onClick={() => setSelectedIds(new Set())}
              className="outline"
              style={{ margin: 0, padding: '0.35rem 0.8rem', fontSize: '0.85rem' }}
            >
              Deselect All
            </button>
          </div>
        </div>
      )}

      {/* Pagination & Select All Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', fontSize: '0.85rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
          <button
            onClick={selectAllOnPage}
            className="outline"
            style={{ margin: 0, padding: '0.2rem 0.6rem', fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
          >
            {selectedIds.size === items.length && items.length > 0 ? <CheckSquare size={14} /> : <Square size={14} />}
            Select All on Page
          </button>

          <span style={{ opacity: 0.8 }}>
            Showing <strong>{items.length}</strong> of <strong>{total}</strong> products (Page {page} of {totalPages})
          </span>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <select
            value={limit}
            onChange={(e) => updateParams({ limit: Number(e.target.value), page: 1 })}
            style={{ margin: 0, padding: '0.2rem 0.5rem', fontSize: '0.8rem', width: 'auto' }}
          >
            <option value={20}>20 per page</option>
            <option value={50}>50 per page</option>
            <option value={100}>100 per page</option>
          </select>

          <button
            disabled={page <= 1 || loading}
            onClick={() => updateParams({ page: Math.max(page - 1, 1) })}
            className="outline"
            style={{ padding: '0.2rem 0.5rem', margin: 0 }}
          >
            <ChevronLeft size={16} />
          </button>

          <button
            disabled={page >= totalPages || loading}
            onClick={() => updateParams({ page: page + 1 })}
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
          {items.map((product) => {
            const isSelected = selectedIds.has(product.id);
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
                  border: `1px solid ${isSelected ? '#4ade80' : 'rgba(255,255,255,0.08)'}`,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  position: 'relative',
                  transition: 'border-color 0.15s ease'
                }}
              >
                {/* Selection Checkbox */}
                <div
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleSelect(product.id);
                  }}
                  style={{
                    position: 'absolute',
                    top: '12px',
                    left: '12px',
                    zIndex: 10,
                    background: isSelected ? '#4ade80' : 'rgba(0,0,0,0.5)',
                    color: isSelected ? '#000' : '#fff',
                    borderRadius: '4px',
                    width: '24px',
                    height: '24px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    border: '1px solid rgba(255,255,255,0.2)'
                  }}
                >
                  {isSelected && <Check size={16} strokeWidth={3} />}
                </div>

                <div>
                  <div style={{ height: '140px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', marginBottom: '1rem', overflow: 'hidden' }}>
                    {fullImageUrl ? (
                      <img
                        src={fullImageUrl}
                        alt={product.display_name}
                        style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }}
                        onError={(e) => { e.currentTarget.style.display = 'none'; }}
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

      {/* Batch Edit Modal Dialog */}
      {isBatchEditing && (
        <dialog open>
          <article style={{ maxWidth: '580px', width: '100%' }}>
            <header>
              <button aria-label="Close" className="close" onClick={() => setIsBatchEditing(false)} />
              <strong>Batch Edit ({selectedIds.size} Products Selected)</strong>
            </header>

            <p style={{ fontSize: '0.85rem', opacity: 0.8 }}>
              Only fields you enter will be updated. Blank fields will leave existing product values untouched.
            </p>

            <form onSubmit={handleBatchSave}>
              <div className="grid">
                <label>
                  Category
                  <select
                    value={batchForm.category}
                    onChange={(e) => setBatchForm((p) => ({ ...p, category: e.target.value }))}
                  >
                    <option value="">(Keep Existing)</option>
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </label>

                <label>
                  Product Type
                  <input
                    type="text"
                    placeholder="e.g. dairy_cheese"
                    value={batchForm.product_type}
                    onChange={(e) => setBatchForm((p) => ({ ...p, product_type: e.target.value }))}
                  />
                </label>
              </div>

              <div className="grid">
                <label>
                  Brand
                  <input
                    type="text"
                    placeholder="e.g. Spar"
                    value={batchForm.brand}
                    onChange={(e) => setBatchForm((p) => ({ ...p, brand: e.target.value }))}
                  />
                </label>

                <label>
                  Organic
                  <select
                    value={batchForm.organic}
                    onChange={(e) => setBatchForm((p) => ({ ...p, organic: e.target.value }))}
                  >
                    <option value="">(Keep Existing)</option>
                    <option value="yes">Yes</option>
                    <option value="no">No</option>
                    <option value="unknown">Unknown</option>
                  </select>
                </label>
              </div>

              <footer>
                <div style={{ display: 'flex', gap: '0.8rem', justifyContent: 'flex-end' }}>
                  <button type="button" className="secondary outline" onClick={() => setIsBatchEditing(false)} disabled={batchSubmitting}>
                    Cancel
                  </button>
                  <button type="submit" disabled={batchSubmitting}>
                    {batchSubmitting ? 'Updating...' : `Update ${selectedIds.size} Products`}
                  </button>
                </div>
              </footer>
            </form>
          </article>
        </dialog>
      )}
    </div>
  );
}