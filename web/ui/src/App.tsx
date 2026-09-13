import { useEffect, useState } from "react";
import { Onboarding } from "@/screens/Onboarding";
import { Dataset } from "@/screens/Dataset";
import { Mission1 } from "@/screens/Mission1";
import { Roadmap } from "@/screens/Roadmap";
import { Level } from "@/screens/Level";
import { Verify } from "@/screens/Verify";
import { Visualize } from "@/screens/Visualize";
import { MLFoundations } from "@/screens/MLFoundations";
import { Model } from "@/screens/Model";
import { Results } from "@/screens/Results";
import { AutoAdvance } from "@/components/ui/AutoAdvance";
import { LoadingScene } from "@/components/ui/LoadingScene";
import { LevelTransition } from "@/components/ui/LevelTransition";
import { AiMentor } from "@/components/mentor/AiMentor";
import { MentorProvider, useMentor } from "@/components/mentor/MentorContext";
import { NotesButton } from "@/components/notes/NotesButton";
import { NotesScreen } from "@/components/notes/NotesScreen";
import { NotesProvider } from "@/components/notes/NotesContext";
import { clearSession, type DatasetLoadResponse, type GuessResult, type MentorLessonContext, type Profile } from "@/lib/api";

type Screen =
  | { name: "onboarding" }
  | { name: "dataset" }
  | { name: "roadmapLoading" }
  | { name: "roadmap" }
  | { name: "mission1Loading" }
  | { name: "mission1" }
  | { name: "level"; index: number }
  | { name: "verify" }
  | { name: "visualize" }
  | { name: "mlFoundations" }
  | { name: "model" }
  | { name: "results" };

const MENTOR_LESSON_BY_SCREEN: Partial<Record<Screen["name"], MentorLessonContext>> = {
  roadmap: { id: "roadmap", title: "Your roadmap", step: "learn" },
  mission1: { id: "mission1", title: "Python & Data Fundamentals", step: "learn" },
  verify: { id: "verify", title: "Verification", step: "apply" },
  visualize: { id: "visualize", title: "Exploratory Data Analysis", step: "explain" },
  mlFoundations: { id: "mlFoundations", title: "Machine Learning Foundations", step: "learn" },
  model: { id: "model", title: "Model Selection & Evaluation", step: "apply" },
  results: { id: "results", title: "Final Project", step: "explain" },
};

