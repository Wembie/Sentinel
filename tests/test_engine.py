from __future__ import annotations

import pytest

from sentinel.config import Settings
from sentinel.models.audit import AuditRequest, AuditScope, AuditStatus


@pytest.fixture
def settings(tmp_path):
    return Settings(llm_provider="none", rules_dirs=[], plugin_dirs=[])


@pytest.mark.asyncio
async def test_audit_empty_directory(settings, tmp_path):
    from sentinel.core.engine import AuditEngine

    engine = AuditEngine(settings)
    result = await engine.run(AuditRequest(target=tmp_path))

    assert result.status == AuditStatus.COMPLETED
    assert result.summary.files_analyzed == 0
    assert result.summary.total_findings == 0
    assert result.errors == []


@pytest.mark.asyncio
async def test_audit_detects_sql_injection(settings, tmp_path):
    from sentinel.core.engine import AuditEngine

    vuln_file = tmp_path / "app.py"
    vuln_file.write_text(
        'def get_user(user_id):\n    cursor.execute(f"SELECT * FROM users WHERE id={user_id}")\n'
    )

    engine = AuditEngine(settings)
    result = await engine.run(
        AuditRequest(target=tmp_path, scope=AuditScope(languages=["python"]))
    )

    assert result.status == AuditStatus.COMPLETED
    sql_findings = [f for f in result.findings if f.rule_id == "INJ-001"]
    assert len(sql_findings) >= 1
    assert sql_findings[0].locations[0].file == "app.py"


@pytest.mark.asyncio
async def test_audit_detects_command_injection(settings, tmp_path):
    from sentinel.core.engine import AuditEngine

    vuln_file = tmp_path / "runner.py"
    vuln_file.write_text(
        'import subprocess\ndef run(cmd): subprocess.run(f"bash -c {cmd}", shell=True)\n'
    )

    engine = AuditEngine(settings)
    result = await engine.run(AuditRequest(target=tmp_path))

    cmd_findings = [f for f in result.findings if f.rule_id == "INJ-002"]
    assert len(cmd_findings) >= 1


@pytest.mark.asyncio
async def test_report_generation(settings, tmp_path):
    from sentinel.core.engine import AuditEngine

    engine = AuditEngine(settings)
    result = await engine.run(AuditRequest(target=tmp_path))

    md = engine.generate_report(result, "markdown")
    assert "SENTINEL" in md

    json_out = engine.generate_report(result, "json")
    import json
    data = json.loads(json_out)
    assert "findings" in data

    sarif = engine.generate_report(result, "sarif")
    sarif_data = json.loads(sarif)
    assert sarif_data["version"] == "2.1.0"


@pytest.mark.asyncio
async def test_rule_loader_loads_builtins(settings):
    from sentinel.rules.loader import RuleLoader

    loader = RuleLoader()
    loader.load_builtin()

    rule_ids = [r.metadata.id for r in loader.rules]
    assert "INJ-001" in rule_ids
    assert "INJ-002" in rule_ids
    assert "AUTH-001" in rule_ids
    assert "AUTH-002" in rule_ids
