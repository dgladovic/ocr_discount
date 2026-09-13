import React from 'react';
import { ShieldCheck, Lock } from 'lucide-react';
import { buildAssetUrl } from '../../utils/formatters';

export default function ProductHero({ canonical }) {
  const imageUrl = buildAssetUrl(canonical.image_url);

  return (
    <article className="product-hero" style={{ margin: '1.5rem 0' }}>
      <div className="hero-img-box">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={canonical.display_name}
            className="hero-img"
            onError={(e) => { e.currentTarget.style.display = 'none'; }}
          />
        ) : (
          <small style={{ opacity: 0.5 }}>No Image Available</small>
        )}
      </div>

      <div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.5rem' }}>
          <span className="badge badge-yes">Canonical Master</span>
          {canonical.is_manually_edited && (
            <span className="badge" style={{ background: '#eab308', color: '#000', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <Lock size={12} /> Manually Locked
            </span>
          )}
          <small style={{ opacity: 0.6 }}>{canonical.category} › {canonical.product_type}</small>
        </div>

        <h2 style={{ margin: '0.2rem 0 0.5rem 0' }}>{canonical.display_name}</h2>
        {canonical.brand && <p style={{ margin: '0 0 1rem 0', opacity: 0.8 }}>Brand: <strong>{canonical.brand}</strong></p>}

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '1.5rem' }}>
          {canonical.unit_size != null && (
            <span className="attribute-pill">
              {canonical.unit_size} {canonical.unit_measurement || ''}
            </span>
          )}
          {canonical.fat_percent != null && (
            <span className="attribute-pill">{canonical.fat_percent}% Fat</span>
          )}
          {canonical.organic && canonical.organic !== 'unknown' && (
            <span className="attribute-pill">Organic: {canonical.organic}</span>
          )}
        </div>

        <small style={{ opacity: 0.6, display: 'block' }}>
          <ShieldCheck size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
          ID: <code>{canonical.id}</code>
        </small>
      </div>
    </article>
  );
}