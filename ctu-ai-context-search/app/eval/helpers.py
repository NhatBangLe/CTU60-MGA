import ast
import csv
import hashlib
import json
import logging
import math
import os
import random
import re
from pathlib import Path
from typing import Optional

from datasets import load_dataset

from app.config import config
from app.eval.metrics import f1_at_k, mrr, ndcg_at_k, precision_at_k, recall_at_k
from app.services.hybrid_search import reciprocal_rank_fusion, rerank_with_llm
from app.services.keyword_search import KeywordSearch
from app.services.semantic_search import SemanticSearch
from app.utils.bm25_indexer import BM25Indexer
from app.utils.chroma_client import ChromaClient
from app.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

LEGALRAG_CHUNK_CHARS = int(os.environ.get("EVAL_LEGALRAG_CHUNK_CHARS", "4000"))
LEGALRAG_CHUNK_OVERLAP_CHARS = int(
    os.environ.get("EVAL_LEGALRAG_CHUNK_OVERLAP_CHARS", "400")
)
VIQUAD_CONTEXT_LABEL_RE = re.compile("Ng\u1eef c\u1ea3nh\\s*\\d+\\s*:")
VIQUAD_ANSWER_TEXT_RE = re.compile(
    r"'text'\s*:\s*array\((\[.*?\])(?:,\s*dtype=[^)]+)?\)",
    re.DOTALL,
)
VIQUAD_ANSWER_START_RE = re.compile(
    r"'answer_start'\s*:\s*array\((\[.*?\])(?:,\s*dtype=[^)]+)?\)",
    re.DOTALL,
)

SUBSET_CONFIG = {
    "BKAI_RAG": {
        "context_field": "context",
        "is_list": True,
        "chunk_chars": LEGALRAG_CHUNK_CHARS,
        "chunk_overlap_chars": LEGALRAG_CHUNK_OVERLAP_CHARS,
    },
    "LegalRAG": {
        "context_field": "context",
        "is_list": True,
        "chunk_chars": LEGALRAG_CHUNK_CHARS,
        "chunk_overlap_chars": LEGALRAG_CHUNK_OVERLAP_CHARS,
    },
    "viQuAD": {
        "context_field": "contexts",
        "is_list": False,
        "split_labeled_contexts": True,
    },
}

DEFAULT_K_VALUES = [3, 5]
RETRIEVAL_TOPK = 100
GENERATION_PROMPT_VERSION = 4
BATCH_SIZE = 8
GENERATION_CONTEXT_WINDOW_TOKENS = int(
    os.environ.get("EVAL_LLM_CONTEXT_WINDOW_TOKENS", "128000")
)
GENERATION_RESERVED_TOKENS = int(os.environ.get("EVAL_LLM_RESERVED_TOKENS", "4096"))
GENERATION_CHARS_PER_TOKEN = float(os.environ.get("EVAL_LLM_CHARS_PER_TOKEN", "2.5"))
TRUNCATION_NOTICE = "\n\n[Context truncated to fit the model window.]"


def get_chunk_chars(subset: str) -> int:
    return int(SUBSET_CONFIG[subset].get("chunk_chars") or 0)


def get_chunk_overlap_chars(subset: str) -> int:
    return int(SUBSET_CONFIG[subset].get("chunk_overlap_chars") or 0)


def get_subset_processing_metadata(subset: str) -> dict:
    chunk_chars = get_chunk_chars(subset)
    if chunk_chars <= 0:
        if SUBSET_CONFIG[subset].get("split_labeled_contexts"):
            return {"context_processing": "labeled_passages"}
        return {"context_processing": "full_context"}
    return {
        "context_processing": "chunked",
        "chunk_chars": chunk_chars,
        "chunk_overlap_chars": get_chunk_overlap_chars(subset),
    }


def get_subset_output_name(subset: str) -> str:
    chunk_chars = get_chunk_chars(subset)
    if chunk_chars > 0:
        return f"{subset}_chunk{chunk_chars}_overlap{get_chunk_overlap_chars(subset)}"
    if SUBSET_CONFIG[subset].get("split_labeled_contexts"):
        return f"{subset}_passages"
    return subset


def context_parent_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def retrieval_trace_key(row_id: str, query: str) -> str:
    raw_key = f"{row_id}\n{query}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def row_identifier(row: dict, fallback_idx: int) -> str:
    return str(row.get("id") or row.get("uit_id") or fallback_idx)


