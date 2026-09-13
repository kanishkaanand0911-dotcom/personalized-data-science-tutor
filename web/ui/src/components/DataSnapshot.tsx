/* A small, plain look at the learner's own data - just enough rows to see
   the actual problem, not a full data browser. */
export function DataSnapshot({
  column,
  issueType,
  rows,
}: {
  column: string;
  issueType: string;
  rows: Record<string, unknown>[];
}) {
  const isMissingKind = issueType === "missing_numeric" || issueType === "missing_categorical";
  const neighborCols = rows.length ? Object.keys(rows[0]).filter((c) => c !== column).slice(0, 2) : [];
  const cols = [column, ...neighborCols];

  return (
    <div className="overflow-x-auto rounded-md border border-line">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-line bg-surface">
            {cols.map((c) => (
              <th
                key={c}
                className={`whitespace-nowrap px-3 py-2 text-left font-semibold ${
                  c === column ? "text-hero" : "text-ink-soft"
                }`}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 5).map((row, i) => (
            <tr key={i} className="border-b border-line last:border-b-0">
              {cols.map((c) => {
                const v = row[c];
                const empty = v == null || v === "";
                const flagged = c === column && isMissingKind && empty;
                return (
                  <td
                    key={c}
                    className={`whitespace-nowrap px-3 py-2 ${
                      flagged
                        ? "bg-fail/10 font-semibold text-fail"
                        : c === column
                          ? "text-ink"
                          : "text-ink-soft"
                    }`}
                  >
                    {empty ? "blank" : String(v)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
