import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import Sidebar from '../components/Sidebar';
import IngestionStatusView from '../components/IngestionStatusView';
import TableView from '../components/TableView';
import CanonicalProductsPage from '../pages/CanonicalProductsPage'; // <--- Import here
import { TABLES, API_BASE_URL } from '../constants/tables';

export default function Dashboard() {
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
    if (activeTable.id !== 'canonical-catalog') {
      fetchData(activeTable);
    }
  }, [activeTable]);

  const handleRowClick = (row) => {
    if (activeTable.id === 'canonical-products' || activeTable.id === 'canonical-catalog') {
      navigate(`/canonical/${row.id}`);
    } else if (activeTable.id === 'store-products') {
      if (row.canonical_id) {
        navigate(`/canonical/${row.canonical_id}`);
      } else {
        navigate(`/products/${row.id}`);
      }
    } else if (activeTable.id === 'price-offers') {
      if (row.canonical_id) {
        navigate(`/canonical/${row.canonical_id}`);
      } else {
        navigate(`/products/${row.store_product_id || row.id}`);
      }
    }
  };

  return (
    <div className="app-container">
      <Sidebar activeTable={activeTable} onSelectTable={setActiveTable} />

      <main className="main-content">
        {activeTable.id === 'canonical-catalog' ? (
          <CanonicalProductsPage />
        ) : (
          <>
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

            {!loading && !error && activeTable.id === 'ingestion-status' && (
              <IngestionStatusView data={data} />
            )}

            {!loading && !error && activeTable.id !== 'ingestion-status' && (
              <TableView data={data} activeTableId={activeTable.id} onRowClick={handleRowClick} />
            )}
          </>
        )}
      </main>
    </div>
  );
}