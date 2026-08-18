# ==============================================================================
# ENTERPRISE PRACTICE: Elsamag IT Solutions
# LEAD TECHNICAL CONSULTANT: Samuel Chinwendu Agu
# FILE: src/sprint_governance_engine.py
# REPOSITORY: pm-ecom-checkout-agile-migration-engine
# OBJECTIVE: Production Agile Sprint Governance, Telemetry Validation & Quality Gate Engine
# ==============================================================================

import json
import logging
import math
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # Fallback gracefully if PyYAML is not pre-installed in environment

# Configure structured enterprise logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Elsamag-SprintGov] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("SprintGovernanceEngine")


@dataclass
class UserStory:
    story_id: str
    title: str
    story_points: int
    epic_id: str
    risk_level: str
    acceptance_criteria: List[str] = field(default_factory=list)
    unit_test_coverage_pct: float = 0.0
    integration_tests_passed: bool = False
    p99_latency_ms: float = 0.0
    security_scan_passed: bool = False
    dod_cleared: bool = False
    escaped_defects: int = 0


@dataclass
class CanaryTelemetryMetric:
    stage_id: str
    traffic_pct: float
    sample_size: int
    http_5xx_rate_pct: float
    p99_latency_ms: float
    cart_abandonment_spike_pct: float
    circuit_breaker_triggered: bool = False


@dataclass
class SprintAuditReport:
    sprint_id: str
    framework: str
    timestamp_utc: str
    target_velocity_points: int
    committed_story_points: int
    completed_story_points: int
    velocity_stability_pct: float
    velocity_variance_pct: float
    escaped_defects_total: int
    avg_p99_latency_ms: float
    max_p99_latency_ms: float
    overall_quality_gate_passed: bool
    canary_cutover_approved: bool
    audit_findings: List[str] = field(default_factory=list)


