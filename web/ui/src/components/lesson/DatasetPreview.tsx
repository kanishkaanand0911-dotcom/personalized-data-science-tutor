/* A plain look at the learner's real data. Column headers are clickable
   when onSelectColumn is given - used for "pick a column" interactions. */
export function DatasetPreview({
  columns,
  rows,
  selectedColumn,
  onSelectColumn,
}: {
  columns: string[];
  rows: Record<string, unknown>[];
  selectedColumn?: string | null;
  onSelectColumn?: (column: string) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-md border border-line">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-line bg-surface">
            {columns.map((c) => {
              const clickable = !!onSelectColumn;
              const selected = c === selectedColumn;
              return (
                <th key={c} className="whitespace-nowrap px-3 py-2 text-left font-semibold">
                  {clickable ? (
                    <button
                      type="button"
                      onClick={() => onSelectColumn?.(c)}
                      className={`rounded px-1.5 py-0.5 transition-colors ${
                        selected ? "bg-hero text-white" : "text-ink-soft hover:text-hero"
                      }`}
                    >
                      {c}
                    </button>
                  ) : (
                    <span className="text-ink-soft">{c}</span>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 6).map((row, i) => (
            <tr key={i} className="border-b border-line last:border-b-0">
              {columns.map((c) => {
                const v = row[c];
                const empty = v == null || v === "";
                return (
                  <td
                    key={c}
                    className={`whitespace-nowrap px-3 py-2 ${
                      c === selectedColumn ? "bg-hero/5 text-ink" : "text-ink-soft"
                    } ${empty ? "italic text-fail" : ""}`}
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
