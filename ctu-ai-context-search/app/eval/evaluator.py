import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from datasets import load_dataset

from app.config import config
from app.eval.gen_metrics import (
    bertscore_f1,
    bleu_score,
    rouge_l_f1,
    sentence_embedding_f1,
)

from app.services.hybrid_search import reciprocal_rank_fusion
from app.services.keyword_search import KeywordSearch
from app.services.semantic_search import SemanticSearch
from app.utils.bm25_indexer import BM25Indexer
from app.utils.chroma_client import ChromaClient
from app.utils.embeddings import EmbeddingModel
from app.utils.llm_client import LLMClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)
logger = logging.getLogger(__name__)

SUBSET_CONFIG = {
    "BKAI_RAG": {"context_field": "context", "is_list": True},
    "LegalRAG": {"context_field": "context", "is_list": True},
    "viQuAD": {"context_field": "contexts", "is_list": False},
}

DEFAULT_K_VALUES = [3, 5]
RETRIEVAL_TOPK = 100


def get_context_items(row: dict, subset: str) -> list[str]:
    cfg = SUBSET_CONFIG[subset]
    val = row[cfg["context_field"]]
    if cfg["is_list"]:
        return list(val)
    if isinstance(val, list):
        return val
    return [str(val)]


def build_context_index(
    dataset, subset: str,
) -> tuple[dict[str, int], list[str]]:
    unique: dict[str, int] = {}
    for row in dataset:
        for ctx in get_context_items(row, subset):
            if ctx not in unique:
                unique[ctx] = len(unique)
    texts = list(unique.keys())
    return unique, texts


def create_collection_name(subset: str) -> str:
    return f"eval_{subset}"


BATCH_SIZE = 8


def collection_is_ready(temp_name: str, expected_count: int) -> bool:
    try:
        col = ChromaClient.get_instance().client.get_collection(temp_name)
        count = col.count()
        if count == expected_count:
            logger.info(f"Reusing existing collection '{temp_name}' ({count} docs)")
            return True
        logger.info(f"Collection '{temp_name}' has {count} docs, expected {expected_count}, rebuilding...")
    except Exception:
        pass
    return False


def bm25_cache_exists(temp_name: str) -> bool:
    return (config.BM25_CACHE_DIR / f"{temp_name}_bm25.pkl").exists()


def setup_temp_collection(texts: list[str], temp_name: str):
    if collection_is_ready(temp_name, len(texts)) and bm25_cache_exists(temp_name):
        return

    all_ids = [f"{temp_name}_{i}" for i in range(len(texts))]
    metadatas = [{"idx": i} for i in range(len(texts))]

    chroma = ChromaClient.get_instance()
    for start in range(0, len(texts), BATCH_SIZE):
        end = start + BATCH_SIZE
        chroma.add_documents(
            temp_name, texts[start:end], all_ids[start:end], metadatas[start:end]
        )
        logger.info(
            f"Embedded batch {start // BATCH_SIZE + 1}/{(len(texts) - 1) // BATCH_SIZE + 1}"
        )

    bm25 = BM25Indexer.get_instance()
    bm25.index_documents(texts, all_ids, metadatas, collection_name=temp_name)
    bm25.save_index(temp_name)

    logger.info(
        f"Indexed {len(texts)} documents in temp collection '{temp_name}'"
    )
    return all_ids


def run_strategies(query: str, temp_name: str, top_k: int):
    sem_results = SemanticSearch.get_instance().search(
        query, temp_name, top_k=top_k
    )
    kw_results = KeywordSearch.get_instance().search(
        query, temp_name, top_k=top_k
    )

    sem_ids = [r.id for r in sem_results]
    kw_ids = [r.id for r in kw_results]

    rrf_scores = reciprocal_rank_fusion([sem_ids, kw_ids])
    hybrid_ids = sorted(
        rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True
    )

    return {"semantic": sem_ids, "bm25": kw_ids, "hybrid": hybrid_ids}


