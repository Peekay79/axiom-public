import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field  # pydantic v2 upgrade


class Goal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str = Field(..., description="Natural language goal statement")

    # Status and estimation
    status: str = Field(
        default="active", description="One of: active, complete, abandoned, stalled"
    )
    progress: float = Field(
        default=0.0, ge=0.0, le=1.0, description="LLM-estimated completion"
    )
    confidence: float = Field(
        default=0.75, ge=0.0, le=1.0, description="Likelihood of achieving this goal"
    )
    alignment_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Optional: value alignment score"
    )

    # Metadata
    importance: int = Field(
        default=5, ge=1, le=10, description="Priority score: 1 (low) to 10 (critical)"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Domain or context tags (e.g. 'ethics', 'user')",
    )
    notes: Optional[str] = Field(
        default=None, description="Background rationale, user intent, etc."
    )

    # Goal relationships
    source: str = Field(
        default="system", description="Origin: system, user, reflection, imported"
    )
    parent_goal: Optional[str] = Field(
        default=None, description="If this is a subgoal, ID of its parent"
    )
    subgoals: List[str] = Field(
        default_factory=list, description="IDs of decomposed subgoals"
    )

    # Temporal anchors
    created_at: datetime = Field(default_factory=datetime.utcnow)
    due: Optional[datetime] = Field(default=None, description="Optional deadline")
    last_reviewed: Optional[datetime] = Field(
        default=None, description="When last surfaced for review"
    )

    # Task support (optional scaffolding for future)
    actionable_tasks: List[str] = Field(
        default_factory=list, description="LLM-suggested subtasks or planning actions"
    )

    # pydantic v2 upgrade: Added model_config for better validation and serialization
    model_config = {
        "json_schema_extra": {
            "example": {
                "description": "Implement secure AI alignment protocols",
                "status": "active",
                "progress": 0.3,
                "confidence": 0.85,
                "importance": 8,
                "tags": ["safety", "alignment", "technical"],
                "source": "user",
                "notes": "Critical for ensuring safe AI development",
            }
        }
    }
