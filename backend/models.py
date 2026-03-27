from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class Signal(BaseModel):
    id: Optional[int] = None
    source: str
    source_id: Optional[str] = None
    title: str
    body: str
    author: Optional[str] = None
    severity_score: float = 0.0
    category: Optional[str] = None
    is_escalated: bool = False
    agent_reasoning: Optional[str] = None
    created_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None


class SignalCreate(BaseModel):
    source: str
    source_id: Optional[str] = None
    title: str
    body: str
    author: Optional[str] = None


class Decision(BaseModel):
    id: Optional[int] = None
    signal_id: int
    action_taken: str  # 'escalated', 'ignored', 'queued'
    severity_score: float
    confidence: float
    reasoning: str
    created_at: Optional[datetime] = None


class Feedback(BaseModel):
    id: Optional[int] = None
    decision_id: int
    response: str  # 'good_call', 'not_important', 'create_issue', 'ignore'
    response_details: Optional[str] = None
    created_at: Optional[datetime] = None


class FeedbackCreate(BaseModel):
    response: str
    response_details: Optional[str] = None


class LearnedRule(BaseModel):
    id: Optional[int] = None
    rule: str
    confidence: float
    source_feedback_ids: Optional[List[int]] = None
    created_at: Optional[datetime] = None


class AccuracyPoint(BaseModel):
    scan_number: int
    total_decisions: int
    correct_decisions: int
    accuracy: float
    created_at: Optional[datetime] = None


class ScanResult(BaseModel):
    total_processed: int
    escalated: int
    ignored: int
    queued: int
    decisions: List[dict]
