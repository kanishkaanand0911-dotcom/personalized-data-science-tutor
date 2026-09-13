import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/Button";
import { QuizOption } from "@/components/ui/QuizOption";
import { DownHint } from "@/components/ui/DownHint";
import { LoadingScene } from "@/components/ui/LoadingScene";
import { HeroIllustration } from "@/components/HeroIllustration";
import { TopBar } from "@/components/TopBar";
import { Login } from "@/screens/Login";
import { api, type Profile } from "@/lib/api";

type QuizKey = "role" | "experience" | "goal";
type QuizStep = { key: QuizKey; question: string; options: string[]; allowCustom?: boolean };

const QUIZ: QuizStep[] = [
  {
    key: "role",
    question: "What’s your day-to-day?",
    options: ["Sales", "Operations", "HR", "Student"],
    allowCustom: true,
  },
  {
    key: "experience",
    question: "How much do you already know?",
    options: ["New to this", "Know the basics", "Pretty confident"],
  },
  {
    key: "goal",
    question: "What are you hoping to get out of this?",
    options: [
      "Get better at my job",
      "Curious how it actually works",
      "Coursework or school",
      "Just exploring",
    ],
  },
];

type Stage = "hero" | "login" | "quiz" | "loading";

export function Onboarding({ onDone }: { onDone: (profile: Profile) => void }) {
  const [stage, setStage] = useState<Stage>("hero");
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Partial<Record<QuizKey, string>>>({});
  const [customRole, setCustomRole] = useState("");
  const [error, setError] = useState<string | null>(null);

  const current = QUIZ[step];
  const isCustom = current.key === "role" && answers.role === "__custom__";
  const answered = isCustom ? customRole.trim().length > 0 : !!answers[current.key];

  const choose = (key: QuizKey, value: string) => {
    setAnswers((a) => ({ ...a, [key]: value }));
    if (key === "role" && value !== "__custom__") setCustomRole("");
  };

  const finish = async (profile: Profile, fallbackStage: Stage) => {
    setStage("loading");
    setError(null);
    try {
      await Promise.all([
        api.startSession(profile),
        new Promise((r) => setTimeout(r, 1400)), // let the loading scene breathe
      ]);
      onDone(profile);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start. Try again.");
      setStage(fallbackStage);
    }
  };

  const next = () => {
    if (step < QUIZ.length - 1) {
      setStep((s) => s + 1);
      return;
    }
    const roleValue = answers.role === "__custom__" ? customRole.trim() : answers.role ?? null;
    void finish(
      {
        role: roleValue ? roleValue.toLowerCase() : null,
        experience: answers.experience ?? null,
        goal: answers.goal ?? null,
      },
      "quiz",
    );
  };

  const loginSuccess = () => {
    // A returning/demo login skips the quiz - reasonable defaults, no
    // guessing needed since there's no real account data behind this.
    void finish({ role: "admin", experience: "pretty confident", goal: "just exploring" }, "login");
  };

  if (stage === "loading") {
    return <LoadingScene label="Tweaking things and building a roadmap just for you." />;
  }

  if (stage === "login") {
    return <Login onBack={() => setStage("hero")} onSuccess={loginSuccess} />;
  }

  if (stage === "quiz") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-bg px-8 py-16 text-center">
        <span className="text-sm font-extrabold uppercase tracking-[0.1em] text-hero">
          First, a couple of things &mdash; let&rsquo;s get to know you
        </span>

        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="mt-6 flex w-full flex-col items-center"
          >
            <h2 className="text-3xl text-ink">{current.question}</h2>

            <div className="mt-8 flex w-full max-w-[360px] flex-col items-center gap-2.5">
              {current.options.map((o) => (
                <QuizOption
                  key={o}
                  label={o}
                  selected={answers[current.key] === o}
                  onClick={() => choose(current.key, o)}
                />
              ))}
              {current.allowCustom && (
                <QuizOption
                  label={isCustom ? customRole || "Something else" : "Something else"}
                  selected={isCustom}
                  onClick={() => choose(current.key, "__custom__")}
                />
              )}
              {isCustom && (
                <input
                  autoFocus
                  className="w-full max-w-[320px] border border-white/10 bg-white/[0.03] px-4 py-2.5 text-center text-sm text-ink outline-none focus-visible:border-hero"
                  placeholder="Type it in"
                  value={customRole}
                  onChange={(e) => setCustomRole(e.target.value)}
                />
              )}
            </div>
          </motion.div>
        </AnimatePresence>

        {error && <p className="mt-4 text-sm text-fail">{error}</p>}

        <div className="mt-10 flex items-center gap-4">
          {step > 0 && (
            <button
              type="button"
              onClick={() => setStep((s) => s - 1)}
              className="text-sm font-semibold text-ink-soft hover:text-ink"
            >
              &larr; Back
            </button>
          )}
          <Button glow disabled={!answered} onClick={next}>
            {step < QUIZ.length - 1 ? "Continue" : "Let's go"}
            <span aria-hidden>&rarr;</span>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg">
      <TopBar right="Login" onRightClick={() => setStage("login")} />

      <div className="px-4 pb-4 md:px-6 md:pb-6">
        <div className="relative grid min-h-[calc(100vh-88px)] grid-cols-1 overflow-hidden border border-white/10 bg-white/[0.025] lg:grid-cols-2">
          <div className="flex flex-col justify-center px-8 py-14 lg:px-14">
            <div className="mx-auto w-full max-w-[440px]">
              <h1 className="text-6xl leading-[0.96] text-ink lg:text-[4.25rem]">
                Let&rsquo;s vybe
              </h1>
              <p className="mt-4 max-w-[38ch] text-[15px] font-medium text-ink-soft">
                <span className="text-hero">Who says data science has to be boring?</span>{" "}
                Bring your messiest spreadsheet and find out.
              </p>
              <div className="mt-8">
                <Button glow type="button" onClick={() => setStage("quiz")}>
                  Let&rsquo;s go <span aria-hidden>&rarr;</span>
                </Button>
              </div>
              <button
                type="button"
                onClick={() => setStage("quiz")}
                className="mt-10 w-fit text-left"
                aria-label="Get started"
              >
                <DownHint />
              </button>
            </div>
          </div>

          <div className="relative hidden lg:block">
            <HeroIllustration />
          </div>
        </div>
      </div>
    </div>
  );
}
