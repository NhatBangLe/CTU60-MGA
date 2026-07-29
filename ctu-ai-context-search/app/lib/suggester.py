import json
import logging

from tqdm import tqdm

from app.config import PROJECT_ROOT
from app.utils.chroma_client import ChromaClient

logger = logging.getLogger(__name__)

BATCH_SIZE = 32


class FAQBuilder:
    def __init__(self, reset: bool = False, show_progress: bool = True):
        self.reset = reset
        self.show_progress = show_progress
        self.chroma_client = ChromaClient.get_instance()

    def build(self) -> dict:
        if self.reset and "faq" in self.chroma_client.list_collections():
            self.chroma_client.delete_collection("faq")
            logger.info("Existing 'faq' collection deleted")

        toc_questions = self.load_toc_questions()
        followup_map = self.load_followup_mapping()

        ids = list(toc_questions.keys())
        documents = list(toc_questions.values())
        metadatas = []
        for qid in ids:
            follow_up_ids = followup_map.get(qid, [])
            if follow_up_ids:
                metadatas.append({"follow_up_ids": follow_up_ids})

        n_batches = (len(documents) + BATCH_SIZE - 1) // BATCH_SIZE
        batch_iter = tqdm(
            range(0, len(documents), BATCH_SIZE),
            desc="Embedding",
            unit="batch",
            total=n_batches,
            disable=not self.show_progress,
        )
        for i in batch_iter:
            batch_docs = documents[i : i + BATCH_SIZE]
            batch_ids = ids[i : i + BATCH_SIZE]
            batch_metadatas = metadatas[i : i + BATCH_SIZE]

            self.chroma_client.add_documents(
                collection_name="faq",
                documents=batch_docs,
                ids=batch_ids,
                metadatas=batch_metadatas,
            )
            batch_iter.set_postfix_str(f"{len(batch_docs)} docs")

        logger.info("FAQ collection built with %d questions", len(documents))
        return {"collection": "faq", "questions": len(documents)}

    def load_questions(self) -> dict[str, str]:
        questions_path = PROJECT_ROOT / "data" / "questions-index.json"
        logger.info("Loading questions from %s", questions_path)

        with open(questions_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    def load_toc_questions(self) -> dict[str, str]:
        questions_path = PROJECT_ROOT / "data" / "questions-index.json"
        logger.info("Loading questions from %s", questions_path)

        with open(questions_path, "r", encoding="utf-8") as f:
            questions_index = json.load(f)

        toc_path = PROJECT_ROOT / "data" / "toc.json"
        logger.info("Loading questions from TOC %s", toc_path)

        with open(toc_path, "r", encoding="utf-8") as f:
            toc_data = json.load(f)

        toc_question_ids = set()

        def extract_question_ids(items):
            for item in items:
                if "questions" in item:
                    for q in item["questions"]:
                        toc_question_ids.add(q["id"])
                if "parts" in item:
                    extract_question_ids(item["parts"])

        extract_question_ids(toc_data)

        return {
            qid: questions_index[qid]
            for qid in toc_question_ids
            if qid in questions_index
        }

    def load_followup_mapping(self) -> dict[str, list[str]]:
        toc_path = PROJECT_ROOT / "data" / "toc.json"
        logger.info("Loading follow-up mapping from %s", toc_path)

        followup_map: dict[str, list[str]] = {}
        with open(toc_path, "r", encoding="utf-8") as f:
            toc_data = json.load(f)

        def extract_questions(items):
            for item in items:
                if "questions" in item:
                    for q in item["questions"]:
                        followup_map[q["id"]] = q.get("followUpIds", [])
                if "parts" in item:
                    extract_questions(item["parts"])

        extract_questions(toc_data)
        return followup_map
