import React from 'react';
import { API_BASE_URL } from '../constants/tables';

export default function TableView({ data, activeTableId, onRowClick }) {
  // Handle both array responses and paginated { items: [...] } responses
  const items = Array.isArray(data) ? data : (data?.items || []);

  if (items.length === 0) {
    return <p style={{ opacity: 0.7 }}>No records found for this table.</p>;
  }

  const isClickable = ['store-products', 'price-offers', 'canonical-products', 'canonical-catalog'].includes(activeTableId);

  const formatCellValue = (key, value) => {
    if (value === null || value === undefined) return <span style={{ opacity: 0.3 }}>—</span>;
    if (typeof value === 'boolean') return <span className={`badge ${value ? 'badge-yes' : ''}`}>{value ? 'Yes' : 'No'}</span>;

    if (key.includes('image_url') || key.includes('imageUrl') || key.includes('cropped_image_path')) {
      if (!value) return <span style={{ opacity: 0.3 }}>—</span>;
      const normalizedPath = String(value).replace(/\\/g, '/');
      const fullImageUrl = normalizedPath.startsWith('http') ? normalizedPath : `${API_BASE_URL}/${normalizedPath.replace(/^\//, '')}`;
      return (
        <img
          src={fullImageUrl}
          alt="Product"
          className="product-img"
          onError={(e) => { e.target.style.display = 'none'; }}
        />
      );
    }

    if (key.includes('price') && typeof value === 'number') {
      return <strong>€{value.toFixed(2)}</strong>;
    }

    if (typeof value === 'object') {
      return <pre style={{ margin: 0, fontSize: '0.7rem' }}>{JSON.stringify(value)}</pre>;
    }

    return String(value);
  };

  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            {Object.keys(items[0]).map((col) => (
              <th key={col}>{col.replace(/_/g, ' ').toUpperCase()}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((row, idx) => (
            <tr
              key={row.id || idx}
              onClick={() => isClickable && onRowClick(row)}
              className={isClickable ? 'clickable-row' : ''}
            >
              {Object.entries(row).map(([key, val], i) => (
                <td key={i}>{formatCellValue(key, val)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}