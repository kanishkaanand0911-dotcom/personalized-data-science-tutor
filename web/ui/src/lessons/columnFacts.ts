/* A small, honest read of one column from the real preview rows the backend
   already sent - never invented. Only as confident as 5-6 sample rows can
   make it, and it says so. */
export type ColumnFacts = {
  column: string;
  kind: "numeric" | "text";
  sampleValues: string[];
  missingCount: number | null; // null when the backend reported none for this column
};

export function analyzeColumn(
  column: string,
  preview: Record<string, unknown>[],
  missing: Record<string, number>,
): ColumnFacts {
  const values = preview.map((r) => r[column]).filter((v) => v != null && v !== "");
  const numeric = values.length > 0 && values.every((v) => !Number.isNaN(Number(v)));
  return {
    column,
    kind: numeric ? "numeric" : "text",
    sampleValues: values.slice(0, 3).map(String),
    missingCount: column in missing ? missing[column] : null,
  };
}

/* Plain, no data-type jargon: "a number you can do math on" beats "numeric",
   and "a label you'd group by" beats "categorical". */
export function describeColumn(facts: ColumnFacts): string {
  const kindLine =
    facts.kind === "numeric"
      ? `A number you can do math on - like ${facts.sampleValues.join(", ")}.`
      : `A label you'd sort or group by - like ${facts.sampleValues.join(", ")}.`;
  const missingLine =
    facts.missingCount != null && facts.missingCount > 0
      ? ` ${facts.missingCount} rows have no value here - more on that next mission.`
      : "";
  return `${kindLine}${missingLine}`;
}