def split_context_for_subset(text: str, subset: str) -> list[str]:
    chunk_chars = get_chunk_chars(subset)
    if chunk_chars <= 0 or len(text) <= chunk_chars:
        return [text]

    overlap = min(get_chunk_overlap_chars(subset), chunk_chars - 1)
    step = chunk_chars - overlap
    chunks = []
    for start in range(0, len(text), step):
        chunk = text[start : start + chunk_chars].strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_chars >= len(text):
            break
    return chunks


def split_labeled_contexts_with_spans(text: str) -> list[tuple[str, int, int]]:
    matches = list(VIQUAD_CONTEXT_LABEL_RE.finditer(text))
    if not matches:
        stripped = text.strip()
        start = text.find(stripped) if stripped else 0
        return [(stripped, start, start + len(stripped))] if stripped else []

    contexts = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        raw = text[start:end]
        stripped = raw.strip()
        if not stripped:
            continue
        leading = len(raw) - len(raw.lstrip())
        contexts.append((stripped, start + leading, start + leading + len(stripped)))
    return contexts


def split_labeled_contexts(text: str) -> list[str]:
    return [ctx for ctx, _, _ in split_labeled_contexts_with_spans(text)]


def strip_viquad_context_label(text: str) -> str:
    match = VIQUAD_CONTEXT_LABEL_RE.match(text)
    if not match:
        return text
    return text[match.end() :].lstrip()


def _as_list(value) -> list:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _parse_repr_array(pattern: re.Pattern, text: str) -> list:
    match = pattern.search(text)
    if not match:
        return []
    try:
        return _as_list(ast.literal_eval(match.group(1)))
    except (SyntaxError, ValueError):
        return []


def parse_viquad_answers(row: dict) -> tuple[list[str], list[int]]:
    value = row.get("answers", "")
    if isinstance(value, dict):
        texts = [str(item) for item in _as_list(value.get("text")) if item]
        starts = []
        for item in _as_list(value.get("answer_start")):
            try:
                starts.append(int(item))
            except (TypeError, ValueError):
                pass
        return texts, starts

    if not isinstance(value, str):
        return [], []

    texts = [
        str(item)
        for item in _parse_repr_array(VIQUAD_ANSWER_TEXT_RE, value)
        if item
    ]
    starts = []
    for item in _parse_repr_array(VIQUAD_ANSWER_START_RE, value):
        try:
            starts.append(int(item))
        except (TypeError, ValueError):
            pass
    return texts, starts


def is_unanswerable(row: dict) -> bool:
    return str(row.get("is_impossible", "")).strip().lower() in {"true", "1", "yes"}


def _normalized_for_match(text: str) -> str:
    return " ".join(str(text).split()).casefold()


def get_context_items(row: dict, subset: str) -> list[str]:
    cfg = SUBSET_CONFIG[subset]
    val = row[cfg["context_field"]]
    if cfg.get("split_labeled_contexts"):
        return split_labeled_contexts(str(val))
    if cfg["is_list"] and isinstance(val, list):
        return [str(item) for item in val]
    if isinstance(val, list):
        return [str(item) for item in val]
    return [str(val)]


def _answer_source_context(row: dict, subset: str) -> list[str]:
    answer = str(row.get("answer", "")).strip()
    items = get_context_items(row, subset)
    if not answer or not items:
        return []
    answer_words = {w for w in re.split(r"\W+", answer.lower()) if len(w) > 1}
    if not answer_words:
        return []
    scores = [
        sum(1 for w in answer_words if w in set(re.split(r"\W+", ctx.lower())))
        for ctx in items
    ]
    best = max(range(len(items)), key=scores.__getitem__)
    return [items[best]]


