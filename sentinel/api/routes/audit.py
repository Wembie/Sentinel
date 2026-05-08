from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from sentinel.models.audit import AuditRequest, AuditResult

router = APIRouter()

# In-memory result store for v0.1.
# Replace with a persistent backend (Redis, DB) for multi-worker deployments.
_results: dict[str, AuditResult] = {}


@router.post("/", response_model=AuditResult)
async def run_audit(request: AuditRequest, req: Request) -> AuditResult:
    engine = req.app.state.engine
    result: AuditResult = await engine.run(request)
    _results[str(result.id)] = result
    return result


@router.get("/{audit_id}", response_model=AuditResult)
async def get_audit(audit_id: str) -> AuditResult:
    result = _results.get(audit_id)
    if not result:
        raise HTTPException(status_code=404, detail="Audit not found")
    return result


@router.get("/{audit_id}/report")
async def get_report(audit_id: str, req: Request, fmt: str = "markdown") -> dict[str, str]:
    result = _results.get(audit_id)
    if not result:
        raise HTTPException(status_code=404, detail="Audit not found")
    engine = req.app.state.engine
    try:
        report = engine.generate_report(result, fmt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"format": fmt, "report": report}


@router.get("/")
async def list_audits() -> list[dict[str, str]]:
    return [
        {"id": str(r.id), "status": r.status.value, "findings": str(r.summary.total_findings)}
        for r in _results.values()
    ]
