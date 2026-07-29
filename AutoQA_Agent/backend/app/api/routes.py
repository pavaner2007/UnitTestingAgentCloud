import logging
import uuid
import threading
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import io

from app.core.config import settings
from app.core.exceptions import AnalysisNotFoundException, AutoQAException
from app.db.session import get_db, SessionLocal
from app.schemas.analysis import (
    AnalyzeRepositoryRequest,
    AnalyzeRepositoryResponse,
    HealthResponse,
    RepositoryAnalysisReport,
)
from app.services.analysis_service import RepositoryAnalysisService
from app.services.pdf_service import generate_pdf
from app.services.pipeline_status_service import pipeline_status
from app.services.email_service import (
    send_report_email,
    EmailNotConfiguredError,
    EmailAuthError,
    EmailSendError,
)
from app.agents.qa_chat_agent import QAChatAgent

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["System"])
def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", service=settings.app_name)


def _run_analysis_background(analysis_id: str, github_url: str) -> None:
    """Worker that runs inside a BackgroundTask thread (not the event loop)."""
    db = SessionLocal()
    try:
        service = RepositoryAnalysisService(db)
        service.analyze_repository(github_url, analysis_id=analysis_id)
    except Exception:
        # fail_remaining is already called inside analyze_repository's except block;
        # log here for visibility but don't re-raise (background tasks swallow errors).
        logger.exception("Background analysis failed for %s", analysis_id)
    finally:
        db.close()


@router.post("/analyze-repository", response_model=AnalyzeRepositoryResponse, tags=["Analysis"])
def analyze_repository(
    payload: AnalyzeRepositoryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> AnalyzeRepositoryResponse:
    """
    Start a repository analysis.

    Cache-hit path (fast):
        If the URL was analysed before, return the full cached report immediately
        with `cached: true`.  The frontend must NOT show AgentPipelineView for
        this case — show a brief "Loaded from cache" indicator instead.

    New analysis path (async):
        Generate an `analysis_id`, initialise pipeline stages to "queued", enqueue
        the analysis as a BackgroundTask, and return immediately with
        `status: "processing"`.  The frontend polls GET /analysis/{id}/status for
        live progress, then fetches GET /analysis/{id} for the final report once
        `complete: true` is returned.
    """
    url = str(payload.github_url)

    # Cache-hit check removed as requested — every analysis run executes a fresh live analysis pipeline.

    # ── New analysis — async path ─────────────────────────────────────────────
    analysis_id = str(uuid.uuid4())
    pipeline_status.init_pipeline(analysis_id)
    background_tasks.add_task(_run_analysis_background, analysis_id, url)

    logger.info("Queued background analysis %s for %s", analysis_id, url)
    return AnalyzeRepositoryResponse(
        analysis_id=analysis_id,
        status="processing",
        cached=False,
        report=None,
    )


@router.get("/analysis/{analysis_id}/status", tags=["Analysis"])
def get_analysis_status(analysis_id: str) -> dict:
    """
    Fast in-memory polling endpoint.  Returns pipeline stage statuses.
    Response shape:
    {
        "analysis_id": str,
        "agents": [{"name": str, "status": str, "preview": str | None}],
        "complete": bool
    }
    Note: complete=True does NOT mean success — check individual stage statuses
    for failures.  complete=True simply means all stages have reached a terminal
    state (done / failed / skipped).
    """
    result = pipeline_status.get_status(analysis_id)
    if result is None:
        # Unknown ID — either never started (client error) or already cleaned up.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pipeline status found for analysis_id={analysis_id}. "
                   "The analysis may have completed and been cleaned up, or the ID is invalid.",
        )
    return result



@router.get("/analysis/{analysis_id}", tags=["Analysis"])
def get_analysis(analysis_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        service = RepositoryAnalysisService(db)
        return service.get_analysis(analysis_id)
    except AnalysisNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/analyses", tags=["Analysis"])
def list_analyses(limit: int = 50, db: Session = Depends(get_db)) -> list:
    """Return a summary list of all past analyses, newest first."""
    service = RepositoryAnalysisService(db)
    return service.get_analyses(limit=limit)


@router.get("/analysis/{analysis_id}/pdf", tags=["Analysis"])
def download_pdf(analysis_id: str, db: Session = Depends(get_db)):
    """Generate and stream a PDF report for the given analysis ID."""
    try:
        service = RepositoryAnalysisService(db)
        report_data = service.get_analysis(analysis_id)
        report = RepositoryAnalysisReport(**report_data)
        pdf_bytes = generate_pdf(report)
        filename = f"autoqa-{report.repository_name}-{analysis_id[:8]}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except AnalysisNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("PDF generation failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="PDF generation failed") from exc


