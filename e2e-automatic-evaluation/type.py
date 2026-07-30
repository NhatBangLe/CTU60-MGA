from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RouteType(str, Enum):
    TEXT_ONLY = "TEXT_ONLY"
    TEXT_TO_IMAGE = "TEXT_TO_IMAGE"
    TEXT_TO_VIDEO = "TEXT_TO_VIDEO"
    IMAGE_TO_IMAGE = "IMAGE_TO_IMAGE"
    IMAGE_TO_VIDEO = "IMAGE_TO_VIDEO"


class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class TestMetadata(BaseModel):
    difficulty: DifficultyLevel
    language: Optional[str] = Field(default="vi", description="Language code")
    tags: List[str] = Field(
        default_factory=list, description="List of classification tags"
    )


class TestInput(BaseModel):
    query: str = Field(..., description="User query or request")
    context: Optional[str] = Field(
        default=None, description="Conversation history or RAG context"
    )
    has_input_image: bool = Field(..., description="Whether an input image is attached")


class TestExpectedOutput(BaseModel):
    expected_route: RouteType
    expected_answer: Optional[str] = Field(
        default=None, description="Expected answer if route is TEXT_ONLY"
    )


class TestCase(BaseModel):
    """Complete record structure for a single dataset entry."""

    id: str = Field(..., description="Unique test case ID (e.g., 'route_test_001')")
    metadata: TestMetadata
    input: TestInput
    output: TestExpectedOutput
