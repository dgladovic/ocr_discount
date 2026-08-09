import React from 'react';
import { ShoppingBag } from 'lucide-react';
import { TABLES } from '../constants/tables';

export default function Sidebar({ activeTable, onSelectTable }) {
  return (
    <aside className="sidebar">
      <h2><ShoppingBag size={22} /> Retail Dashboard</h2>
      <ul className="nav-list">
        {TABLES.map((t) => {
          const Icon = t.icon;
          return (
            <li
              key={t.id}
              className={`nav-item ${activeTable.id === t.id ? 'active' : ''}`}
              onClick={() => onSelectTable(t)}
            >
              <Icon size={16} /> {t.label}
            </li>
          );
        })}
      </ul>
    </aside>
  );
}