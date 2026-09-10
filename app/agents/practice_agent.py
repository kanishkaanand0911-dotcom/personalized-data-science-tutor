"""
PRACTICE / CHALLENGE AGENT

Responsibility: set a small, concrete task on the learner's own data, offer
hints, and adjust difficulty.

The task always names real columns from the learner's file. A challenge that
says "make a bar chart of your categories" teaches nothing; "compare average
deal_value across your 5 regions" is something they can actually do and
actually check.

Marking lives in the evaluator agent, not here -- setting the task and judging
the answer are different responsibilities and are kept in different agents.
"""

from __future__ import annotations

from app.agents.base import Agent
from app.core.schemas import AgentResponse, Challenge, UserProfile
from app.llm.prompts import PRACTICE_SYSTEM, PRACTICE_USER
from app.personalization.user_profile import describe_learner

# concept -> (task template, hints, keywords a correct answer should contain)
# {cat}, {num}, {date} are filled from the learner's actual columns.
TASK_BANK: dict[str, tuple[str, list[str], list[str]]] = {
    "rows_and_columns": (
        "Look at your file and write one sentence describing what a single row records. "
        "Then say how many rows and columns you have.",
        ["Read across one row -- every value in it belongs to the same thing.",
         "The row count is how many records you have; the column count is how many details per record."],
        ["row", "record", "column"]),
    "column_meanings": (
        "Pick any three of your columns and write one line each saying what they record and "
        "whether they are a number, a date or a category.",
        ["Numbers you can add up. Dates you can put in order. Categories you can only group by."],
        ["number", "category", "date"]),
    "data_types": (
        "List which of your columns you could calculate an average of, and which you could only count.",
        ["If adding two values together makes no sense, it is a category, not a number."],
        ["average", "count", "category"]),
    "descriptive_stats": (
        "Find the average of '{num}' in your data, then find the middle value. "
        "Are they close? What does the gap tell you?",
        ["The middle value (median) splits your records in half.",
         "A big gap between average and median means a few extreme values are pulling it."],
        ["average", "median", "skew", "middle"]),
    "missing_values": (
        "Find which of your columns have blank cells and how many. For the worst one, "
        "say whether you would fill it in or leave those rows out, and why.",
        ["Count the blanks per column first.",
         "Consider what would be distorted either way -- there is no free option."],
        ["missing", "blank", "fill", "impute", "drop"]),
    "duplicates": (
        "Check whether any records in your file appear more than once, and say which of your "
        "numbers would be wrong if they did.",
        ["Compare rows across all their columns, not just one.",
         "Totals and averages are the first things a duplicate corrupts."],
        ["duplicate", "total", "average", "count"]),
    "inconsistent_categories": (
        "Look at '{cat}' and list any values that are really the same thing written differently. "
        "Say what your grouped totals would look like if you did not merge them.",
        ["Look for differences in capitals, spaces, or alternative names for the same thing.",
         "Unmerged variants split one real group into several smaller ones."],
        ["same", "merge", "spelling", "group", "variant"]),
    "formatting_errors": (
        "Find a column in your file where numbers or dates are stored as text. "
        "Say what you cannot do with it until it is converted.",
        ["Currency symbols, commas and 'k' suffixes are the usual giveaways.",
         "Try to imagine sorting or averaging it -- what breaks?"],
        ["text", "convert", "number", "date", "average", "sort"]),
    "outliers": (
        "Find the largest value in '{num}' and compare it to the typical value. "
        "Decide whether it looks like an error or a genuine record, and say why.",
        ["Compare it against the middle value, not the average.",
         "An error usually breaks a pattern; a genuine extreme usually has a reason behind it."],
        ["outlier", "extreme", "error", "genuine", "typical"]),
    "cleaning_decisions": (
        "Pick one fix that was applied to your data and write down what it improved "
        "and what it cost.",
        ["Every fix trades something -- filling blanks costs you honesty about what was unknown."],
        ["fix", "trade", "cost", "improved", "why"]),
    "bar_chart": (
        "Build a bar chart comparing '{num}' across '{cat}'. Then say which group is highest "
        "and whether the gap is big enough to change anything you would do.",
        ["Put '{cat}' along the bottom and '{num}' up the side.",
         "A gap only matters if it would change a decision."],
        ["bar", "{cat}", "{num}", "highest", "compare"]),
    "line_chart": (
        "Build a line chart of '{num}' over '{date}'. Describe the overall direction "
        "in one sentence.",
        ["Sort by '{date}' first -- the ordering is what makes the line mean anything.",
         "Look at the whole shape before reacting to any single point."],
        ["line", "trend", "{date}", "over time", "direction"]),
    "histogram": (
        "Build a histogram of '{num}'. Say where most of your records sit and whether "
        "there is a long tail.",
        ["The tallest bars show where records cluster.",
         "A long thin tail on one side is what pulls an average away from typical."],
        ["histogram", "distribution", "spread", "tail", "{num}"]),
    "scatter_plot": (
        "Plot '{num}' against another number column. Say whether the dots slope, "
        "and what you would NOT be entitled to conclude from that slope.",
        ["One dot per record, one column on each axis.",
         "A slope shows movement together, never cause."],
        ["scatter", "slope", "relationship", "not cause", "correlation"]),
    "chart_interpretation": (
        "Take any chart you have made from your data. Write one thing it proves "
        "and one thing it cannot tell you.",
        ["Charts describe what happened, never why."],
        ["shows", "cannot", "why", "conclude"]),
    "grouping": (
        "Group your data by '{cat}' and compare the average '{num}' in each group. "
        "Which group stands out, and what would you check next?",
        ["Group first, then summarise inside each group.",
         "A group standing out is a question, not yet an answer."],
        ["group", "{cat}", "average", "compare"]),
    "segmentation": (
        "Split your records into two or three segments using '{cat}', and describe "
        "how each segment behaves differently.",
        ["A useful segment behaves differently from the others -- otherwise it is just a label."],
        ["segment", "group", "differ", "behave"]),
    "trends": (
        "Look at '{num}' over '{date}' and decide whether there is a real trend "
        "or just normal variation. Give your reason.",
        ["A real trend keeps its direction across several periods."],
        ["trend", "direction", "variation", "noise", "period"]),
    "correlation": (
        "Find the two most related number columns in your data. Write down the relationship, "
        "then write one alternative explanation that is not 'one causes the other'.",
        ["A third factor driving both is the most common alternative explanation."],
        ["correlation", "related", "cause", "third", "explanation"]),
    "conversion_metrics": (
        "Define one conversion rate you could calculate from your data. State the "
        "numerator and the denominator explicitly.",
        ["Write it as 'X out of Y' before you calculate anything."],
        ["rate", "numerator", "denominator", "out of"]),
    "attrition_analysis": (
        "Describe how you would measure attrition from your data, and which groups "
        "you would compare it across.",
        ["Attrition is leavers over headcount for a period.",
         "The overall number hides where the problem is."],
        ["attrition", "leave", "group", "compare", "rate"]),
    "feature_engineering": (
        "Name one new column you could build from your existing ones that would carry "
        "more signal than the raw columns do.",
        ["A date becomes a month or a day-of-week; two columns become a ratio."],
        ["new column", "derive", "ratio", "month", "combine"]),
    "model_basics": (
        "In your own words, describe what a model trained on your data has learned, "
        "and what it would do with a brand new record.",
        ["A model is a rule learned from examples."],
        ["pattern", "learn", "predict", "new"]),
    "regression_vs_classification": (
        "Pick a column in your data you would want to predict. Say whether that would "
        "be regression or classification, and why.",
        ["A number is regression; a category is classification."],
        ["regression", "classification", "number", "category"]),
    "train_test_split": (
        "Explain, in your own words, what would go wrong if a model were tested on "
        "exactly the same records it learned from.",
        ["Think about what memorising would look like from the outside."],
        ["unseen", "memoris", "memoriz", "test", "overfit"]),
    "model_evaluation": (
        "Look at the model score for your data and write one sentence on what it does "
        "prove, and one on what it does not.",
        ["A score is about explained variation, not about usefulness."],
        ["score", "explain", "variation", "not", "prove"]),
    "overfitting": (
        "Describe how you would spot an overfitted model using two numbers.",
        ["Compare the training score to the score on data it has not seen."],
        ["training", "test", "gap", "overfit"]),
    "model_selection": (
        "Say why you would start with a simple model on your data, and what specific "
        "evidence would make you move to a more complex one.",
        ["The evidence has to be a measurement, not a hunch."],
        ["simple", "complex", "evidence", "escalate", "reason"]),
    "feature_importance": (
        "Look at which columns drove the model on your data. Pick the top one and say "
        "whether it makes sense given what you know about your work.",
        ["A column that is suspiciously dominant may be leaking the answer."],
        ["important", "column", "drove", "makes sense", "leak"]),
    "business_translation": (
        "Take one number you found in your data and write the decision someone should "
        "make differently because of it.",
        ["If nobody would act differently, the finding has not landed yet."],
        ["decision", "action", "change", "because"]),
}

