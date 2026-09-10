"""
QUIZ AGENT

Responsibility: generate ONE adaptive comprehension question for the concept
just taught, and mark the answer.

"Adaptive" means three concrete things:
  - the question is about the concept the learner just did, not a random topic
  - it is built from the facts of THEIR dataset, so the answer requires having
    understood their own data, not having memorised a definition
  - difficulty follows their level, and a concept they previously got wrong
    comes back rather than being quietly dropped

The deterministic bank below is the guaranteed path. The LLM, when configured,
writes a fresher question from the same grounded facts -- and if its JSON is
malformed the bank is used instead, so a quiz always exists.
"""

from __future__ import annotations

import random

from app.agents.base import Agent
from app.core.schemas import AgentResponse, QuizQuestion, UserProfile
from app.llm.prompts import QUIZ_SYSTEM, QUIZ_USER
from app.personalization.user_profile import describe_learner

# concept -> (question, options, correct index, explanation)
QUESTION_BANK: dict[str, tuple[str, list[str], int, str]] = {
    "rows_and_columns": (
        "In a table of your data, what does one row represent?",
        ["One single record, with all its details", "One column of numbers", "The total of the whole file"],
        0, "A row is one record; the columns are the details recorded about it."),
    "column_meanings": (
        "Why is it worth naming what each column records before analysing?",
        ["Because assuming a column's meaning is where most analysis mistakes start",
         "Because the computer cannot read column names",
         "Because columns must be in alphabetical order"],
        0, "Most analysis errors trace back to a column meaning something other than assumed."),
    "data_types": (
        "Which of these can you calculate a meaningful average of?",
        ["A number column like a value or an amount", "A category column like a region name",
         "An ID column that is different on every row"],
        0, "Averages only make sense for genuine quantities."),
    "descriptive_stats": (
        "The average of a column is much higher than most of its values. What does that suggest?",
        ["A few very large values are pulling the average up",
         "The column has no missing values", "Every value is about the same"],
        0, "That gap between the average and the typical value is the signature of a long tail."),
    "missing_values": (
        "A column is missing a fifth of its values. Why is filling every blank with the middle value risky?",
        ["If the data has distinct groups, one filled-in value distorts the shape for all of them",
         "Because the middle value is always wrong", "Because it takes too long to calculate"],
        0, "One flat value ignores that different records would have had very different real values."),
    "duplicates": (
        "What goes wrong if a record appears twice in your file?",
        ["It gets double-counted, inflating totals and shifting averages",
         "Nothing, the computer removes it automatically", "The file cannot be opened"],
        0, "Each duplicate row looks fine on its own, which is why they are easy to miss."),
    "inconsistent_categories": (
        "Why does a computer treat 'Mumbai' and 'mumbai' as two different things?",
        ["It compares the text exactly, so a difference in case is a difference in value",
         "Because one is a city and the other is not", "Because they have different lengths"],
        0, "Exact text comparison is why your groups split apart and totals come out wrong."),
    "formatting_errors": (
        "A column of amounts is stored as text like \"$2,551\". What can't you do with it?",
        ["Add it up or average it, until it is converted to a number",
         "Read it on screen", "Sort it alphabetically"],
        0, "To the computer it is a word, so no arithmetic is possible until it is converted."),
    "outliers": (
        "You find a value far above all the others. What is the first thing to decide?",
        ["Whether it is a data error or a real, important record",
         "How to delete it fastest", "Whether to round it down"],
        0, "Removing a real extreme value can delete the most interesting thing in your data."),
    "cleaning_decisions": (
        "Why should a cleaning decision be recorded, not just applied?",
        ["Because every fix trades something away, and you need to be able to say what",
         "Because the file will not save otherwise", "Because it makes the file smaller"],
        0, "Being able to state the trade-off is what separates cleaning from quietly changing data."),
    "bar_chart": (
        "Which pair of columns suits a bar chart?",
        ["A category with a few values, plus a number", "Two date columns", "An ID column on its own"],
        0, "A bar chart compares one number across a small set of categories."),
    "line_chart": (
        "Why does a line chart need a date column?",
        ["The line only means something if the points are in time order",
         "Because lines are prettier than bars", "Because dates are easier to read"],
        0, "The ordering is what turns a line into a trend rather than a decoration."),
    "histogram": (
        "What does a histogram show that an average does not?",
        ["Whether values cluster together or stretch out into a long tail",
         "The name of each category", "The total of the column"],
        0, "The shape of the distribution is exactly what a single average number hides."),
    "scatter_plot": (
        "On a scatter plot the dots slope clearly upward. What does that suggest?",
        ["The two columns tend to increase together", "One column caused the other",
         "The data has missing values"],
        0, "A slope shows they move together -- it never shows that one caused the other."),
    "chart_interpretation": (
        "Your chart shows one region far ahead of the others. What can it NOT tell you?",
        ["Why that region is ahead", "Which region is ahead", "How big the gap is"],
        0, "A chart describes what happened; the reason has to come from elsewhere."),
    "grouping": (
        "What does grouping your data by a category let you do?",
        ["Compare a summary of each group side by side",
         "Delete the rows you do not need", "Sort the file alphabetically"],
        0, "Most real business questions are group comparisons."),
    "segmentation": (
        "What makes a segment actually worth having?",
        ["The groups behave differently enough to treat differently",
         "It has a memorable name", "It contains exactly equal numbers of records"],
        0, "A segment that behaves like every other segment changes no decision."),
    "trends": (
        "How do you tell a real trend from one unusual month?",
        ["A trend holds its direction across several periods, not just one",
         "A trend is always upward", "A trend only appears in bar charts"],
        0, "Reacting to a single period is reacting to noise."),
    "correlation": (
        "Two columns are strongly correlated. What can you conclude?",
        ["They tend to move together, and something else may be driving both",
         "One definitely causes the other", "One of them must be an error"],
        0, "Correlation is about movement together; cause needs separate evidence."),
    "conversion_metrics": (
        "What must you be able to state for a conversion rate to mean anything?",
        ["Exactly what the denominator counts", "The colour of the chart",
         "How many columns the file has"],
        0, "The same numerator over a different denominator is a completely different number."),
    "attrition_analysis": (
        "Why is an overall attrition rate often not enough?",
        ["It hides which specific groups the problem is concentrated in",
         "It is always calculated wrongly", "It cannot be put in a chart"],
        0, "The overall figure averages away the very thing you need to act on."),
    "feature_engineering": (
        "Why can't a model use a raw date column directly?",
        ["It needs a number it can do arithmetic on, such as the month",
         "Dates are always missing", "Models only accept text"],
        0, "Turning a date into a month or day-of-week is what makes it usable."),
    "model_basics": (
        "What is a model actually doing?",
        ["Learning a pattern from examples so it can apply it to new records",
         "Storing every row so it can look them up", "Randomly guessing an answer"],
        0, "A model is a learned rule, not a lookup table and not magic."),
    "regression_vs_classification": (
        "You want to predict a deal's value in currency. What kind of problem is that?",
        ["Regression, because the answer is a number", "Classification, because deals have types",
         "Neither, because it cannot be predicted"],
        0, "Predicting a quantity is regression; predicting a category is classification."),
    "train_test_split": (
        "Why hold back part of your data from training?",
        ["So you can test on records the model has genuinely never seen",
         "To make training run faster", "Because some rows are always wrong"],
        0, "Without unseen data, a model that memorised looks perfect."),
    "model_evaluation": (
        "A model has a high score on your data. What should you still check?",
        ["Whether it scores as well on data it has never seen",
         "Whether the chart colours match", "How many columns the file has"],
        0, "A high score on familiar data can simply mean it memorised."),
    "overfitting": (
        "A model scores far better on training data than on test data. What does that mean?",
        ["It memorised the training data instead of learning the pattern",
         "The test data is broken", "It needs more columns"],
        0, "That gap between training and test performance is the definition of overfitting."),
    "model_selection": (
        "Why not always pick the most powerful model available?",
        ["Extra complexity you cannot justify is a cost, not a free upgrade",
         "Powerful models are illegal", "Simple models are always more accurate"],
        0, "You escalate when a measurement gives you a reason to, not by default."),
    "feature_importance": (
        "The top-ranked column is one you did not expect. What do you do first?",
        ["Check whether that column secretly encodes the answer",
         "Delete the column", "Accept it and move on"],
        0, "An unexpectedly dominant column is often leaking the target."),
    "business_translation": (
        "When has an analysis finding actually done its job?",
        ["When someone can name what they will do differently because of it",
         "When it fills a whole slide", "When it uses the most columns"],
        0, "A finding that changes no decision has changed nothing."),
}


