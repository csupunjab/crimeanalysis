import React from 'react';

export default function DataTable({ result, categoryLabels }) {
  if (!result) {
    return <div className="empty-state">Run a query to see district-level results here.</div>;
  }
  const { rows, totals, categories } = result;
  if (!rows.length) {
    return <div className="empty-state">No data for the selected filters.</div>;
  }

  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>District</th>
            {categories.map((c) => (
              <th key={c} className="num">{categoryLabels[c] || c}</th>
            ))}
            <th className="num">Total</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.name_en}</td>
              {categories.map((c) => (
                <td key={c} className="num">{r[c]}</td>
              ))}
              <td className="num total-col">{r.total}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td>Province Total</td>
            {categories.map((c) => (
              <td key={c} className="num">{totals[c]}</td>
            ))}
            <td className="num total-col">{totals.total}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
