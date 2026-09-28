from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON, Index, func
from database import Base
from models.repository_index import (
    RepositoryIndex, FileInfo, Symbol, Dependency, ArchitectureSummary,
    PullRequestAnalysis, PRReviewResponse, AuditReport
)


class RepositoryRecord(Base):
    """PostgreSQL entity for persisting repository metadata, AST graphs, and index structure."""
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), unique=True, nullable=False, index=True)
    repo_name = Column(String(255), nullable=False, index=True)
    repo_path = Column(Text, nullable=False)
    total_files = Column(Integer, default=0)
    total_lines = Column(Integer, default=0)
    languages = Column(JSON, default=dict)
    entry_points = Column(JSON, default=list)
    module_counts = Column(JSON, default=dict)
    circular_cycles = Column(JSON, default=list)
    architecture_summary = Column(JSON, nullable=True)
    files_data = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    __table_args__ = (
        Index("ix_repositories_session_updated", "session_id", "updated_at"),
    )

    def to_repository_index(self) -> RepositoryIndex:
        """Converts database record back into a strongly-typed Pydantic RepositoryIndex model."""
        files: List[FileInfo] = []
        for raw_f in (self.files_data or []):
            try:
                symbols = [Symbol(**s) if isinstance(s, dict) else s for s in raw_f.get("symbols", [])]
                dependencies = [Dependency(**d) if isinstance(d, dict) else d for d in raw_f.get("dependencies", [])]
                raw_copy = dict(raw_f)
                raw_copy["symbols"] = symbols
                raw_copy["dependencies"] = dependencies
                files.append(FileInfo(**raw_copy))
            except Exception:
                pass

        arch_summary = None
        if self.architecture_summary and isinstance(self.architecture_summary, dict):
            try:
                arch_summary = ArchitectureSummary(**self.architecture_summary)
            except Exception:
                pass

        return RepositoryIndex(
            repo_name=self.repo_name,
            repo_path=self.repo_path,
            total_files=self.total_files,
            total_lines=self.total_lines,
            languages_breakdown=self.languages or {},
            entry_points=self.entry_points or [],
            module_counts=self.module_counts or {},
            circular_cycles=self.circular_cycles or [],
            architecture_summary=arch_summary,
            files=files
        )

    @classmethod
    def from_repository_index(cls, session_id: str, repo_index: RepositoryIndex) -> "RepositoryRecord":
        """Instantiates a RepositoryRecord from a RepositoryIndex Pydantic instance."""
        files_json = [f.model_dump() for f in repo_index.files]
        arch_json = repo_index.architecture_summary.model_dump() if repo_index.architecture_summary else None

        return cls(
            session_id=session_id,
            repo_name=repo_index.repo_name,
            repo_path=repo_index.repo_path,
            total_files=repo_index.total_files,
            total_lines=repo_index.total_lines,
            languages=repo_index.languages_breakdown,
            entry_points=repo_index.entry_points,
            module_counts=repo_index.module_counts,
            circular_cycles=repo_index.circular_cycles,
            architecture_summary=arch_json,
            files_data=files_json
        )


class ConversationTurnRecord(Base):
    """PostgreSQL entity storing chat turns and source attributions for persistent multi-turn reasoning."""
    __tablename__ = "conversation_turns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), nullable=False, index=True)
    role = Column(String(32), nullable=False, index=True)  # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    attributions = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_turns_session_created", "session_id", "created_at"),
    )


class PRReviewRecord(Base):
    """PostgreSQL entity storing pull request analyses and reviews."""
    __tablename__ = "pr_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), nullable=False, index=True)
    title = Column(String(500), nullable=True)
    verdict = Column(String(32), default="COMMENT", index=True)
    executive_summary = Column(Text, nullable=True)
    developer_summary = Column(Text, nullable=True)
    risks_count = Column(Integer, default=0)
    full_analysis = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AuditReportRecord(Base):
    """PostgreSQL entity persisting repository health, complexity, and contribution audits."""
    __tablename__ = "audit_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), nullable=False, index=True)
    repo_name = Column(String(255), nullable=False, index=True)
    total_opportunities = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    summary_narrative = Column(Text, nullable=True)
    report_data = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
