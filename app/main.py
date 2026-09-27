"""
FastAPI application service for the Autonomous Software Engineering Agent Platform.
Provides REST API endpoints for task submission, lifecycle monitoring, and health checks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from agent_core.orchestrator import AgentOrchestrator
from agent_core.state import AgentTaskState
from llm.router import LLMRouter

# Check for FastAPI availability
try:
    from fastapi import FastAPI, BackgroundTasks, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from app.schemas import HealthResponse, TaskCreateRequest, TaskResponse

    app = FastAPI(
        title="Autonomous Software Engineering Agent Platform",
        version="2.0.0",
        description="Autonomous SDLC API managing planning, architecture, coding, testing, debugging, and deployment.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize shared orchestrator
    workspace = os.getenv("WORKSPACE_PATH", os.getcwd())
    router = LLMRouter(primary_name=os.getenv("PRIMARY_LLM", "mock"))
    orchestrator = AgentOrchestrator(workspace=workspace, router=router)

    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        return HealthResponse(status="HEALTHY")

    @app.post("/api/tasks", response_model=TaskResponse)
    async def create_task(req: TaskCreateRequest, background_tasks: BackgroundTasks):
        task_ws = req.workspace or workspace
        # Run orchestrator task in background
        task_id = str(len(orchestrator.tasks) + 1)
        background_tasks.add_task(
            orchestrator.execute_task,
            requirement=req.requirement,
            task_id=task_id,
            target_file=req.target_file,
        )
        return TaskResponse(
            task_id=task_id,
            status="pending",
            current_stage="idle",
            requirement=req.requirement,
            created_at="",
            updated_at="",
        )

    @app.get("/api/tasks/{task_id}", response_model=TaskResponse)
    async def get_task(task_id: str):
        state = orchestrator.tasks.get(task_id)
        if not state:
            raise HTTPException(status_code=404, detail="Task not found")
        return TaskResponse(
            task_id=state.task_id,
            status=state.status.value,
            current_stage=state.current_stage.value,
            requirement=state.requirement,
            files_changed=state.files_changed,
            tests_created=state.tests_created,
            test_passed=state.test_passed,
            security_passed=state.security_passed,
            deployment_passed=state.deployment_passed,
            error_message=state.error_message,
            created_at=state.created_at,
            updated_at=state.updated_at,
        )

except ImportError:
    # If fastapi is not installed in the current environment, provide a standalone lightweight server
    app = None


def run_standalone_server(host: str = "0.0.0.0", port: int = 8000):
    """Run server via uvicorn if available, or print instructions."""
    try:
        import uvicorn
        if app:
            uvicorn.run(app, host=host, port=port)
            return
    except ImportError:
        pass
    print(f"FastAPI / Uvicorn server requires 'fastapi' and 'uvicorn'. Run: pip install -r requirements.txt")
