import React from 'react';
import { Tag, Calendar, FileText } from 'lucide-react';
import { buildAssetUrl, isFlyerAvailable } from '../../utils/formatters';

export default function ActiveOffersSection({ activeOffers }) {
  if (!activeOffers || activeOffers.length === 0) {
    return (
      <section style={{ marginTop: '2rem' }}>
        <h3><Tag size={18} style={{ color: '#2e7d32', verticalAlign: 'middle' }} /> Active Flyer Offers</h3>
        <p style={{ opacity: 0.6, fontSize: '0.9rem' }}>No active flyer deals available for this product this week.</p>
      </section>
    );
  }

  return (
    <section style={{ marginTop: '2rem' }}>
      <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Tag size={20} style={{ color: '#2e7d32' }} /> Active Flyer Offers This Week
      </h3>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
        {activeOffers.map((offer) => {
          const pdfUrl = buildAssetUrl(offer.flyer_pdf_url);
          // Only show flyer PDF if the file still exists on disk for the active week
          const hasActiveFlyer = pdfUrl && isFlyerAvailable(offer.week_end);

          return (
            <article key={offer.offer_id} style={{ margin: 0, padding: '1.2rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <strong>{offer.retailer_name}</strong>
                  {offer.discount_percent != null && (
                    <span className="badge" style={{ background: '#d32f2f', color: '#fff' }}>
                      -{offer.discount_percent}%
                    </span>
                  )}
                </div>

                <div style={{ margin: '0.4rem 0' }}>
                  <span style={{ fontSize: '1.8rem', fontWeight: 'bold', color: '#2e7d32' }}>
                    €{Number(offer.current_price || 0).toFixed(2)}
                  </span>
                  {offer.original_price != null && (
                    <span className="big-old-price" style={{ marginLeft: '0.5rem' }}>
                      €{Number(offer.original_price).toFixed(2)}
                    </span>
                  )}
                </div>

                <small style={{ opacity: 0.7, display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Calendar size={13} /> {offer.week_start} to {offer.week_end}
                </small>

                <p style={{ fontSize: '0.8rem', margin: '0.5rem 0 0', opacity: 0.7 }}>
                  Store Item: <strong>{offer.product_name_raw}</strong>
                </p>
              </div>

              {/* PDF button only appears if the flyer hasn't been cleaned up */}
              {hasActiveFlyer ? (
                <div style={{ marginTop: '1rem', paddingTop: '0.8rem', borderTop: '1px solid var(--pico-border-color)' }}>
                  <a
                    href={pdfUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="button outline"
                    style={{ fontSize: '0.8rem', padding: '0.3rem 0.6rem', display: 'inline-flex', alignItems: 'center', gap: '0.4rem', margin: 0 }}
                  >
                    <FileText size={14} /> Open Flyer {offer.flyer_page_number ? `(p. ${offer.flyer_page_number})` : ''}
                  </a>
                </div>
              ) : (
                <small style={{ opacity: 0.4, marginTop: '0.8rem' }}>Flyer PDF not retained</small>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}