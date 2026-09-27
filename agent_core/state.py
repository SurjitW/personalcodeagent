"""
Task state management and SDLC lifecycle models.
"""

from __future__ import annotations

import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class SDLCStage(str, Enum):
    IDLE = "idle"
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    REPOSITORY_ANALYSIS = "repository_analysis"
    PLANNING = "planning"
    ARCHITECTURE = "architecture"
    CODE_GENERATION = "code_generation"
    TEST_GENERATION = "test_generation"
    TEST_EXECUTION = "test_execution"
    DEBUGGING = "debugging"
    SECURITY_VALIDATION = "security_validation"
    DEPLOYMENT = "deployment"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class ExecutionStep:
    stage: SDLCStage
    timestamp: str
    status: str  # "started", "completed", "failed", "retrying"
    details: str
    artifacts_created: List[str] = field(default_factory=list)


@dataclass
class AgentTaskState:
    task_id: str
    requirement: str
    workspace: str
    status: TaskStatus = TaskStatus.PENDING
    current_stage: SDLCStage = SDLCStage.IDLE
    steps: List[ExecutionStep] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    tests_created: List[str] = field(default_factory=list)
    debug_iterations: int = 0
    max_debug_iterations: int = 5
    test_passed: bool = False
    security_passed: bool = False
    deployment_passed: bool = False
    error_message: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def transition(self, stage: SDLCStage, details: str, status: str = "started") -> ExecutionStep:
        self.current_stage = stage
        self.updated_at = datetime.datetime.now().isoformat()
        step = ExecutionStep(
            stage=stage,
            timestamp=self.updated_at,
            status=status,
            details=details,
        )
        self.steps.append(step)
        return step
