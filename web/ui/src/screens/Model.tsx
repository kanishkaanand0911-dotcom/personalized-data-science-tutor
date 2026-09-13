import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Rail } from "@/components/Rail";
import { Fade } from "@/components/ui/Fade";
import { Quiz } from "@/components/lesson/Quiz";
import { CodeReveal } from "@/components/lesson/CodeReveal";
import { Mascot } from "@/components/Mascot";
import { useMentor } from "@/components/mentor/MentorContext";
import { api, type Level, type ModelResult, type GuessResult } from "@/lib/api";

export function Model({
  levels,
  guesses,
  onPointsChange,
  onNext,
}: {
  levels: Level[];
  guesses: Record<number, GuessResult>;
  onPointsChange: (points: number) => void;
  onNext: () => void;
}) {
  const [data, setData] = useState<ModelResult | null>(null);
  // Same reveal -> quiz -> recap -> code beat as a level, once for the
  // whole modeling phase rather than once per level.
  const [stage, setStage] = useState<"result" | "quiz" | "recap" | "code">("result");
  const { setTask } = useMentor();

  useEffect(() => {
    api.model().then(setData).catch(() => setData(null));
  }, []);

  // Gives the mentor real grounding for "Why is this wrong?" / "Explain the
  // output" once the modeling result is in.
  useEffect(() => {
    if (!data?.available) return;
    const attemptsSummary = data.attempts
      .map((a) => `${a.label}: ${a.passed ? "kept" : "escalated"} - ${a.reason}`)
      .join(" | ");
    const chosenSummary = data.chosen
      ? `Chosen: ${data.chosen.label}, R2=${data.chosen.cv_r2} on ${data.target}.`
      : "No model met the bar - flagged for a human.";
    setTask({ output: `${attemptsSummary} | ${chosenSummary}` });
  }, [data, setTask]);

  return (
    <div className="mx-auto flex max-w-[1080px] gap-10 px-8 py-14">
      <Rail
        levels={levels}
        completedLevels={new Set(Object.keys(guesses).map(Number))}
        verifyDone
        visualizeDone
        mlFoundationsDone
        modelDone={!!data}
        active={{ kind: "model", label: "Model Selection" }}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-[0.14em] text-hero">
            Model Selection & Evaluation
          </span>
          <button
            type="button"
            onClick={onNext}
            className="text-xs font-semibold uppercase tracking-[0.1em] text-ink-soft hover:text-ink"
          >
            Skip modeling <span aria-hidden>&rarr;</span>
          </button>
        </div>
        {stage === "quiz" && data ? (
          <Quiz
            resetKey="model"
            fetchQuestions={() => api.modelQuiz()}
            submitAnswers={(answers) => api.submitModelQuiz(answers)}
            onDone={(points) => {
              onPointsChange(points);
              setStage("recap");
            }}
          />
        ) : stage === "recap" && data ? (
          <ModelRecap data={data} onNext={() => setStage("code")} />
        ) : stage === "code" && data ? (
          <CodeReveal
            resetKey="model"
            heading="See the code"
            fetchCode={() => api.modelCode()}
            onNext={onNext}
            nextLabel="See the results"
            onLoaded={(d) => setTask({ code: d.available ? (d.code ?? undefined) : undefined })}
          />
        ) : !data ? (
          <p className="mt-3 text-ink-soft">Fitting models and checking which one actually fits...</p>
        ) : !data.available ? (
          <Fade k="model-unavail">
            <h1 className="mt-1 text-4xl text-ink">Modeling was skipped for this data</h1>
            <p className="mt-2 text-ink-soft">{data.reason}</p>
            <div className="mt-8">
              <Button glow onClick={() => setStage("quiz")}>
                Quick recap <span aria-hidden>&rarr;</span>
              </Button>
            </div>
          </Fade>
        ) : (
          <Fade k="model">
            <h1 className="mt-1 text-4xl text-ink">Predicting {data.target}</h1>

            {data.chosen && (
              <Card className="mt-5 border-hero/30 bg-hero/5">
                <div className="flex items-start gap-3">
                  <Mascot className="h-9 w-9 shrink-0" />
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
                      What&rsquo;s actually happening in a {data.chosen.label}
                    </p>
                    <p className="mt-1 text-sm text-ink">{data.chosen.explanation}</p>
                  </div>
                </div>
              </Card>
            )}

            <Card className="mt-3 bg-hero/5">
              <p className="text-sm text-ink">
                <span className="font-semibold">Why this one. </span>
                {data.observation!.n_samples} rows and {data.observation!.n_features} other
                columns to learn from, with a {data.observation!.linearity_signal} straight-line
                relationship between them (strongest connection: {data.observation!.max_abs_correlation}{" "}
                on a 0-to-1 scale). {data.start_reason}
              </p>
            </Card>
            <div className="mt-4 space-y-3">
              {data.attempts.map((a) => (
                <Card key={a.model} className="flex gap-3">
                  <span
                    className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                      a.passed ? "bg-pass/15 text-pass" : "bg-fail/15 text-fail"
                    }`}
                  >
                    {a.passed ? "✓" : "✕"}
                  </span>
                  <div>
                    <div className="font-semibold text-ink">
                      {a.label}{a.passed ? ", kept" : ", escalated"}
                    </div>
                    <div className="text-sm text-ink-soft">{a.reason}</div>
                  </div>
                </Card>
              ))}
            </div>
            {data.chosen ? (
              <Card className="mt-4 bg-pass/8">
                <p className="text-sm text-ink">
                  <span className="font-semibold">Chosen. </span>
                  {data.chosen.label}, tested on data it hadn&rsquo;t seen before - it explained
                  about {data.chosen.cv_r2} of the pattern in {data.target} (0 to 1, where 1 is a
                  perfect fit).
                </p>
              </Card>
            ) : (
              <p className="mt-4 rounded-[var(--radius-app)] border border-fail bg-fail/8 px-4 py-3 text-sm text-ink">
                No model met the bar, so this was flagged for a human. The
                agent will not force a low-confidence pick.
              </p>
            )}
            <div className="mt-8">
              <Button glow onClick={() => setStage("quiz")}>
                Quick recap <span aria-hidden>&rarr;</span>
              </Button>
            </div>
          </Fade>
        )}
      </div>
    </div>
  );
}

function ModelRecap({ data, onNext }: { data: ModelResult; onNext: () => void }) {
  return (
    <Fade k="model-recap">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">Recap - Modeling</p>
      <p className="mt-2 text-sm text-ink">
        {data.chosen ? (
          <>
            The agent kept <span className="font-semibold">{data.chosen.label}</span> to predict{" "}
            <span className="font-semibold">{data.target}</span>.
          </>
        ) : (
          "No model passed its accuracy check on this data, so it was flagged for a human rather than forced."
        )}
      </p>
      <div className="mt-6">
        <Button variant="flat" onClick={onNext}>
          See the code <span aria-hidden>&rarr;</span>
        </Button>
      </div>
    </Fade>
  );
}
