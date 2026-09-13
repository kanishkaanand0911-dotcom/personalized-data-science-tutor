import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Rail } from "@/components/Rail";
import { Fade } from "@/components/ui/Fade";
import { api, type Level, type ModelResult, type GuessResult } from "@/lib/api";

/* The one stage that was pure concept with no existing screen: features vs
   target, train/test splitting, and regression vs classification - grounded
   in the same real target/feature-count the modeling step already computed,
   not a generic textbook example. Comes right before Model Selection so the
   vocabulary exists before the real thing happens. */
export function MLFoundations({
  levels,
  guesses,
  onNext,
}: {
  levels: Level[];
  guesses: Record<number, GuessResult>;
  onNext: () => void;
}) {
  const [data, setData] = useState<ModelResult | null>(null);

  useEffect(() => {
    api.model().then(setData).catch(() => setData(null));
  }, []);

  return (
    <div className="mx-auto flex max-w-[1080px] gap-10 px-8 py-14">
      <Rail
        levels={levels}
        completedLevels={new Set(Object.keys(guesses).map(Number))}
        verifyDone
        visualizeDone
        mlFoundationsDone={!!data}
        modelDone={false}
        active={{ kind: "mlFoundations", label: "ML Foundations" }}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-[0.14em] text-hero">
            Machine Learning Foundations
          </span>
          <button
            type="button"
            onClick={onNext}
            className="text-xs font-semibold uppercase tracking-[0.1em] text-ink-soft hover:text-ink"
          >
            Skip foundations <span aria-hidden>&rarr;</span>
          </button>
        </div>

        {!data ? (
          <p className="mt-3 text-ink-soft">Working out the vocabulary for your data...</p>
        ) : !data.available ? (
          <Fade k="ml-unavail">
            <h1 className="mt-1 text-4xl text-ink">No modeling problem here</h1>
            <p className="mt-2 max-w-[60ch] text-[15px] text-ink-soft">{data.reason}</p>
            <div className="mt-8">
              <Button glow onClick={onNext}>
                Continue <span aria-hidden>&rarr;</span>
              </Button>
            </div>
          </Fade>
        ) : (
          <Fade k="ml-foundations">
            <h1 className="mt-1 text-4xl text-ink">The vocabulary before the model</h1>
            <p className="mt-2 max-w-[60ch] text-[15px] text-ink-soft">
              A few terms the next stage assumes you already have - all grounded in your own
              dataset, not a generic example.
            </p>

            <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Card>
                <p className="text-sm font-semibold text-ink">Target</p>
                <p className="mt-1 text-sm text-ink-soft">
                  The column you&rsquo;re trying to predict. For your data, that&rsquo;s{" "}
                  <span className="font-semibold text-ink">{data.target}</span>.
                </p>
              </Card>
              <Card>
                <p className="text-sm font-semibold text-ink">Features</p>
                <p className="mt-1 text-sm text-ink-soft">
                  Every other column the model is allowed to look at to make that prediction -{" "}
                  <span className="font-semibold text-ink">{data.observation?.n_features}</span> of
                  them here.
                </p>
              </Card>
              <Card>
                <p className="text-sm font-semibold text-ink">Training set &amp; test set</p>
                <p className="mt-1 text-sm text-ink-soft">
                  The {data.observation?.n_samples} rows get split: most are used to teach the
                  model, the rest are held back so it can be graded on rows it never saw - the
                  only fair way to know if it actually learned anything.
                </p>
              </Card>
              <Card>
                <p className="text-sm font-semibold text-ink">Regression vs. classification</p>
                <p className="mt-1 text-sm text-ink-soft">
                  {data.target} is a number, so this is{" "}
                  <span className="font-semibold text-ink">regression</span> - predicting a
                  quantity. If the target were a category instead (like &ldquo;will churn&rdquo; or
                  &ldquo;won&rsquo;t&rdquo;), it would be{" "}
                  <span className="font-semibold text-ink">classification</span> instead.
                </p>
              </Card>
            </div>

            <div className="mt-8">
              <Button glow onClick={onNext}>
                On to model selection <span aria-hidden>&rarr;</span>
              </Button>
            </div>
          </Fade>
        )}
      </div>
    </div>
  );
}
