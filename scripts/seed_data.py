#!/usr/bin/env python3
"""
Seed the Stratum database with demo projects and analysis results.

Usage:
    python scripts/seed_data.py

Creates 5 demo projects with realistic analysis data so the
dashboard and report views have content to display immediately.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, UTC, timedelta

# -- Seed projects ----------------------------------------------------------

SEED_PROJECTS = [
    {
        "project_id": "prj_demo_acme01",
        "name": "Acme Payment Gateway",
        "description": "Core payment processing service — handles Stripe, PayPal, and wire transfers. Acquired in 2024 merger.",
        "scenario": "ma_due_diligence",
        "analysis_status": "completed",
        "overall_health_score": 4.8,
        "owner_id": "usr_mvp_001",
    },
    {
        "project_id": "prj_demo_atlas02",
        "name": "Atlas Frontend",
        "description": "React SPA for the customer-facing dashboard. 180k LOC, 12 contributors.",
        "scenario": "cto_onboarding",
        "analysis_status": "completed",
        "overall_health_score": 7.1,
        "owner_id": "usr_mvp_001",
    },
    {
        "project_id": "prj_demo_titan03",
        "name": "Titan Data Pipeline",
        "description": "ETL pipeline processing 2M events/day. Python + Apache Beam. Outsourced to vendor in 2023.",
        "scenario": "vendor_audit",
        "analysis_status": "completed",
        "overall_health_score": 5.9,
        "owner_id": "usr_mvp_001",
    },
    {
        "project_id": "prj_demo_nexus04",
        "name": "Nexus Auth Service",
        "description": "OAuth2/OIDC identity provider. Java 17 + Spring Boot. Scheduled for decommission Q3.",
        "scenario": "decommission",
        "analysis_status": "completed",
        "overall_health_score": 3.2,
        "owner_id": "usr_mvp_001",
    },
    {
        "project_id": "prj_demo_orbit05",
        "name": "Orbit Mobile SDK",
        "description": "Cross-platform SDK (iOS/Android) for partner integrations. TypeScript core with native bridges.",
        "scenario": "oss_assessment",
        "analysis_status": "pending",
        "overall_health_score": None,
        "owner_id": "usr_mvp_001",
    },
]

# -- Seed analysis results (in-memory DTO format) --------------------------

def _make_dimension(value: float, label: str, evidence: str) -> dict:
    if value >= 7:
        severity = "high"
    elif value >= 4:
        severity = "medium"
    elif value >= 2:
        severity = "low"
    else:
        severity = "minimal"
    return {"value": round(value, 1), "severity": severity, "label": label, "evidence": evidence}


def _make_component(name: str, score: float, dims: dict[str, dict]) -> dict:
    return {
        "component_name": name,
        "composite_score": round(score, 1),
        "systemic_risk": sum(1 for d in dims.values() if d["value"] > 7) >= 3,
        "dimension_scores": dims,
    }


def _make_hotspot(path: str, score: float, indicators: dict[str, float], rec: str, effort: str) -> dict:
    return {
        "file_path": path,
        "composite_risk_score": round(score, 1),
        "risk_indicators": indicators,
        "refactoring_recommendation": rec,
        "effort_estimate": effort,
    }


SEED_ANALYSIS: dict[str, dict] = {
    # --- Acme Payment Gateway (health 4.8 — high risk) ---
    "prj_demo_acme01": {
        "project_name": "Acme Payment Gateway",
        "scenario": "ma_due_diligence",
        "analysis_timestamp": (datetime.now(UTC) - timedelta(hours=6)).isoformat(),
        "overall_health_score": 4.8,
        "dimension_scores": {
            "knowledge_distribution": _make_dimension(7.8, "Knowledge Distribution", "4 files with >80% single-author ownership; bus factor=1 on payment core"),
            "temporal_coupling": _make_dimension(6.2, "Temporal Coupling", "payment_handler.py and transaction_log.py co-change 78% of the time"),
            "churn_rate": _make_dimension(8.1, "Churn Rate", "payment_router.py modified 47 times in 90 days — 3x above baseline"),
            "code_complexity": _make_dimension(7.5, "Code Complexity", "3 God Class candidates; PaymentProcessor has ~45 estimated methods"),
            "code_duplication": _make_dimension(5.8, "Code Duplication", "2 Shotgun Surgery candidates across payment and billing modules"),
            "commit_quality": _make_dimension(4.2, "Commit Quality", "32% of commits are mega-commits (>15 files); poor commit hygiene"),
            "bug_fix_ratio": _make_dimension(6.9, "Bug Fix Ratio", "41% of recent commits are bug fixes — elevated regression risk"),
            "dependency_currency": _make_dimension(5.1, "Dependency Currency", "stripe-python 2 major versions behind; 3 deps with known CVEs"),
            "dependency_vulnerability": _make_dimension(8.5, "Dependency Vulnerability", "CVE-2024-3651 (CVSS 9.1) in idna; CVE-2024-6345 in setuptools"),
            "license_risk": _make_dimension(1.2, "License Risk", "All dependencies use permissive licenses (MIT, Apache-2.0)"),
            "api_stability": _make_dimension(3.5, "API Stability", "REST endpoints have been stable for 6 months; no breaking changes"),
            "documentation_coverage": _make_dimension(6.0, "Documentation Coverage", "README exists but no API docs; 12% of public functions documented"),
            "test_coverage": _make_dimension(3.8, "Test Coverage", "Estimated 38% coverage from commit patterns; payment core undertested"),
            "deployment_frequency": _make_dimension(2.5, "Deployment Frequency", "~3 deploys per week; healthy CI/CD cadence"),
            "team_activity": _make_dimension(4.0, "Team Activity", "2 of 5 contributors account for 85% of commits in last 90 days"),
        },
        "component_risks": [
            _make_component("payment", 7.6, {
                "knowledge_distribution": _make_dimension(8.2, "Knowledge Distribution", "Single author: 82%"),
                "churn_rate": _make_dimension(8.1, "Churn Rate", "47 modifications in 90 days"),
                "code_complexity": _make_dimension(7.5, "Code Complexity", "PaymentProcessor god class"),
                "test_coverage": _make_dimension(3.8, "Test Coverage", "Low coverage on core paths"),
            }),
            _make_component("billing", 5.9, {
                "temporal_coupling": _make_dimension(6.2, "Temporal Coupling", "Coupled to payment module"),
                "commit_quality": _make_dimension(5.5, "Commit Quality", "Mixed quality commits"),
                "bug_fix_ratio": _make_dimension(6.9, "Bug Fix Ratio", "High bug fix ratio"),
            }),
            _make_component("webhooks", 4.1, {
                "code_complexity": _make_dimension(4.5, "Code Complexity", "Moderate complexity"),
                "documentation_coverage": _make_dimension(3.0, "Documentation", "Minimal docs"),
            }),
        ],
        "file_hotspots": [
            _make_hotspot("src/payment/payment_handler.py", 9.2, {"churn": 9.5, "complexity": 8.8, "ownership": 9.1}, "Extract payment validation into dedicated service; reduce method count from ~45 to <15", "large"),
            _make_hotspot("src/payment/transaction_log.py", 7.8, {"churn": 7.2, "coupling": 8.5, "bug_density": 7.8}, "Decouple from payment_handler; introduce event-driven logging", "medium"),
            _make_hotspot("src/billing/invoice_generator.py", 7.1, {"complexity": 7.5, "duplication": 6.8}, "Extract PDF generation; reduce conditional branching", "medium"),
            _make_hotspot("src/webhooks/stripe_webhook.py", 6.5, {"churn": 6.8, "bug_density": 6.2}, "Add retry logic and idempotency keys", "small"),
            _make_hotspot("src/payment/refund_processor.py", 6.2, {"complexity": 6.5, "test_coverage": 5.8}, "Add integration tests for refund edge cases", "small"),
        ],
        "top_risks": [
            {"dimension": "dependency_vulnerability", "value": 8.5, "severity": "high", "label": "Dependency Vulnerability", "evidence": "CVE-2024-3651 (CVSS 9.1)"},
            {"dimension": "churn_rate", "value": 8.1, "severity": "high", "label": "Churn Rate", "evidence": "payment_router.py: 47 changes/90 days"},
            {"dimension": "knowledge_distribution", "value": 7.8, "severity": "high", "label": "Knowledge Distribution", "evidence": "Bus factor=1 on payment core"},
            {"dimension": "code_complexity", "value": 7.5, "severity": "high", "label": "Code Complexity", "evidence": "3 God Class candidates"},
            {"dimension": "bug_fix_ratio", "value": 6.9, "severity": "medium", "label": "Bug Fix Ratio", "evidence": "41% bug fix commits"},
        ],
        "ai_narrative": (
            "## Executive Assessment: Acme Payment Gateway\n\n"
            "**Overall Risk: HIGH (4.8/10)**\n\n"
            "The Acme Payment Gateway presents significant acquisition risk concentrated in three areas:\n\n"
            "1. **Critical Knowledge Silos**: The payment processing core — the most business-critical module — "
            "is effectively maintained by a single developer. An 82% single-author ownership rate on `payment_handler.py` "
            "means departure of one engineer could halt development for weeks.\n\n"
            "2. **Active Vulnerability Exposure**: Two CVEs with CVSS scores above 7.0 affect production dependencies. "
            "CVE-2024-3651 in the `idna` package (CVSS 9.1) is particularly concerning as it enables denial-of-service "
            "attacks on the payment URL validation path.\n\n"
            "3. **Architectural Debt**: The `PaymentProcessor` class has grown into a God Object with an estimated "
            "45+ methods. This, combined with 47 modifications in 90 days, indicates the team is patching rather "
            "than properly decomposing the system.\n\n"
            "**Recommendation**: Budget 4-6 engineering weeks post-acquisition for: (a) immediate CVE remediation, "
            "(b) knowledge transfer program for payment core, (c) PaymentProcessor decomposition into bounded contexts."
        ),
        "pdf_output_path": "",
    },

    # --- Atlas Frontend (health 7.1 — moderate risk) ---
    "prj_demo_atlas02": {
        "project_name": "Atlas Frontend",
        "scenario": "cto_onboarding",
        "analysis_timestamp": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        "overall_health_score": 7.1,
        "dimension_scores": {
            "knowledge_distribution": _make_dimension(3.5, "Knowledge Distribution", "Well-distributed ownership across 12 contributors"),
            "temporal_coupling": _make_dimension(4.1, "Temporal Coupling", "Moderate coupling between state management and UI layers"),
            "churn_rate": _make_dimension(3.2, "Churn Rate", "Healthy churn levels; no anomalous files"),
            "code_complexity": _make_dimension(5.8, "Code Complexity", "2 component files exceed 400 lines; consider splitting"),
            "code_duplication": _make_dimension(4.5, "Code Duplication", "Some repeated patterns in form validation logic"),
            "commit_quality": _make_dimension(2.8, "Commit Quality", "Good commit hygiene; conventional commits enforced"),
            "bug_fix_ratio": _make_dimension(3.1, "Bug Fix Ratio", "22% bug fixes — healthy ratio"),
            "dependency_currency": _make_dimension(2.0, "Dependency Currency", "All major deps within 1 version of latest"),
            "dependency_vulnerability": _make_dimension(1.5, "Dependency Vulnerability", "No known CVEs in production dependencies"),
            "license_risk": _make_dimension(0.5, "License Risk", "All MIT/Apache-2.0 licensed"),
            "api_stability": _make_dimension(2.2, "API Stability", "Stable component interfaces"),
            "documentation_coverage": _make_dimension(4.8, "Documentation Coverage", "Storybook covers 60% of components; missing for utils"),
            "test_coverage": _make_dimension(5.5, "Test Coverage", "55% estimated coverage; critical paths well tested"),
            "deployment_frequency": _make_dimension(1.8, "Deployment Frequency", "Daily deploys via CI/CD"),
            "team_activity": _make_dimension(2.0, "Team Activity", "Active team of 12; good distribution"),
        },
        "component_risks": [
            _make_component("components/forms", 5.2, {
                "code_duplication": _make_dimension(5.8, "Code Duplication", "Repeated validation patterns"),
                "code_complexity": _make_dimension(5.5, "Code Complexity", "Large form components"),
            }),
            _make_component("state/store", 4.8, {
                "temporal_coupling": _make_dimension(5.2, "Temporal Coupling", "Tightly coupled to views"),
                "test_coverage": _make_dimension(4.5, "Test Coverage", "State logic undertested"),
            }),
            _make_component("pages", 3.5, {
                "code_complexity": _make_dimension(4.2, "Code Complexity", "Some large page components"),
            }),
        ],
        "file_hotspots": [
            _make_hotspot("src/components/forms/PaymentForm.tsx", 6.8, {"complexity": 7.2, "churn": 5.5, "duplication": 6.8}, "Extract validation into shared hook; split into sub-components", "medium"),
            _make_hotspot("src/state/store/cartSlice.ts", 5.9, {"coupling": 6.5, "churn": 5.2}, "Decouple cart state from payment flow", "small"),
            _make_hotspot("src/pages/Dashboard.tsx", 5.5, {"complexity": 6.0, "ownership": 4.8}, "Extract widget components; reduce direct API calls", "medium"),
        ],
        "top_risks": [
            {"dimension": "code_complexity", "value": 5.8, "severity": "medium", "label": "Code Complexity", "evidence": "2 files exceed 400 lines"},
            {"dimension": "test_coverage", "value": 5.5, "severity": "medium", "label": "Test Coverage", "evidence": "55% estimated coverage"},
            {"dimension": "documentation_coverage", "value": 4.8, "severity": "medium", "label": "Documentation Coverage", "evidence": "60% Storybook coverage"},
            {"dimension": "code_duplication", "value": 4.5, "severity": "medium", "label": "Code Duplication", "evidence": "Repeated form patterns"},
            {"dimension": "temporal_coupling", "value": 4.1, "severity": "medium", "label": "Temporal Coupling", "evidence": "State-UI coupling"},
        ],
        "ai_narrative": (
            "## CTO Onboarding Brief: Atlas Frontend\n\n"
            "**Overall Health: GOOD (7.1/10)**\n\n"
            "The Atlas Frontend is in solid shape for a 180k LOC React application with 12 contributors. "
            "Key strengths include well-distributed code ownership, healthy deployment cadence (daily CI/CD), "
            "and no dependency vulnerabilities.\n\n"
            "**Areas to address in your first 90 days:**\n\n"
            "1. **Form validation duplication** — The `PaymentForm.tsx` and related components contain repeated "
            "validation logic. A shared validation hook would reduce ~800 lines of duplication.\n\n"
            "2. **State-UI coupling** — The cart state slice is tightly coupled to payment views, making "
            "the checkout flow brittle to change. Consider introducing a facade pattern.\n\n"
            "3. **Test coverage gaps** — At 55%, coverage is adequate but not robust. Focus new tests on "
            "the payment flow and cart state management — the highest-risk paths."
        ),
        "pdf_output_path": "",
    },

    # --- Titan Data Pipeline (health 5.9 — moderate risk) ---
    "prj_demo_titan03": {
        "project_name": "Titan Data Pipeline",
        "scenario": "vendor_audit",
        "analysis_timestamp": (datetime.now(UTC) - timedelta(days=3)).isoformat(),
        "overall_health_score": 5.9,
        "dimension_scores": {
            "knowledge_distribution": _make_dimension(8.2, "Knowledge Distribution", "3 key files authored entirely by vendor team; no internal knowledge"),
            "temporal_coupling": _make_dimension(5.5, "Temporal Coupling", "ETL stages moderately coupled"),
            "churn_rate": _make_dimension(4.8, "Churn Rate", "Moderate churn; spike during Q4 data model migration"),
            "code_complexity": _make_dimension(6.8, "Code Complexity", "Beam pipeline transforms exceed recommended complexity"),
            "code_duplication": _make_dimension(7.2, "Code Duplication", "3 Shotgun Surgery candidates; data schema changes ripple across 12+ files"),
            "commit_quality": _make_dimension(5.5, "Commit Quality", "Mixed — vendor commits lack context; large batch commits"),
            "bug_fix_ratio": _make_dimension(5.2, "Bug Fix Ratio", "35% bug fixes in last 90 days"),
            "dependency_currency": _make_dimension(4.5, "Dependency Currency", "apache-beam 1 minor behind; pandas 2 versions behind"),
            "dependency_vulnerability": _make_dimension(3.8, "Dependency Vulnerability", "1 moderate CVE in transitive dependency"),
            "license_risk": _make_dimension(2.5, "License Risk", "Apache-2.0 throughout; no copyleft risk"),
            "api_stability": _make_dimension(3.2, "API Stability", "Pipeline interfaces stable; schema evolving"),
            "documentation_coverage": _make_dimension(7.5, "Documentation Coverage", "Vendor documentation is sparse; no runbooks"),
            "test_coverage": _make_dimension(4.2, "Test Coverage", "42% coverage; no integration tests for full pipeline"),
            "deployment_frequency": _make_dimension(3.0, "Deployment Frequency", "Weekly deploys"),
            "team_activity": _make_dimension(6.5, "Team Activity", "Vendor team responsive but slow knowledge transfer"),
        },
        "component_risks": [
            _make_component("transforms", 6.8, {
                "code_complexity": _make_dimension(7.5, "Code Complexity", "Complex beam transforms"),
                "knowledge_distribution": _make_dimension(8.5, "Knowledge Distribution", "Vendor-only knowledge"),
                "code_duplication": _make_dimension(6.5, "Code Duplication", "Repeated transform patterns"),
            }),
            _make_component("schemas", 5.5, {
                "code_duplication": _make_dimension(7.2, "Code Duplication", "Schema changes ripple widely"),
                "churn_rate": _make_dimension(5.8, "Churn Rate", "Frequent schema modifications"),
            }),
            _make_component("connectors", 4.2, {
                "test_coverage": _make_dimension(4.5, "Test Coverage", "Connector tests incomplete"),
            }),
        ],
        "file_hotspots": [
            _make_hotspot("pipeline/transforms/event_enricher.py", 8.1, {"complexity": 8.5, "ownership": 9.0, "churn": 6.8}, "Vendor-only file; immediate knowledge transfer needed. Split into composable transforms.", "large"),
            _make_hotspot("pipeline/schemas/event_schema.py", 6.5, {"duplication": 7.2, "churn": 6.0}, "Introduce schema registry to decouple producers from consumers", "medium"),
            _make_hotspot("pipeline/transforms/aggregator.py", 6.2, {"complexity": 7.0, "test_coverage": 5.0}, "Add windowing tests; reduce nested conditional logic", "medium"),
            _make_hotspot("pipeline/connectors/bigquery_sink.py", 5.8, {"test_coverage": 5.5, "bug_density": 5.2}, "Add retry/idempotency; missing error handling for partial writes", "small"),
        ],
        "top_risks": [
            {"dimension": "knowledge_distribution", "value": 8.2, "severity": "high", "label": "Knowledge Distribution", "evidence": "Vendor-only knowledge on critical files"},
            {"dimension": "documentation_coverage", "value": 7.5, "severity": "high", "label": "Documentation Coverage", "evidence": "No runbooks; sparse inline docs"},
            {"dimension": "code_duplication", "value": 7.2, "severity": "high", "label": "Code Duplication", "evidence": "Schema changes ripple across 12+ files"},
            {"dimension": "code_complexity", "value": 6.8, "severity": "medium", "label": "Code Complexity", "evidence": "Beam transforms exceed complexity thresholds"},
            {"dimension": "team_activity", "value": 6.5, "severity": "medium", "label": "Team Activity", "evidence": "Slow knowledge transfer from vendor"},
        ],
        "ai_narrative": (
            "## Vendor Audit Report: Titan Data Pipeline\n\n"
            "**Overall Health: MODERATE (5.9/10)**\n\n"
            "The Titan Data Pipeline presents manageable but concerning vendor dependency risks. "
            "The pipeline processes 2M events/day reliably, but the codebase has significant "
            "knowledge concentration with the outsourced vendor team.\n\n"
            "**Critical Findings:**\n\n"
            "1. **Vendor Lock-in Risk (CRITICAL)**: The `event_enricher.py` transform — the most complex "
            "and business-critical component — has been authored and maintained exclusively by the vendor. "
            "No internal team member has contributed to or reviewed this file.\n\n"
            "2. **Structural Duplication**: Data schema changes require modifications across 12+ files. "
            "A schema registry pattern would reduce this coupling significantly.\n\n"
            "3. **Missing Operational Documentation**: No runbooks exist for incident response. The vendor "
            "has been the sole responder for pipeline failures.\n\n"
            "**Recommendation**: Before contract renewal, require (a) pair programming sessions for knowledge "
            "transfer on all critical transforms, (b) comprehensive runbook creation, (c) schema registry "
            "implementation to reduce change amplification."
        ),
        "pdf_output_path": "",
    },

    # --- Nexus Auth Service (health 3.2 — critical risk) ---
    "prj_demo_nexus04": {
        "project_name": "Nexus Auth Service",
        "scenario": "decommission",
        "analysis_timestamp": (datetime.now(UTC) - timedelta(hours=18)).isoformat(),
        "overall_health_score": 3.2,
        "dimension_scores": {
            "knowledge_distribution": _make_dimension(9.1, "Knowledge Distribution", "Original author left 18 months ago; no active maintainer"),
            "temporal_coupling": _make_dimension(7.8, "Temporal Coupling", "Auth and session modules are inseparable"),
            "churn_rate": _make_dimension(2.5, "Churn Rate", "Very low churn — code is essentially frozen"),
            "code_complexity": _make_dimension(8.8, "Code Complexity", "5 God Class candidates; AuthenticationManager has 60+ methods"),
            "code_duplication": _make_dimension(7.5, "Code Duplication", "4 Shotgun Surgery candidates"),
            "commit_quality": _make_dimension(6.0, "Commit Quality", "Last 20 commits are all hotfixes"),
            "bug_fix_ratio": _make_dimension(8.5, "Bug Fix Ratio", "85% of recent commits are bug fixes — system is in firefighting mode"),
            "dependency_currency": _make_dimension(9.2, "Dependency Currency", "Spring Boot 2.7 (EOL); Java 11 (EOL approaching)"),
            "dependency_vulnerability": _make_dimension(9.5, "Dependency Vulnerability", "7 CVEs including 2 critical; Spring4Shell variant exposure"),
            "license_risk": _make_dimension(1.0, "License Risk", "Clean license profile"),
            "api_stability": _make_dimension(5.5, "API Stability", "API unchanged but undocumented"),
            "documentation_coverage": _make_dimension(8.0, "Documentation Coverage", "No documentation; tribal knowledge lost"),
            "test_coverage": _make_dimension(2.0, "Test Coverage", "Estimated 20% coverage; no integration tests"),
            "deployment_frequency": _make_dimension(1.5, "Deployment Frequency", "Monthly hotfix deploys only"),
            "team_activity": _make_dimension(9.0, "Team Activity", "No dedicated maintainer; ad-hoc fixes only"),
        },
        "component_risks": [
            _make_component("auth", 8.9, {
                "knowledge_distribution": _make_dimension(9.1, "Knowledge Distribution", "No active maintainer"),
                "code_complexity": _make_dimension(8.8, "Code Complexity", "AuthenticationManager: 60+ methods"),
                "dependency_vulnerability": _make_dimension(9.5, "Dependency Vulnerability", "Critical CVEs"),
                "test_coverage": _make_dimension(2.0, "Test Coverage", "20% coverage"),
            }),
            _make_component("session", 7.2, {
                "temporal_coupling": _make_dimension(7.8, "Temporal Coupling", "Inseparable from auth"),
                "code_complexity": _make_dimension(7.0, "Code Complexity", "SessionManager complexity"),
            }),
            _make_component("token", 6.5, {
                "dependency_vulnerability": _make_dimension(8.0, "Dependency Vulnerability", "JWT library CVE"),
                "documentation_coverage": _make_dimension(7.5, "Documentation Coverage", "Undocumented token format"),
            }),
        ],
        "file_hotspots": [
            _make_hotspot("src/main/java/auth/AuthenticationManager.java", 9.6, {"complexity": 9.5, "ownership": 9.8, "vulnerability": 9.2}, "CRITICAL: This file is unmaintainable. Plan replacement, not refactoring.", "large"),
            _make_hotspot("src/main/java/session/SessionStore.java", 8.2, {"coupling": 8.5, "complexity": 7.8}, "Tightly coupled to AuthenticationManager; must be replaced together", "large"),
            _make_hotspot("src/main/java/token/JwtTokenProvider.java", 7.5, {"vulnerability": 8.0, "test_coverage": 7.0}, "JWT library has known CVE; upgrade or replace", "medium"),
            _make_hotspot("src/main/java/auth/PasswordEncoder.java", 7.0, {"vulnerability": 7.5, "currency": 6.5}, "Uses deprecated hashing algorithm; security risk", "medium"),
            _make_hotspot("src/main/java/config/SecurityConfig.java", 6.8, {"complexity": 7.0, "documentation": 6.5}, "500+ line config file; Spring Security rules undocumented", "medium"),
        ],
        "top_risks": [
            {"dimension": "dependency_vulnerability", "value": 9.5, "severity": "critical", "label": "Dependency Vulnerability", "evidence": "7 CVEs; 2 critical including Spring4Shell variant"},
            {"dimension": "dependency_currency", "value": 9.2, "severity": "critical", "label": "Dependency Currency", "evidence": "Spring Boot 2.7 EOL; Java 11 approaching EOL"},
            {"dimension": "knowledge_distribution", "value": 9.1, "severity": "critical", "label": "Knowledge Distribution", "evidence": "Original author departed; no maintainer"},
            {"dimension": "team_activity", "value": 9.0, "severity": "critical", "label": "Team Activity", "evidence": "No dedicated maintainer"},
            {"dimension": "code_complexity", "value": 8.8, "severity": "high", "label": "Code Complexity", "evidence": "5 God Classes; AuthenticationManager: 60+ methods"},
        ],
        "ai_narrative": (
            "## Decommission Assessment: Nexus Auth Service\n\n"
            "**Overall Risk: CRITICAL (3.2/10)**\n\n"
            "The Nexus Auth Service is in a critical state and decommission should be accelerated. "
            "This is a security liability in its current form.\n\n"
            "**Immediate Risks:**\n\n"
            "1. **Active Security Vulnerabilities (CRITICAL)**: 7 known CVEs including 2 critical-severity "
            "issues. The Spring4Shell variant exposure on the authentication endpoint is exploitable. "
            "This alone justifies emergency remediation or accelerated decommission.\n\n"
            "2. **Complete Knowledge Loss**: The original author departed 18 months ago. No internal "
            "engineer has meaningful understanding of the 60+ method `AuthenticationManager`. The system "
            "is in firefighting mode — 85% of recent commits are bug fixes.\n\n"
            "3. **Technology Debt**: Running on EOL Spring Boot 2.7 and approaching-EOL Java 11. "
            "Upgrade paths are complex due to the monolithic architecture.\n\n"
            "**Recommendation**: Do NOT invest in refactoring. Instead: (a) immediately patch the 2 critical "
            "CVEs as a stopgap, (b) fast-track migration to the new identity platform, (c) set a hard "
            "decommission deadline of Q3 with no new feature work on this service."
        ),
        "pdf_output_path": "",
    },
}

# -- Seed trend data (for the trends chart) --------------------------------

SEED_TRENDS: dict[str, list[dict]] = {
    "prj_demo_acme01": [
        {"period": "2025-W40", "features": 8, "bugs": 12, "refactors": 2, "total_commits": 22},
        {"period": "2025-W44", "features": 6, "bugs": 15, "refactors": 1, "total_commits": 22},
        {"period": "2025-W48", "features": 10, "bugs": 9, "refactors": 4, "total_commits": 23},
        {"period": "2025-W52", "features": 5, "bugs": 11, "refactors": 3, "total_commits": 19},
        {"period": "2026-W04", "features": 7, "bugs": 14, "refactors": 2, "total_commits": 23},
        {"period": "2026-W08", "features": 9, "bugs": 10, "refactors": 5, "total_commits": 24},
    ],
    "prj_demo_atlas02": [
        {"period": "2025-W40", "features": 18, "bugs": 5, "refactors": 8, "total_commits": 31},
        {"period": "2025-W44", "features": 15, "bugs": 6, "refactors": 10, "total_commits": 31},
        {"period": "2025-W48", "features": 20, "bugs": 4, "refactors": 7, "total_commits": 31},
        {"period": "2025-W52", "features": 12, "bugs": 3, "refactors": 9, "total_commits": 24},
        {"period": "2026-W04", "features": 16, "bugs": 5, "refactors": 6, "total_commits": 27},
        {"period": "2026-W08", "features": 22, "bugs": 4, "refactors": 8, "total_commits": 34},
    ],
    "prj_demo_titan03": [
        {"period": "2025-W40", "features": 5, "bugs": 8, "refactors": 2, "total_commits": 15},
        {"period": "2025-W44", "features": 3, "bugs": 10, "refactors": 1, "total_commits": 14},
        {"period": "2025-W48", "features": 8, "bugs": 6, "refactors": 4, "total_commits": 18},
        {"period": "2025-W52", "features": 4, "bugs": 7, "refactors": 3, "total_commits": 14},
        {"period": "2026-W04", "features": 6, "bugs": 9, "refactors": 2, "total_commits": 17},
        {"period": "2026-W08", "features": 7, "bugs": 5, "refactors": 5, "total_commits": 17},
    ],
    "prj_demo_nexus04": [
        {"period": "2025-W40", "features": 0, "bugs": 4, "refactors": 0, "total_commits": 4},
        {"period": "2025-W44", "features": 0, "bugs": 6, "refactors": 1, "total_commits": 7},
        {"period": "2025-W48", "features": 1, "bugs": 5, "refactors": 0, "total_commits": 6},
        {"period": "2025-W52", "features": 0, "bugs": 3, "refactors": 0, "total_commits": 3},
        {"period": "2026-W04", "features": 0, "bugs": 7, "refactors": 0, "total_commits": 7},
        {"period": "2026-W08", "features": 0, "bugs": 4, "refactors": 1, "total_commits": 5},
    ],
}


async def seed() -> None:
    """Populate the database with demo projects and analysis results."""
    from infrastructure.persistence.database import init_db, async_session_factory
    from infrastructure.persistence.models import ProjectModel
    from presentation.api.routers.analysis import _analysis_results, _analysis_status, _trend_data
    from presentation.api.schemas import AnalysisStatus
    from application.dtos.analysis_dto import AnalysisResultDTO, RiskScoreDTO, ComponentRiskDTO, FileHotspotDTO

    print("Initialising database...")
    await init_db()

    async with async_session_factory() as session:
        # Check if already seeded
        from sqlalchemy import select, func
        count = (await session.execute(select(func.count()).select_from(ProjectModel))).scalar()
        if count and count > 0:
            print(f"Database already has {count} projects. Clearing for fresh seed...")
            await session.execute(ProjectModel.__table__.delete())
            await session.commit()

        now = datetime.now(UTC)
        for i, proj_data in enumerate(SEED_PROJECTS):
            project = ProjectModel(
                project_id=proj_data["project_id"],
                name=proj_data["name"],
                description=proj_data["description"],
                scenario=proj_data["scenario"],
                analysis_status=proj_data["analysis_status"],
                overall_health_score=proj_data["overall_health_score"],
                owner_id=proj_data["owner_id"],
                created_at=now - timedelta(days=30 - i * 5),
                updated_at=now - timedelta(hours=i * 12),
            )
            session.add(project)
            print(f"  + {proj_data['name']} ({proj_data['project_id']})")

        await session.commit()
        print(f"\nInserted {len(SEED_PROJECTS)} projects into database.")

    # Populate in-memory analysis results (used by report endpoints)
    for project_id, analysis in SEED_ANALYSIS.items():
        # Build DTO from seed data
        dim_scores = {}
        for dim_name, dim_data in analysis["dimension_scores"].items():
            dim_scores[dim_name] = RiskScoreDTO(
                value=dim_data["value"],
                severity=dim_data["severity"],
                label=dim_data["label"],
                evidence=dim_data["evidence"],
            )

        comp_risks = []
        for comp in analysis.get("component_risks", []):
            comp_dim_scores = {}
            for d_name, d_data in comp.get("dimension_scores", {}).items():
                comp_dim_scores[d_name] = RiskScoreDTO(
                    value=d_data["value"],
                    severity=d_data["severity"],
                    label=d_data["label"],
                    evidence=d_data["evidence"],
                )
            comp_risks.append(ComponentRiskDTO(
                component_name=comp["component_name"],
                composite_score=comp["composite_score"],
                systemic_risk=comp["systemic_risk"],
                dimension_scores=comp_dim_scores,
            ))

        hotspots = []
        for hs in analysis.get("file_hotspots", []):
            hotspots.append(FileHotspotDTO(
                file_path=hs["file_path"],
                composite_risk_score=hs["composite_risk_score"],
                risk_indicators=hs["risk_indicators"],
                refactoring_recommendation=hs["refactoring_recommendation"],
                effort_estimate=hs["effort_estimate"],
            ))

        dto = AnalysisResultDTO(
            project_name=analysis["project_name"],
            scenario=analysis["scenario"],
            analysis_timestamp=analysis["analysis_timestamp"],
            overall_health_score=analysis["overall_health_score"],
            dimension_scores=dim_scores,
            component_risks=comp_risks,
            file_hotspots=hotspots,
            top_risks=analysis.get("top_risks", []),
            ai_narrative=analysis.get("ai_narrative", ""),
            pdf_output_path=analysis.get("pdf_output_path", ""),
        )

        _analysis_results[project_id] = dto
        _analysis_status[project_id] = {
            "status": AnalysisStatus.completed,
            "started_at": analysis["analysis_timestamp"],
            "completed_at": analysis["analysis_timestamp"],
            "message": f"Analysis complete. Health score: {analysis['overall_health_score']}/10",
        }

    # Populate trend data
    for project_id, trends in SEED_TRENDS.items():
        _trend_data[project_id] = trends

    print(f"Loaded {len(SEED_ANALYSIS)} analysis results and {len(SEED_TRENDS)} trend datasets into memory.")
    print("\nSeed complete! Start the server with: make api")


if __name__ == "__main__":
    asyncio.run(seed())
