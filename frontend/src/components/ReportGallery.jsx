import React from 'react';

export default function ReportGallery({ catalog, onSelect }) {
  return (
    <div className="report-grid">
      {catalog.map((r) => (
        <button key={r.id} className="report-card" onClick={() => onSelect(r)} type="button">
          <div className="report-card-top">
            <span className={`format-badge format-${r.format}`}>{r.format.toUpperCase()}</span>
          </div>
          <div className="report-card-name">{r.name}</div>
          <div className="report-card-desc">{r.description}</div>
          <div className="report-card-cta">Generate &rarr;</div>
        </button>
      ))}
    </div>
  );
}
