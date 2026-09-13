import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import ActiveOffersPage from './pages/ActiveOffersPage';
import IngestionMonitoringPage from './pages/IngestionMonitoringPage';
import CanonicalProductsPage from './pages/CanonicalProductsPage';
import CanonicalDetailPage from './pages/CanonicalDetailPage';
import StoreProductDetailPage from './components/StoreProductDetailPage';
import OverridesView from './components/OverridesView';
import WatchlistPage from './pages/WatchlistPage';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-container" style={{ display: 'flex', minHeight: '100vh' }}>
        <Sidebar />
        <main className="main-content" style={{ flexGrow: 1, padding: '1.5rem', overflowY: 'auto' }}>
          <Routes>
            <Route path="/" element={<Navigate to="/active-offers" replace />} />
            <Route path="/watchlist" element={<WatchlistPage />} />
            <Route path="/active-offers" element={<ActiveOffersPage />} />
            <Route path="/ingestion-status" element={<IngestionMonitoringPage />} />
            <Route path="/catalog" element={<CanonicalProductsPage />} />
            <Route path="/canonical/:id" element={<CanonicalDetailPage />} />
            <Route path="/products/:id" element={<StoreProductDetailPage />} />
            <Route path="/overrides" element={<OverridesView />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}