DIFFICULTY_SUFFIX = {
    "beginner": "",
    "intermediate": " Also state one assumption you are making.",
    "advanced": " Also state one assumption you are making, and how you would test whether it holds.",
}


class PracticeAgent(Agent):
    name = "practice_agent"
    responsibility = "Set a concrete practical task on the learner's own data, with hints and adjustable difficulty."

    def _columns_for(self, analysis: dict | None) -> dict:
        """Real column names to substitute into the task template, with safe
        placeholders when there is no dataset yet."""
        fallback = {"cat": "one of your category columns", "num": "one of your number columns",
                    "date": "your date column"}
        if not analysis:
            return fallback

        opportunities = analysis.get("chart_opportunities") or []
        chosen = dict(fallback)
        for opp in opportunities:
            if opp["chart_type"] == "bar":
                chosen["cat"], chosen["num"] = opp["x"], opp["y"]
                break
        for opp in opportunities:
            if opp["chart_type"] == "line":
                chosen["date"] = opp["x"]
                chosen["num"] = chosen.get("num") or opp["y"]
                break
        if chosen["num"] == fallback["num"]:
            for opp in opportunities:
                if opp["chart_type"] == "histogram":
                    chosen["num"] = opp["x"]
                    break
        return chosen

    def build(self, concept_key: str, profile: UserProfile, analysis: dict | None = None,
              difficulty: str | None = None) -> Challenge:
        difficulty = difficulty or profile.experience_level
        cols = self._columns_for(analysis)

        llm_challenge = self._llm_challenge(concept_key, profile, analysis, cols, difficulty)
        if llm_challenge:
            return llm_challenge

        entry = TASK_BANK.get(concept_key)
        if not entry:
            return Challenge(
                prompt=f"Apply what you just learned about {concept_key.replace('_', ' ')} to your own data, "
                       f"and write down what you found.",
                concept_key=concept_key, hints=["Start from the columns you already understand."],
                expected_keywords=[], difficulty=difficulty)

        template, hints, keywords = entry
        prompt = template.format(**cols) + DIFFICULTY_SUFFIX.get(difficulty, "")
        return Challenge(
            prompt=prompt,
            concept_key=concept_key,
            hints=[h.format(**cols) for h in hints],
            expected_keywords=[k.format(**cols).lower() for k in keywords],
            difficulty=difficulty,
        )

    def _llm_challenge(self, concept_key: str, profile: UserProfile, analysis: dict | None,
                       cols: dict, difficulty: str) -> Challenge | None:
        if not self.llm_enabled or not analysis:
            return None

        facts = [f"Columns in their data: {', '.join(analysis.get('columns') or [])}."]
        for opp in (analysis.get("chart_opportunities") or [])[:3]:
            facts.append(f"They can chart {opp['chart_type']} using {opp['x']}"
                          + (f" and {opp['y']}" if opp.get("y") else "") + ".")

        parsed = self.llm.complete_json(
            PRACTICE_SYSTEM,
            PRACTICE_USER.format(
                role_description=describe_learner(profile),
                experience_level=difficulty,
                concept=concept_key.replace("_", " "),
                facts="\n".join(f"- {f}" for f in facts),
            ),
            max_tokens=500,
        )
        if not isinstance(parsed, dict) or not parsed.get("prompt"):
            return None

        keywords = parsed.get("expected_keywords")
        if not isinstance(keywords, list) or not keywords:
            return None   # without keywords the evaluator cannot mark it

        return Challenge(
            prompt=str(parsed["prompt"]),
            concept_key=concept_key,
            hints=[str(h) for h in (parsed.get("hints") or [])],
            expected_keywords=[str(k).lower() for k in keywords],
            difficulty=difficulty,
        )

    def run(self, concept_key: str = "", profile: UserProfile | None = None,
            analysis: dict | None = None, difficulty: str | None = None, **kwargs) -> AgentResponse:
        profile = profile or UserProfile()
        challenge = self.build(concept_key, profile, analysis, difficulty)
        message = f"Challenge: {challenge.prompt}"
        if challenge.hints:
            message += "\n\nStuck? " + challenge.hints[0]
        return self._respond("practice", message, {"challenge": challenge.to_dict()},
                             used_llm=False)
