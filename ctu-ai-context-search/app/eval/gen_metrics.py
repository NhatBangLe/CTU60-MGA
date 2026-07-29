import logging
from typing import Optional

import numpy as np
from underthesea import sent_tokenize

from app.utils.embeddings import EmbeddingModel

logger = logging.getLogger(__name__)

_bert_scorer: Optional[object] = None


def _get_bert_scorer():
    global _bert_scorer
    if _bert_scorer is None:
        from bert_score import BERTScorer

        _bert_scorer = BERTScorer(
            model_type="distilbert-base-multilingual-cased",
            lang="vi",
            device="cuda:0",
            batch_size=1,
            nthreads=4,
            rescale_with_baseline=False,
        )
        logger.info("BERTScorer initialized (distilbert-base-multilingual-cased)")
    return _bert_scorer


def sentence_embedding_f1(generated: str, reference: str, model: EmbeddingModel) -> dict:
    gen_sents = [s.strip() for s in sent_tokenize(generated) if s.strip()]
    ref_sents = [s.strip() for s in sent_tokenize(reference) if s.strip()]

    if not gen_sents or not ref_sents:
        return {"p": 0.0, "r": 0.0, "f1": 0.0}

    all_vecs = model.embed_documents(gen_sents + ref_sents)
    gen_vecs = np.array(all_vecs[: len(gen_sents)])
    ref_vecs = np.array(all_vecs[len(gen_sents) :])

    sim = np.dot(gen_vecs, ref_vecs.T)

    p = float(np.mean(np.max(sim, axis=1)))
    r = float(np.mean(np.max(sim, axis=0)))
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    return {"p": round(p, 4), "r": round(r, 4), "f1": round(f1, 4)}


def bleu_score(generated: str, reference: str) -> dict:
    from sacrebleu import sentence_bleu

    result = sentence_bleu(generated, [reference])
    return {
        "bleu1": round(result.precisions[0] / 100, 4),
        "bleu2": round(result.precisions[1] / 100, 4),
        "bleu3": round(result.precisions[2] / 100, 4),
        "bleu4": round(result.score / 100, 4),
    }


def rouge_l_f1(generated: str, reference: str) -> dict:
    from rouge_score import rouge_scorer

    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)
    scores = scorer.score(reference, generated)
    return {
        "p": round(scores["rougeL"].precision, 4),
        "r": round(scores["rougeL"].recall, 4),
        "f1": round(scores["rougeL"].fmeasure, 4),
    }


def bertscore_f1(generated: str, reference: str) -> dict:
    scorer = _get_bert_scorer()
    P, R, F1 = scorer.score([generated], [reference])
    return {
        "p": round(P.item(), 4),
        "r": round(R.item(), 4),
        "f1": round(F1.item(), 4),
    }
