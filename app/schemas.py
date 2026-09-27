"""
Data schemas for API requests, responses, and state models.
Supports Pydantic v2 when available, with standard dataclass fallback.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field

    class TaskCreateRequest(BaseModel):
        requirement: str = Field(..., description="Software engineering task or requirement description")
        workspace: Optional[str] = Field(None, description="Optional target workspace directory")
        target_file: Optional[str] = Field(None, description="Optional target implementation file")
        provider: Optional[str] = Field("mock", description="Preferred LLM provider (mock, openai, claude, gemini, openrouter)")

    class TaskResponse(BaseModel):
        task_id: str
        status: str
        current_stage: str
        requirement: str
        files_changed: List[str] = []
        tests_created: List[str] = []
        test_passed: bool = False
        security_passed: bool = False
        deployment_passed: bool = False
        error_message: Optional[str] = None
        created_at: str
        updated_at: str

    class HealthResponse(BaseModel):
        status: str
        version: str = "2.0.0"
        platform: str = "Autonomous Software Engineering Agent Platform"

except ImportError:
    # Graceful fallback without external pydantic library
    from dataclasses import dataclass, field

    @dataclass
    class TaskCreateRequest:
        requirement: str
        workspace: Optional[str] = None
        target_file: Optional[str] = None
        provider: Optional[str] = "mock"

    @dataclass
    class TaskResponse:
        task_id: str
        status: str
        current_stage: str
        requirement: str
        created_at: str
        updated_at: str
        files_changed: List[str] = field(default_factory=list)
        tests_created: List[str] = field(default_factory=list)
        test_passed: bool = False
        security_passed: bool = False
        deployment_passed: bool = False
        error_message: Optional[str] = None

    @dataclass
    class HealthResponse:
        status: str
        version: str = "2.0.0"
        platform: str = "Autonomous Software Engineering Agent Platform"
