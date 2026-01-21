"""
Settings Router
===============

Server-side "advanced settings" used by the Web UI to configure spawned agent/orchestrator env vars.
"""

from __future__ import annotations

from typing import Literal
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError, model_validator

from ..settings_store import AdvancedSettings, load_advanced_settings, save_advanced_settings


router = APIRouter(prefix="/api/settings", tags=["settings"])

ReviewMode = Literal["off", "advisory", "gate"]
ReviewType = Literal["none", "command", "claude", "multi_cli"]
WorkerProvider = Literal["claude", "codex_cli", "gemini_cli", "multi_cli"]
PlannerSynthesizer = Literal["none", "claude", "codex", "gemini"]
CodexReasoningEffort = Literal["low", "medium", "high", "xlow", "xmedium", "xhigh"]
ReviewConsensus = Literal["any", "majority", "all"]
InitializerProvider = Literal["claude", "codex_cli", "gemini_cli", "multi_cli"]
InitializerSynthesizer = Literal["none", "claude", "codex", "gemini"]


class AdvancedSettingsModel(BaseModel):
    # Review (optional)
    review_enabled: bool = False
    review_mode: ReviewMode = Field(default="off")
    review_type: ReviewType = Field(default="none")
    review_command: str = Field(default="", max_length=2000)
    review_timeout_s: int = Field(default=0, ge=0, le=3600)
    review_model: str = Field(default="", max_length=128)
    review_agents: str = Field(default="", max_length=256)
    # Blank means "use default" for the configured reviewer type.
    review_consensus: str = Field(default="", max_length=64)
    codex_model: str = Field(default="", max_length=128)
    codex_reasoning_effort: str = Field(default="", max_length=64)  # low|medium|high|xhigh
    gemini_model: str = Field(default="", max_length=128)

    locks_enabled: bool = True
    worker_verify: bool = True
    worker_provider: WorkerProvider = Field(default="claude")
    worker_patch_max_iterations: int = Field(default=2, ge=1, le=20)
    worker_patch_agents: str = Field(default="codex,gemini", max_length=256)

    qa_fix_enabled: bool = False
    qa_model: str = Field(default="", max_length=128)
    qa_max_sessions: int = Field(default=0, ge=0, le=50)
    qa_subagent_enabled: bool = True
    qa_subagent_max_iterations: int = Field(default=2, ge=1, le=20)
    qa_subagent_provider: WorkerProvider = Field(default="claude")
    qa_subagent_agents: str = Field(default="codex,gemini", max_length=256)

    controller_enabled: bool = False
    controller_model: str = Field(default="", max_length=128)
    controller_max_sessions: int = Field(default=0, ge=0, le=50)

    regression_pool_enabled: bool = False
    regression_pool_max_agents: int = Field(default=1, ge=0, le=10)
    regression_pool_model: str = Field(default="", max_length=128)
    regression_pool_min_interval_s: int = Field(default=600, ge=30, le=86400)
    regression_pool_max_iterations: int = Field(default=1, ge=1, le=5)

    planner_enabled: bool = False
    planner_model: str = Field(default="", max_length=128)
    planner_agents: str = Field(default="codex,gemini", max_length=256)
    planner_synthesizer: PlannerSynthesizer = Field(default="claude")
    planner_timeout_s: int = Field(default=180, ge=30, le=3600)

    initializer_provider: InitializerProvider = Field(default="claude")
    initializer_agents: str = Field(default="codex,gemini", max_length=256)
    initializer_synthesizer: InitializerSynthesizer = Field(default="claude")
    initializer_timeout_s: int = Field(default=300, ge=30, le=3600)
    initializer_stage_threshold: int = Field(default=120, ge=0, le=100000)
    initializer_enqueue_count: int = Field(default=30, ge=0, le=100000)

    logs_keep_days: int = Field(default=7, ge=0, le=3650)
    logs_keep_files: int = Field(default=200, ge=0, le=100000)
    logs_max_total_mb: int = Field(default=200, ge=0, le=100000)
    logs_prune_artifacts: bool = False
    activity_keep_days: int = Field(default=14, ge=0, le=3650)
    activity_keep_rows: int = Field(default=5000, ge=0, le=200000)

    diagnostics_fixtures_dir: str = Field(default="", max_length=2000)
    ui_host: str = Field(default="", max_length=255)
    ui_allow_remote: bool = False
    agent_color_running: str = Field(default="#00b4d8", max_length=16)
    agent_color_done: str = Field(default="#70e000", max_length=16)
    agent_color_retry: str = Field(default="#f59e0b", max_length=16)

    sdk_max_attempts: int = Field(default=3, ge=1, le=20)
    sdk_initial_delay_s: int = Field(default=1, ge=0, le=600)
    sdk_rate_limit_initial_delay_s: int = Field(default=30, ge=0, le=3600)
    sdk_max_delay_s: int = Field(default=60, ge=0, le=3600)
    sdk_exponential_base: int = Field(default=2, ge=1, le=10)
    sdk_jitter: bool = True

    require_gatekeeper: bool = True
    allow_no_tests: bool = False
    stop_when_done: bool = True

    api_port_range_start: int = Field(default=5000, ge=1024, le=65535)
    api_port_range_end: int = Field(default=5100, ge=1024, le=65536)
    web_port_range_start: int = Field(default=5173, ge=1024, le=65535)
    web_port_range_end: int = Field(default=5273, ge=1024, le=65536)
    skip_port_check: bool = False

    @model_validator(mode="after")
    def _validate_conditionals(self):
        def _normalize_agents_csv(field_label: str, raw: str) -> str:
            if not raw or not raw.strip():
                return ""
            parts = [p.strip().lower() for p in raw.replace(";", ",").split(",") if p.strip()]
            allowed = {"codex", "gemini"}
            unknown = [p for p in parts if p not in allowed]
            if unknown:
                raise ValueError(f"{field_label} must be a csv of codex,gemini (unknown: {', '.join(unknown)})")
            seen: set[str] = set()
            out: list[str] = []
            for p in parts:
                if p in allowed and p not in seen:
                    seen.add(p)
                    out.append(p)
            return ",".join(out)

        # Review conditionals
        if self.review_enabled:
            if self.review_mode == "off":
                raise ValueError("review_mode must be advisory|gate when review_enabled=true")
            if self.review_type == "none":
                raise ValueError("review_type must be set when review_enabled=true")
            if self.review_type == "command" and not (self.review_command or "").strip():
                raise ValueError("review_command is required when review_type=command")
            if self.review_type == "multi_cli":
                if not (self.review_agents or "").strip():
                    raise ValueError("review_agents is required when review_type=multi_cli")
                self.review_agents = _normalize_agents_csv("review_agents", self.review_agents)
                if self.review_consensus and self.review_consensus not in ("any", "majority", "all"):
                    raise ValueError("review_consensus must be any|majority|all (or blank)")

        if self.codex_reasoning_effort and self.codex_reasoning_effort not in ("low", "medium", "high", "xlow", "xmedium", "xhigh"):
            raise ValueError("codex_reasoning_effort must be low|medium|high|xlow|xmedium|xhigh (or blank)")

        # Worker conditionals
        if self.worker_provider == "multi_cli" and not (self.worker_patch_agents or "").strip():
            raise ValueError("worker_patch_agents is required when worker_provider=multi_cli")
        if self.worker_provider == "multi_cli":
            self.worker_patch_agents = _normalize_agents_csv("worker_patch_agents", self.worker_patch_agents)

        # QA sub-agent conditionals
        if self.qa_subagent_enabled:
            if self.qa_subagent_provider == "multi_cli" and not (self.qa_subagent_agents or "").strip():
                raise ValueError("qa_subagent_agents is required when qa_subagent_provider=multi_cli")
        if self.qa_subagent_provider == "multi_cli":
            self.qa_subagent_agents = _normalize_agents_csv("qa_subagent_agents", self.qa_subagent_agents)

        # Planner conditionals
        if self.planner_enabled and not (self.planner_agents or "").strip():
            raise ValueError("planner_agents is required when planner_enabled=true")
        if self.planner_agents:
            self.planner_agents = _normalize_agents_csv("planner_agents", self.planner_agents)

        if self.regression_pool_enabled and self.regression_pool_max_agents <= 0:
            raise ValueError("regression_pool_max_agents must be > 0 when regression_pool_enabled=true")

        # Initializer conditionals
        if self.initializer_provider == "multi_cli" and not (self.initializer_agents or "").strip():
            raise ValueError("initializer_agents is required when initializer_provider=multi_cli")
        if self.initializer_provider == "multi_cli":
            self.initializer_agents = _normalize_agents_csv("initializer_agents", self.initializer_agents)

        if self.initializer_enqueue_count < 0:
            raise ValueError("initializer_enqueue_count must be >= 0")

        color_fields = {
            "agent_color_running": "agent_color_running",
            "agent_color_done": "agent_color_done",
            "agent_color_retry": "agent_color_retry",
        }
        for field_name, label in color_fields.items():
            value = getattr(self, field_name, "")
            if not value:
                continue
            if not value.startswith("#"):
                value = f"#{value}"
                setattr(self, field_name, value)
            if not re.match(r"^#[0-9a-fA-F]{6}$", value):
                raise ValueError(f"{label} must be a 6-digit hex color (e.g. #00b4d8)")

        return self

    def to_settings(self) -> AdvancedSettings:
        return AdvancedSettings(**self.model_dump())


@router.get("/advanced", response_model=AdvancedSettingsModel)
async def get_advanced_settings():
    settings = load_advanced_settings()
    try:
        return AdvancedSettingsModel(**settings.__dict__)
    except ValidationError:
        # If legacy/migrated settings are invalid, avoid breaking the UI.
        return AdvancedSettingsModel()


@router.put("/advanced", response_model=AdvancedSettingsModel)
async def update_advanced_settings(req: AdvancedSettingsModel):
    # Basic sanity: end must exceed start.
    if req.api_port_range_end <= req.api_port_range_start:
        raise HTTPException(status_code=400, detail="api_port_range_end must be greater than api_port_range_start")
    if req.web_port_range_end <= req.web_port_range_start:
        raise HTTPException(status_code=400, detail="web_port_range_end must be greater than web_port_range_start")

    settings = req.to_settings()
    save_advanced_settings(settings)
    return req
