from collections import Counter
from typing import Any, Sequence
from datasets import Dataset


class DatasetAnalyzer:
    """Class for analyzing and calculating statistics on evaluation datasets."""

    def __init__(self, dataset: Dataset):
        self.dataset = dataset

    def _compute_stats(self, values: Sequence[Any]) -> dict[str, dict[str, float]]:
        """Compute counts and percentages for a sequence of values."""
        total = len(self.dataset)
        counts = Counter(values)
        return {
            str(key): {
                "count": count,
                "percentage": (count / total) * 100 if total > 0 else 0.0,
            }
            for key, count in sorted(counts.items(), key=lambda x: str(x[0]))
        }

    def get_difficulty_statistics(self) -> dict[str, dict[str, float]]:
        """Compute counts and percentages grouped by difficulty."""
        return self._compute_stats([item["difficulty"] for item in self.dataset["metadata"]])

    def get_expected_route_statistics(self) -> dict[str, dict[str, float]]:
        """Compute counts and percentages grouped by expected_route."""
        return self._compute_stats(self.dataset["expected_route"])

    def get_language_statistics(self) -> dict[str, dict[str, float]]:
        """Compute counts and percentages grouped by language."""
        return self._compute_stats([item["language"] for item in self.dataset["metadata"]])

    def get_context_statistics(self) -> dict[str, dict[str, float]]:
        """Compute counts and percentages grouped by presence of context (True/False)."""
        has_context_list = [
            bool(item["context"]) if item.get("context") is not None else False
            for item in self.dataset["input"]
        ]
        return self._compute_stats(has_context_list)

    def get_has_input_image_statistics(self) -> dict[str, dict[str, float]]:
        """Compute counts and percentages grouped by has_input_image (True/False)."""
        return self._compute_stats([item["has_input_image"] for item in self.dataset["input"]])

    def print_summary(self) -> None:
        """Print formatted statistics summary grouped by difficulty, expected_route, language, context, and has_input_image."""
        sections = [
            ("Difficulty", self.get_difficulty_statistics()),
            ("Expected Route", self.get_expected_route_statistics()),
            ("Language", self.get_language_statistics()),
            ("Has Context", self.get_context_statistics()),
            ("Has Input Image", self.get_has_input_image_statistics()),
        ]

        for title, stats in sections:
            print(f"=== Statistics Grouped by {title} ===")
            for key, val in stats.items():
                print(f"  {key}: {int(val['count'])} ({val['percentage']:.1f}%)")
            print()
