import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ShoppingBag, ExternalLink } from 'lucide-react';
import { buildAssetUrl } from '../../utils/formatters';

export default function LinkedStoreProducts({ priceHistory }) {
  const navigate = useNavigate();

  // Deduplicate store products
  const storeProductsMap = {};
  priceHistory.forEach((item) => {
    if (item.store_product_id && !storeProductsMap[item.store_product_id]) {
      storeProductsMap[item.store_product_id] = {
        id: item.store_product_id,
        name_raw: item.product_name_raw,
        retailer_name: item.retailer_name,
        image_url: buildAssetUrl(item.store_product_image_url),
      };
    }
  });

  const storeProducts = Object.values(storeProductsMap);
  if (storeProducts.length === 0) return null;

  return (
    <section style={{ marginTop: '2rem' }}>
      <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <ShoppingBag size={20} /> Linked Store Items
      </h3>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '0.8rem' }}>
        {storeProducts.map((sp) => (
          <article
            key={sp.id}
            onClick={() => navigate(`/products/${sp.id}`)}
            className="clickable-row"
            style={{ margin: 0, padding: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.8rem' }}
          >
            {sp.image_url && (
              <img
                src={sp.image_url}
                alt={sp.name_raw}
                style={{ width: '42px', height: '42px', objectFit: 'contain', borderRadius: '4px', background: 'rgba(0,0,0,0.1)' }}
                onError={(e) => { e.currentTarget.style.display = 'none'; }}
              />
            )}
            <div style={{ flexGrow: 1, minWidth: 0 }}>
              <span className="badge" style={{ fontSize: '0.7rem' }}>{sp.retailer_name}</span>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {sp.name_raw}
              </div>
            </div>
            <ExternalLink size={14} style={{ opacity: 0.5, flexShrink: 0 }} />
          </article>
        ))}
      </div>
    </section>
  );
}