def get_relevant_context_items(row: dict, subset: str) -> list[str]:
    if subset != "viQuAD":
        # ponytail: heuristic gold label (max answer-word overlap); the dataset
        # has no explicit source-passage labels for LegalRAG/BKAI_RAG
        return _answer_source_context(row, subset)

    if is_unanswerable(row):
        return []

    cfg = SUBSET_CONFIG[subset]
    contexts_with_spans = split_labeled_contexts_with_spans(
        str(row[cfg["context_field"]])
    )
    answer_texts, answer_starts = parse_viquad_answers(row)
    if not answer_texts and not answer_starts:
        return []

    matched = []
    seen = set()

    def add_match(ctx: str) -> None:
        parent_id = context_parent_id(ctx)
        if parent_id not in seen:
            seen.add(parent_id)
            matched.append(ctx)

    for ctx, _, _ in contexts_with_spans:
        body = strip_viquad_context_label(ctx)
        for answer_idx, answer_start in enumerate(answer_starts):
            if answer_start < 0 or answer_start >= len(body):
                continue

            answer = answer_texts[answer_idx] if answer_idx < len(answer_texts) else ""
            if not answer:
                return [ctx]

            candidate = body[answer_start : answer_start + len(answer)]
            window = body[max(0, answer_start - 10) : answer_start + len(answer) + 10]
            answer_in_window = _normalized_for_match(answer) in _normalized_for_match(
                window
            )
            if candidate == answer or answer_in_window:
                return [ctx]

    if matched:
        return matched

    normalized_answers = [
        _normalized_for_match(answer) for answer in answer_texts if str(answer).strip()
    ]
    for ctx, _, _ in contexts_with_spans:
        normalized_ctx = _normalized_for_match(ctx)
        if any(answer and answer in normalized_ctx for answer in normalized_answers):
            add_match(ctx)
            break

    if matched:
        return matched

    for answer_start in answer_starts:
        for ctx, start, end in contexts_with_spans:
            if start <= answer_start < end:
                return [ctx]

    return matched


def get_ground_truth_answer(row: dict) -> str:
    for field in ("answer", "answers"):
        val = row.get(field, "")
        if field == "answers":
            answers, _ = parse_viquad_answers(row)
            if answers:
                return "\n".join(answers)
            if isinstance(val, str) and "'text'" in val and "array(" in val:
                return ""
        if isinstance(val, list):
            return "\n".join(str(item) for item in val if item)
        if val:
            return str(val)
    return ""


def is_evaluable_query(row: dict, subset: str) -> bool:
    if subset == "viQuAD":
        return not is_unanswerable(row) and bool(get_ground_truth_answer(row))
    return True


def select_eval_dataset(dataset, subset: str, sample: Optional[int]):
    candidate_indices = [
        idx for idx, row in enumerate(dataset) if is_evaluable_query(row, subset)
    ]
    selected_indices = list(candidate_indices)
    if sample is not None:
        rng = random.Random(42)
        rng.shuffle(selected_indices)
        selected_indices = selected_indices[: min(sample, len(selected_indices))]

    if hasattr(dataset, "select"):
        return dataset.select(selected_indices), len(candidate_indices)
    return [dataset[idx] for idx in selected_indices], len(candidate_indices)


def build_context_index(
    dataset, subset: str,
) -> tuple[dict[str, list[int]], list[str], list[dict]]:
    context_map: dict[str, list[int]] = {}
    texts: list[str] = []
    metadatas: list[dict] = []

    for row in dataset:
        for ctx in get_context_items(row, subset):
            parent_id = context_parent_id(ctx)
            if parent_id in context_map:
                continue

            chunks = split_context_for_subset(ctx, subset)
            context_map[parent_id] = []
            for chunk_index, chunk in enumerate(chunks):
                idx = len(texts)
                texts.append(chunk)
                context_map[parent_id].append(idx)
                metadatas.append(
                    {
                        "parent_id": parent_id,
                        "chunk_index": chunk_index,
                        "chunk_count": len(chunks),
                        "subset": subset,
                    }
                )

    return context_map, texts, metadatas


def create_collection_name(subset: str) -> str:
    return f"eval_{get_subset_output_name(subset)}"


def default_generation_cache_path(subset: str, rerank: bool = False) -> Path:
    suffix = "_rerank" if rerank else ""
    return Path("reports") / f"{subset}{suffix}.json"


def default_metrics_output_path(
    subset: str, mode: str, sample: Optional[int], rerank: bool = False
) -> Path:
    suffix = "_rerank" if rerank else ""
    return Path("reports") / f"{subset}{suffix}.csv"


def default_details_output_path(subset: str, mode: str, sample: Optional[int]) -> Path:
    sample_label = "full" if sample is None else str(sample)
    return (
        Path("reports")
        / f"eval_{get_subset_output_name(subset)}_{mode}_{sample_label}.json"
    )


def ensure_csv_path(output_path: Path) -> Path:
    if output_path.suffix.lower() == ".csv":
        return output_path
    return output_path.with_suffix(".csv")


def ensure_json_path(output_path: Path) -> Path:
    if output_path.suffix.lower() == ".json":
        return output_path
    return output_path.with_suffix(".json")


