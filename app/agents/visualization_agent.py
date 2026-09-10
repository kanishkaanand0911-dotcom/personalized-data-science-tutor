"""
VISUALIZATION AGENT

Responsibility: choose the right chart for a question, explain why, render it,
and say what to look for in it.

The choice is a rule, not a guess: what the columns ARE determines what chart
is legitimate. Comparing a number across categories is a bar chart; a number
over a real date column is a line; one number's shape is a histogram; two
numbers together is a scatter. Those rules are in CHART_RULES below and the
agent will not propose a chart the learner's columns cannot support.
"""

from __future__ import annotations

import pandas as pd

from app.agents.base import Agent
from app.agents.data_agent import pick_chart_columns
from app.core.schemas import AgentResponse, UserProfile
from app.llm.prompts import VIZ_SYSTEM, VIZ_USER
from app.personalization.user_profile import describe_learner
from app.visualization.charts import render

# question shape -> chart type. Used when the learner asks in words rather
# than naming a chart.
INTENT_KEYWORDS = {
    "bar": ("compare", "by region", "by category", "which is highest", "ranking", "across", "versus", "vs"),
    "line": ("over time", "trend", "monthly", "growth", "by month", "history", "since"),
    "histogram": ("distribution", "spread", "how common", "shape", "range of"),
    "scatter": ("relationship", "correlat", "related", "move together", "against each other"),
}

CHART_RULES = {
    "bar": "you are comparing one number across a small set of categories",
    "line": "you are following one number across a real date column, in time order",
    "histogram": "you are looking at the shape of a single number column on its own",
    "scatter": "you are checking whether two number columns move together",
}

WHAT_TO_LOOK_FOR = {
    "bar": "which bar is tallest and by how much -- and whether the gap is big enough to act on.",
    "line": "the overall direction, and whether any single point is a genuine turn or just one odd period.",
    "histogram": "where most records sit, and whether a long tail on one side is dragging the average away from typical.",
    "scatter": "whether the cloud slopes, and whether a handful of far-out points are creating the slope by themselves.",
}


class VisualizationAgent(Agent):
    name = "visualization_agent"
    responsibility = "Recommend the appropriate chart for a question, justify it, render it, and explain how to read it."

    def recommend(self, question: str, analysis: dict) -> dict | None:
        """
        Pick the best-supported chart for a natural-language question. Falls
        back to the dataset's first genuine chart opportunity when the question
        gives no signal -- never to a chart the data can't produce.
        """
        opportunities = analysis.get("chart_opportunities") or []
        if not opportunities:
            return None

        lowered = question.lower()

        def mentions(col: str | None) -> bool:
            """Underscores are stripped so "deal value" matches 'deal_value'."""
            return bool(col) and (col.lower() in lowered or col.lower().replace("_", " ") in lowered)

        def column_score(opp: dict) -> int:
            """
            The x column is what distinguishes one bar chart from another --
            every bar opportunity shares the same y, so matching on y alone
            would always return whichever came first. x is worth more.
            """
            return (2 if mentions(opp["x"]) else 0) + (1 if mentions(opp.get("y")) else 0)

        for chart_type, keywords in INTENT_KEYWORDS.items():
            if not any(k in lowered for k in keywords):
                continue
            matching = [o for o in opportunities if o["chart_type"] == chart_type]
            if not matching:
                continue
            # Within the right chart type, the columns the learner named win.
            return max(matching, key=column_score)

        # No keyword hit: honour a column the learner named, if any.
        best = max(opportunities, key=column_score)
        return best if column_score(best) > 0 else opportunities[0]

    def _explain(self, opp: dict, profile: UserProfile, rendered: dict) -> tuple[str, bool]:
        columns = opp["x"] + (f" and {opp['y']}" if opp.get("y") else "")
        deterministic = (
            f"A {opp['chart_type']} chart is the right shape here because {CHART_RULES[opp['chart_type']]}. "
            f"It uses {columns}. {opp['reason']} "
            f"When you look at it, focus on {WHAT_TO_LOOK_FOR[opp['chart_type']]}"
        )
        if rendered.get("data"):
            deterministic += f" The actual values from your data: {rendered['data']}."

        if not self.llm_enabled:
            return deterministic, False

        text = self.llm.complete(
            VIZ_SYSTEM,
            VIZ_USER.format(
                role_description=describe_learner(profile),
                experience_level=profile.experience_level,
                chart_type=opp["chart_type"],
                columns=columns,
                reason=opp["reason"],
                facts=str(rendered.get("data", "")),
            ),
            max_tokens=400,
        )
        return (text, True) if text else (deterministic, False)

    def run(self, question: str = "", analysis: dict | None = None, df: pd.DataFrame | None = None,
            profile: UserProfile | None = None, chart_type: str | None = None, **kwargs) -> AgentResponse:
        profile = profile or UserProfile()
        if not analysis:
            return self._respond("visualize", "Upload a dataset and I'll show you which chart fits your question.", {})

        opp = None
        if chart_type:
            opp = next((o for o in (analysis.get("chart_opportunities") or [])
                        if o["chart_type"] == chart_type), None)
        opp = opp or self.recommend(question, analysis)

        if not opp:
            return self._respond("visualize",
                                  "Your dataset doesn't have the column types any of my charts need "
                                  "(a category plus a number, a date plus a number, or two numbers).", {})

        rendered = {}
        if df is not None:
            rendered = render(opp["chart_type"], df, opp["x"], opp.get("y"))

        explanation, used_llm = self._explain(opp, profile, rendered)
        message = f"Chart: {opp['chart_type']}\nQuestion it answers: {opp['question']}\n\n{explanation}"
        if rendered.get("path"):
            message += f"\n\nSaved to: {rendered['path']}"
        elif rendered.get("error"):
            message += f"\n\n(Could not render the image: {rendered['error']})"

        return self._respond("visualize", message,
                             {"recommendation": opp, "rendered": rendered}, used_llm=used_llm)
