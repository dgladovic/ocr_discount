import React from 'react';
import { NavLink } from 'react-router-dom';
import { Flame, Activity, Layers, Edit3, ShoppingBag, BookmarkCheck } from 'lucide-react';

export default function Sidebar() {
  const navItems = [
    { to: '/watchlist', label: 'My Watchlist', icon: BookmarkCheck },
    { to: '/active-offers', label: 'Active Deals', icon: Flame },
    { to: '/catalog', label: 'Canonical Catalog', icon: Layers },
    { to: '/ingestion-status', label: 'Flyer Ingestion Health', icon: Activity },
    { to: '/overrides', label: 'Manual Overrides', icon: Edit3 },
  ];

  return (
    <aside
      className="sidebar"
      style={{
        width: '260px',
        borderRight: '1px solid rgba(255,255,255,0.08)',
        padding: '1.5rem 1rem',
        background: 'var(--pico-card-background-color)',
        flexShrink: 0,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '2rem', paddingLeft: '0.5rem' }}>
        <ShoppingBag size={24} style={{ color: '#4ade80' }} />
        <h2 style={{ fontSize: '1.15rem', margin: 0, fontWeight: 700 }}>RetailRadar</h2>
      </div>

      <nav>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  style={({ isActive }) => ({
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                    padding: '0.6rem 0.8rem',
                    borderRadius: '8px',
                    textDecoration: 'none',
                    fontWeight: 500,
                    fontSize: '0.9rem',
                    color: isActive ? '#4ade80' : 'var(--pico-color)',
                    background: isActive ? 'rgba(74, 222, 128, 0.1)' : 'transparent',
                  })}
                >
                  <Icon size={18} />
                  {item.label}
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}