class AgileSprintGovernanceEngine:
    """
    Enterprise Scrum governance and release-readiness engine designed by
    Elsamag IT Solutions to validate sprint DoD adherence, calculate velocity
    stability indexes, and audit telemetry against canary SLAs.
    """

    def __init__(self, sprint_id: str = "Sprint-06", target_velocity: int = 50):
        self.sprint_id = sprint_id
        self.target_velocity = target_velocity
        self.stories: List[UserStory] = []
        self.canary_metrics: List[CanaryTelemetryMetric] = []
        self.config_params: Dict[str, Any] = {}
        self.telemetry_thresholds: Dict[str, Any] = {}

    def load_parameters_from_yaml(self, yaml_path: str) -> bool:
        """Loads configuration from agile_sprint_parameters.yaml."""
        p = Path(yaml_path)
        if not p.exists():
            logger.warning(f"YAML config file not found at '{yaml_path}'. Operating with default parameters.")
            return False

        if yaml is None:
            logger.warning("PyYAML not installed. Using internal defaults.")
            return False

        try:
            with open(p, "r", encoding="utf-8") as f:
                self.config_params = yaml.safe_load(f)
            sprint_gov = self.config_params.get("sprint_cadence_governance", {})
            self.target_velocity = sprint_gov.get("target_velocity_points", self.target_velocity)
            logger.info(f"Loaded sprint governance configuration from {yaml_path}")
            return True
        except Exception as ex:
            logger.error(f"Failed parsing YAML config: {ex}")
            return False

    def load_telemetry_thresholds_from_json(self, json_path: str) -> bool:
        """Loads telemetry thresholds and SLAs from telemetry_thresholds.json."""
        p = Path(json_path)
        if not p.exists():
            logger.warning(f"Telemetry JSON not found at '{json_path}'. Applying baseline SLAs.")
            return False

        try:
            with open(p, "r", encoding="utf-8") as f:
                self.telemetry_thresholds = json.load(f)
            logger.info(f"Loaded telemetry SLAs from {json_path}")
            return True
        except Exception as ex:
            logger.error(f"Failed parsing JSON telemetry thresholds: {ex}")
            return False

    def register_story(self, story: UserStory) -> None:
        """Registers a user story to the active sprint backlog."""
        self.stories.append(story)
        logger.info(
            f"Registered Story [{story.story_id}] - '{story.title}' "
            f"({story.story_points} pts) | Risk: {story.risk_level}"
        )

    def register_canary_metric(self, metric: CanaryTelemetryMetric) -> None:
        """Registers telemetry data collected during a canary rollout stage."""
        self.canary_metrics.append(metric)
        logger.info(
            f"Logged Canary Telemetry: {metric.stage_id} ({metric.traffic_pct}% traffic) "
            f"| P99: {metric.p99_latency_ms}ms | 5XX: {metric.http_5xx_rate_pct}%"
        )

    def audit_definition_of_done(
        self,
        min_unit_test_pct: float = 95.0,
        hard_latency_ceiling_ms: float = 200.0
    ) -> Tuple[bool, List[str]]:
        """
        Audits every user story against rigorous enterprise Definition of Done criteria.
        """
        findings = []
        all_passed = True

        for story in self.stories:
            story_passed = True
            
            # Unit Test Coverage Gate
            if story.unit_test_coverage_pct < min_unit_test_pct:
                story_passed = False
                findings.append(
                    f"Story {story.story_id} failed Unit Test gate: "
                    f"{story.unit_test_coverage_pct}% < {min_unit_test_pct}% threshold."
                )

            # Integration Test Gate
            if not story.integration_tests_passed:
                story_passed = False
                findings.append(f"Story {story.story_id} failed Integration Test verification.")

            # Hard Latency Ceiling Gate
            if story.p99_latency_ms > hard_latency_ceiling_ms:
                story_passed = False
                findings.append(
                    f"Story {story.story_id} breached hard latency ceiling: "
                    f"{story.p99_latency_ms}ms > {hard_latency_ceiling_ms}ms."
                )

            # Security and Compliance Gate
            if not story.security_scan_passed:
                story_passed = False
                findings.append(f"Story {story.story_id} failed SAST/DAST or PCI compliance checks.")

            # Escaped Defects
            if story.escaped_defects > 0:
                story_passed = False
                findings.append(f"Story {story.story_id} recorded {story.escaped_defects} escaped defect(s).")

            story.dod_cleared = story_passed
            if not story_passed:
                all_passed = False

        return all_passed, findings

    def evaluate_canary_stages(
        self,
        p99_max_ms: float = 180.0,
        error_rate_max_pct: float = 0.05,
        abandonment_max_pct: float = 2.5
    ) -> Tuple[bool, List[str]]:
        """
        Evaluates canary rollout telemetry against circuit breaker triggers.
        """
        canary_findings = []
        canary_approved = True

        for m in self.canary_metrics:
            if m.http_5xx_rate_pct > error_rate_max_pct:
                canary_approved = False
                m.circuit_breaker_triggered = True
                canary_findings.append(
                    f"Circuit Breaker Triggered on {m.stage_id}: 5XX rate {m.http_5xx_rate_pct}% "
                    f"exceeded threshold of {error_rate_max_pct}%"
                )

            if m.p99_latency_ms > p99_max_ms:
                canary_approved = False
                m.circuit_breaker_triggered = True
                canary_findings.append(
                    f"Circuit Breaker Triggered on {m.stage_id}: P99 Latency {m.p99_latency_ms}ms "
                    f"exceeded threshold of {p99_max_ms}ms"
                )

            if m.cart_abandonment_spike_pct > abandonment_max_pct:
                canary_approved = False
                m.circuit_breaker_triggered = True
                canary_findings.append(
                    f"Circuit Breaker Triggered on {m.stage_id}: Cart abandonment spike "
                    f"{m.cart_abandonment_spike_pct}% exceeded threshold of {abandonment_max_pct}%"
                )

        return canary_approved, canary_findings

    def run_sprint_audit(self) -> SprintAuditReport:
        """
        Executes end-to-end sprint health calculation, quality gate checks,
        and generates an immutable audit ledger.
        """
        committed_pts = sum(s.story_points for s in self.stories)
        
        # Audit DoD
        dod_passed, dod_findings = self.audit_definition_of_done()
        
        # Calculate completed points based on cleared DoD
        completed_pts = sum(s.story_points for s in self.stories if s.dod_cleared)
        escaped_defects = sum(s.escaped_defects for s in self.stories)

        # Velocity Stability & Variance
        stability_pct = (
            (completed_pts / self.target_velocity) * 100.0
            if self.target_velocity > 0 else 0.0
        )
        variance_pct = abs(100.0 - stability_pct)

        # Latency Metrics
        latencies = [s.p99_latency_ms for s in self.stories if s.p99_latency_ms > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        max_latency = max(latencies) if latencies else 0.0

        # Audit Canary Rollout
        canary_approved, canary_findings = self.evaluate_canary_stages()

        all_findings = dod_findings + canary_findings
        overall_pass = dod_passed and canary_approved and (escaped_defects == 0)

        report = SprintAuditReport(
            sprint_id=self.sprint_id,
            framework="Scrum-Agile-Iterative (CI/CD Canary Routing)",
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            target_velocity_points=self.target_velocity,
            committed_story_points=committed_pts,
            completed_story_points=completed_pts,
            velocity_stability_pct=round(stability_pct, 2),
            velocity_variance_pct=round(variance_pct, 2),
            escaped_defects_total=escaped_defects,
            avg_p99_latency_ms=round(avg_latency, 2),
            max_p99_latency_ms=round(max_latency, 2),
            overall_quality_gate_passed=overall_pass,
            canary_cutover_approved=canary_approved,
            audit_findings=all_findings
        )
        return report

    def render_console_dashboard(self, report: SprintAuditReport) -> None:
        """Renders an executive ASCII audit dashboard to stdout."""
        border = "=" * 80
        divider = "-" * 80
        print(f"\n{border}")
        print("  ELSAMAG IT SOLUTIONS - ENTERPRISE SPRINT GOVERNANCE & TELEMETRY ENGINE")
        print("  Lead Technical Consultant: Samuel Chinwendu Agu | Repository: pm-ecom-checkout-agile-migration-engine")
        print(f"{border}")
        print(f" SPRINT ID                  : {report.sprint_id}")
        print(f" METHODOLOGY                : {report.framework}")
        print(f" AUDIT TIMESTAMP (UTC)      : {report.timestamp_utc}")
        print(divider)
        print(" STORY EXECUTION & DEFINITION OF DONE BREAKDOWN:")
        for s in self.stories:
            status_symbol = "✔ [PASS]" if s.dod_cleared else "✖ [FAIL]"
            print(
                f"  [{s.story_id}] {s.title.ljust(44)} "
                f"| {str(s.story_points).rjust(2)} pts | {s.p99_latency_ms:5.1f}ms | {status_symbol}"
            )
        print(divider)
        print(" CANARY TELEMETRY STAGE AUDIT:")
        for c in self.canary_metrics:
            c_status = "✖ [TRIPPED]" if c.circuit_breaker_triggered else "✔ [HEALTHY]"
            print(
                f"  [{c.stage_id}] Traffic: {c.traffic_pct:5.1f}% | Samples: {c.sample_size:5d} "
                f"| 5XX: {c.http_5xx_rate_pct:.3f}% | P99: {c.p99_latency_ms:5.1f}ms | {c_status}"
            )
        print(divider)
        print(" SPRINT PERFORMANCE KPIS:")
        print(f"  • Velocity Target         : {report.target_velocity_points} pts")
        print(f"  • Completed Velocity      : {report.completed_story_points} / {report.committed_story_points} pts")
        print(f"  • Velocity Stability Index: {report.velocity_stability_pct}% (Variance: {report.velocity_variance_pct}%)")
        print(f"  • Escaped Defects         : {report.escaped_defects_total}")
        print(f"  • Average P99 Latency     : {report.avg_p99_latency_ms} ms (Peak: {report.max_p99_latency_ms} ms)")
        print(f"  • Quality Gates Cleared   : {'PASSED' if report.overall_quality_gate_passed else 'FAILED'}")
        print(f"  • Canary 100% Cutover OK  : {'AUTHORIZED' if report.canary_cutover_approved else 'BLOCKED'}")
        
        if report.audit_findings:
            print(divider)
            print(" AUDIT FINDINGS & WARNINGS:")
            for f in report.audit_findings:
                print(f"  ⚠ {f}")
        else:
            print(divider)
            print(" AUDIT FINDINGS & WARNINGS : ZERO NON-COMPLIANCES DETECTED. READY FOR MERGE.")

        print(f"{border}\n")


def execute_production_sprint_simulation() -> None:
    """Simulates production execution with official sprint epics and canary telemetry."""
    engine = AgileSprintGovernanceEngine(sprint_id="Sprint-06", target_velocity=50)

    # [cite_start]1. Register Stories matching config/agile_sprint_parameters.yaml [cite: 1587-1594]
    engine.register_story(
        UserStory(
            story_id="ST-101",
            title="Apple Pay & Stripe API V3 Integration",
            story_points=8,
            epic_id="EPIC-01-AUTH-GATEWAY",
            risk_level="HIGH",
            acceptance_criteria=["Stripe v3 webhooks", "Apple Pay <150ms", "Coverage >=95%"],
            unit_test_coverage_pct=98.4,
            integration_tests_passed=True,
            p99_latency_ms=142.5,
            security_scan_passed=True,
            escaped_defects=0
        )
    )

    engine.register_story(
        UserStory(
            story_id="ST-102",
            title="Real-Time Tokenized Fraud Detection",
            story_points=5,
            epic_id="EPIC-01-AUTH-GATEWAY",
            risk_level="HIGH",
            acceptance_criteria=["ML Tokenization", "Zero plaintext logs", "Overhead <=25ms"],
            unit_test_coverage_pct=96.2,
            integration_tests_passed=True,
            p99_latency_ms=168.0,
            security_scan_passed=True,
            escaped_defects=0
        )
    )

    engine.register_story(
        UserStory(
            story_id="ST-103",
            title="Alternative Payment Methods (Klarna & PayPal)",
            story_points=5,
            epic_id="EPIC-01-AUTH-GATEWAY",
            risk_level="MEDIUM",
            acceptance_criteria=["Klarna installment hook", "PayPal Commerce 14 fiat currencies"],
            unit_test_coverage_pct=97.0,
            integration_tests_passed=True,
            p99_latency_ms=155.4,
            security_scan_passed=True,
            escaped_defects=0
        )
    )

    engine.register_story(
        UserStory(
            story_id="ST-201",
            title="Deploy Prometheus & Datadog APM Hooks",
            story_points=5,
            epic_id="EPIC-02-CART-TELEMETRY",
            risk_level="LOW",
            acceptance_criteria=["Millisecond conversion metrics", "P50/P95/P99 latency tracking"],
            unit_test_coverage_pct=99.1,
            integration_tests_passed=True,
            p99_latency_ms=110.2,
            security_scan_passed=True,
            escaped_defects=0
        )
    )

    engine.register_story(
        UserStory(
            story_id="ST-202",
            title="Dynamic Canary Traffic Router Implementation",
            story_points=8,
            epic_id="EPIC-02-CART-TELEMETRY",
            risk_level="CRITICAL",
            acceptance_criteria=["Phased routing (5%-100%)", "Session affinity", "Health-based diversion"],
            unit_test_coverage_pct=97.8,
            integration_tests_passed=True,
            p99_latency_ms=135.8,
            security_scan_passed=True,
            escaped_defects=0
        )
    )

    engine.register_story(
        UserStory(
            story_id="ST-301",
            title="Zero-Downtime Instant Rollback Circuit Breakers",
            story_points=12,
            epic_id="EPIC-03-CUTOVER-RESILIENCE",
            risk_level="CRITICAL",
            acceptance_criteria=["Rollback trigger >0.05% error", "Fallback <500ms", "Zero session drop"],
            unit_test_coverage_pct=100.0,
            integration_tests_passed=True,
            p99_latency_ms=128.4,
            security_scan_passed=True,
            escaped_defects=0
        )
    )

    # [cite_start]2. Register Live Canary Rollout Metrics matching config/telemetry_thresholds.json [cite: 1598-1600]
    engine.register_canary_metric(
        CanaryTelemetryMetric(
            stage_id="STAGE-01-CANARY",
            traffic_pct=5.0,
            sample_size=12500,
            http_5xx_rate_pct=0.008,
            p99_latency_ms=138.4,
            cart_abandonment_spike_pct=0.12
        )
    )

    engine.register_canary_metric(
        CanaryTelemetryMetric(
            stage_id="STAGE-02-CANARY",
            traffic_pct=25.0,
            sample_size=62000,
            http_5xx_rate_pct=0.015,
            p99_latency_ms=144.1,
            cart_abandonment_spike_pct=0.18
        )
    )

    engine.register_canary_metric(
        CanaryTelemetryMetric(
            stage_id="STAGE-03-CANARY",
            traffic_pct=50.0,
            sample_size=124000,
            http_5xx_rate_pct=0.021,
            p99_latency_ms=148.6,
            cart_abandonment_spike_pct=0.25
        )
    )

    engine.register_canary_metric(
        CanaryTelemetryMetric(
            stage_id="STAGE-04-CANARY",
            traffic_pct=100.0,
            sample_size=250000,
            http_5xx_rate_pct=0.024,
            p99_latency_ms=151.2,
            cart_abandonment_spike_pct=0.30
        )
    )

    # 3. Run Sprint Audit and Print Report
    report = engine.run_sprint_audit()
    engine.render_console_dashboard(report)

    # Output formatted JSON report for continuous integration pipeline artifact storage
    json_output_path = Path("benchmarks/sprint_audit_summary.json")
    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, indent=2)
    logger.info(f"Immutable audit artifact saved to {json_output_path.resolve()}")


if __name__ == "__main__":
    execute_production_sprint_simulation()
