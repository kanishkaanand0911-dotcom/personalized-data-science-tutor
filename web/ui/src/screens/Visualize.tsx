import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Rail } from "@/components/Rail";
import { Fade } from "@/components/ui/Fade";
import { Bars, Trend } from "@/components/charts/Charts";
import { api, type Level, type ModelResult, type VisualizeData, type GuessResult } from "@/lib/api";

export function Visualize({
  levels,
  guesses,
  onNext,
}: {
  levels: Level[];
  guesses: Record<number, GuessResult>;
  onNext: () => void;
}) {
  const [data, setData] = useState<VisualizeData | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Reuses the same observation the modeling step already computed - "find
  // relationships between variables" doesn't need its own separate stat.
  const [model, setModel] = useState<ModelResult | null>(null);

  useEffect(() => {
    api.visualize().then(setData).catch((e) => setError(e instanceof Error ? e.message : "Failed to load charts."));
    api.model().then(setModel).catch(() => setModel(null));
  }, []);

  return (
    <div className="mx-auto flex max-w-[1080px] gap-10 px-8 py-14">
      <Rail
        levels={levels}
        completedLevels={new Set(Object.keys(guesses).map(Number))}
        verifyDone
        visualizeDone={!!data}
        modelDone={false}
        active={{ kind: "visualize", label: "EDA" }}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-[0.14em] text-hero">
            Exploratory Data Analysis
          </span>
          <button
            type="button"
            onClick={onNext}
            className="text-xs font-semibold uppercase tracking-[0.1em] text-ink-soft hover:text-ink"
          >
            Skip EDA <span aria-hidden>&rarr;</span>
          </button>
        </div>
        {!data ? (
          <p className="mt-3 text-ink-soft">{error ?? "Charting your cleaned data..."}</p>
        ) : (
          <Fade k="visualize">
            <h1 className="mt-1 text-4xl text-ink">The shape of your data</h1>
            <p className="mt-2 max-w-[60ch] text-[15px] text-ink-soft">
              Real charts built from the cleaned columns - the same data every check and model
              downstream is actually using, not a mockup.
            </p>

            {model?.available && model.observation && (
              <Card className="mt-6 border-hero/30 bg-hero/5">
                <p className="text-sm font-semibold text-ink">Relationships between variables</p>
                <p className="mt-1 text-sm text-ink-soft">
                  Across your {model.observation.n_features} other columns, the strongest
                  connection to {model.target} is a{" "}
                  <span className="font-semibold text-ink">{model.observation.linearity_signal}</span>{" "}
                  one (correlation {model.observation.max_abs_correlation} on a 0-to-1 scale) - that&rsquo;s
                  the real signal the next stage will try to model.
                </p>
              </Card>
            )}

            {data.trend_chart && (
              <Card className="mt-6">
                <p className="text-sm font-semibold text-ink">
                  {data.trend_chart.column} over time
                </p>
                <p className="mt-0.5 text-xs text-ink-soft">
                  Monthly average, grouped by {data.trend_chart.date_column}.
                </p>
                <div className="mt-3">
                  <Trend points={data.trend_chart.points} />
                </div>
              </Card>
            )}

            {data.category_charts.length === 0 && data.numeric_charts.length === 0 && !data.trend_chart ? (
              <p className="mt-6 text-sm text-ink-soft">
                This dataset didn&rsquo;t have a column shape a chart could say something useful
                about.
              </p>
            ) : (
              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                {data.category_charts.map((c) => (
                  <Card key={c.column}>
                    <p className="text-sm font-semibold text-ink">{c.column}</p>
                    <p className="mt-0.5 text-xs text-ink-soft">How many rows fall in each group.</p>
                    <div className="mt-3">
                      <Bars bars={c.bars} color="var(--color-points)" />
                    </div>
                  </Card>
                ))}
                {data.numeric_charts.map((c) => (
                  <Card key={c.column}>
                    <p className="text-sm font-semibold text-ink">{c.column}</p>
                    <p className="mt-0.5 text-xs text-ink-soft">How the values are spread out.</p>
                    <div className="mt-3">
                      <Bars bars={c.bars} />
                    </div>
                  </Card>
                ))}
              </div>
            )}

            <div className="mt-8">
              <Button glow onClick={onNext}>
                On to modeling <span aria-hidden>&rarr;</span>
              </Button>
            </div>
          </Fade>
        )}
      </div>
    </div>
  );
}