class ChatRequest(BaseModel):
    question: str


class EmailRequest(BaseModel):
    recipient_email: str


@router.post("/analysis/{analysis_id}/chat", tags=["Analysis"])
def chat_with_codebase(analysis_id: str, payload: ChatRequest, db: Session = Depends(get_db)) -> dict:
    """Q&A Chatbot endpoint using RAG vector retrieval + Groq reasoning."""
    try:
        agent = QAChatAgent(db)
        return agent.answer_question(analysis_id, payload.question)
    except Exception as exc:
        logger.exception("Q&A Chat endpoint failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Q&A Chat request failed") from exc


@router.post("/analysis/{analysis_id}/email", tags=["Analysis"])
def email_report(
    analysis_id: str,
    payload: EmailRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Generate the PDF report and email it to the supplied recipient address.
    Reuses generate_pdf() — identical output to the /pdf download endpoint.
    """
    # Basic sanity check: must contain exactly one '@' with chars on both sides
    email = payload.recipient_email.strip()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email address.",
        )

    try:
        service = RepositoryAnalysisService(db)
        report_data = service.get_analysis(analysis_id)
        report = RepositoryAnalysisReport(**report_data)
        pdf_bytes = generate_pdf(report)
        send_report_email(
            to_email=email,
            repo_name=report.repository_name,
            pdf_bytes=pdf_bytes,
        )
        return {"success": True, "message": f"Report sent to {email}"}

    except AnalysisNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    except EmailNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.detail,
        ) from exc

    except EmailAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.detail,
        ) from exc

    except EmailSendError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.detail,
        ) from exc

    except Exception as exc:
        logger.exception("Email report endpoint failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send report email. Check server logs.",
        ) from exc


# ── V2.0 Enterprise Agent API Endpoints ───────────────────────────────────────

@router.get("/analysis/{analysis_id}/impact", tags=["V2 Agents"])
def get_change_impact(
    analysis_id: str,
    file: str,
    db: Session = Depends(get_db),
) -> dict:
    """Predict affected files, routes, and services when `file` is modified."""
    try:
        service = RepositoryAnalysisService(db)
        report_data = service.get_analysis(analysis_id)
        from app.agents.change_impact_agent import ChangeImpactAnalysisAgent
        agent = ChangeImpactAnalysisAgent()
        code_insights = report_data.get("code_insights") or {}
        res = agent.analyze_impact(
            target_file=file,
            dependency_graph=report_data.get("dependency_graph") or code_insights.get("dependency_graph"),
            api_inventory=report_data.get("api_inventory", []),
        )
        return res.model_dump()
    except AnalysisNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Change Impact calculation failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/analysis/{analysis_id}/architecture-drift", tags=["V2 Agents"])
def get_architecture_drift(analysis_id: str, db: Session = Depends(get_db)) -> dict:
    """Get architectural drift violation audit report."""
    try:
        service = RepositoryAnalysisService(db)
        report_data = service.get_analysis(analysis_id)
        if report_data.get("architecture_drift"):
            return report_data["architecture_drift"]

        from app.agents.architecture_drift_agent import ArchitectureDriftAgent
        agent = ArchitectureDriftAgent()
        code_insights = report_data.get("code_insights") or {}
        res = agent.audit(
            dependency_graph=report_data.get("dependency_graph") or code_insights.get("dependency_graph"),
            api_inventory=report_data.get("api_inventory", []),
            tech_stack=report_data.get("technology_stack", {}),
            analyzed_files=code_insights.get("analyzed_files", []),
        )
        return res.model_dump()
    except AnalysisNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/compare-repositories", tags=["V2 Agents"])
def compare_repositories(
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    """Compare two analyzed repositories to detect code duplication & shared architecture."""
    analysis_id_a = payload.get("analysis_id_a")
    analysis_id_b = payload.get("analysis_id_b")
    if not analysis_id_a or not analysis_id_b:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Both 'analysis_id_a' and 'analysis_id_b' are required.",
        )
    try:
        from app.agents.cross_repo_duplicate_agent import CrossRepoDuplicateAgent
        agent = CrossRepoDuplicateAgent(db)
        res = agent.compare(analysis_id_a, analysis_id_b)
        return res.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Cross-repository comparison failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/analysis/{analysis_id}/onboarding", tags=["V2 Agents"])
def get_project_onboarding(analysis_id: str, db: Session = Depends(get_db)) -> dict:
    """Get developer onboarding guide, recommended reading path, and quizzes."""
    try:
        service = RepositoryAnalysisService(db)
        report_data = service.get_analysis(analysis_id)
        if report_data.get("project_onboarding"):
            return report_data["project_onboarding"]

        from app.agents.project_onboarding_agent import AIProjectOnboardingAgent
        agent = AIProjectOnboardingAgent()
        res = agent.generate_onboarding(report_data)
        return res.model_dump()
    except AnalysisNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/analysis/{analysis_id}/health-score", tags=["V2 Agents"])
def get_repository_health(analysis_id: str, db: Session = Depends(get_db)) -> dict:
    """Get repository health score (0-100) and 8-category breakdown."""
    try:
        service = RepositoryAnalysisService(db)
        report_data = service.get_analysis(analysis_id)
        if report_data.get("repository_health"):
            return report_data["repository_health"]

        from app.agents.repository_health_agent import RepositoryHealthScoreAgent
        agent = RepositoryHealthScoreAgent()
        res = agent.calculate_health(report_data, report_data.get("architecture_drift"))
        return res.model_dump()
    except AnalysisNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/analysis/{analysis_id}/technical-debt", tags=["V2 Agents"])
def get_technical_debt(analysis_id: str, db: Session = Depends(get_db)) -> dict:
    """Get prioritized technical debt backlog ranked by business impact."""
    try:
        service = RepositoryAnalysisService(db)
        report_data = service.get_analysis(analysis_id)
        if report_data.get("technical_debt"):
            return report_data["technical_debt"]

        from app.agents.technical_debt_agent import TechnicalDebtPrioritizationAgent
        agent = TechnicalDebtPrioritizationAgent()
        res = agent.prioritize_debt(report_data, report_data.get("architecture_drift"))
        return res.model_dump()
    except AnalysisNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ── V3 Agent Endpoints ───────────────────────────────────────────────────────

@router.get("/analysis/{analysis_id}/execution-flow", tags=["V3 Agents"])
def get_execution_flow(
    analysis_id: str,
    entry_point: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """
    Return execution flow graphs for all traced API entry points.

    Optional query parameter:
        ?entry_point=POST+/login   — filter to a specific entry point.

    Returns a list of ExecutionFlowResult objects in `flows`.
    """
    try:
        service = RepositoryAnalysisService(db)
        report_data = service.get_analysis(analysis_id)

        flows = report_data.get("execution_flow_data") or []

        if entry_point and flows:
            # Filter to matching entry point (case-insensitive partial match)
            ep_lower = entry_point.lower()
            flows = [
                f for f in flows
                if ep_lower in (f.get("entry_point", "") or "").lower()
            ]

        return {
            "analysis_id": analysis_id,
            "total_flows": len(flows),
            "entry_point_filter": entry_point,
            "flows": flows,
        }
    except AnalysisNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Execution Flow endpoint failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve execution flow data.",
        ) from exc


@router.get("/analysis/{analysis_id}/feature-map", tags=["V3 Agents"])
def get_feature_map(
    analysis_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Return the detected business feature map for the analyzed repository.

    Returns FeatureMapResult with a list of DetectedBusinessFeature objects.
    """
    try:
        service = RepositoryAnalysisService(db)
        report_data = service.get_analysis(analysis_id)

        feature_map = report_data.get("feature_map")
        if feature_map:
            return feature_map

        # Fallback: compute on-demand if not stored (e.g. older analysis)
        from app.agents.feature_extraction_agent import FeatureExtractionAgent
        agent = FeatureExtractionAgent()
        result = agent.extract_features(
            api_inventory=report_data.get("api_inventory", []),
            dep_graph=report_data.get("dependency_graph"),
            code_insights=report_data.get("code_insights"),
            tech_stack=report_data.get("technology_stack"),
            module_summaries=report_data.get("module_summaries", {}),
        )
        return result.model_dump()

    except AnalysisNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Feature Map endpoint failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feature map data.",
        ) from exc
