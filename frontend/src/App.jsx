import React, { useEffect, useState } from 'react';
import { api } from './api';
import FilterPanel from './components/FilterPanel';
import DataTable from './components/DataTable';
import ReportGallery from './components/ReportGallery';
import ReportModal from './components/ReportModal';

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}
function daysAgoISO(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

export default function App() {
  const [districts, setDistricts] = useState([]);
  const [categories, setCategories] = useState({ headline: [], all: [] });
  const [catalog, setCatalog] = useState([]);

  const [startDate, setStartDate] = useState(daysAgoISO(30));
  const [endDate, setEndDate] = useState(todayISO());
  const [selectedDistrictIds, setSelectedDistrictIds] = useState([]);
  const [selectedCategories, setSelectedCategories] = useState([]);

  const [queryResult, setQueryResult] = useState(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [activeReport, setActiveReport] = useState(null);
  const [apiOk, setApiOk] = useState(null);

  useEffect(() => {
    api.health().then(() => setApiOk(true)).catch(() => setApiOk(false));
    api.districts().then(setDistricts).catch(() => {});
    api.categories().then((c) => {
      setCategories(c);
      setSelectedCategories(c.headline.map((x) => x.key));
    }).catch(() => {});
    api.reportCatalog().then(setCatalog).catch(() => {});
    api.dateBounds().then((b) => {
      if (b.latest) setEndDate(b.latest);
      if (b.earliest) setStartDate(b.earliest);
    }).catch(() => {});
  }, []);

  const categoryLabels = Object.fromEntries(categories.all.map((c) => [c.key, c.label]));

  const toggleDistrict = (id) =>
    setSelectedDistrictIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  const toggleCategory = (key) =>
    setSelectedCategories((prev) => (prev.includes(key) ? prev.filter((x) => x !== key) : [...prev, key]));

  const runQuery = async () => {
    setQueryLoading(true);
    try {
      const res = await api.runQuery({
        start_date: startDate,
        end_date: endDate,
        district_ids: selectedDistrictIds,
        categories: selectedCategories,
      });
      setQueryResult(res);
    } catch (e) {
      console.error(e);
    } finally {
      setQueryLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">CSU</span>
          <div>
            <div className="brand-title">Crime Analysis Portal</div>
            <div className="brand-sub">Daily reporting &amp; deep-analysis report generator</div>
          </div>
        </div>
        <div className={`status-pill ${apiOk ? 'status-ok' : apiOk === false ? 'status-down' : ''}`}>
          {apiOk === null ? 'checking…' : apiOk ? 'API connected' : 'API unreachable'}
        </div>
      </header>

      <main className="app-main">
        <FilterPanel
          startDate={startDate}
          endDate={endDate}
          onStartDate={setStartDate}
          onEndDate={setEndDate}
          districts={districts}
          selectedDistrictIds={selectedDistrictIds}
          onToggleDistrict={toggleDistrict}
          onSelectAllDistricts={() => setSelectedDistrictIds(districts.filter(d => !d.exclude_from_analysis).map((d) => d.id))}
          onClearDistricts={() => setSelectedDistrictIds([])}
          categories={categories.headline}
          selectedCategories={selectedCategories}
          onToggleCategory={toggleCategory}
          onRunQuery={runQuery}
          loading={queryLoading}
        />

        <section className="content-col">
          <div className="panel">
            <h2>Query Results</h2>
            <DataTable result={queryResult} categoryLabels={categoryLabels} />
          </div>

          <div className="panel">
            <h2>Reports</h2>
            <p className="panel-sub">Pick a report type to generate it for the selected date range. You can add a custom note that appears at the top of every page.</p>
            <ReportGallery catalog={catalog} onSelect={setActiveReport} />
          </div>
        </section>
      </main>

      <ReportModal
        report={activeReport}
        startDate={startDate}
        endDate={endDate}
        onClose={() => setActiveReport(null)}
      />
    </div>
  );
}
