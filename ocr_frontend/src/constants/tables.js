import {
  Activity, ShoppingBag, DollarSign, Layers, Link2,
  Tag, Megaphone, Edit3, Users, Eye
} from 'lucide-react';

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const TABLES = [
  { id: 'canonical-catalog', label: 'Canonical Catalog', icon: Layers, endpoint: '/canonical-products' },
  { id: 'ingestion-status', label: 'Ingestion Status', icon: Activity, endpoint: '/ingestion-status' },
  { id: 'store-products', label: 'Store Products', icon: ShoppingBag, endpoint: '/store-products' },
  { id: 'price-offers', label: 'Price Offers', icon: DollarSign, endpoint: '/price-offers' },
  { id: 'canonical-products', label: 'Canonical Table', icon: Layers, endpoint: '/canonical-products' },
  { id: 'store-product-links', label: 'Product Links', icon: Link2, endpoint: '/store-product-links' },
  { id: 'retailers', label: 'Retailers', icon: Tag, endpoint: '/retailers' },
  { id: 'category-announcements', label: 'Announcements', icon: Megaphone, endpoint: '/category-announcements' },
  { id: 'product-overrides', label: 'Overrides', icon: Edit3, endpoint: '/product-overrides' },
  { id: 'users', label: 'Users', icon: Users, endpoint: '/users' },
  { id: 'watchlist-items', label: 'Watchlist', icon: Eye, endpoint: '/watchlist-items' },
];