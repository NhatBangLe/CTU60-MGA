import argparse
import logging
import sys
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
from app.eval.helpers import (
    DEFAULT_K_VALUES,
    GENERATION_CHARS_PER_TOKEN,
    GENERATION_CONTEXT_WINDOW_TOKENS,
    GENERATION_PROMPT_VERSION,
    GENERATION_RESERVED_TOKENS,
    RETRIEVAL_TOPK,
    SUBSET_CONFIG,
    aggregate_gen_metrics,
    build_context_index,
    cleanup,
    create_collection_name,
    default_generation_cache_path,
    default_metrics_output_path,
    ensure_csv_path,
    generate_answer,
    generation_cache_key,
    get_ground_truth_answer,
    get_relevant_ids,
    get_subset_processing_metadata,
    load_generation_cache,
    map_retrieved_to_parent_ids,
    postprocess_retrieval_metrics,
    print_gen_report,
    retrieval_trace_key,
    row_identifier,
    run_strategies,
    save_generation_cache,
    select_eval_dataset,
    setup_temp_collection,
)
from app.utils.embeddings import EmbeddingModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)
logger = logging.getLogger(__name__)


def evaluate(
    subset: str,
    k_values: list[int],
    strategies: list[str],
    sample: Optional[int] = None,
    output_path: Optional[Path] = None,
    persist: bool = True,
    generation_cache_path: Optional[Path] = None,
):
    print(f"=== Evaluating subset={subset}, sample={sample} ===", flush=True)
    logger.info(f"Loading dataset 'sailor2/Vietnamese_RAG' subset '{subset}'...")
    dataset = load_dataset("sailor2/Vietnamese_RAG", subset, split="train")
    total_queries = len(dataset)
    logger.info(f"Loaded {total_queries} queries")
    output_path = ensure_csv_path(
        output_path or default_metrics_output_path(subset, "generation", sample)
    )

    eval_dataset, total_evaluable_queries = select_eval_dataset(dataset, subset, sample)
    if sample is not None:
        logger.info(
            f"Evaluating {len(eval_dataset)} sampled queries from "
            f"{total_evaluable_queries} evaluable queries; indexing all "
            f"{total_queries} queries"
        )
    elif total_evaluable_queries != total_queries:
        logger.info(
            f"Evaluating {len(eval_dataset)} evaluable queries; skipped "
            f"{total_queries - total_evaluable_queries} non-evaluable queries; "
            f"indexing all {total_queries} queries"
        )

    logger.info("Building context index...")
    context_map, texts, metadatas = build_context_index(dataset, subset)
    logger.info(
        f"Found {len(context_map)} unique context documents; "
        f"indexing {len(texts)} passages/chunks"
    )

    temp_name = create_collection_name(subset)
    generation_cache_path = generation_cache_path or default_generation_cache_path(subset)
    generation_cache = load_generation_cache(generation_cache_path)
    generation_cache.update(
        {
            "version": 1,
            "dataset": "sailor2/Vietnamese_RAG",
            "subset": subset,
            "llm_model": config.LLM_MODEL_NAME,
            "prompt_version": GENERATION_PROMPT_VERSION,
            **get_subset_processing_metadata(subset),
            "context_window_tokens": GENERATION_CONTEXT_WINDOW_TOKENS,
            "reserved_tokens": GENERATION_RESERVED_TOKENS,
            "chars_per_token": GENERATION_CHARS_PER_TOKEN,
        }
    )
    cache_hits = 0
    cache_misses = 0
    logger.info(f"Using generation cache: {generation_cache_path}")

    id_to_text = {f"{temp_name}_{idx}": text for idx, text in enumerate(texts)}
    id_to_parent_id = {
        f"{temp_name}_{idx}": metadata["parent_id"]
        for idx, metadata in enumerate(metadatas)
    }
    embed_model = EmbeddingModel.get_instance()

    try:
        logger.info("Setting up temp ChromaDB collection and BM25 index...")
        setup_temp_collection(texts, temp_name, metadatas)

        all_results = []
        trace_keys_for_run = []

        for i, row in enumerate(eval_dataset):
            query = row["question"]
            ground_truth = get_ground_truth_answer(row)
            if not ground_truth:
                logger.debug(f"Skipping query {i}: no ground truth answer")
                continue

            retrieved = run_strategies(query, temp_name, RETRIEVAL_TOPK)
            row_id = row_identifier(row, i)
            relevant_ids = get_relevant_ids(row, subset, context_map, temp_name)
            trace_key = retrieval_trace_key(row_id, query)
            trace_keys_for_run.append(trace_key)
            retrieved_parent_ids = map_retrieved_to_parent_ids(
                retrieved, id_to_parent_id
            )
            generation_cache.setdefault("retrieval_traces", {})[
                trace_key
            ] = {
                "row_id": row_id,
                "query": query,
                "relevant_ids": sorted(relevant_ids),
                "retrieved_ids": retrieved,
                "retrieved_parent_ids": retrieved_parent_ids,
            }
            query_results = {}

            for strategy in strategies:
                strategy_results = {}
                for k in k_values:
                    top_k_ids = retrieved[strategy][:k]
                    top_k_texts = [
                        id_to_text[doc_id] for doc_id in top_k_ids if doc_id in id_to_text
                    ]

                    if not top_k_texts:
                        logger.debug(f"Query {i}, {strategy}@{k}: no retrieved texts")
                        strategy_results[k] = {
                            "sem_f1": 0.0,
                            "sem_p": 0.0,
                            "sem_r": 0.0,
                            "bleu1": 0.0,
                            "bleu4": 0.0,
                            "rouge_f1": 0.0,
                            "rouge_p": 0.0,
                            "rouge_r": 0.0,
                            "bert_f1": 0.0,
                            "bert_p": 0.0,
                            "bert_r": 0.0,
                        }
                        continue

                    cache_key = generation_cache_key(
                        subset=subset,
                        strategy=strategy,
                        k=k,
                        query=query,
                        retrieved_ids=top_k_ids,
                    )
                    cached = generation_cache["responses"].get(cache_key)
                    if cached and cached.get("generated_answer"):
                        gen_answer = cached["generated_answer"]
                        cache_hits += 1
                    else:
                        gen_answer = generate_answer(query, top_k_texts)
                        cache_misses += 1
                        generation_cache["responses"][cache_key] = {
                            "query": query,
                            "row_id": row_id,
                            "strategy": strategy,
                            "k": k,
                            "retrieved_ids": top_k_ids,
                            "generated_answer": gen_answer,
                            "ground_truth_answer": ground_truth,
                            "llm_model": config.LLM_MODEL_NAME,
                            "prompt_version": GENERATION_PROMPT_VERSION,
                            **get_subset_processing_metadata(subset),
                            "context_window_tokens": GENERATION_CONTEXT_WINDOW_TOKENS,
                            "reserved_tokens": GENERATION_RESERVED_TOKENS,
                            "chars_per_token": GENERATION_CHARS_PER_TOKEN,
                            "retrieved_parent_ids": [
                                id_to_parent_id.get(doc_id, doc_id)
                                for doc_id in top_k_ids
                            ],
                            "relevant_ids": sorted(relevant_ids),
                        }
                        save_generation_cache(generation_cache, generation_cache_path)

                    sem_f1 = sentence_embedding_f1(gen_answer, ground_truth, embed_model)
                    bleu = bleu_score(gen_answer, ground_truth)
                    rouge = rouge_l_f1(gen_answer, ground_truth)
                    bert = bertscore_f1(gen_answer, ground_truth)

                    strategy_results[k] = {
                        "sem_f1": sem_f1["f1"],
                        "sem_p": sem_f1["p"],
                        "sem_r": sem_f1["r"],
                        "bleu1": bleu["bleu1"],
                        "bleu4": bleu["bleu4"],
                        "rouge_f1": rouge["f1"],
                        "rouge_p": rouge["p"],
                        "rouge_r": rouge["r"],
                        "bert_f1": bert["f1"],
                        "bert_p": bert["p"],
                        "bert_r": bert["r"],
                    }
                query_results[strategy] = strategy_results

            all_results.append(query_results)

            if (i + 1) % 10 == 0:
                logger.info(f"Evaluated {i + 1}/{len(eval_dataset)} queries")

        logger.info(f"Evaluated {len(all_results)}/{len(eval_dataset)} queries")
        logger.info(
            f"Generation cache hits: {cache_hits}; new LLM calls: {cache_misses}"
        )
        generation_cache["last_run"] = {
            "subset": subset,
            "sample": sample,
            "k_values": k_values,
            "strategies": strategies,
            "num_queries": len(all_results),
            "trace_keys": trace_keys_for_run,
        }
        save_generation_cache(generation_cache, generation_cache_path)
        summary = aggregate_gen_metrics(all_results, k_values, strategies)
        print_gen_report(
            summary,
            k_values,
            strategies,
            subset,
            len(all_results),
            output_path,
            generation_cache_path,
        )

    finally:
        cleanup(temp_name, persist=persist)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate CTU AI Context Search generated answers"
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
        help="Save metrics CSV to this path",
    )
    parser.add_argument(
        "--generation-cache",
        type=Path,
        default=None,
        help="JSON cache file for generated LLM responses",
    )
    parser.add_argument(
        "--postprocess-retrieval-metrics",
        action="store_true",
        help=(
            "Compute Recall@k, MRR, and nDCG@k from the saved JSON cache "
            "and update the metrics CSV without calling the LLM"
        ),
    )
    parser.add_argument(
        "--cleanup",
        dest="persist",
        action="store_false",
        help="Delete ChromaDB/BM25 index after evaluation",
    )
    parser.set_defaults(persist=True)

    args = parser.parse_args()

    k_values = sorted(args.k)

    if args.postprocess_retrieval_metrics:
        postprocess_retrieval_metrics(
            subset=args.subset,
            k_values=k_values,
            strategies=args.strategies,
            output_path=args.output,
            generation_cache_path=args.generation_cache,
        )
        return

    evaluate(
        subset=args.subset,
        k_values=k_values,
        strategies=args.strategies,
        sample=args.sample,
        output_path=args.output,
        persist=args.persist,
        generation_cache_path=args.generation_cache,
    )


if __name__ == "__main__":
    main()
