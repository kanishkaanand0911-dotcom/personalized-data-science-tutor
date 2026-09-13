import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { DownHint } from "@/components/ui/DownHint";
import { Reveal } from "@/components/ui/Reveal";
import { api, type Results as ResultsT } from "@/lib/api";

export function Results({
  onRestart,
  onNewDataset,
}: {
  onRestart: () => void;
  onNewDataset: () => void;
}) {
  const [data, setData] = useState<ResultsT | null>(null);

  useEffect(() => {
    api.results().then(setData).catch(() => setData(null));
  }, []);

  if (!data) {
    return <p className="mx-auto max-w-[900px] px-8 py-16 text-ink-soft">Putting your results together...</p>;
  }

  return (
    <div className="mx-auto max-w-[900px] px-8 py-16">
      <span className="text-xs font-bold uppercase tracking-[0.14em] text-hero">Final Project</span>
      <h1 className="mt-2 text-5xl text-ink">Your complete, portfolio-ready analysis</h1>
      <p className="mt-3 max-w-[60ch] text-[15px] text-ink-soft">
        Every decision below is the agent&rsquo;s real, explained work - cleaning, checks,
        charts, and the chosen model. Your guesses were scored alongside it, never fed into it.
      </p>

      <div className="mt-4">
        <DownHint label="keep scrolling" />
      </div>

      <div className="mt-8 grid grid-cols-2 gap-6 sm:grid-cols-4">
        <Stat n={data.points_total} k="points" />
        <Stat n={`${data.levels_correct}/${data.levels_total}`} k="guesses right" />
        <Stat n={data.downstream_passed ? "Pass" : "Mixed"} k="verification" />
        <Stat n={data.model.chosen ? data.model.chosen.label : "None"} k="model chosen" />
      </div>

      <Reveal>
        <div className="mt-10">
          <h2 className="text-2xl">What changed</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {data.columns_changed.length ? (
              data.columns_changed.map((c) => (
                <span
                  key={c}
                  className="rounded-full border border-line bg-hero/5 px-3 py-1 text-sm font-medium text-ink"
                >
                  {c}
                </span>
              ))
            ) : (
              <span className="text-sm text-ink-soft">no columns needed changes</span>
            )}
          </div>
        </div>
      </Reveal>

      <Reveal delay={0.08}>
        <div className="mt-8 overflow-x-auto rounded-[var(--radius-app)] border border-line">
          <table className="w-full text-sm">
            <thead className="bg-hero/5">
              <tr>
                {data.cleaned_columns.map((c) => (
                  <th key={c} className="whitespace-nowrap px-3 py-2 text-left font-semibold">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.cleaned_preview.map((row, i) => (
                <tr key={i} className="border-t border-line">
                  {data.cleaned_columns.map((c) => (
                    <td key={c} className="whitespace-nowrap px-3 py-2">
                      {row[c] == null ? (
                        <span className="italic text-fail">empty</span>
                      ) : (
                        String(row[c])
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Reveal>

      <Reveal delay={0.16}>
        <Lesson markdown={data.lesson} />
      </Reveal>

      <div className="mt-10 flex gap-3">
        <Button glow onClick={onNewDataset}>
          Try another dataset
        </Button>
        <Button variant="ghost" onClick={onRestart}>
          Start over
        </Button>
      </div>
    </div>
  );
}

function Stat({ n, k }: { n: string | number; k: string }) {
  return (
    <div>
      <div className="text-3xl font-semibold text-ink">{n}</div>
      <div className="text-xs text-ink-soft">{k}</div>
    </div>
  );
}

function Lesson({ markdown }: { markdown: string }) {
  const blocks: React.ReactNode[] = [];
  let list: string[] = [];
  const flush = (key: string) => {
    if (list.length) {
      blocks.push(
        <ul key={key} className="ml-5 list-disc space-y-1.5 text-sm text-ink">
          {list.map((li, i) => (
            <li key={i}>{li}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };
  markdown.split("\n").forEach((raw, i) => {
    const line = raw.trim();
    if (!line) return;
    if (line.startsWith("## ")) {
      flush(`ul-${i}`);
      blocks.push(
        <h2 key={i} className="mt-5 text-xl first:mt-0">
          {line.slice(3)}
        </h2>,
      );
    } else if (line.startsWith("- ")) {
      list.push(line.slice(2));
    } else {
      flush(`ul-${i}`);
      blocks.push(
        <p key={i} className="text-sm text-ink">
          {line}
        </p>,
      );
    }
  });
  flush("ul-end");

  return (
    <div className="mt-10 rounded-[var(--radius-app)] border border-line bg-surface p-6">
      {blocks}
    </div>
  );
}
