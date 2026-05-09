from __future__ import annotations

import re

from sentinel.core.context import AuditContext
from sentinel.models.finding import Confidence, ExploitChainStep, Finding, Location, Severity
from sentinel.rules.base import BaseRule, RuleMetadata

_ANALYZER = "sentinel.rules.builtin.auth"

# Hardcoded credential patterns
_HARDCODED_SECRET_PATTERNS = [
    re.compile(
        r'(password|passwd|secret|api_key|apikey|token|auth_token)\s*=\s*["\'][^"\']{4,}["\']',
        re.IGNORECASE,
    ),
    re.compile(r'(AWS_SECRET|AWS_ACCESS_KEY|PRIVATE_KEY)\s*=\s*["\'][^"\']+["\']', re.IGNORECASE),
]

# Disabled security controls
_DISABLED_AUTH_PATTERNS = [
    re.compile(r"verify\s*=\s*False", re.IGNORECASE),
    re.compile(r"ssl_verify\s*=\s*False", re.IGNORECASE),
    re.compile(r"check_hostname\s*=\s*False", re.IGNORECASE),
    re.compile(r"ALLOW_ALL_ORIGINS\s*=\s*True", re.IGNORECASE),
    re.compile(r"DEBUG\s*=\s*True", re.IGNORECASE),
]


class HardcodedCredentialRule(BaseRule):
    metadata = RuleMetadata(
        id="AUTH-001",
        title="Hardcoded Credential or Secret",
        description="Credential or secret key assigned as a string literal in source code.",
        severity="high",
        confidence="medium",
        cwe_ids=["CWE-798"],
        tags=["secrets", "credentials", "hardcoded"],
        languages=["python"],
    )

    async def match(self, ctx: AuditContext) -> list[Finding]:
        findings: list[Finding] = []

        for rel_path, content in ctx.file_contents.items():
            lang = ctx.file_metadata.get(rel_path, {}).get("language")
            if lang != "python":
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                matched = next((p for p in _HARDCODED_SECRET_PATTERNS if p.search(line)), None)
                if not matched:
                    continue

                findings.append(
                    Finding(
                        title="Hardcoded Credential or Secret",
                        severity=Severity.HIGH,
                        confidence=Confidence.MEDIUM,
                        affected_components=[rel_path],
                        locations=[Location(file=rel_path, line_start=line_no)],
                        attack_surface="Source code, version control history, build artifacts",
                        exploitation_requirements=(
                            "Read access to source code, git history, or any artifact containing this file"
                        ),
                        technical_explanation=(
                            f"`{rel_path}:{line_no}` contains what appears to be a hardcoded credential. "
                            "Once committed to VCS, secrets persist in history even after removal."
                        ),
                        root_cause="Secret stored in source code instead of environment variables or a secrets manager",
                        attack_scenario=(
                            "Attacker gains read access to the repository (leaked, public, or insider), "
                            "extracts the credential from source or git history, and authenticates as the service."
                        ),
                        exploit_chain=[
                            ExploitChainStep(
                                step=1, component="VCS", action="Clone or access repository"
                            ),
                            ExploitChainStep(
                                step=2,
                                component=rel_path,
                                action=f"Extract credential at line {line_no}",
                            ),
                            ExploitChainStep(
                                step=3,
                                component="Target Service",
                                action="Authenticate using extracted secret",
                            ),
                        ],
                        potential_impact="Service impersonation, data access, lateral movement to connected systems",
                        blast_radius="All resources the credential grants access to",
                        detection_difficulty="Easy — any secret scanner finds this",
                        business_risk="Credential compromise, unauthorized access, compliance violation",
                        mitigation_strategy=(
                            "Remove secret from source. Rotate it immediately. "
                            "Load from environment variables or a secrets manager (Vault, AWS Secrets Manager)."
                        ),
                        secure_refactor_recommendations=[
                            "Use `os.environ['SECRET_NAME']` or pydantic-settings",
                            "Add a pre-commit hook with `detect-secrets` or `trufflehog`",
                            "Purge from git history with `git filter-repo`",
                        ],
                        analyzer=_ANALYZER,
                        rule_id="AUTH-001",
                        cwe_ids=["CWE-798"],
                        tags=["secrets", "CWE-798"],
                    )
                )
                break

        return findings


class DisabledTLSVerificationRule(BaseRule):
    metadata = RuleMetadata(
        id="AUTH-002",
        title="TLS/SSL Verification Disabled",
        description="SSL certificate verification explicitly disabled, enabling MITM attacks.",
        severity="high",
        confidence="high",
        cwe_ids=["CWE-295"],
        tags=["tls", "ssl", "mitm", "auth"],
        languages=["python"],
    )

    async def match(self, ctx: AuditContext) -> list[Finding]:
        findings: list[Finding] = []

        for rel_path, content in ctx.file_contents.items():
            lang = ctx.file_metadata.get(rel_path, {}).get("language")
            if lang != "python":
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                matched = next((p for p in _DISABLED_AUTH_PATTERNS if p.search(line)), None)
                if not matched:
                    continue

                findings.append(
                    Finding(
                        title="TLS/SSL Verification Disabled",
                        severity=Severity.HIGH,
                        confidence=Confidence.HIGH,
                        affected_components=[rel_path],
                        locations=[Location(file=rel_path, line_start=line_no)],
                        attack_surface="All HTTPS connections made with this client",
                        exploitation_requirements=(
                            "Network position between client and server (LAN, VPN, compromised router)"
                        ),
                        technical_explanation=(
                            f"`{rel_path}:{line_no}` disables certificate verification. "
                            "All TLS connections are vulnerable to man-in-the-middle interception."
                        ),
                        root_cause="Developer disabled verification to bypass self-signed cert errors in dev/test; never re-enabled",
                        attack_scenario=(
                            "Attacker with network position presents a forged certificate. "
                            "Client accepts it without verification, attacker reads/modifies all traffic."
                        ),
                        exploit_chain=[
                            ExploitChainStep(
                                step=1, component="Network", action="ARP spoofing or rogue AP"
                            ),
                            ExploitChainStep(
                                step=2,
                                component="TLS Handshake",
                                action="Attacker presents forged cert",
                            ),
                            ExploitChainStep(
                                step=3,
                                component=rel_path,
                                action="Client accepts cert (verify=False)",
                            ),
                            ExploitChainStep(
                                step=4,
                                component="Traffic",
                                action="Attacker reads plaintext credentials/data",
                            ),
                        ],
                        potential_impact="Credential theft, session hijacking, data interception",
                        blast_radius="All data transmitted over affected connections",
                        detection_difficulty="Easy — grep for `verify=False`",
                        business_risk="Compliance violation, credential theft, data breach",
                        mitigation_strategy=(
                            "Re-enable certificate verification. Use a proper CA bundle or "
                            "configure `REQUESTS_CA_BUNDLE` for internal CAs."
                        ),
                        secure_refactor_recommendations=[
                            "Remove `verify=False` — use `verify='/path/to/ca-bundle.crt'` for internal CAs",
                            "Never disable verification in production code paths",
                        ],
                        analyzer=_ANALYZER,
                        rule_id="AUTH-002",
                        cwe_ids=["CWE-295"],
                        tags=["tls", "CWE-295"],
                    )
                )
                break

        return findings
