import React from 'react';

export default function FilterPanel({
  startDate, endDate, onStartDate, onEndDate,
  districts, selectedDistrictIds, onToggleDistrict, onSelectAllDistricts, onClearDistricts,
  categories, selectedCategories, onToggleCategory,
  onRunQuery, loading,
}) {
  const byDivision = districts.reduce((acc, d) => {
    const key = d.division || 'Other';
    (acc[key] ||= []).push(d);
    return acc;
  }, {});

  return (
    <div className="panel">
      <h2>Filters</h2>

      <div className="field-row">
        <label>
          Start Date
          <input type="date" value={startDate} onChange={(e) => onStartDate(e.target.value)} />
        </label>
        <label>
          End Date
          <input type="date" value={endDate} onChange={(e) => onEndDate(e.target.value)} />
        </label>
      </div>

      <div className="field-block">
        <div className="field-label-row">
          <span className="field-label">Crime Categories</span>
        </div>
        <div className="chip-row">
          {categories.map((c) => (
            <button
              key={c.key}
              className={`chip ${selectedCategories.includes(c.key) ? 'chip-active' : ''}`}
              onClick={() => onToggleCategory(c.key)}
              type="button"
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      <div className="field-block">
        <div className="field-label-row">
          <span className="field-label">Districts ({selectedDistrictIds.length || 'all'})</span>
          <span className="link-row">
            <button className="link-btn" onClick={onSelectAllDistricts} type="button">select all</button>
            <button className="link-btn" onClick={onClearDistricts} type="button">clear</button>
          </span>
        </div>
        <div className="district-scroll">
          {Object.entries(byDivision).map(([division, ds]) => (
            <div key={division} className="division-group">
              <div className="division-label">{division}</div>
              <div className="chip-row">
                {ds.map((d) => (
                  <button
                    key={d.id}
                    type="button"
                    disabled={d.exclude_from_analysis}
                    title={d.exclude_from_analysis ? 'Excluded from analysis (incomplete reporting)' : ''}
                    className={`chip chip-sm ${selectedDistrictIds.includes(d.id) ? 'chip-active' : ''} ${d.exclude_from_analysis ? 'chip-disabled' : ''}`}
                    onClick={() => onToggleDistrict(d.id)}
                  >
                    {d.name_en}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <button className="btn-primary" onClick={onRunQuery} disabled={loading}>
        {loading ? 'Running…' : 'Run Query'}
      </button>
    </div>
  );
}
