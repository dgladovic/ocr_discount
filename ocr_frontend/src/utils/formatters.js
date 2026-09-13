import { API_BASE_URL } from '../constants/tables';

export const buildAssetUrl = (url) => {
  if (!url) return null;
  const normalized = String(url).replace(/\\/g, '/');
  return normalized.startsWith('http')
    ? normalized
    : `${API_BASE_URL}/${normalized.replace(/^\/+/, '')}`;
};

/**
 * Checks if the flyer PDF is still available on disk.
 * Since the scraper cleans up PDFs whose EndDate has passed,
 * flyers are only physically present if week_end >= today.
 */
export const isFlyerAvailable = (weekEndStr) => {
  if (!weekEndStr) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const end = new Date(weekEndStr);
  return end >= today;
};