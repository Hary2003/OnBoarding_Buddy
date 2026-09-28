import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from database import get_db_context
from models.db_models import RepositoryRecord, PRReviewRecord, AuditReportRecord
from models.repository_index import RepositoryIndex, PullRequestAnalysis, PRReviewResponse, AuditReport

logger = logging.getLogger("onboarding_buddy.persistence")


class RepositoryPersistenceService:
    """Handles database persistence for parsed repository indexes, PR reviews, and audit reports."""

    def save_repository(self, session_id: str, repo_index: RepositoryIndex) -> bool:
        """Persists or updates an analyzed repository index in PostgreSQL."""
        try:
            with get_db_context() as db:
                existing = db.query(RepositoryRecord).filter(RepositoryRecord.session_id == session_id).first()
                if existing:
                    # Update existing record
                    record = RepositoryRecord.from_repository_index(session_id, repo_index)
                    existing.repo_name = record.repo_name
                    existing.repo_path = record.repo_path
                    existing.total_files = record.total_files
                    existing.total_lines = record.total_lines
                    existing.languages = record.languages
                    existing.entry_points = record.entry_points
                    existing.module_counts = record.module_counts
                    existing.circular_cycles = record.circular_cycles
                    existing.architecture_summary = record.architecture_summary
                    existing.files_data = record.files_data
                    logger.info(f"Updated repository '{repo_index.repo_name}' for session '{session_id}' in PostgreSQL.")
                else:
                    new_record = RepositoryRecord.from_repository_index(session_id, repo_index)
                    db.add(new_record)
                    logger.info(f"Persisted new repository '{repo_index.repo_name}' for session '{session_id}' in PostgreSQL.")
                return True
        except Exception as e:
            logger.error(f"Failed to persist repository to PostgreSQL: {e}", exc_info=True)
            return False

    def load_repository(self, session_id: str) -> Optional[RepositoryIndex]:
        """Loads a persisted repository index from PostgreSQL by session_id."""
        try:
            with get_db_context() as db:
                record = db.query(RepositoryRecord).filter(RepositoryRecord.session_id == session_id).first()
                if record:
                    repo_index = record.to_repository_index()
                    logger.info(f"Loaded repository '{repo_index.repo_name}' for session '{session_id}' from PostgreSQL.")
                    return repo_index
        except Exception as e:
            logger.error(f"Failed to load repository from PostgreSQL: {e}", exc_info=True)
        return None

    def delete_repository(self, session_id: str) -> bool:
        """Removes a repository index record from PostgreSQL."""
        try:
            with get_db_context() as db:
                record = db.query(RepositoryRecord).filter(RepositoryRecord.session_id == session_id).first()
                if record:
                    db.delete(record)
                    return True
        except Exception as e:
            logger.error(f"Failed to delete repository from PostgreSQL: {e}")
        return False

    def list_repositories(self) -> List[Dict[str, Any]]:
        """Returns all persisted repositories with key metadata."""
        try:
            with get_db_context() as db:
                records = db.query(RepositoryRecord).order_by(RepositoryRecord.updated_at.desc()).all()
                return [
                    {
                        "session_id": r.session_id,
                        "repo_name": r.repo_name,
                        "total_files": r.total_files,
                        "total_lines": r.total_lines,
                        "languages": r.languages,
                        "updated_at": r.updated_at.isoformat() if r.updated_at else None
                    }
                    for r in records
                ]
        except Exception as e:
            logger.error(f"Failed to list repositories from PostgreSQL: {e}")
            return []

    def save_pr_review(self, session_id: str, review: PRReviewResponse, title: str = "") -> bool:
        """Persists a PR review analysis in PostgreSQL."""
        try:
            with get_db_context() as db:
                findings_json = [f.model_dump() for f in review.security_findings]
                full_json = review.model_dump()
                record = PRReviewRecord(
                    session_id=session_id,
                    title=title or "Pull Request Review",
                    risk_level=review.risk_level,
                    executive_summary=review.executive_summary,
                    developer_summary=review.developer_summary,
                    security_findings=findings_json,
                    full_analysis=full_json
                )
                db.add(record)
                return True
        except Exception as e:
            logger.error(f"Failed to persist PR review: {e}")
            return False

    def save_audit_report(self, session_id: str, report: AuditReport) -> bool:
        """Persists a repository audit report in PostgreSQL."""
        try:
            with get_db_context() as db:
                record = AuditReportRecord(
                    session_id=session_id,
                    repo_name=report.repo_name,
                    overall_score=report.overall_score,
                    health_grade=report.health_grade,
                    opportunities_count=len(report.opportunities),
                    report_data=report.model_dump()
                )
                db.add(record)
                return True
        except Exception as e:
            logger.error(f"Failed to persist audit report: {e}")
            return False


repository_persistence = RepositoryPersistenceService()
