"""
TEACHER AGENT

Responsibility: teach ONE lesson, in this learner's language, using this
learner's own data.

The structure is fixed and non-negotiable, because it is what stops the
platform becoming a lecture generator:

    EXPLAIN  ->  EXAMPLE (from their own file)  ->  CHECK (a question back)

Two paths produce that structure:

  * `_facts_for()` pulls the real numbers out of the DatasetAnalysis. This is
    the only place lesson content touches data, and it is pure Python.
  * The explanation is then either reworded by an LLM (given those facts and
    forbidden from adding to them) or written from a deterministic template.

So the lesson a learner sees with no API key is the same lesson, grounded in
the same real numbers -- only the prose is plainer.
"""

from __future__ import annotations

from app.agents.base import Agent
from app.core.schemas import AgentResponse, Lesson, TeachingBlock, UserProfile
from app.llm.prompts import TEACHER_SYSTEM, TEACHER_USER
from app.personalization.user_profile import describe_learner, role_context


class TeacherAgent(Agent):
    name = "teacher_agent"
    responsibility = "Teach one concept interactively, grounded in the learner's own dataset and job context."

    # ------------------------------------------------------------------ facts

    def _facts_for(self, concept_key: str, analysis: dict | None, profile: UserProfile) -> list[str]:
        """
        The real, computed facts this concept should be taught with. Every
        string returned here comes from a number the data agent calculated.
        Returns [] when there is no dataset -- the lesson is then taught
        conceptually, and says so, rather than inventing an example.
        """
        if not analysis:
            return []

        facts: list[str] = []
        columns = analysis.get("columns") or []
        dtypes = analysis.get("dtypes") or {}
        stats = analysis.get("column_stats") or {}
        issues = analysis.get("issues") or []
        eda = analysis.get("eda") or {}

        numeric = [c for c in columns if "int" in dtypes.get(c, "") or "float" in dtypes.get(c, "")]
        datetimes = [c for c in columns if "datetime" in dtypes.get(c, "")]
        categorical = [c for c in columns if c not in numeric and c not in datetimes]

        def issues_of(*types: str) -> list[dict]:
            return [i for i in issues if i["issue_type"] in types]

        if concept_key == "rows_and_columns":
            facts.append(f"Your file has {analysis.get('n_rows')} rows and {analysis.get('n_cols')} columns.")
            facts.append(f"The columns are: {', '.join(columns)}.")
            facts.append("Each row is one record; each column is one thing recorded about it.")

        elif concept_key == "column_meanings":
            for col in columns[:6]:
                s = stats.get(col, {})
                kind = ("a number" if col in numeric else "a date" if col in datetimes else "a category or label")
                extra = ""
                if s.get("unique_count") is not None:
                    extra = f" with {s['unique_count']} distinct values"
                facts.append(f"'{col}' is {kind}{extra}.")

        elif concept_key == "data_types":
            facts.append(f"Number columns you can do maths on: {', '.join(numeric) or 'none'}.")
            facts.append(f"Date columns you can put in time order: {', '.join(datetimes) or 'none'}.")
            facts.append(f"Category columns you can only count or group by: {', '.join(categorical) or 'none'}.")

        elif concept_key == "descriptive_stats":
            for col in numeric[:3]:
                s = stats.get(col, {})
                if s.get("mean") is not None:
                    facts.append(f"'{col}': average {s['mean']}, spread (standard deviation) {s.get('std')}.")
            td = eda.get("target_distribution")
            if td:
                facts.append(f"'{td['column']}' is {td['shape']}.")

        elif concept_key == "missing_values":
            found = issues_of("missing_numeric", "missing_categorical")
            for i in found[:3]:
                pct = i["details"].get("null_pct")
                facts.append(f"'{i['column']}' is missing {pct}% of its values.")
            for entry in (analysis.get("cleaning_log") or []):
                if str(entry.get("issue_type", "")).startswith("missing"):
                    verdict = "worked" if entry.get("passed") else "was rejected and rolled back"
                    facts.append(f"Filling '{entry['column']}' using {entry['action_tried']} {verdict}: {entry['reason']}.")
            if not found:
                facts.append("No column in your file has enough missing values to be worth flagging.")

        elif concept_key == "duplicates":
            facts.append(f"Your file has {analysis.get('n_rows')} rows.")
            facts.append("A duplicate is a row that repeats a record already counted, which would "
                          "double-count it in any total or average.")

        elif concept_key == "inconsistent_categories":
            found = issues_of("label_inconsistency")
            for i in found[:2]:
                d = i["details"]
                facts.append(f"'{i['column']}' has {d.get('raw_label_count')} different written labels, but only "
                              f"{d.get('cluster_count_after_fuzzy_match')} genuinely different things.")
            for entry in (analysis.get("cleaning_log") or []):
                if entry.get("issue_type") == "label_inconsistency" and entry.get("passed"):
                    facts.append(f"Merging them on '{entry['column']}' {entry['reason']}.")
            if not found:
                facts.append("None of your category columns show spelling variants of the same value.")

        elif concept_key == "formatting_errors":
            found = issues_of("format_error_numeric", "format_error_date")
            for i in found[:3]:
                kind = "numbers" if "numeric" in i["issue_type"] else "dates"
                facts.append(f"'{i['column']}' holds {kind} stored as text, so no maths or sorting worked on it.")
            for entry in (analysis.get("cleaning_log") or []):
                if str(entry.get("issue_type", "")).startswith("format_error") and entry.get("passed"):
                    facts.append(f"Converting '{entry['column']}' with {entry['action_tried']}: {entry['reason']}.")
            if not found:
                facts.append("All your number and date columns are already stored in a usable type.")

        elif concept_key == "outliers":
            for c in (eda.get("column_summaries") or [])[:3]:
                if c.get("outlier_count"):
                    facts.append(f"'{c['column']}' has {c['outlier_count']} unusually extreme values "
                                  f"({c['outlier_pct']}% of its rows), against an average of {c['mean']}.")
            if not facts:
                facts.append("No column in your file has an unusual number of extreme values.")

        elif concept_key == "cleaning_decisions":
            for entry in (analysis.get("cleaning_log") or [])[:4]:
                verdict = "kept" if entry.get("passed") else "rejected"
                facts.append(f"On '{entry['column']}', {entry['action_tried']} was {verdict} because {entry['reason']}. "
                              f"It was tried because {entry.get('why_tried', 'it suits this problem')}.")

        elif concept_key in ("bar_chart", "line_chart", "histogram", "scatter_plot"):
            wanted = {"bar_chart": "bar", "line_chart": "line",
                      "histogram": "histogram", "scatter_plot": "scatter"}[concept_key]
            for opp in (analysis.get("chart_opportunities") or []):
                if opp["chart_type"] == wanted:
                    cols = opp["x"] + (f" and {opp['y']}" if opp.get("y") else "")
                    facts.append(f"In your data this chart would use {cols}.")
                    facts.append(opp["reason"])
                    facts.append(f"It answers: {opp['question']}")
                    break
            if not facts:
                facts.append("Your dataset doesn't have the column types this chart needs.")

        elif concept_key == "chart_interpretation":
            downstream = analysis.get("downstream") or {}
            for check in downstream.get("checks", []):
                if check.get("passed") and check.get("result_preview"):
                    preview = list(check["result_preview"].items())[:4]
                    rendered = ", ".join(f"{k}: {v}" for k, v in preview)
                    facts.append(f"A real result from your data -- {rendered}.")
                    break
            facts.append("A chart shows what happened, never why it happened.")

        elif concept_key in ("grouping", "segmentation"):
            downstream = analysis.get("downstream") or {}
            for check in downstream.get("checks", []):
                if check.get("passed") and check.get("result_preview") and "aggregation" in check["check"]:
                    facts.append(f"Grouped result from your own data: {check['result_preview']}.")
                    facts.append(check["reason"])
                    break
            if not facts and categorical:
                s = stats.get(categorical[0], {})
                facts.append(f"'{categorical[0]}' has {s.get('unique_count')} distinct groups you could split by.")

        elif concept_key in ("trends",):
            downstream = analysis.get("downstream") or {}
            for check in downstream.get("checks", []):
                if "time_series" in check.get("check", "") and check.get("passed"):
                    facts.append(check["reason"])
                    break
            if datetimes:
                facts.append(f"'{datetimes[0]}' is your time column, so your data can be put in date order.")

        elif concept_key == "correlation":
            sc = eda.get("strongest_correlation")
            if sc:
                facts.append(f"The strongest relationship in your data is between '{sc['col_a']}' and "
                              f"'{sc['col_b']}', at {sc['correlation']}.")
            facts.append("A correlation says two columns move together; it never says one caused the other.")

        elif concept_key == "conversion_metrics":
            facts.append(f"Your file has {analysis.get('n_rows')} records to work from.")
            if categorical:
                facts.append(f"You could compare rates across '{categorical[0]}'.")
            facts.append("A conversion rate is one count divided by another -- which denominator you pick changes the number.")

        elif concept_key == "attrition_analysis":
            if categorical:
                facts.append(f"You could compare groups using '{categorical[0]}'.")
            facts.append(f"With {analysis.get('n_rows')} records, attrition is a count of leavers over a headcount.")

        elif concept_key == "feature_engineering":
            modeling = analysis.get("modeling") or {}
            if datetimes:
                facts.append(f"'{datetimes[0]}' was turned into a month number so a model could use it -- "
                              f"a raw date is not something a model can do arithmetic on.")
            if modeling.get("roles"):
                facts.append(f"The columns used as features were: {', '.join(modeling['roles']['feature_cols'])}.")

        elif concept_key in ("model_basics", "regression_vs_classification", "train_test_split",
                             "model_evaluation", "overfitting", "model_selection", "feature_importance"):
            facts += self._modeling_facts(concept_key, analysis)

        elif concept_key == "business_translation":
            downstream = analysis.get("downstream") or {}
            for check in downstream.get("checks", []):
                if check.get("passed") and check.get("result_preview"):
                    facts.append(f"One real number from your data: {list(check['result_preview'].items())[:3]}.")
                    break
            role = role_context(profile)
            facts.append(f"For {role['description']}, the useful question is what to do differently "
                          f"about {role['vocabulary']['metric']}.")

        return facts

    def _modeling_facts(self, concept_key: str, analysis: dict) -> list[str]:
        modeling = analysis.get("modeling") or {}
        if not modeling or modeling.get("skipped") or modeling.get("error"):
            return ["No model was trained on your data yet, so this lesson stays conceptual for now."]

        facts: list[str] = []
        target = modeling.get("target")
        chosen = modeling.get("chosen_model_name")
        ev = modeling.get("chosen_model_eval") or {}

        if concept_key == "model_basics":
            facts.append(f"A model was trained to predict '{target}' from your other columns.")
            if chosen:
                facts.append(f"The one selected was {chosen}.")
        elif concept_key == "regression_vs_classification":
            facts.append(f"'{target}' is a number, so this is a regression problem -- predicting a quantity, "
                          f"not sorting records into categories.")
        elif concept_key == "train_test_split":
            facts.append("The model was scored with 5-fold cross-validation, meaning it was repeatedly "
                          "trained on part of your data and tested on the part it had not seen.")
            if ev.get("test_r2") is not None:
                facts.append(f"Its score on unseen data was {ev['test_r2']}.")
        elif concept_key == "model_evaluation":
            if ev:
                facts.append(f"{chosen} scored a cross-validated R-squared of {ev.get('cv_r2_mean')}, "
                              f"with a typical error of {ev.get('test_rmse')} in the units of '{target}'.")
            facts.append("R-squared is the share of the variation the model explains; 1.0 is perfect, 0 is no better than the average.")
        elif concept_key == "overfitting":
            if ev.get("overfit_gap") is not None:
                facts.append(f"On your data the training score beat the test score by {ev['overfit_gap']} -- "
                              f"the gap that reveals memorising rather than learning.")
        elif concept_key == "model_selection":
            for entry in modeling.get("model_log", []):
                verdict = "was accepted" if entry["passed"] else "was rejected"
                facts.append(f"{entry['model_tried']} {verdict}: {entry['reason']}")
            if modeling.get("start_reason"):
                facts.append(f"The starting choice was made because {modeling['start_reason']}.")
        elif concept_key == "feature_importance":
            for f in (modeling.get("feature_importance") or [])[:4]:
                facts.append(f"{f['feature']}: {round(f['importance'] * 100, 1)}% of the model's decision.")
            if not modeling.get("feature_importance"):
                facts.append("The chosen model does not expose per-column influence.")
        return facts

    # ------------------------------------------------------------------ deterministic teaching

    EXPLANATIONS: dict[str, str] = {
        "rows_and_columns": "A dataset is just a table. Every row is one thing that happened -- one {record}. Every column is one detail recorded about it. Once you can say out loud what a single row of your file means, the rest of data work is much less intimidating.",
        "column_meanings": "Before analysing anything, it is worth naming what each column actually records. Half of all analysis mistakes come from assuming a column means something it doesn't.",
        "data_types": "Columns come in three practical kinds: numbers you can add up and average, dates you can put in order, and categories you can only count or group by. Which kind a column is decides what you are allowed to do with it.",
        "descriptive_stats": "The average tells you the typical value, and the spread tells you how much things vary around it. The average alone can be misleading when a few very large values pull it upward.",
        "missing_values": "Blank cells are not neutral. Ignoring them quietly drops records from your totals; filling them with the wrong value quietly distorts your results. The right choice depends on how much is missing and why.",
        "duplicates": "A duplicate row is the same record counted twice. It inflates every total and shifts every average, and it is easy to miss because each individual row looks perfectly fine.",
        "inconsistent_categories": "When people type values by hand, the same thing gets written several ways. To a computer those are entirely separate categories, so your groups split apart and your totals come out wrong.",
        "formatting_errors": "A number stored as text looks like a number to you and like a word to the computer. Until it is converted, you cannot add it, average it or sort by it.",
        "outliers": "An outlier is a value far from the rest. The important question is not how to remove it but whether it is a mistake or the most interesting thing in your data.",
        "cleaning_decisions": "Every cleaning choice trades something away. What matters is being able to say what you chose, why, and what it cost -- that is the difference between cleaning data and quietly changing it.",
        "bar_chart": "A bar chart compares a number across a handful of categories. The length of each bar is the value, so differences between groups are visible instantly.",
        "line_chart": "A line chart shows how a number changes over time. The line only means something because the points are in date order -- that ordering is what makes a trend readable.",
        "histogram": "A histogram shows the shape of one number column: which values are common, which are rare, and whether things cluster or stretch out. It shows what an average hides.",
        "scatter_plot": "A scatter plot puts one number on each axis and one dot per record. The shape of the cloud tells you whether the two columns tend to move together.",
        "chart_interpretation": "Reading a chart properly means stating one thing it shows and one thing it cannot show. A chart describes what happened; it never explains why.",
        "grouping": "Grouping splits your data by a category and summarises each group separately. It is the single most useful operation in everyday analysis -- most real questions are group comparisons.",
        "segmentation": "Segmentation splits your records into meaningful groups so you can treat them differently. A useful segment is one where the groups actually behave differently.",
        "trends": "A trend is a direction that holds up over time, as opposed to normal month-to-month wobble. Distinguishing the two is what stops you reacting to noise.",
        "correlation": "Correlation measures whether two columns move together, from -1 to 1. It is genuinely useful and constantly misread -- moving together is not the same as one causing the other.",
        "conversion_metrics": "A conversion rate is one count divided by another. The number is only meaningful once you can say exactly what the denominator is.",
        "attrition_analysis": "Attrition measures who leaves and when. It is most useful compared across groups, because the overall rate hides where the problem actually is.",
        "feature_engineering": "Models cannot use raw dates or free text. Feature engineering turns what you have into something a model can actually do arithmetic on.",
        "model_basics": "A model is a rule learned from examples. You show it inputs and known answers, and it works out a pattern it can apply to new records.",
        "regression_vs_classification": "If the thing you are predicting is a number, that is regression. If it is a category, that is classification. Everything downstream depends on which one you have.",
        "train_test_split": "You hold some data back and never train on it, so you can test the model on records it has genuinely never seen. Without that, a model that memorised looks perfect.",
        "model_evaluation": "A model's score says how much of the variation it explains. A high score is not proof it is useful, and a low one is not proof it is worthless -- both need context.",
        "overfitting": "Overfitting is when a model memorises the data it was trained on instead of learning the pattern. It looks excellent on old data and falls apart on new data.",
        "model_selection": "A more complex model is not automatically a better one. You start simple and only escalate when there is a measured reason -- otherwise you have added complexity you cannot explain.",
        "feature_importance": "Feature importance ranks which columns actually drove the predictions. It is how you sanity-check a model against what you already know about your business.",
        "business_translation": "A finding only counts once it changes a decision. The test is whether you can name the action someone would take differently because of it.",
    }

    def _deterministic_block(self, lesson: Lesson, facts: list[str], profile: UserProfile) -> TeachingBlock:
        role = role_context(profile)
        explanation = self.EXPLANATIONS.get(
            lesson.concept_key, f"{lesson.title}. {lesson.objective}"
        ).format(**role["vocabulary"])

        if profile.experience_level == "beginner":
            explanation += f" For {role['description']}, this usually shows up as {role['examples']}."
        elif profile.experience_level == "advanced":
            explanation += " You likely know this -- it is here because the rest of your path builds on it."

        if facts:
            example = "In your own data: " + " ".join(facts)
        else:
            example = ("You haven't uploaded a dataset yet, so this one stays general. "
                        "Upload a CSV and I'll re-teach it using your own columns.")

        return TeachingBlock(
            lesson_step=lesson.step,
            title=lesson.title,
            explanation=explanation,
            example=example,
            check_question=self._check_question(lesson, facts, profile),
            grounded_facts=facts,
            source="deterministic",
        )

    CHECK_QUESTIONS: dict[str, str] = {
        "rows_and_columns": "In your own words, what does a single row of your file represent?",
        "column_meanings": "Pick one column from your file and tell me what it records.",
        "data_types": "Which of your columns could you calculate an average of, and which could you only count?",
        "descriptive_stats": "If the average is much higher than most of the values, what does that tell you?",
        "missing_values": "Would you rather fill a blank with a typical value, or leave the row out? Why?",
        "duplicates": "If a record appeared twice, which of your numbers would be wrong?",
        "inconsistent_categories": "Why would a computer treat 'Mumbai' and 'mumbai' as two different places?",
        "formatting_errors": "Why can't you calculate an average of a column stored as text?",
        "outliers": "If a value is far above the rest, how would you decide whether it's an error?",
        "cleaning_decisions": "Name one thing you give up when you fill a blank with the typical value.",
        "bar_chart": "Which category column in your data would you put along the bottom of a bar chart?",
        "line_chart": "Why does a line chart need a date column to make sense?",
        "histogram": "What does a histogram show you that an average doesn't?",
        "scatter_plot": "If the dots form a rising cloud, what does that suggest about the two columns?",
        "chart_interpretation": "Name one thing your chart can show, and one thing it cannot.",
        "grouping": "Which column would you group by to compare performance across your business?",
        "segmentation": "What would make a segment worth treating differently?",
        "trends": "How would you tell a real trend from a single unusual month?",
        "correlation": "Two columns move together. Why isn't that enough to say one causes the other?",
        "conversion_metrics": "What exactly would your denominator be when calculating a conversion rate?",
        "attrition_analysis": "Which groups would you compare attrition across, and why those?",
        "feature_engineering": "Why can't a model use a raw date column directly?",
        "model_basics": "In one sentence, what is a model learning from your data?",
        "regression_vs_classification": "Is the thing you want to predict a number or a category?",
        "train_test_split": "What goes wrong if you test a model on the same data it learned from?",
        "model_evaluation": "A model scores well. What would you still want to check before trusting it?",
        "overfitting": "How would you spot a model that memorised instead of learned?",
        "model_selection": "Why not just always use the most powerful model available?",
        "feature_importance": "If the top-ranked column surprised you, what would you check first?",
        "business_translation": "What would you actually do differently because of what you just saw?",
    }

    def _check_question(self, lesson: Lesson, facts: list[str], profile: UserProfile) -> str:
        return self.CHECK_QUESTIONS.get(
            lesson.concept_key, f"What is the main thing you take away from '{lesson.title}'?"
        )

    # ------------------------------------------------------------------ llm path

    def _llm_block(self, lesson: Lesson, facts: list[str], profile: UserProfile) -> TeachingBlock | None:
        if not self.llm_enabled:
            return None

        raw = self.llm.complete(
            TEACHER_SYSTEM,
            TEACHER_USER.format(
                role_description=describe_learner(profile),
                experience_level=profile.experience_level,
                concept=lesson.title,
                objective=lesson.objective,
                facts="\n".join(f"- {f}" for f in facts) if facts
                      else "- (the learner has not uploaded a dataset, so use no specific numbers)",
            ),
            max_tokens=600,
        )
        if not raw:
            return None

        parts = [p.strip() for p in raw.split("###") if p.strip()]
        if len(parts) < 3:
            return None   # malformed -> caller falls back to the deterministic block

        def strip_label(text: str) -> str:
            for label in ("EXPLAIN:", "EXAMPLE:", "CHECK:", "1.", "2.", "3."):
                if text.upper().startswith(label.upper()):
                    return text[len(label):].strip()
            return text

        return TeachingBlock(
            lesson_step=lesson.step,
            title=lesson.title,
            explanation=strip_label(parts[0]),
            example=strip_label(parts[1]),
            check_question=strip_label(parts[2]),
            grounded_facts=facts,
            source="llm",
        )

    # ------------------------------------------------------------------ agent api

    def teach(self, lesson: Lesson, profile: UserProfile, analysis: dict | None = None) -> TeachingBlock:
        facts = self._facts_for(lesson.concept_key, analysis, profile)
        return self._llm_block(lesson, facts, profile) or self._deterministic_block(lesson, facts, profile)

    def run(self, lesson: Lesson | None = None, profile: UserProfile | None = None,
            analysis: dict | None = None, **kwargs) -> AgentResponse:
        if lesson is None:
            return self._respond("teach", "There's no lesson to teach yet -- build a learning path first.", {})

        profile = profile or UserProfile()
        block = self.teach(lesson, profile, analysis)
        message = (f"Lesson {block.lesson_step}: {block.title}\n\n"
                    f"{block.explanation}\n\n{block.example}\n\n{block.check_question}")

        return self._respond("teach", message, {"teaching_block": block.to_dict()},
                             used_llm=(block.source == "llm"))