class QuizAgent(Agent):
    name = "quiz_agent"
    responsibility = "Generate one grounded, level-appropriate comprehension question and mark the answer."

    def generate(self, concept_key: str, profile: UserProfile,
                 facts: list[str] | None = None, shuffle: bool = True) -> QuizQuestion:
        facts = facts or []

        llm_question = self._llm_question(concept_key, profile, facts)
        if llm_question:
            return llm_question

        entry = QUESTION_BANK.get(concept_key)
        if not entry:
            return QuizQuestion(
                question=f"What was the main idea of the '{concept_key.replace('_', ' ')}' lesson?",
                options=["The one explained in the lesson", "Something unrelated", "Nothing in particular"],
                correct_index=0, explanation="", concept_key=concept_key)

        question, options, correct, explanation = entry
        options = list(options)

        if shuffle:
            # The correct answer is written first in the bank for readability;
            # without shuffling, "always pick option A" would score 100%.
            correct_option = options[correct]
            random.shuffle(options)
            correct = options.index(correct_option)

        return QuizQuestion(question=question, options=options, correct_index=correct,
                            explanation=explanation, concept_key=concept_key, source="deterministic")

    def _llm_question(self, concept_key: str, profile: UserProfile, facts: list[str]) -> QuizQuestion | None:
        if not self.llm_enabled or not facts:
            return None

        parsed = self.llm.complete_json(
            QUIZ_SYSTEM,
            QUIZ_USER.format(
                role_description=describe_learner(profile),
                experience_level=profile.experience_level,
                concept=concept_key.replace("_", " "),
                facts="\n".join(f"- {f}" for f in facts),
            ),
            max_tokens=500,
        )
        if not isinstance(parsed, dict):
            return None

        options = parsed.get("options")
        idx = parsed.get("correct_index")
        if (not parsed.get("question") or not isinstance(options, list) or len(options) < 2
                or not isinstance(idx, int) or not 0 <= idx < len(options)):
            return None   # malformed -> the deterministic bank is used instead

        return QuizQuestion(question=str(parsed["question"]), options=[str(o) for o in options],
                            correct_index=idx, explanation=str(parsed.get("explanation", "")),
                            concept_key=concept_key, source="llm")

    def mark(self, question: QuizQuestion, answer_index: int) -> dict:
        """Marking is a comparison, never an LLM call -- a learner's score must
        be reproducible and cannot depend on a model's mood."""
        correct = answer_index == question.correct_index
        return {
            "correct": correct,
            "correct_index": question.correct_index,
            "correct_option": question.options[question.correct_index],
            "explanation": question.explanation,
            "feedback": ("Correct. " + question.explanation) if correct
                         else (f"Not quite -- the answer is \"{question.options[question.correct_index]}\". "
                               f"{question.explanation}"),
        }

    def run(self, concept_key: str = "", profile: UserProfile | None = None,
            facts: list[str] | None = None, **kwargs) -> AgentResponse:
        profile = profile or UserProfile()
        question = self.generate(concept_key, profile, facts)
        lines = [question.question] + [f"  {i}. {o}" for i, o in enumerate(question.options)]
        return self._respond("quiz", "\n".join(lines), {"quiz": question.to_dict()},
                             used_llm=(question.source == "llm"))