def cleanup(temp_name: str, persist: bool = False):
    if persist:
        logger.info(f"Skipping cleanup (--persist), keeping collection '{temp_name}'")
        return

    try:
        ChromaClient.get_instance().delete_collection(temp_name)
        logger.info(f"Deleted ChromaDB collection '{temp_name}'")
    except Exception as e:
        logger.warning(f"Failed to delete ChromaDB collection '{temp_name}': {e}")

    try:
        bm25 = BM25Indexer.get_instance()
        bm25._indexes.pop(temp_name, None)
        bm25._documents.pop(temp_name, None)
        bm25._ids.pop(temp_name, None)
        bm25._metadatas.pop(temp_name, None)
        logger.info(f"Cleaned BM25 index for '{temp_name}'")
    except Exception as e:
        logger.warning(f"Failed to clean BM25 index: {e}")

    cache_file = config.BM25_CACHE_DIR / f"{temp_name}_bm25.pkl"
    if cache_file.exists():
        try:
            cache_file.unlink()
            logger.info(f"Deleted BM25 cache file '{cache_file}'")
        except Exception as e:
            logger.warning(f"Failed to delete BM25 cache: {e}")


def generate_answer(query: str, chunks: list[str]) -> str:
    context = "\n\n".join(chunks)
    prompt = (
        "Dựa vào các đoạn văn sau, hãy trả lời câu hỏi một cách ngắn gọn (1-3 câu).\n\n"
        f"Các đoạn văn:\n{context}\n\n"
        f"Câu hỏi: {query}\n\n"
        "Trả lời:"
    )
    return LLMClient().generate(prompt)


def evaluate_gen(
    subset: str,
    k_values: list[int],
    strategies: list[str],
    sample: Optional[int] = None,
    output_path: Optional[Path] = None,
    persist: bool = False,
    eval_mode: str = "no-llm",
):
    print(f"=== Evaluating (eval_mode={eval_mode}) subset={subset}, sample={sample} ===", flush=True)
    logger.info(f"Loading dataset 'sailor2/Vietnamese_RAG' subset '{subset}'...")
    dataset = load_dataset("sailor2/Vietnamese_RAG", subset, split="train")
    total_queries = len(dataset)
    logger.info(f"Loaded {total_queries} queries")

    if sample is not None:
        dataset = dataset.shuffle(seed=42).select(range(min(sample, total_queries)))

    logger.info("Building context index...")
    context_map, texts = build_context_index(dataset, subset)
    logger.info(f"Found {len(texts)} unique context documents")

    temp_name = create_collection_name(subset)

    id_to_text = {f"{temp_name}_{idx}": text for idx, text in enumerate(texts)}
    embed_model = EmbeddingModel.get_instance()

    try:
        logger.info("Setting up temp ChromaDB collection and BM25 index...")
        setup_temp_collection(texts, temp_name)

        all_results = []

        for i, row in enumerate(dataset):
            query = row["question"]
            ground_truth = row.get("answer", "")
            if not ground_truth:
                logger.debug(f"Skipping query {i}: no ground truth answer")
                continue

            retrieved = run_strategies(query, temp_name, RETRIEVAL_TOPK)
            query_results = {}

            max_k = max(k_values)

            for strategy in strategies:
                strategy_results = {}
                top_k_ids = retrieved[strategy][:max_k]
                top_k_texts = [id_to_text[doc_id] for doc_id in top_k_ids if doc_id in id_to_text]

                if not top_k_texts:
                    logger.debug(f"Query {i}, {strategy}: no retrieved texts")
                    for k in k_values:
                        strategy_results[k] = {
                            "sem_f1": 0.0, "sem_p": 0.0, "sem_r": 0.0,
                            "bleu1": 0.0, "bleu4": 0.0,
                            "rouge_f1": 0.0, "rouge_p": 0.0, "rouge_r": 0.0,
                            "bert_f1": 0.0, "bert_p": 0.0, "bert_r": 0.0,
                        }
                    query_results[strategy] = strategy_results
                    continue

                if eval_mode == "gen":
                    gen_answer = generate_answer(query, top_k_texts)

                for k in k_values:
                    answer = "\n".join(top_k_texts[:k]) if eval_mode == "no-llm" else gen_answer
                    sem_f1 = sentence_embedding_f1(answer, ground_truth, embed_model)
                    bleu = bleu_score(answer, ground_truth)
                    rouge = rouge_l_f1(answer, ground_truth)
                    bert = bertscore_f1(answer, ground_truth)

                    strategy_results[k] = {
                        "sem_f1": sem_f1["f1"], "sem_p": sem_f1["p"], "sem_r": sem_f1["r"],
                        "bleu1": bleu["bleu1"], "bleu4": bleu["bleu4"],
                        "rouge_f1": rouge["f1"], "rouge_p": rouge["p"], "rouge_r": rouge["r"],
                        "bert_f1": bert["f1"], "bert_p": bert["p"], "bert_r": bert["r"],
                    }
                query_results[strategy] = strategy_results

            all_results.append(query_results)

            if (i + 1) % 10 == 0:
                logger.info(f"Evaluated {i + 1}/{len(dataset)} queries")

        logger.info(f"Evaluated {len(all_results)}/{len(dataset)} queries")
        summary = aggregate_gen_metrics(all_results, k_values, strategies)
        print_gen_report(summary, k_values, strategies, subset, len(all_results), output_path)

    finally:
        cleanup(temp_name, persist=persist)