def load_generation_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {"version": 1, "responses": {}}

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load generation cache '{cache_path}': {e}")
        return {"version": 1, "responses": {}}

    if not isinstance(cache, dict):
        return {"version": 1, "responses": {}}

    cache.setdefault("version", 1)
    if not isinstance(cache.get("responses"), dict):
        cache["responses"] = {}
    return cache


def save_generation_cache(cache: dict, cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def save_json_report(data: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generation_cache_key(
    subset: str,
    strategy: str,
    k: int,
    query: str,
    retrieved_ids: list[str],
) -> str:
    payload = {
        "prompt_version": GENERATION_PROMPT_VERSION,
        "llm_model": config.LLM_MODEL_NAME,
        "subset": subset,
        "strategy": strategy,
        "k": k,
        "query": query,
        "retrieved_ids": retrieved_ids,
        **get_subset_processing_metadata(subset),
        "context_window_tokens": GENERATION_CONTEXT_WINDOW_TOKENS,
        "reserved_tokens": GENERATION_RESERVED_TOKENS,
        "chars_per_token": GENERATION_CHARS_PER_TOKEN,
    }
    raw_key = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def collection_is_ready(temp_name: str, expected_count: int) -> bool:
    try:
        col = ChromaClient.get_instance().client.get_collection(temp_name)
        count = col.count()
        if count == expected_count:
            logger.info(f"Reusing existing collection '{temp_name}' ({count} docs)")
            return True
        logger.info(
            f"Collection '{temp_name}' has {count} docs, expected {expected_count}, rebuilding..."
        )
    except Exception:
        pass
    return False


def setup_temp_collection(
    texts: list[str], temp_name: str, metadatas: Optional[list[dict]] = None
):
    collection_ready = collection_is_ready(temp_name, len(texts))
    bm25 = BM25Indexer.get_instance()

    if collection_ready and bm25.load_index(temp_name):
        return

    try:
        ChromaClient.get_instance().delete_collection(temp_name)
        logger.info(f"Deleted stale ChromaDB collection '{temp_name}' before rebuild")
    except Exception:
        pass

    bm25._indexes.pop(temp_name, None)
    bm25._documents.pop(temp_name, None)
    bm25._ids.pop(temp_name, None)
    bm25._metadatas.pop(temp_name, None)

    cache_file = config.BM25_CACHE_DIR / f"{temp_name}_bm25.pkl"
    if cache_file.exists():
        cache_file.unlink()
        logger.info(f"Deleted stale BM25 cache file '{cache_file}' before rebuild")

    all_ids = [f"{temp_name}_{i}" for i in range(len(texts))]
    base_metadatas = metadatas or [{} for _ in texts]
    indexed_metadatas = []
    for i, metadata in enumerate(base_metadatas):
        indexed_metadatas.append({**metadata, "idx": i, "id": all_ids[i]})

    chroma = ChromaClient.get_instance()
    for start in range(0, len(texts), BATCH_SIZE):
        end = start + BATCH_SIZE
        chroma.add_documents(
            temp_name,
            texts[start:end],
            all_ids[start:end],
            indexed_metadatas[start:end],
        )
        logger.info(
            f"Embedded batch {start // BATCH_SIZE + 1}/{(len(texts) - 1) // BATCH_SIZE + 1}"
        )

    bm25.index_documents(texts, all_ids, indexed_metadatas, collection_name=temp_name)
    bm25.save_index(temp_name)

    logger.info(f"Indexed {len(texts)} documents in temp collection '{temp_name}'")
    return all_ids


def get_relevant_ids(
    row: dict, subset: str, context_map: dict[str, list[int]], temp_name: str
) -> set[str]:
    ids = set()
    for ctx in get_relevant_context_items(row, subset):
        parent_id = context_parent_id(ctx)
        if parent_id in context_map:
            ids.add(parent_id)
    return ids


def map_retrieved_to_parent_ids(
    retrieved: dict[str, list[str]], id_to_parent_id: dict[str, str]
) -> dict[str, list[str]]:
    mapped: dict[str, list[str]] = {}
    for strategy, ids in retrieved.items():
        seen = set()
        parent_ids = []
        for doc_id in ids:
            parent_id = id_to_parent_id.get(doc_id, doc_id)
            if parent_id in seen:
                continue
            seen.add(parent_id)
            parent_ids.append(parent_id)
        mapped[strategy] = parent_ids
    return mapped


def run_strategies(
    query: str,
    temp_name: str,
    top_k: int,
    rerank: bool = False,
    rerank_candidates: Optional[int] = None,
):
    sem_results = SemanticSearch.get_instance().search(query, temp_name, top_k=top_k)
    kw_results = KeywordSearch.get_instance().search(query, temp_name, top_k=top_k)

    sem_ids = [r.id for r in sem_results]
    kw_ids = [r.id for r in kw_results]

    rrf_scores = reciprocal_rank_fusion([sem_ids, kw_ids])
    hybrid_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    if rerank and rerank_candidates:
        head, tail = hybrid_ids[:rerank_candidates], hybrid_ids[rerank_candidates:]
        doc_lookup = {r.id: r.document for r in sem_results}
        doc_lookup.update({r.id: r.document for r in kw_results})
        order = rerank_with_llm(query, [doc_lookup.get(i, "") for i in head])
        hybrid_ids = [head[i] for i in order] + tail

    return {"semantic": sem_ids, "bm25": kw_ids, "hybrid": hybrid_ids}


def compute_query_metrics(
    retrieved: dict[str, list[str]],
    relevant_ids: set[str],
    k_values: list[int],
) -> dict:
    results = {}
    for strategy, ids in retrieved.items():
        strategy_metrics = {}
        for k in k_values:
            p = precision_at_k(ids, relevant_ids, k)
            r = recall_at_k(ids, relevant_ids, k)
            f1 = f1_at_k(p, r)
            ndcg = ndcg_at_k(ids, relevant_ids, k)
            strategy_metrics[k] = {
                "p": round(p, 4),
                "r": round(r, 4),
                "f1": round(f1, 4),
                "ndcg": round(ndcg, 4),
            }
        strategy_metrics["mrr"] = round(mrr(ids, relevant_ids), 4)
        results[strategy] = strategy_metrics
    return results


def aggregate_metrics(
    all_results: list[dict], k_values: list[int], strategies: list[str]
) -> dict:
    agg = {}
    for strategy in strategies:
        agg[strategy] = {}
        for k in k_values:
            agg[strategy][k] = {"p": [], "r": [], "f1": [], "ndcg": []}
        agg[strategy]["mrr"] = []

    for row in all_results:
        for strategy in strategies:
            for k in k_values:
                agg[strategy][k]["p"].append(row[strategy][k]["p"])
                agg[strategy][k]["r"].append(row[strategy][k]["r"])
                agg[strategy][k]["f1"].append(row[strategy][k]["f1"])
                agg[strategy][k]["ndcg"].append(row[strategy][k]["ndcg"])
            agg[strategy]["mrr"].append(row[strategy]["mrr"])

    def _mean(vals):
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    summary = {}
    for strategy in strategies:
        summary[strategy] = {}
        for k in k_values:
            summary[strategy][k] = {
                "p": _mean(agg[strategy][k]["p"]),
                "r": _mean(agg[strategy][k]["r"]),
                "f1": _mean(agg[strategy][k]["f1"]),
                "ndcg": _mean(agg[strategy][k]["ndcg"]),
            }
        summary[strategy]["mrr"] = _mean(agg[strategy]["mrr"])
    return summary


def _as_str_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _select_trace_records(cache: dict, subset: str) -> tuple[list[dict], str]:
    traces = cache.get("retrieval_traces")
    if not isinstance(traces, dict) or not traces:
        return [], "responses"

    last_run = cache.get("last_run")
    if isinstance(last_run, dict) and last_run.get("subset") == subset:
        trace_keys = [
            key
            for key in last_run.get("trace_keys", [])
            if isinstance(key, str) and key in traces
        ]
        if trace_keys:
            return [traces[key] for key in trace_keys], "last_run_traces"

    return [trace for trace in traces.values() if isinstance(trace, dict)], "all_traces"


def _build_relevance_lookup(subset: str):
    logger.info(
        "Loading dataset to recover relevance labels for cached responses without traces..."
    )
    dataset = load_dataset("sailor2/Vietnamese_RAG", subset, split="train")
    context_map, _, _ = build_context_index(dataset, subset)
    row_lookup: dict[str, dict] = {}
    query_lookup: dict[str, dict] = {}

    for idx, row in enumerate(dataset):
        for value in {row_identifier(row, idx), row.get("id"), row.get("uit_id")}:
            if value is not None and str(value):
                row_lookup.setdefault(str(value), row)
        query = str(row.get("question", ""))
        if query:
            query_lookup.setdefault(query, row)

    return row_lookup, query_lookup, context_map


def _resolve_relevant_ids(
    entry: dict,
    subset: str,
    relevance_lookup,
):
    relevant_ids = _as_str_list(entry.get("relevant_ids"))
    if relevant_ids:
        return set(relevant_ids), relevance_lookup

    if relevance_lookup is None:
        relevance_lookup = _build_relevance_lookup(subset)

    row_lookup, query_lookup, context_map = relevance_lookup
    row = None
    row_id = entry.get("row_id")
    if row_id is not None:
        row = row_lookup.get(str(row_id))
    if row is None:
        row = query_lookup.get(str(entry.get("query", "")))
    if row is None:
        return set(), relevance_lookup

    relevant_ids = get_relevant_ids(
        row,
        subset,
        context_map,
        create_collection_name(subset),
    )
    return relevant_ids, relevance_lookup


def _retrieved_from_trace(trace: dict, strategies: list[str]) -> dict[str, list[str]]:
    source = trace.get("retrieved_parent_ids")
    if not isinstance(source, dict):
        source = trace.get("retrieved_ids")
    if not isinstance(source, dict):
        return {strategy: [] for strategy in strategies}

    return {
        strategy: _as_str_list(source.get(strategy, []))
        for strategy in strategies
    }


def _response_groups(cache: dict, strategies: list[str]) -> list[dict]:
    responses = cache.get("responses")
    if not isinstance(responses, dict):
        return []

    grouped: dict[tuple[str, str], dict] = {}
    for response in responses.values():
        if not isinstance(response, dict):
            continue

        strategy = response.get("strategy")
        if strategy not in strategies:
            continue

        query = str(response.get("query", ""))
        row_id = str(response.get("row_id", ""))
        group_key = (row_id, query)
        group = grouped.setdefault(
            group_key,
            {
                "row_id": row_id,
                "query": query,
                "relevant_ids": _as_str_list(response.get("relevant_ids")),
                "retrieved": {item: [] for item in strategies},
            },
        )

        if not group["relevant_ids"]:
            group["relevant_ids"] = _as_str_list(response.get("relevant_ids"))

        retrieved_ids = _as_str_list(
            response.get("retrieved_parent_ids")
            or response.get("retrieved_ids")
            or []
        )
        if len(retrieved_ids) > len(group["retrieved"].get(strategy, [])):
            group["retrieved"][strategy] = retrieved_ids

    return list(grouped.values())


def collect_retrieval_metrics_from_cache(
    cache: dict,
    subset: str,
    k_values: list[int],
    strategies: list[str],
) -> tuple[dict, int, str]:
    cached_subset = cache.get("subset")
    if cached_subset and cached_subset != subset:
        logger.warning(
            "Cache subset is '%s' but CLI subset is '%s'; using CLI subset for labels",
            cached_subset,
            subset,
        )

    trace_records, source = _select_trace_records(cache, subset)
    relevance_lookup = None
    all_results = []

    if trace_records:
        for trace in trace_records:
            relevant_ids, relevance_lookup = _resolve_relevant_ids(
                trace, subset, relevance_lookup
            )
            retrieved = _retrieved_from_trace(trace, strategies)
            if not relevant_ids or not any(retrieved.values()):
                continue
            all_results.append(compute_query_metrics(retrieved, relevant_ids, k_values))
    else:
        for group in _response_groups(cache, strategies):
            relevant_ids, relevance_lookup = _resolve_relevant_ids(
                group, subset, relevance_lookup
            )
            retrieved = group.get("retrieved", {})
            if not relevant_ids or not any(retrieved.values()):
                continue
            all_results.append(compute_query_metrics(retrieved, relevant_ids, k_values))

    if not all_results:
        raise ValueError(
            "No retrieval data found in generation cache. Run evaluator once first."
        )

    return aggregate_metrics(all_results, k_values, strategies), len(all_results), source


def update_metrics_csv_with_retrieval(
    output_path: Path,
    subset: str,
    summary: dict,
    k_values: list[int],
    strategies: list[str],
    num_queries: int,
) -> None:
    rows = []
    existing_fields: list[str] = []

    if output_path.exists():
        with open(output_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            existing_fields = reader.fieldnames or []
            rows = list(reader)

    if not existing_fields:
        existing_fields = ["dataset", "mode", "num_queries", "strategy", "k"]

    index = {
        (row.get("strategy", ""), str(row.get("k", ""))): row
        for row in rows
        if row.get("dataset", subset) == subset
    }

    for strategy in strategies:
        for k in k_values:
            row = index.get((strategy, str(k)))
            if row is None:
                row = {
                    "dataset": subset,
                    "mode": "retrieval_postprocess",
                    "num_queries": str(num_queries),
                    "strategy": strategy,
                    "k": str(k),
                }
                rows.append(row)

            row.setdefault("dataset", subset)
            row.setdefault("mode", "generation")
            row["strategy"] = strategy
            row["k"] = str(k)
            row["retrieval_num_queries"] = str(num_queries)
            row["retrieval_recall_at_k"] = summary[strategy][k]["r"]
            row["retrieval_mrr"] = summary[strategy]["mrr"]
            row["retrieval_ndcg_at_k"] = summary[strategy][k]["ndcg"]

    retrieval_fields = [
        "retrieval_num_queries",
        "retrieval_recall_at_k",
        "retrieval_mrr",
        "retrieval_ndcg_at_k",
    ]
    preferred_fields = [
        "dataset",
        "mode",
        "num_queries",
        "strategy",
        "k",
        "semantic_precision",
        "semantic_recall",
        "semantic_f1",
        "bleu1",
        "bleu4",
        "rouge_precision",
        "rouge_recall",
        "rouge_f1",
        "bert_precision",
        "bert_recall",
        "bert_f1",
        *retrieval_fields,
    ]
    fieldnames = []
    for field in preferred_fields + existing_fields:
        if field not in fieldnames and (
            field in existing_fields or field in retrieval_fields or field in rows[0]
        ):
            fieldnames.append(field)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def postprocess_retrieval_metrics(
    subset: str,
    k_values: list[int],
    strategies: list[str],
    output_path: Optional[Path] = None,
    generation_cache_path: Optional[Path] = None,
    rerank: bool = False,
) -> None:
    output_path = ensure_csv_path(
        output_path
        or default_metrics_output_path(subset, "generation", None, rerank=rerank)
    )
    generation_cache_path = (
        generation_cache_path
        or default_generation_cache_path(subset, rerank=rerank)
    )

    if not generation_cache_path.exists():
        raise FileNotFoundError(
            f"Generation cache not found: {generation_cache_path}. Run evaluator first."
        )

    cache = load_generation_cache(generation_cache_path)
    summary, num_queries, source = collect_retrieval_metrics_from_cache(
        cache, subset, k_values, strategies
    )
    update_metrics_csv_with_retrieval(
        output_path, subset, summary, k_values, strategies, num_queries
    )
    print(
        f"Retrieval metrics updated in {output_path} "
        f"from {source} ({num_queries} queries)."
    )


def print_report(
    summary: dict,
    k_values: list[int],
    strategies: list[str],
    subset: str,
    num_queries: int,
    output_path: Optional[Path] = None,
):
    header = (
        f"Dataset: {subset} ({num_queries} queries)\n"
        + "-" * (18 + 18 * len(k_values) + 12)
    )
    print(f"\n{header}")

    col_headers = f"{'Strategy':<12}"
    for k in k_values:
        col_headers += f"{f'P@{k}':>8}{f'R@{k}':>8}{f'F1@{k}':>8}{f'nDCG@{k}':>10}"
    col_headers += f"{'MRR':>8}"
    print(col_headers)
    print("-" * len(col_headers))

    for strategy in strategies:
        row_str = f"{strategy:<12}"
        for k in k_values:
            m = summary[strategy][k]
            row_str += (
                f"{m['p']:<8.4f}{m['r']:<8.4f}"
                f"{m['f1']:<8.4f}{m['ndcg']:<10.4f}"
            )
        row_str += f"{summary[strategy]['mrr']:<8.4f}"
        print(row_str)

    print("-" * len(col_headers))

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            fieldnames = [
                "dataset",
                "mode",
                "num_queries",
                "strategy",
                "k",
                "precision",
                "recall",
                "f1",
                "ndcg",
                "mrr",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for strategy in strategies:
                for k in k_values:
                    m = summary[strategy][k]
                    writer.writerow(
                        {
                            "dataset": subset,
                            "mode": "retrieval",
                            "num_queries": num_queries,
                            "strategy": strategy,
                            "k": k,
                            "precision": m["p"],
                            "recall": m["r"],
                            "f1": m["f1"],
                            "ndcg": m["ndcg"],
                            "mrr": summary[strategy]["mrr"],
                        }
                    )
        print(f"\nMetrics CSV saved to {output_path}")


def cleanup(temp_name: str, persist: bool = True):
    if persist:
        logger.info(f"Keeping ChromaDB collection and BM25 cache for '{temp_name}'")
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


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / GENERATION_CHARS_PER_TOKEN))


def build_generation_prompt(query: str, context: str) -> str:
    return (
        "Using only the following Vietnamese context passages, answer the "
        "question in Vietnamese in 1-3 concise sentences.\n\n"
        f"Context passages:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )


def build_context_with_budget(query: str, chunks: list[str]) -> tuple[str, bool]:
    prompt_without_context = build_generation_prompt(query, "")
    available_tokens = (
        GENERATION_CONTEXT_WINDOW_TOKENS
        - GENERATION_RESERVED_TOKENS
        - estimate_tokens(prompt_without_context)
    )
    available_chars = max(0, int(available_tokens * GENERATION_CHARS_PER_TOKEN))

    selected: list[str] = []
    used_chars = 0
    truncated = False

    for chunk in chunks:
        text = str(chunk).strip()
        if not text:
            continue

        separator_chars = 2 if selected else 0
        needed_chars = separator_chars + len(text)
        if used_chars + needed_chars <= available_chars:
            selected.append(text)
            used_chars += needed_chars
            continue

        remaining_chars = available_chars - used_chars - separator_chars
        if remaining_chars > len(TRUNCATION_NOTICE):
            selected.append(
                text[: remaining_chars - len(TRUNCATION_NOTICE)].rstrip()
                + TRUNCATION_NOTICE
            )
        truncated = True
        break

    return "\n\n".join(selected), truncated


def generate_answer(query: str, chunks: list[str]) -> str:
    context, truncated = build_context_with_budget(query, chunks)
    if truncated:
        logger.info(
            "Truncated generation context to fit %s-token window "
            "(reserved=%s, chars_per_token=%s)",
            GENERATION_CONTEXT_WINDOW_TOKENS,
            GENERATION_RESERVED_TOKENS,
            GENERATION_CHARS_PER_TOKEN,
        )
    prompt = build_generation_prompt(query, context)
    return LLMClient().generate(prompt)


def aggregate_gen_metrics(
    all_results: list[dict], k_values: list[int], strategies: list[str]
) -> dict:
    metrics = [
        "sem_f1",
        "sem_p",
        "sem_r",
        "bleu1",
        "bleu4",
        "rouge_f1",
        "rouge_p",
        "rouge_r",
        "bert_f1",
        "bert_p",
        "bert_r",
    ]

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
    generation_cache_path: Optional[Path] = None,
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
        f"Dataset: {subset} ({num_queries} queries)  [GEN MODE]\n"
        + "-" * line_len
    )
    print(f"\n{header}")

    col_headers = f"{'Strategy':<12}"
    for k in k_values:
        for m in report_metrics:
            col_headers += f"{col_labels[m]}@{k}".rjust(9)
    print(col_headers)
    print("-" * len(col_headers))

    for strategy in strategies:
        row_str = f"{strategy:<12}"
        for k in k_values:
            for m in report_metrics:
                val = summary[strategy][k].get(m, 0.0)
                row_str += f"{val:<9.4f}"
        print(row_str)

    print("-" * len(col_headers))

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            fieldnames = [
                "dataset",
                "mode",
                "num_queries",
                "strategy",
                "k",
                "semantic_precision",
                "semantic_recall",
                "semantic_f1",
                "bleu1",
                "bleu4",
                "rouge_precision",
                "rouge_recall",
                "rouge_f1",
                "bert_precision",
                "bert_recall",
                "bert_f1",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for strategy in strategies:
                for k in k_values:
                    m = summary[strategy][k]
                    writer.writerow(
                        {
                            "dataset": subset,
                            "mode": "generation",
                            "num_queries": num_queries,
                            "strategy": strategy,
                            "k": k,
                            "semantic_precision": m["sem_p"],
                            "semantic_recall": m["sem_r"],
                            "semantic_f1": m["sem_f1"],
                            "bleu1": m["bleu1"],
                            "bleu4": m["bleu4"],
                            "rouge_precision": m["rouge_p"],
                            "rouge_recall": m["rouge_r"],
                            "rouge_f1": m["rouge_f1"],
                            "bert_precision": m["bert_p"],
                            "bert_recall": m["bert_r"],
                            "bert_f1": m["bert_f1"],
                        }
                    )
        print(f"\nMetrics CSV saved to {output_path}")
    if generation_cache_path:
        print(f"Generated responses cache: {generation_cache_path}")
