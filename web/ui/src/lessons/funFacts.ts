/* Short, fun, deterministic facts/tips for the bottom banner on every level -
   deliberately NOT LLM-generated, so this stays instant and free of quota
   issues no matter what's happening with any live model. One per issue
   type is enough; add more here if a topic feels repetitive over time. */
const FUN_FACTS: Record<string, string> = {
  missing_numeric:
    "Fun fact: the average is the most “famous” statistic, but it's also the easiest to fool - a single huge outlier can drag it far from where most of your data actually sits.",
  missing_categorical:
    "Better way to think about it: a missing category is still information. “Unknown” is sometimes a more honest label than a guessed one.",
  label_inconsistency:
    "Fun fact: “NY”, “N.Y.”, and “New York” look obvious to you, but a computer treats them as three unrelated words until you tell it otherwise.",
  format_error_numeric:
    "Better way to think about it: if a number has a currency symbol or a comma in it, it's not a number yet to a computer - it's just a string that happens to look like one.",
  format_error_date:
    "Fun fact: there are dozens of ways to write the same date. “03/04/2024” means two different days depending on which country wrote it.",
};

const DEFAULT_FACT =
  "Fun fact: most of the work in data science isn't building models - it's getting the data into a shape a model can even use.";

export function funFactFor(issueType: string): string {
  return FUN_FACTS[issueType] ?? DEFAULT_FACT;
}
