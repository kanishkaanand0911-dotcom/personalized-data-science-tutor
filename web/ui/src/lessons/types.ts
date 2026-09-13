/* Lesson content lives as data, not JSX, so a new lesson is a new object in
   lessons/*.ts, not a new screen. Every field that needs a real number
   (dataset stats, column names) is filled from the actual loaded dataset at
   render time - nothing here is allowed to fabricate a fact about the
   learner's data. */

export type LearnerCtx = {
  role: string | null;
  experience: string | null;
  goal: string | null;
  datasetName: string;
  rows: number;
  cols: number;
  columns: string[];
};

export type MissionId = "mission-1" | "mission-2" | "mission-3" | "mission-4" | "mission-5";

export const MISSIONS: { id: MissionId; title: string }[] = [
  { id: "mission-1", title: "Meet your data" },
  { id: "mission-2", title: "Clean the data" },
  { id: "mission-3", title: "Discover patterns" },
  { id: "mission-4", title: "Build your first model" },
  { id: "mission-5", title: "Solve the business problem" },
];