def aggregate_gen_metrics(
    all_results: list[dict], k_values: list[int], strategies: list[str]
) -> dict:
    metrics = ["sem_f1", "sem_p", "sem_r", "bleu1", "bleu4",
               "rouge_f1", "rouge_p", "rouge_r", "bert_f1", "bert_p", "bert_r"]

    agg = {}
    for strategy in strategies:
        agg[strategy] = {}
        for k in k_values:
            agg[strategy][k] = {m: [] for m in metrics}

    for row in all_results:
        for strategy in strategies:
            for k in k_values:
                if k in row.get(strategy, {}):
                    for m in metrics:
                        agg[strategy][k][m].append(row[strategy][k][m])

    def _mean(vals):
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    summary = {}
    for strategy in strategies:
        summary[strategy] = {}
        for k in k_values:
            summary[strategy][k] = {}
            for m in metrics:
                summary[strategy][k][m] = _mean(agg[strategy][k][m])
    return summary


def print_gen_report(
    summary: dict,
    k_values: list[int],
    strategies: list[str],
    subset: str,
    num_queries: int,
    output_path: Optional[Path] = None,
):
    report_metrics = ["sem_f1", "bert_f1", "rouge_f1", "bleu4"]
    col_labels = {
        "sem_f1": "SEmb-F1",
        "bert_f1": "BERT-F1",
        "rouge_f1": "R-L-F1",
        "bleu4": "BLEU-4",
    }

    line_len = 12 + len(k_values) * 9 * len(report_metrics)

    header = (
        f"Dataset: {subset} ({num_queries} queries)\n"
        + "─" * line_len
    )
    print(f"\n{header}")

    col_headers = f"{'Strategy':<12}"
    for k in k_values:
        for m in report_metrics:
            col_headers += f"{col_labels[m]}@{k}".rjust(9)
    print(col_headers)
    print("─" * len(col_headers))

    for strategy in strategies:
        row_str = f"{strategy:<12}"
        for k in k_values:
            for m in report_metrics:
                val = summary[strategy][k].get(m, 0.0)
                row_str += f"{val:<9.4f}"
        print(row_str)

    print("─" * len(col_headers))

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "subset": subset,
                    "num_queries": num_queries,
                    "k_values": k_values,
                    "strategies": strategies,
                    "mode": "gen",
                    "summary": summary,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        print(f"\nReport saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate CTU AI Context Search retrieval performance"
    )
    parser.add_argument(
        "--subset",
        default="BKAI_RAG",
        choices=list(SUBSET_CONFIG.keys()),
        help="Dataset subset to evaluate on",
    )
    parser.add_argument(
        "--k",
        nargs="+",
        type=int,
        default=DEFAULT_K_VALUES,
        help=f"K values for precision/recall/F1 (default: {' '.join(str(v) for v in DEFAULT_K_VALUES)})",
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=["semantic", "bm25", "hybrid"],
        choices=["semantic", "bm25", "hybrid"],
        help="Strategies to evaluate (default: all)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Randomly sample N queries (default: use all)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Save report JSON to this path",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Keep ChromaDB/BM25 index after evaluation for faster reruns",
    )
    parser.add_argument(
        "--eval-mode",
        default="no-llm",
        choices=["gen", "no-llm"],
        help="'gen' uses LLM to generate answer from chunks; 'no-llm' uses raw chunks as answer (default: no-llm)",
    )

    args = parser.parse_args()

    evaluate_gen(
        subset=args.subset,
        k_values=sorted(args.k),
        strategies=args.strategies,
        sample=args.sample,
        output_path=args.output,
        persist=args.persist,
        eval_mode=args.eval_mode,
    )


if __name__ == "__main__":
    main()
