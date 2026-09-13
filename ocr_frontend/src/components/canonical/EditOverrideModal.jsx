import React, { useState } from 'react';

export default function EditOverrideModal({ canonical, onSave, onCancel, submitting }) {
  const [formData, setFormData] = useState({ ...canonical });

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({
      display_name: formData.display_name,
      brand: formData.brand,
      category: formData.category,
      product_type: formData.product_type,
      unit_size: formData.unit_size ? Number(formData.unit_size) : null,
      unit_measurement: formData.unit_measurement,
      fat_percent: formData.fat_percent ? Number(formData.fat_percent) : null,
      organic: formData.organic,
      image_url: formData.image_url,
      edited_by: 'admin@retailoffers.com',
    });
  };

  return (
    <dialog open>
      <article style={{ maxWidth: '600px', width: '100%' }}>
        <header>
          <button aria-label="Close" className="close" onClick={onCancel} />
          <strong>Edit Canonical Product Override</strong>
        </header>

        <p style={{ fontSize: '0.85rem', opacity: 0.7 }}>
          Saving an override locks this product from automated weekly AI ingestion updates.
        </p>

        <form onSubmit={handleSubmit}>
          <label>
            Display Name
            <input
              type="text"
              value={formData.display_name || ''}
              onChange={(e) => handleChange('display_name', e.target.value)}
              required
            />
          </label>

          <div className="grid">
            <label>
              Brand
              <input
                type="text"
                value={formData.brand || ''}
                onChange={(e) => handleChange('brand', e.target.value)}
              />
            </label>

            <label>
              Category
              <input
                type="text"
                value={formData.category || ''}
                onChange={(e) => handleChange('category', e.target.value)}
                required
              />
            </label>
          </div>

          <div className="grid">
            <label>
              Product Type
              <input
                type="text"
                value={formData.product_type || ''}
                onChange={(e) => handleChange('product_type', e.target.value)}
                required
              />
            </label>

            <label>
              Organic
              <select
                value={formData.organic || 'unknown'}
                onChange={(e) => handleChange('organic', e.target.value)}
              >
                <option value="yes">Yes</option>
                <option value="no">No</option>
                <option value="unknown">Unknown</option>
              </select>
            </label>
          </div>

          <div className="grid">
            <label>
              Unit Size
              <input
                type="number"
                step="any"
                value={formData.unit_size ?? ''}
                onChange={(e) => handleChange('unit_size', e.target.value)}
              />
            </label>

            <label>
              Unit
              <select
                value={formData.unit_measurement || ''}
                onChange={(e) => handleChange('unit_measurement', e.target.value)}
              >
                <option value="">None</option>
                <option value="g">g</option>
                <option value="kg">kg</option>
                <option value="ml">ml</option>
                <option value="l">l</option>
                <option value="pcs">pcs</option>
                <option value="washes">washes</option>
              </select>
            </label>

            <label>
              Fat %
              <input
                type="number"
                step="any"
                value={formData.fat_percent ?? ''}
                onChange={(e) => handleChange('fat_percent', e.target.value)}
              />
            </label>
          </div>

          <label>
            Image URL
            <input
              type="text"
              value={formData.image_url || ''}
              onChange={(e) => handleChange('image_url', e.target.value)}
            />
          </label>

          <footer>
            <div style={{ display: 'flex', gap: '0.8rem', justifyContent: 'flex-end' }}>
              <button type="button" className="secondary outline" onClick={onCancel} disabled={submitting}>
                Cancel
              </button>
              <button type="submit" disabled={submitting}>
                {submitting ? 'Saving...' : 'Save & Lock Product'}
              </button>
            </div>
          </footer>
        </form>
      </article>
    </dialog>
  );
}