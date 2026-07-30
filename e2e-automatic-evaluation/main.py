from datasets import load_dataset
from config import settings
from utility import DatasetAnalyzer


def main():
    # Load dataset using data_file path from Settings
    dataset = load_dataset("json", data_files=settings.data_file, split="train")

    # Analyze dataset statistics
    analyzer = DatasetAnalyzer(dataset)
    analyzer.print_summary()


if __name__ == "__main__":
    main()
