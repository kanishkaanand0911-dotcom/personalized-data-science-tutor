import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Tag } from "@/components/ui/Tag";
import { Fade } from "@/components/ui/Fade";
import { LevelTransition } from "@/components/ui/LevelTransition";
import { StudyTopBar } from "@/components/StudyTopBar";
import { DataSnapshot } from "@/components/DataSnapshot";
import { Chatbot } from "@/components/lesson/Chatbot";
import { Callouts } from "@/components/lesson/Callouts";
import { Quiz } from "@/components/lesson/Quiz";
import { Flashcard } from "@/components/lesson/Flashcard";
import { FunFactBanner } from "@/components/lesson/FunFactBanner";
import { CodeReveal } from "@/components/lesson/CodeReveal";
import { Mascot } from "@/components/Mascot";
import { topicName, matchAnswer } from "@/lib/grading";
import { useMentor } from "@/components/mentor/MentorContext";
import { api, type Attempt, type GuessResult, type Level as LevelT } from "@/lib/api";

export function Level({
  levels,
  index,
  guesses,
  onGuessed,
  pointsTotal,
  onPointsChange,
  datasetPreview,
  onBack,
  onNext,
  onSkipCleaning,
}: {
  levels: LevelT[];
  index: number;
  guesses: Record<number, GuessResult>;
  onGuessed: (levelId: number, result: GuessResult) => void;
  pointsTotal: number;
  onPointsChange: (points: number) => void;
  datasetPreview: Record<string, unknown>[];
  verifyDone: boolean;
  modelDone: boolean;
  onBack: () => void;
  onNext: (nextIndex: number | null) => void;
  onSkipCleaning: () => void;
}) {
  const level = levels[index];
  const existing = guesses[level.id];
  const { setTask } = useMentor();

  // Reveal -> quiz -> recap -> code -> next level. Resets whenever the level
  // itself changes so navigating back into an already-guessed level starts over.
  const [revealStage, setRevealStage] = useState<"result" | "quiz" | "recap" | "code">("result");
  useEffect(() => setRevealStage("result"), [level.id]);

  // Forward-only transition beat: "Level N completed" -> "Level N+1 started".
  // Going back to review a level skips it.
  const [transition, setTransition] = useState<string[] | null>(() =>
    index === 0 ? [`Level 1 started`] : null,
  );
  const prevIndexRef = useRef(index);
  useEffect(() => {
    if (index > prevIndexRef.current) {
      setTransition([`Level ${prevIndexRef.current + 1} completed`, `Level ${index + 1} started`]);
    }
    prevIndexRef.current = index;
  }, [index]);

  // Reading the explanation earns a small bonus, once per level, independent
  // of whether the answer that follows is right.
  // Gives the mentor real grounding for "Why is this wrong?" / "Explain the
  // output" once a guess is scored - the same attempt reasons shown below.
  useEffect(() => {
    if (!existing) return;
    const summary = existing.attempts
      .map((a) => `${a.label}: ${a.passed ? "kept" : "discarded"} - ${a.reason}`)
      .join(" | ");
    setTask({ output: summary || undefined });
  }, [existing, setTask]);

  const readSent = useRef<Set<number>>(new Set());
  useEffect(() => {
    if (transition || existing || readSent.current.has(level.id)) return;
    readSent.current.add(level.id);
    api
      .markRead(level.id)
      .then((res) => onPointsChange(res.points_total))
      .catch(() => {
        /* the read bonus is a nice-to-have, never block the level on it */
      });
  }, [transition, existing, level.id, onPointsChange]);

  // A typed message that names one of the real options is treated as an
  // attempt (and actually scored by the agent); anything else goes to the
  // chatbot instead. Errors propagate to the Chatbot's own error bubble.
  const handleAttempt = async (text: string): Promise<boolean> => {
    const matched = matchAnswer(level, text);
    if (!matched) return false;
    const result = await api.guess(level.id, matched);
    onGuessed(level.id, result);
    onPointsChange(result.points_total);
    return true;
  };

  if (transition) {
    return (
      <LevelTransition phases={transition} points={pointsTotal} onDone={() => setTransition(null)} />
    );
  }

  return (
    <div className="min-h-screen bg-bg">
      <StudyTopBar skipLabel="Skip cleaning" onSkip={onSkipCleaning} />
      <div className="h-0.5 w-full bg-line">
        <div
          className="h-full bg-hero transition-[width] duration-300"
          style={{ width: `${(Object.keys(guesses).length / levels.length) * 100}%` }}
        />
      </div>

      <div className="mx-auto max-w-[980px] px-6 py-10">
        <button onClick={onBack} className="text-sm text-ink-soft hover:text-ink">
          &larr; Back
        </button>

        {!existing ? (
          <Fade k={`predict-${level.id}`}>
            {/* Two halves, no visible divider - just a gap. Left: what's
                wrong and the real data. Right: the tutor, with prompts up
                top so a blank chat box isn't the first thing you face. */}
            <div className="mt-4 grid grid-cols-1 gap-10 lg:grid-cols-2">
              <div>
                <div className="flex items-start gap-3">
                  <Mascot className="h-10 w-10 shrink-0" />
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
                      Level {index + 1} of {levels.length}
                    </p>
                    <h1 className="mt-0.5 text-2xl text-ink">{topicName(level.issue_type)}</h1>
                  </div>
                </div>
                <p className="mt-3 text-sm text-ink-soft">{level.analogy}</p>

                <div className="mt-6">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-soft">
                    A look at your data &mdash; column: {level.column}
                  </p>
                  {datasetPreview.length > 0 && (
                    <DataSnapshot column={level.column} issueType={level.issue_type} rows={datasetPreview} />
                  )}
                </div>
                <p className="mt-3 text-xs text-ink-soft">{pointsTotal} points so far</p>
              </div>

              <div className="flex flex-col gap-4">
                <Callouts levelId={level.id} />
                <div className="flex-1">
                  <Chatbot level={level} onAttempt={handleAttempt} heading="Learn while vybing" />
                </div>
              </div>
            </div>
            <FunFactBanner issueType={level.issue_type} />
          </Fade>
        ) : (
          <div className="mx-auto max-w-[640px]">
            {revealStage === "result" && (
              <Reveal level={level} result={existing} onNext={() => setRevealStage("quiz")} />
            )}
            {revealStage === "quiz" && (
              // Alternates by level so a recap never feels like the same
              // drill every time - even levels get a one-question flashcard,
              // odd levels get the fuller quiz.
              (index % 2 === 0 ? (
                <Flashcard
                  resetKey={level.id}
                  fetchQuestions={() => api.quiz(level.id)}
                  submitAnswers={(answers) => api.submitQuiz(level.id, answers)}
                  onDone={(points) => {
                    onPointsChange(points);
                    setRevealStage("recap");
                  }}
                />
              ) : (
                <Quiz
                  resetKey={level.id}
                  fetchQuestions={() => api.quiz(level.id)}
                  submitAnswers={(answers) => api.submitQuiz(level.id, answers)}
                  onDone={(points) => {
                    onPointsChange(points);
                    setRevealStage("recap");
                  }}
                />
              ))
            )}
            {revealStage === "recap" && (
              <Recap level={level} result={existing} onNext={() => setRevealStage("code")} />
            )}
            {revealStage === "code" && (
              <CodeReveal
                resetKey={level.id}
                heading="See the code"
                fetchCode={() => api.levelCode(level.id)}
                onNext={() => onNext(existing.next_level)}
                nextLabel={existing.next_level != null ? "Next topic" : "Check the data works"}
                onLoaded={(d) => setTask({ code: d.available ? (d.code ?? undefined) : undefined })}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Reveal({
  level,
  result,
  onNext,
}: {
  level: LevelT;
  result: GuessResult;
  onNext: () => void;
}) {
  return (
    <Fade k={`reveal-${level.id}`}>
      <div className="mt-2 text-center">
        <div className="flex justify-center">
          <Mascot className="h-14 w-14" />
        </div>
        <p className="mt-3 text-lg text-ink">
          {result.correct ? "Fixed. Nice read." : "Not quite - here is what actually happened."}
        </p>
        <span
          className={`mt-2 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${
            result.correct ? "bg-pass/12 text-pass" : "bg-fail/12 text-fail"
          }`}
        >
          {result.correct ? "You called it" : "The agent disagreed"}
        </span>
      </div>

      {result.attempts.length > 1 && (
        <div className="mt-6 flex items-start gap-3 rounded-md border border-hero/30 bg-hero/5 px-4 py-3 text-left">
          <Mascot className="h-8 w-8 shrink-0" />
          <p className="text-sm text-ink">
            <span className="font-semibold">Watch what just happened: </span>
            the agent didn&rsquo;t just pick an answer - it tried a fix, checked whether the fix
            actually held up on your real data, and switched strategies when the first one
            distorted things too much. That&rsquo;s the whole loop below.
          </p>
        </div>
      )}

      <div className="mt-4 space-y-3 text-left">
        {result.attempts.map((a) => (
          <AttemptCard key={a.strategy} a={a} mine={a.strategy === result.your_choice} />
        ))}
      </div>

      {!result.resolved && (
        <p className="mt-4 rounded-md border border-points bg-points/10 px-4 py-3 text-sm text-ink">
          Every strategy for this column failed its check, so the agent
          flagged it for a human. That is the honest-failure path, not a bug.
        </p>
      )}

      <div className="mt-4 text-center">
        <Tag tone={result.points_awarded >= 0 ? "points" : "fail"}>
          {result.points_awarded >= 0 ? "+" : ""}
          {result.points_awarded} points
        </Tag>
      </div>

      <div className="mt-6 flex justify-center">
        <Button variant="flat" onClick={onNext}>
          Quick recap <span aria-hidden>&rarr;</span>
        </Button>
      </div>
    </Fade>
  );
}

function Recap({ level, result, onNext }: { level: LevelT; result: GuessResult; onNext: () => void }) {
  return (
    <Fade k={`recap-${level.id}`}>
      <div className="text-center">
        <div className="flex justify-center">
          <Mascot className="h-12 w-12" />
        </div>
        <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-ink-soft">
          Recap &mdash; {topicName(level.issue_type)}
        </p>
        <p className="mt-2 text-sm text-ink">
          On <span className="font-semibold">{level.column}</span>, the agent kept{" "}
          <span className="font-semibold">{result.agent_choice_label}</span>
          {result.resolved ? "." : " only after every other option failed its check."}
        </p>
      </div>

      <div className="mt-6 flex justify-center">
        <Button variant="flat" onClick={onNext}>
          See the code <span aria-hidden>&rarr;</span>
        </Button>
      </div>
    </Fade>
  );
}

function AttemptCard({ a, mine }: { a: Attempt; mine: boolean }) {
  // "Skew" is the real statistic behind this check, but it's not a word a
  // non-technical learner needs - the reason text above already explains the
  // shift in plain language, so this line just shows it moved, not its jargon.
  const stats: string[] = [];
  if (a.before.skew != null && a.after.skew != null)
    stats.push(`shape ${a.before.skew} to ${a.after.skew}`);
  if (a.before.null_pct != null && a.after.null_pct != null)
    stats.push(`blanks ${a.before.null_pct}% to ${a.after.null_pct}%`);
  // "labels" only makes sense for text columns (merging spelling variants) -
  // a numeric column's distinct-value count naturally shifts after filling
  // blanks with new numbers, and calling that "labels" is just confusing.
  const isTextColumn = a.before.dtype === "object" || a.after.dtype === "object";
  if (isTextColumn && a.before.unique_count != null && a.after.unique_count !== a.before.unique_count)
    stats.push(`labels ${a.before.unique_count} to ${a.after.unique_count}`);

  return (
    <Card className="border-line bg-surface">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`font-semibold ${!a.passed ? "text-ink-soft line-through" : "text-ink"}`}>
          {a.label}
        </span>
        <Tag tone={a.passed ? "pass" : "fail"}>{a.passed ? "kept" : "discarded"}</Tag>
        {mine && <Tag tone="neutral">your guess</Tag>}
      </div>
      <p className="mt-2 text-sm text-ink">{a.reason}</p>
      {stats.length > 0 && (
        <>
          <div className="mt-2 flex flex-wrap gap-4 text-xs text-ink-soft">
            {stats.map((s) => (
              <span key={s}>{s}</span>
            ))}
          </div>
          {a.before.skew != null && (
            <p className="mt-1 text-[11px] text-ink-soft">
              (&ldquo;shape&rdquo; here: the closer the second number stays to the first, the less this fix distorted your data)
            </p>
          )}
        </>
      )}
    </Card>
  );
}
