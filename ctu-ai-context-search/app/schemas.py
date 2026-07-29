from dataclasses import dataclass


@dataclass
class SearchRequest():
    query: str
    top_k: int = 5


@dataclass
class SearchResult():
    id: str
    document: str
    metadata: dict
    score: float


@dataclass
class SearchResultItem():
    id: str
    document: str
    metadata: dict
    score: float


@dataclass
class HybridSearchResult():
    id: str
    document: str
    metadata: dict
    semantic_score: float
    keyword_score: float
    combined_score: float


@dataclass
class HybridSearchResultItem():
    id: str
    document: str
    metadata: dict
    semantic_score: float
    keyword_score: float
    combined_score: float


@dataclass
class FAQFollowUpQuestion():
    id: str
    content: str


@dataclass
class FAQQuestion():
    id: str
    content: str
    followUp: list[FAQFollowUpQuestion]


@dataclass
class FAQPart():
    part_id: str
    chapter: str
    part: str
    score: float
    num_questions: int
    questions: list[FAQQuestion]


@dataclass
class FAQResponse():
    query: str
    parts: list[FAQPart]
