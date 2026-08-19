import React, { useState, useEffect } from 'react';
import { api } from '../api';

// Same four accent colours the report's Executive Summary cards already use
// for automatic findings (crimson/violet/teal/amber) -- a user-added note
// picks from this exact palette so it reads as first-class, not bolted on.
const INSIGHT_COLORS = [
  { id: 'crimson', label: 'Red', hex: '#9f1239' },
  { id: 'violet', label: 'Purple', hex: '#6d28d9' },
  { id: 'teal', label: 'Teal', hex: '#0f766e' },
  { id: 'amber', label: 'Amber', hex: '#b45309' },
];

export default function ReportModal({ report, startDate, endDate, onClose }) {
  const [start, setStart] = useState(startDate);
  const [end, setEnd] = useState(endDate);
  const [headerNote, setHeaderNote] = useState('');
  const [customInsights, setCustomInsights] = useState([]);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsError, setInsightsError] = useState('');
  const [status, setStatus] = useState('idle'); // idle | working | done | error
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const isCrimeAnalytics = report && (report.id === 'crime_analytics' || report.id === 'crime_analytics_monthly');

  // Load the automatic findings into the editable list as soon as the modal
  // opens for one of these two reports, so the user sees -- and can change
  // -- exactly what would otherwise print by default, instead of finding
  // out only after generating the PDF.
  const loadDefaults = () => {
    if (!isCrimeAnalytics) return;
    setInsightsLoading(true);
    setInsightsError('');
    api.defaultInsights(report.id, start, end)
      .then((rows) => setCustomInsights(rows.map((r) => ({ text: r.text, color: r.color, tag: r.tag }))))
      .catch((e) => setInsightsError(e.message))
      .finally(() => setInsightsLoading(false));
  };

  useEffect(() => {
    if (report) {
      setCustomInsights([]);
      loadDefaults();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report?.id]);

  if (!report) return null;

  const dayCount = start && end ? Math.round((new Date(end) - new Date(start)) / 86400000) + 1 : null;

  const addInsight = () => setCustomInsights((rows) => [...rows, { text: '', color: 'crimson', tag: '' }]);
  const updateInsight = (i, field, value) =>
    setCustomInsights((rows) => rows.map((r, idx) => (idx === i ? { ...r, [field]: value } : r)));
  const removeInsight = (i) => setCustomInsights((rows) => rows.filter((_, idx) => idx !== i));

  const run = async (output) => {
    setStatus('working');
    setError('');
    try {
      const res = await api.generateReport({
        report_type: report.id,
        start_date: start,
        end_date: end,
        header_note: headerNote,
        // The whole edited list -- defaults as loaded, edited, reordered by
        // deletion, plus anything added -- replaces the report's own
        // computation entirely, so what's in this window is what prints.
        override_defaults: isCrimeAnalytics || undefined,
        custom_insights: isCrimeAnalytics
          ? customInsights.filter((ci) => ci.text.trim()).map((ci) => ({ text: ci.text.trim(), color: ci.color, tag: ci.tag }))
          : undefined,
        output,
      });
      if (res.type === 'csv') {
        const url = URL.createObjectURL(res.blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${report.id}-${start}-to-${end}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setResult({ type: 'csv' });
      } else if (output === 'html') {
        window.open(res.url, '_blank');
        setResult({ type: 'html', url: res.url });
      } else {
        setResult({ type: 'pdf', url: res.url });
      }
      setStatus('done');
    } catch (e) {
      setError(e.message);
      setStatus('error');
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{report.name}</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <p className="modal-desc">{report.description}</p>

        {isCrimeAnalytics ? (
          <div className="alert-success" style={{ marginTop: 0, marginBottom: 14 }}>
            Defaults to the full data history (01 July through the latest date on file). Change the dates below if you need a different window.
          </div>
        ) : null}

        <div className="field-row">
          <label>
            Start Date
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label>
            End Date
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
        </div>
        {dayCount ? (
          <p className="panel-sub" style={{ marginTop: -8, marginBottom: 14 }}>
            {dayCount} day{dayCount !== 1 ? 's' : ''} in this window &mdash; the report header will show this too.
          </p>
        ) : null}

        <label className="field-block">
          <span className="field-label">Header Note (optional)</span>
          <textarea
            placeholder='Shown at the top of every page, e.g. "Prepared for the CM Weekly Security Briefing"'
            value={headerNote}
            onChange={(e) => setHeaderNote(e.target.value)}
            rows={3}
          />
        </label>

        {isCrimeAnalytics && (
          <div className="field-block">
            <div className="field-label-row">
              <span className="field-label">Key Insights (first page)</span>
              <button type="button" className="link-btn" onClick={loadDefaults} disabled={insightsLoading}>
                {insightsLoading ? 'Loading…' : 'Reload Defaults'}
              </button>
            </div>
            <p className="panel-sub" style={{ marginTop: -2, marginBottom: 8 }}>
              This is exactly what will print on the first page. Edit or remove any of these, and add your own &mdash; if you leave everything as loaded, these defaults print as-is.
            </p>
            {insightsError && <div className="alert-error" style={{ marginBottom: 8 }}>{insightsError}</div>}
            {insightsLoading && customInsights.length === 0 ? (
              <p className="panel-sub">Loading current findings for this date range&hellip;</p>
            ) : (
              customInsights.map((row, i) => (
                <div key={i} className="insight-edit-row">
                  <div className="insight-color-picker">
                    {INSIGHT_COLORS.map((c) => (
                      <button
                        key={c.id}
                        type="button"
                        title={c.label}
                        className={`insight-swatch${row.color === c.id ? ' insight-swatch-active' : ''}`}
                        style={{ background: c.hex }}
                        onClick={() => updateInsight(i, 'color', c.id)}
                      />
                    ))}
                  </div>
                  {row.tag ? <span className="insight-tag-chip">{row.tag}</span> : null}
                  <input
                    type="text"
                    className="insight-text-input"
                    placeholder="e.g. Additional patrols deployed in Multan division this week"
                    value={row.text}
                    onChange={(e) => updateInsight(i, 'text', e.target.value)}
                  />
                  <button type="button" className="insight-remove-btn" title="Remove" onClick={() => removeInsight(i)}>&times;</button>
                </div>
              ))
            )}
            <button type="button" className="btn-secondary btn-add-insight" onClick={addInsight}>+ Add Insight</button>
          </div>
        )}

        {report.format === 'pdf' ? (
          <div className="field-row" style={{ marginBottom: 0 }}>
            <button className="btn-primary" onClick={() => run('html')} disabled={status === 'working'}>
              {status === 'working' ? 'Working…' : 'Preview & Edit'}
            </button>
            <button className="btn-primary" onClick={() => run('pdf')} disabled={status === 'working'}>
              {status === 'working' ? 'Working…' : 'Generate PDF Directly'}
            </button>
          </div>
        ) : (
          <button className="btn-primary" onClick={() => run('csv')} disabled={status === 'working'}>
            {status === 'working' ? 'Generating…' : 'Generate Report'}
          </button>
        )}

        {report.format === 'pdf' && (
          <p className="panel-sub" style={{ marginTop: 8, marginBottom: 0 }}>
            "Preview & Edit" opens the report in a new tab where you can click into any heading or text and retype it, then export the edited version to PDF from a button on that page.
          </p>
        )}

        {status === 'error' && <div className="alert-error">{error}</div>}

        {status === 'done' && result?.type === 'pdf' && (
          <div className="alert-success">
            Report ready.{' '}
            <a href={result.url} target="_blank" rel="noreferrer">Open PDF</a>
          </div>
        )}
        {status === 'done' && result?.type === 'html' && (
          <div className="alert-success">Preview opened in a new tab.</div>
        )}
        {status === 'done' && result?.type === 'csv' && (
          <div className="alert-success">CSV downloaded.</div>
        )}
      </div>
    </div>
  );
}
