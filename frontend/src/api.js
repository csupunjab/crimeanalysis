const BASE = import.meta.env.VITE_API_BASE || '/api';

async function req(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Request failed: ${res.status}`);
  }
  return res;
}

export const api = {
  health: () => req('/health').then((r) => r.json()),
  districts: () => req('/meta/districts').then((r) => r.json()),
  divisions: () => req('/meta/divisions').then((r) => r.json()),
  categories: () => req('/meta/categories').then((r) => r.json()),
  dateBounds: () => req('/meta/date_bounds').then((r) => r.json()),
  runQuery: (payload) =>
    req('/query', { method: 'POST', body: JSON.stringify(payload) }).then((r) => r.json()),
  reportCatalog: () => req('/reports/catalog').then((r) => r.json()),
  defaultInsights: (reportType, startDate, endDate) => {
    const qs = new URLSearchParams({ report_type: reportType, start_date: startDate || '', end_date: endDate || '' });
    return req(`/reports/default_insights?${qs}`).then((r) => r.json());
  },
  generateReport: async (payload) => {
    const res = await req('/reports/generate', { method: 'POST', body: JSON.stringify(payload) });
    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('text/csv')) {
      const blob = await res.blob();
      return { type: 'csv', blob };
    }
    const json = await res.json();
    if (json.url) json.url = BASE + json.url;
    return { type: 'pdf', ...json };
  },
  exportEditedHtml: (html) =>
    req('/reports/export_html', { method: 'POST', body: JSON.stringify({ html }) }).then((r) => r.json()),
};
