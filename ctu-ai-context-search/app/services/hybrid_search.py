"""Hybrid search combining BM25 keyword search with ChromaDB semantic search."""

import re
import json
import logging

from app.config import config
from app.schemas import HybridSearchResult
from app.services.keyword_search import KeywordSearch
from app.services.semantic_search import SemanticSearch
from app.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

RRF_K = 60


class HybridSearch:
    """Hybrid search combining BM25 keyword and ChromaDB semantic search.

    Uses Min-Max normalization followed by Reciprocal Rank Fusion (RRF)
    to combine results from both search methods.
    """

    @classmethod
    def get_instance(cls) -> "HybridSearch":
        """Get singleton instance of HybridSearch."""
        if not hasattr(cls, "_instance") or cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_semantic(self) -> SemanticSearch:
        """Get semantic search lazily."""
        return SemanticSearch.get_instance()

    def get_keyword(self) -> KeywordSearch:
        """Get keyword search lazily."""
        return KeywordSearch.get_instance()

    def get_llm(self) -> LLMClient:
        """Get LLM client lazily."""
        return LLMClient()

    def rerank_with_llm(
        self,
        query: str,
        results: list["HybridSearchResult"],
    ) -> list["HybridSearchResult"]:
        """Rerank results using LLM judgment.

        Args:
            query: Original search query.
            results: List of hybrid search results to rerank.

        Returns:
            Reranked list of HybridSearchResult.
        """
        if len(results) <= 1:
            return results

        llm = self.get_llm()

        docs_text = "\n\n".join(
            f"[{i}] {r.document[:500]}" for i, r in enumerate(results)
        )

        prompt = f"""Given the search query: "{query}"

Rank the following documents by relevance to this query. Consider both semantic meaning and keyword matching. Return the document indices in order of relevance, most relevant first.

Documents:
{docs_text}

Return ONLY a JSON array of indices (e.g., [2, 0, 1, 3]), ordered from most relevant to least relevant. Include all indices."""

        try:
            response = llm.generate(prompt)

            match = re.search(r"\[.*\]", response)
            if match:
                rankings = json.loads(match.group())
                if isinstance(rankings, list) and all(
                    isinstance(i, int) for i in rankings
                ):
                    reranked = [results[i] for i in rankings if 0 <= i < len(results)]
                    missing = [r for r in results if r not in reranked]
                    return reranked + missing
        except Exception as e:
            logger.warning(f"LLM reranking failed: {e}")

        return results

    def search(
        self,
        query: str,
        collection_name: str,
        top_k: int = 5,
    ) -> list[HybridSearchResult]:
        """Search using hybrid BM25 + ChromaDB fusion.

        Args:
            query: Search query text.
            collection_name: Name of the collection to search.
            top_k: Number of results to return.

        Returns:
            List of HybridSearchResult sorted by combined score.
        """
        semantic_results = self.get_semantic().search(
            query=query,
            collection_name=collection_name,
            top_k=top_k * config.HYBRID_SEARCH_MULTIPLIER,
        )
        keyword_results = self.get_keyword().search(
            query=query,
            collection_name=collection_name,
            top_k=top_k * config.HYBRID_SEARCH_MULTIPLIER,
        )

        if not semantic_results and not keyword_results:
            return []

        semantic_ids = [r.id for r in semantic_results]
        keyword_ids = [r.id for r in keyword_results]

        normalized_semantic = min_max_normalize({r.id: r.score for r in semantic_results})
        normalized_keyword = min_max_normalize({r.id: r.score for r in keyword_results})

        rrf_scores = reciprocal_rank_fusion([semantic_ids, keyword_ids])

        doc_lookup: dict[str, tuple[str, dict]] = {}
        for r in semantic_results:
            doc_lookup[r.id] = (r.document, r.metadata)
        for r in keyword_results:
            if r.id not in doc_lookup:
                doc_lookup[r.id] = (r.document, r.metadata)

        hybrid_results = []
        for doc_id, combined_score in rrf_scores.items():
            document, metadata = doc_lookup.get(doc_id, ("", {}))
            sem_score = normalized_semantic.get(doc_id, 0.0)
            kw_score = normalized_keyword.get(doc_id, 0.0)

            hybrid_results.append(
                HybridSearchResult(
                    id=doc_id,
                    document=document,
                    metadata=metadata,
                    semantic_score=sem_score,
                    keyword_score=kw_score,
                    combined_score=combined_score,
                )
            )

        hybrid_results.sort(key=lambda x: x.combined_score, reverse=True)
        logger.debug(f"Hybrid search returned {len(hybrid_results)} results")

        if not config.LLM_RERANK_ENABLED:
            return hybrid_results[:top_k]

        candidate_results = hybrid_results[: top_k * config.LLM_RERANK_MULTIPLIER]
        reranked = self.rerank_with_llm(query, candidate_results)
        return reranked[:top_k]


def min_max_normalize(scores: dict[str, float]) -> dict[str, float]:
    """Normalize scores to [0, 1] range using min-max normalization.

    Args:
        scores: Dict mapping doc_id to score.

    Returns:
        Dict mapping doc_id to normalized score.
    """
    if not scores:
        return {}

    values = list(scores.values())
    min_val = min(values)
    max_val = max(values)

    if max_val == min_val:
        return {doc_id: 1.0 for doc_id in scores}

    return {
        doc_id: (val - min_val) / (max_val - min_val) for doc_id, val in scores.items()
    }


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    k: int = RRF_K,
) -> dict[str, float]:
    """Combine multiple result lists using Reciprocal Rank Fusion.

    RRF formula: score(d) = sum_i(1 / (k + rank_i(d)))

    Args:
        ranked_lists: List of ranked doc ID lists (one per search method),
                      ordered from most to least relevant.
        k: RRF constant (default 60).

    Returns:
        Dict mapping doc_id to combined RRF score.
    """
    rrf_scores: dict[str, float] = {}

    for ranked_list in ranked_lists:
        for rank, doc_id in enumerate(ranked_list, 1):
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0.0
            rrf_scores[doc_id] += 1.0 / (k + rank)

    return rrf_scores
