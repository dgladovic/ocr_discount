import React from 'react';
import { DollarSign, FileText } from 'lucide-react';
import { buildAssetUrl, isFlyerAvailable } from '../../utils/formatters';

export default function PriceHistoryTable({ priceHistory }) {
  if (!priceHistory || priceHistory.length === 0) {
    return (
      <section style={{ marginTop: '2rem' }}>
        <h3><DollarSign size={20} /> Price History</h3>
        <p style={{ opacity: 0.6 }}>No historical price records found.</p>
      </section>
    );
  }

  return (
    <section style={{ marginTop: '2rem' }}>
      <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <DollarSign size={20} /> Price History
      </h3>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Retailer</th>
              <th>Validity</th>
              <th>Current Price</th>
              <th>Original Price</th>
              <th>Discount</th>
              <th>Type</th>
              <th>Flyer PDF</th>
            </tr>
          </thead>
          <tbody>
            {priceHistory.map((h) => {
              const pdfUrl = buildAssetUrl(h.flyer_pdf_url);
              // Only active weeks keep their PDFs on disk!
              const pdfExists = pdfUrl && isFlyerAvailable(h.week_end);

              return (
                <tr key={h.offer_id}>
                  <td><strong>{h.retailer_name}</strong></td>
                  <td><small>{h.week_start} – {h.week_end}</small></td>
                  <td><strong style={{ color: '#2e7d32' }}>€{Number(h.current_price || 0).toFixed(2)}</strong></td>
                  <td>{h.original_price != null ? `€${Number(h.original_price).toFixed(2)}` : '—'}</td>
                  <td>{h.discount_percent != null ? `-${h.discount_percent}%` : '—'}</td>
                  <td><span className="badge">{h.offer_type || 'SPECIAL'}</span></td>
                  <td>
                    {pdfExists ? (
                      <a
                        href={pdfUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: '#4ade80', fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                      >
                        <FileText size={13} /> Page {h.flyer_page_number || '—'}
                      </a>
                    ) : (
                      <small style={{ opacity: 0.4 }}>Expired</small>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}