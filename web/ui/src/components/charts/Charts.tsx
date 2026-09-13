import type { ChartBar, TrendPoint } from "@/lib/api";

/* Hand-rolled SVG charts, not a charting library - a handful of static bars
   and one trend line don't need a dependency, and this way every color is
   already a Night Signal token instead of fighting a library's own theme. */

const VIEW_W = 560;
const VIEW_H = 220;

export function Bars({ bars, color = "var(--color-hero)" }: { bars: ChartBar[]; color?: string }) {
  if (bars.length === 0) return null;
  const padBottom = 34;
  const padTop = 16;
  const max = Math.max(...bars.map((b) => b.value), 1);
  const slot = VIEW_W / bars.length;
  const gap = slot * 0.22;
  const plotH = VIEW_H - padBottom - padTop;

  return (
    <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} className="w-full" role="img" aria-label="Bar chart">
      {bars.map((b, i) => {
        const h = (plotH * b.value) / max;
        const x = i * slot + gap / 2;
        const y = VIEW_H - padBottom - h;
        const w = slot - gap;
        const label = b.label.length > 11 ? `${b.label.slice(0, 10)}…` : b.label;
        return (
          <g key={`${b.label}-${i}`}>
            <rect x={x} y={y} width={w} height={Math.max(h, 1)} rx={3} style={{ fill: color, opacity: 0.85 }} />
            <text x={x + w / 2} y={y - 4} textAnchor="middle" fontSize="9" style={{ fill: "var(--color-ink)" }}>
              {b.value}
            </text>
            <text x={x + w / 2} y={VIEW_H - padBottom + 13} textAnchor="middle" fontSize="9" style={{ fill: "var(--color-ink-soft)" }}>
              {label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function Trend({ points, color = "var(--color-hero)" }: { points: TrendPoint[]; color?: string }) {
  if (points.length < 2) return null;
  const padLeft = 8;
  const padRight = 8;
  const padTop = 16;
  const padBottom = 26;
  const plotW = VIEW_W - padLeft - padRight;
  const plotH = VIEW_H - padTop - padBottom;
  const values = points.map((p) => p.value);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;

  const coords = points.map((p, i) => ({
    x: padLeft + (plotW * i) / (points.length - 1),
    y: padTop + plotH - ((p.value - min) / range) * plotH,
    ...p,
  }));
  const linePath = coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L ${coords[coords.length - 1].x.toFixed(1)} ${VIEW_H - padBottom} L ${coords[0].x.toFixed(1)} ${VIEW_H - padBottom} Z`;
  const labelEvery = Math.max(1, Math.ceil(coords.length / 6));

  return (
    <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} className="w-full" role="img" aria-label="Trend line chart">
      <path d={areaPath} style={{ fill: color, opacity: 0.12 }} />
      <path d={linePath} style={{ fill: "none", stroke: color, strokeWidth: 2 }} />
      {coords.map((c, i) => (
        <circle key={`${c.label}-${i}`} cx={c.x} cy={c.y} r={2.5} style={{ fill: color }} />
      ))}
      {coords.map((c, i) =>
        i % labelEvery === 0 ? (
          <text
            key={`label-${c.label}-${i}`}
            x={c.x}
            y={VIEW_H - padBottom + 14}
            textAnchor="middle"
            fontSize="9"
            style={{ fill: "var(--color-ink-soft)" }}
          >
            {c.label}
          </text>
        ) : null,
      )}
    </svg>
  );
}