function AppInner() {
  const [screen, setScreen] = useState<Screen>({ name: "onboarding" });
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loaded, setLoaded] = useState<DatasetLoadResponse | null>(null);
  const [guesses, setGuesses] = useState<Record<number, GuessResult>>({});
  const [pointsTotal, setPointsTotal] = useState(0);
  const { setTask } = useMentor();

  // Pushes "where the learner currently is" into the mentor whenever it
  // changes, so every screen gets a grounded mentor without being touched
  // individually - App.tsx already tracks all of this for routing anyway.
  useEffect(() => {
    const dataset = loaded
      ? {
          name: loaded.dataset.name,
          columns: loaded.dataset.columns,
          shape: { rows: loaded.dataset.rows, cols: loaded.dataset.cols },
          sample_rows: loaded.dataset.preview,
          current_version: (screen.name === "model" || screen.name === "results"
            ? "model_ready"
            : screen.name === "verify" || screen.name === "visualize" || screen.name === "mlFoundations"
              ? "cleaned"
              : "raw") as "raw" | "cleaned" | "model_ready",
        }
      : undefined;

    let lesson = MENTOR_LESSON_BY_SCREEN[screen.name];
    if (screen.name === "level" && loaded) {
      const level = loaded.levels[screen.index];
      lesson = level
        ? { id: `level-${level.id}`, title: level.title, objective: level.analogy, step: "predict" }
        : undefined;
    }

    // Clears any code/output/error a previous screen pushed - a fresh
    // screen shouldn't inherit the last one's leftover code-aware context.
    setTask({ lesson, dataset, code: undefined, output: undefined, error: undefined });
  }, [screen, loaded, setTask]);

  const resetToDataset = () => {
    setLoaded(null);
    setGuesses({});
    setPointsTotal(0);
    setScreen({ name: "dataset" });
  };

  const resetAll = () => {
    clearSession();
    setProfile(null);
    setLoaded(null);
    setGuesses({});
    setPointsTotal(0);
    setScreen({ name: "onboarding" });
  };

  const needsDataset = screen.name !== "onboarding" && screen.name !== "dataset" && !loaded;
  useEffect(() => {
    if (needsDataset) setScreen({ name: "dataset" });
  }, [needsDataset]);
  if (needsDataset) return null;

  switch (screen.name) {
    case "onboarding":
      return (
        <Onboarding
          onDone={(p) => {
            setProfile(p);
            setScreen({ name: "dataset" });
          }}
        />
      );

    case "dataset":
      return (
        <Dataset
          onDone={(data) => {
            setLoaded(data);
            setGuesses({});
            setPointsTotal(0);
            setScreen({ name: "roadmapLoading" });
          }}
        />
      );

    case "roadmapLoading":
      return (
        <AutoAdvance onDone={() => setScreen({ name: "roadmap" })}>
          <LoadingScene label="Tweaking a roadmap just for you." />
        </AutoAdvance>
      );

    case "roadmap":
      if (!loaded) return null;
      return (
        <Roadmap
          roadmap={loaded.roadmap}
          levels={loaded.levels}
          hasLevels={loaded.levels.length > 0}
          onStart={() => setScreen({ name: "mission1Loading" })}
        />
      );

    case "mission1Loading":
      return (
        <LevelTransition
          phases={["Mission 1 started"]}
          points={pointsTotal}
          onDone={() => setScreen({ name: "mission1" })}
        />
      );

    case "mission1":
      if (!loaded) return null;
      return (
        <Mission1
          dataset={loaded.dataset}
          role={profile?.role ?? null}
          pointsTotal={pointsTotal}
          onPointsChange={setPointsTotal}
          onComplete={() =>
            setScreen(loaded.levels.length > 0 ? { name: "level", index: 0 } : { name: "verify" })
          }
          onSkip={() =>
            setScreen(loaded.levels.length > 0 ? { name: "level", index: 0 } : { name: "verify" })
          }
        />
      );

    case "level": {
      if (!loaded) return null;
      return (
        <Level
          levels={loaded.levels}
          index={screen.index}
          guesses={guesses}
          onGuessed={(levelId, result) =>
            setGuesses((g) => ({ ...g, [levelId]: result }))
          }
          pointsTotal={pointsTotal}
          onPointsChange={setPointsTotal}
          datasetPreview={loaded.dataset.preview}
          verifyDone={false}
          modelDone={false}
          onBack={() =>
            setScreen(screen.index === 0 ? { name: "roadmap" } : { name: "level", index: screen.index - 1 })
          }
          onNext={(next) =>
            setScreen(next != null ? { name: "level", index: next } : { name: "verify" })
          }
          onSkipCleaning={() => setScreen({ name: "verify" })}
        />
      );
    }

    case "verify":
      if (!loaded) return null;
      return (
        <Verify
          levels={loaded.levels}
          guesses={guesses}
          onNext={() => setScreen({ name: "visualize" })}
        />
      );

    case "visualize":
      if (!loaded) return null;
      return (
        <Visualize
          levels={loaded.levels}
          guesses={guesses}
          onNext={() => setScreen({ name: "mlFoundations" })}
        />
      );

    case "mlFoundations":
      if (!loaded) return null;
      return (
        <MLFoundations
          levels={loaded.levels}
          guesses={guesses}
          onNext={() => setScreen({ name: "model" })}
        />
      );

    case "model":
      if (!loaded) return null;
      return (
        <Model
          levels={loaded.levels}
          guesses={guesses}
          onPointsChange={setPointsTotal}
          onNext={() => setScreen({ name: "results" })}
        />
      );

    case "results":
      return <Results onRestart={resetAll} onNewDataset={resetToDataset} />;
  }
}

export default function App() {
  return (
    <NotesProvider>
      <MentorProvider>
        <AppInner />
        <AiMentor />
      </MentorProvider>
      <NotesButton />
      <NotesScreen />
    </NotesProvider>
  );
}
