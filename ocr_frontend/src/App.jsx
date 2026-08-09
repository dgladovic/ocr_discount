import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import CanonicalDetailPage from './pages/CanonicalDetailPage';
import StoreProductDetailPage from './components/StoreProductDetailPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/canonical/:id" element={<CanonicalDetailPage />} />
        <Route path="/products/:id" element={<StoreProductDetailPage />} />
      </Routes>
    </BrowserRouter>
  );
}