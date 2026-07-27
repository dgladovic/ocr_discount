import React, { useState, useEffect } from 'react';
import {
  Tag, ShoppingBag, Layers, Link2, DollarSign,
  Megaphone, Edit3, Users, Eye, RefreshCw
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const TABLES = [
  { id: 'price-offers', label: 'Price Offers', icon: DollarSign, endpoint: '/price-offers' },
  { id: 'store-products', label: 'Store Products', icon: ShoppingBag, endpoint: '/store-products' },
  { id: 'canonical-products', label: 'Canonical Products', icon: Layers, endpoint: '/canonical-products' },
  { id: 'store-product-links', label: 'Product Links', icon: Link2, endpoint: '/store-product-links' },
  { id: 'retailers', label: 'Retailers', icon: Tag, endpoint: '/retailers' },
  { id: 'category-announcements', label: 'Announcements', icon: Megaphone, endpoint: '/category-announcements' },
  { id: 'product-overrides', label: 'Overrides', icon: Edit3, endpoint: '/product-overrides' },
  { id: 'users', label: 'Users', icon: Users, endpoint: '/users' },
  { id: 'watchlist-items', label: 'Watchlist', icon: Eye, endpoint: '/watchlist-items' },
];

export default function App() {
  const [activeTable, setActiveTable] = useState(TABLES[0]);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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

  const formatCellValue = (key, value) => {
    if (value === null || value === undefined) return <span style={{ opacity: 0.3 }}>—</span>;
    if (typeof value === 'boolean') return <span className={`badge ${value ? 'badge-yes' : ''}`}>{value ? 'Yes' : 'No'}</span>;
    if (key.includes('image_url') || key.includes('imageUrl')) {
      return <img src={value} alt="Product" className="product-img" onError={(e) => e.target.style.display = 'none'} />;
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

        {!loading && !error && data.length === 0 && (
          <article>No records found in {activeTable.label}.</article>
        )}

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
                  <tr key={row.id || idx}>
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