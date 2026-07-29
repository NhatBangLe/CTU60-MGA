"""FastAPI entry point for CTU AI Context Search API."""

import json
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import PROJECT_ROOT, config
from app.schemas import HybridSearchResultItem, SearchRequest, FAQResponse
from app.services.hybrid_search import HybridSearch
from app.utils.bm25_indexer import BM25Indexer
from app.utils.chroma_client import ChromaClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting CTU AI Context Search API...")
    config.BM25_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    bm25_indexer = BM25Indexer.get_instance()
    chroma_client = ChromaClient.get_instance()
    collections = chroma_client.list_collections()
    for coll in collections:
        if coll in config.BM25_SKIP_COLLECTIONS:
            logger.info(f"Skipping BM25 index for collection '{coll}' (excluded)")
            continue
        loaded = bm25_indexer.load_index(coll)
        if loaded:
            logger.info(f"Loaded/rebuilt BM25 index for collection '{coll}'")
        else:
            logger.info(f"No BM25 index available for collection '{coll}'")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="CTU AI Context Search API",
    description="Hybrid semantic search using ChromaDB and BM25 with Vietnamese language support",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chroma_client = ChromaClient.get_instance()
hybrid_search = HybridSearch.get_instance()
bm25_indexer = BM25Indexer.get_instance()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    collections = chroma_client.list_collections()
    return {
        "status": "healthy",
        "collections": collections,
        "available_collections": ["book", "web", "news"],
    }


@app.post("/search/book")
async def search_book(request: SearchRequest):
    """Search the book collection.

    The book collection contains historical documents about the university.
    """
    results = hybrid_search.search(
        query=request.query,
        collection_name="book",
        top_k=request.top_k,
    )
    return {
        "query": request.query,
        "mode": "hybrid",
        "collection": "book",
        "results": [
            HybridSearchResultItem(
                id=r.id,
                document=r.document,
                metadata=r.metadata,
                semantic_score=r.semantic_score,
                keyword_score=r.keyword_score,
                combined_score=r.combined_score,
            )
            for r in results
        ],
    }


@app.post("/search/web")
async def search_web(request: SearchRequest):
    """Search the web collection.

    The web collection contains administrative structure documents.
    """
    results = hybrid_search.search(
        query=request.query,
        collection_name="web",
        top_k=request.top_k,
    )
    return {
        "query": request.query,
        "mode": "hybrid",
        "collection": "web",
        "results": [
            HybridSearchResultItem(
                id=r.id,
                document=r.document,
                metadata=r.metadata,
                semantic_score=r.semantic_score,
                keyword_score=r.keyword_score,
                combined_score=r.combined_score,
            )
            for r in results
        ],
    }


@app.post("/search/news")
async def search_news(request: SearchRequest):
    """Search the news collection.

    The news collection contains news articles organized by year.
    """
    results = hybrid_search.search(
        query=request.query,
        collection_name="news",
        top_k=request.top_k,
    )
    return {
        "query": request.query,
        "mode": "hybrid",
        "collection": "news",
        "results": [
            HybridSearchResultItem(
                id=r.id,
                document=r.document,
                metadata=r.metadata,
                semantic_score=r.semantic_score,
                keyword_score=r.keyword_score,
                combined_score=r.combined_score,
            )
            for r in results
        ],
    }


@app.post("/search/faq")
async def search_faq(request: SearchRequest):
    """Search the FAQ collection for similar question suggestions.

    Returns questions grouped by part with their follow-ups fully populated.
    """
    questions_index_path = PROJECT_ROOT / "data" / "questions-index.json"
    with open(questions_index_path, "r", encoding="utf-8") as f:
        questions_index = json.load(f)

    toc_path = PROJECT_ROOT / "data" / "toc.json"
    with open(toc_path, "r", encoding="utf-8") as f:
        toc_data = json.load(f)

    results = chroma_client.query(
        collection_name="faq",
        query_text=request.query,
        top_k=request.top_k,
    )

    if not results["documents"] or not results["documents"][0]:
        return FAQResponse(query=request.query, parts=[])

    def build_toc_map(items, chapter="", part_id="", part_name=""):
        for item in items:
            if "chapter" in item:
                chapter = item["chapter"]
            if "part" in item and "id" in item:
                part_id = item["id"]
                part_name = item["part"]
            if "questions" in item:
                for q in item["questions"]:
                    qid = q["id"]
                    follow_ups = q.get("followUpIds", [])
                    yield {
                        "qid": qid,
                        "chapter": chapter,
                        "part_id": part_id,
                        "part": part_name,
                        "follow_ups": follow_ups,
                    }
            if "parts" in item:
                yield from build_toc_map(item["parts"], chapter, part_id, part_name)

    toc_map = {item["qid"]: item for item in build_toc_map(toc_data)}

    part_scores: dict[str, dict] = {}
    part_questions: dict[str, list] = {}

    for i, doc in enumerate(results["documents"][0]):
        question_id = results["ids"][0][i]
        distance = results["distances"][0][i] if results.get("distances") else 0.0
        score = 1.0 - distance if distance else 0.0

        if question_id not in toc_map:
            continue

        toc_entry = toc_map[question_id]
        part_id = toc_entry["part_id"]

        if part_id not in part_scores:
            part_scores[part_id] = 0.0
            part_questions[part_id] = []

        part_scores[part_id] += score

        follow_up_list = []
        for fid in toc_entry.get("follow_ups", []):
            follow_up_list.append({"id": fid, "content": questions_index.get(fid, "")})

        part_questions[part_id].append(
            {
                "id": question_id,
                "content": doc,
                "followUp": follow_up_list,
            }
        )

    parts = []
    for part_id, questions in part_questions.items():
        if not questions:
            continue
        toc_entry = toc_map[questions[0]["id"]]
        parts.append(
            {
                "part_id": part_id,
                "chapter": toc_entry["chapter"],
                "part": toc_entry["part"],
                "score": part_scores[part_id],
                "num_questions": len(questions),
                "questions": questions,
            }
        )

    parts.sort(key=lambda x: x["score"], reverse=True)

    return FAQResponse(query=request.query, parts=parts)


@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <html>
        <head>
            <title>CTU Context Search</title>
            <style>
                body { font-family: Arial; padding: 32px; background: #fafafa; }
                .box { 
                    max-width: 600px; margin: auto; padding: 24px; 
                    background: white; border-radius: 16px; 
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                }
                h1 { color: #4B7BEC; }
                p { color: #555; font-size: 16px; }
                a { color: #20bf6b; font-weight: bold; text-decoration: none; }
            </style>
        </head>
        <body>
            <div class="box">
                <h1>CTU Context Search API</h1>
                <p>Your backend is running successfully </p>

                <p>Explore API docs:</p>
                <ul>
                    <li><a href="/docs">Swagger UI</a></li>
                    <li><a href="/redoc">ReDoc UI</a></li>
                </ul>

                <p>Current status: <b style="color:green;">ONLINE</b></p>
            </div>
        </body>
    </html>
    """


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
