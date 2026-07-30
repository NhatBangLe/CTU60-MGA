from collections import Counter
from datasets import Dataset


class DatasetAnalyzer:
    """Class for analyzing and calculating statistics on evaluation datasets."""

    def __init__(self, dataset: Dataset):
        self.dataset = dataset

    def get_difficulty_statistics(self) -> dict[str, dict[str, float]]:
        """Compute counts and percentages grouped by difficulty."""
        total = len(self.dataset)
        counts = Counter(item["difficulty"] for item in self.dataset["metadata"])
        return {
            difficulty: {
                "count": count,
                "percentage": (count / total) * 100 if total > 0 else 0.0,
            }
            for difficulty, count in sorted(counts.items())
        }

    def get_expected_route_statistics(self) -> dict[str, dict[str, float]]:
        """Compute counts and percentages grouped by expected_route."""
        total = len(self.dataset)
        counts = Counter(self.dataset["expected_route"])
        return {
            route: {
                "count": count,
                "percentage": (count / total) * 100 if total > 0 else 0.0,
            }
            for route, count in sorted(counts.items())
        }

    def print_summary(self) -> None:
        """Print formatted statistics summary grouped by difficulty and expected_route."""
        print("=== Statistics Grouped by Difficulty ===")
        for difficulty, stats in self.get_difficulty_statistics().items():
            print(f"  {difficulty}: {int(stats['count'])} ({stats['percentage']:.1f}%)")

        print("\n=== Statistics Grouped by Expected Route ===")
        for route, stats in self.get_expected_route_statistics().items():
            print(f"  {route}: {int(stats['count'])} ({stats['percentage']:.1f}%)")
