"""
Workflow State Machine: defines the full autonomous SDLC execution lifecycle.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional
from agent_core.state import AgentTaskState, SDLCStage, TaskStatus

logger = logging.getLogger(__name__)


class SDLCWorkflow:
    """State machine graph governing transitions across the SDLC stages."""

    TRANSITIONS: Dict[SDLCStage, List[SDLCStage]] = {
        SDLCStage.IDLE: [SDLCStage.REQUIREMENT_ANALYSIS, SDLCStage.FAILED],
        SDLCStage.REQUIREMENT_ANALYSIS: [SDLCStage.REPOSITORY_ANALYSIS, SDLCStage.FAILED],
        SDLCStage.REPOSITORY_ANALYSIS: [SDLCStage.PLANNING, SDLCStage.FAILED],
        SDLCStage.PLANNING: [SDLCStage.ARCHITECTURE, SDLCStage.FAILED],
        SDLCStage.ARCHITECTURE: [SDLCStage.CODE_GENERATION, SDLCStage.FAILED],
        SDLCStage.CODE_GENERATION: [SDLCStage.TEST_GENERATION, SDLCStage.FAILED],
        SDLCStage.TEST_GENERATION: [SDLCStage.TEST_EXECUTION, SDLCStage.FAILED],
        SDLCStage.TEST_EXECUTION: [SDLCStage.DEBUGGING, SDLCStage.SECURITY_VALIDATION, SDLCStage.FAILED],
        SDLCStage.DEBUGGING: [SDLCStage.TEST_EXECUTION, SDLCStage.FAILED],
        SDLCStage.SECURITY_VALIDATION: [SDLCStage.DEPLOYMENT, SDLCStage.FAILED],
        SDLCStage.DEPLOYMENT: [SDLCStage.REPORT_GENERATION, SDLCStage.FAILED],
        SDLCStage.REPORT_GENERATION: [SDLCStage.COMPLETED, SDLCStage.FAILED],
        SDLCStage.COMPLETED: [],
        SDLCStage.FAILED: [],
    }

    @classmethod
    def can_transition(cls, from_stage: SDLCStage, to_stage: SDLCStage) -> bool:
        allowed = cls.TRANSITIONS.get(from_stage, [])
        return to_stage in allowed
