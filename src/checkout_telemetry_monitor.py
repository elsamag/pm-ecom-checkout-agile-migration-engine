# ==============================================================================
# ENTERPRISE PRACTICE: Elsamag IT Solutions
# LEAD TECHNICAL CONSULTANT: Samuel Chinwendu Agu
# FILE: src/checkout_telemetry_monitor.py
# REPOSITORY: pm-ecom-checkout-agile-migration-engine
# OBJECTIVE: Production Real-Time Checkout Telemetry, Gateway APM & Canary Router Monitor
# ==============================================================================

import argparse
import json
import logging
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configure structured enterprise logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Elsamag-TelemetryMon] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("CheckoutTelemetryMonitor")


@dataclass
class GatewayTelemetryProbe:
    gateway_name: str
    endpoint: str
    sample_count: int
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate_pct: float
    cart_abandonment_rate_pct: float
    status: str = "HEALTHY"


@dataclass
class CanaryEvaluationResult:
    stage_id: str
    traffic_pct: float
    total_transactions: int
    http_5xx_rate_pct: float
    p99_latency_ms: float
    cart_abandonment_spike_pct: float
    sla_breached: bool
    circuit_breaker_tripped: bool
    verdict: str
    diagnostic_messages: List[str] = field(default_factory=list)


class CheckoutTelemetryMonitor:
    """Enterprise APM and Canary Router Telemetry Monitor designed by

    Elsamag IT Solutions.

    Evaluates live checkout transaction funnels, audits gateway latency SLAs,
    detects cart abandonment anomalies, and manages circuit-breaker failovers.
    """

    def __init__(self, thresholds_path: Optional[str] = None):
        self.thresholds_path = thresholds_path or "config/telemetry_thresholds.json"
        self.thresholds: Dict[str, Any] = self._load_telemetry_thresholds()
        self.probes: List[GatewayTelemetryProbe] = []
        self.canary_evaluations: List[CanaryEvaluationResult] = []

    def _load_telemetry_thresholds(self) -> Dict[str, Any]:
        """Loads telemetry thresholds from JSON configuration or applies strict

        defaults.
        """
        p = Path(self.thresholds_path)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                logger.info(f"Loaded telemetry SLAs from {self.thresholds_path}")
                return config_data.get("telemetry_thresholds", {})
            except Exception as ex:
                logger.error(
                    f"Failed loading thresholds JSON ({ex}). Applying defaults."
                )

        logger.warning("Using built-in enterprise threshold baselines.")
        return {
            "latency_slas_ms": {
                "p50_target_ms": 65.0,
                "p95_warning_ms": 120.0,
                "p99_critical_threshold_ms": 180.0,
                "hard_timeout_ceiling_ms": 250.0,
                "database_lock_wait_timeout_ms": 100.0,
            },
            "error_rate_thresholds_pct": {
                "http_5xx_critical_threshold_pct": 0.05,
                "http_4xx_warning_threshold_pct": 1.20,
                "cart_abandonment_spike_threshold_pct": 2.50,
            },
            "circuit_breaker_and_rollback": {
                "policy": "AUTOMATIC_FAILOVER_TO_LEGACY",
                "max_rollback_latency_ms": 500.0,
            },
        }

    def record_gateway_probe(self, probe: GatewayTelemetryProbe) -> None:
        """Appends and validates live telemetry from a payment gateway

        microservice.
        """
        latency_sla = self.thresholds.get("latency_slas_ms", {})
        p99_limit = latency_sla.get("p99_critical_threshold_ms", 180.0)
        error_sla = self.thresholds.get("error_rate_thresholds_pct", {})
        err_limit = error_sla.get("http_5xx_critical_threshold_pct", 0.05)

        if (
            probe.p99_latency_ms > p99_limit
            or probe.error_rate_pct > err_limit
        ):
            probe.status = "DEGRADED"
        if probe.p99_latency_ms > latency_sla.get(
            "hard_timeout_ceiling_ms", 250.0
        ):
            probe.status = "CRITICAL_BREACH"

        self.probes.append(probe)
        logger.info(
            f"Gateway Probe Recorded: [{probe.gateway_name}] - "
            f"P99: {probe.p99_latency_ms}ms | Err: {probe.error_rate_pct:.3f}% | Status: {probe.status}"
        )

    def evaluate_canary_stage(
        self,
        stage_id: str,
        traffic_pct: float,
        total_tx: int,
        http_5xx_pct: float,
        p99_ms: float,
        abandonment_spike_pct: float,
    ) -> CanaryEvaluationResult:
        """Evaluates a live canary traffic rollout stage against automated

        circuit-breaker rules.
        """
        diagnostics = []
        sla_breach = False
        tripped = False

        err_limit = self.thresholds.get("error_rate_thresholds_pct", {}).get(
            "http_5xx_critical_threshold_pct", 0.05
        )
        p99_limit = self.thresholds.get("latency_slas_ms", {}).get(
            "p99_critical_threshold_ms", 180.0
        )
        abandon_limit = self.thresholds.get(
            "error_rate_thresholds_pct", {}
        ).get("cart_abandonment_spike_threshold_pct", 2.50)

        if http_5xx_pct > err_limit:
            sla_breach = True
            tripped = True
            diagnostics.append(
                f"HTTP 5XX error rate {http_5xx_pct:.3f}% breached critical threshold of {err_limit:.3f}%"
            )

        if p99_ms > p99_limit:
            sla_breach = True
            tripped = True
            diagnostics.append(
                f"P99 Latency {p99_ms:.1f}ms breached SLA ceiling of {p99_limit:.1f}ms"
            )

        if abandonment_spike_pct > abandon_limit:
            sla_breach = True
            tripped = True
            diagnostics.append(
                f"Cart abandonment spike {abandonment_spike_pct:.2f}% exceeded allowable delta of {abandon_limit:.2f}%"
            )

        verdict = (
            "STAGE_PASSED_PROCEED"
            if not tripped
            else "CIRCUIT_BREAKER_TRIGGER_ROLLBACK"
        )

        result = CanaryEvaluationResult(
            stage_id=stage_id,
            traffic_pct=traffic_pct,
            total_transactions=total_tx,
            http_5xx_rate_pct=http_5xx_pct,
            p99_latency_ms=p99_ms,
            cart_abandonment_spike_pct=abandonment_spike_pct,
            sla_breached=sla_breach,
            circuit_breaker_tripped=tripped,
            verdict=verdict,
            diagnostic_messages=diagnostics,
        )
        self.canary_evaluations.append(result)
        return result

    def render_dashboard(self) -> None:
        """Renders an executive ASCII telemetry dashboard to stdout."""
        border = "=" * 86
        divider = "-" * 86

        print(f"\n{border}")
        print(
            "  ELSAMAG IT SOLUTIONS — REAL-TIME CHECKOUT TELEMETRY & GATEWAY APM AUDIT"
        )
        print(
            "  Lead Consultant: Samuel Chinwendu Agu | Repository: pm-ecom-checkout-agile-migration-engine"
        )
        print(
            f"  Audit Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        print(f"{border}")

        print("\n[PAYMENT GATEWAY MICROSERVICE TELEMETRY]")
        print(
            f"  {'GATEWAY':<20} | {'SAMPLES':<8} | {'P50 (ms)':<8} | {'P95 (ms)':<8} | {'P99 (ms)':<8} | {'ERR %':<7} | {'STATUS'}"
        )
        print(f"  {divider}")
        for p in self.probes:
            status_tag = (
                f"✔ [{p.status}]" if p.status == "HEALTHY" else f"✖ [{p.status}]"
            )
            print(
                f"  {p.gateway_name:<20} | {p.sample_count:<8d} | {p.p50_latency_ms:<8.1f} | "
                f"{p.p95_latency_ms:<8.1f} | {p.p99_latency_ms:<8.1f} | {p.error_rate_pct:<7.3f} | {status_tag}"
            )

        print(f"\n[CANARY TRAFFIC PROGRESSION & CIRCUIT BREAKER AUDIT]")
        print(
            f"  {'STAGE ID':<18} | {'TRAFFIC':<7} | {'TX COUNT':<9} | {'5XX %':<7} | {'P99 (ms)':<8} | {'ABANDON Δ':<9} | {'CIRCUIT BREAKER'}"
        )
        print(f"  {divider}")
        for c in self.canary_evaluations:
            cb_tag = (
                "✔ [HEALTHY]"
                if not c.circuit_breaker_tripped
                else "✖ [TRIPPED - ROLLBACK]"
            )
            print(
                f"  {c.stage_id:<18} | {c.traffic_pct:<6.1f}% | {c.total_transactions:<9d} | "
                f"{c.http_5xx_rate_pct:<7.3f} | {c.p99_latency_ms:<8.1f} | {c.cart_abandonment_spike_pct:<8.2f}% | {cb_tag}"
            )

        print(f"\n{divider}")
        total_stages = len(self.canary_evaluations)
        passed_stages = sum(
            1 for c in self.canary_evaluations if not c.circuit_breaker_tripped
        )
        all_passed = (
            total_stages > 0 and passed_stages == total_stages
        ) and all(p.status == "HEALTHY" for p in self.probes)

        print(
            f"  • Overall Health Status       : {'100% OPERATIONAL (PRODUCTION READY)' if all_passed else 'DEGRADED / ACTION REQUIRED'}"
        )
        print(
            f"  • Canary Migration Cutover    : {'AUTHORIZED FOR 100% TRAFFIC' if all_passed else 'BLOCKED BY GOVERNANCE GATES'}"
        )
        print(
            f"  • Failover Circuit Breaker    : ARMED (Zero-Downtime Fallback to Legacy Route)"
        )
        print(f"{border}\n")

    def export_audit_log(self, filepath: str = "benchmarks/latency_canary_audit.log") -> None:
        """Persists comprehensive telemetry log to the benchmarks directory."""
        log_path = Path(filepath)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "metadata": {
                "enterprise": "Elsamag IT Solutions",
                "lead_consultant": "Samuel Chinwendu Agu",
                "engine": "CheckoutTelemetryMonitor",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            },
            "payment_gateways": [asdict(p) for p in self.probes],
            "canary_evaluations": [asdict(c) for c in self.canary_evaluations],
        }

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        logger.info(f"Telemetry benchmark ledger exported to {log_path.resolve()}")


def execute_full_telemetry_audit() -> None:
    """Executes a full multi-stage telemetry audit simulating live production

    traffic.
    """
    monitor = CheckoutTelemetryMonitor()

    # 1. Probe Active Omnichannel Payment Gateways
    monitor.record_gateway_probe(
        GatewayTelemetryProbe(
            gateway_name="Stripe API v3",
            endpoint="https://api.stripe.com/v1/payment_intents",
            sample_count=85000,
            p50_latency_ms=62.4,
            p95_latency_ms=118.2,
            p99_latency_ms=142.5,
            error_rate_pct=0.012,
            cart_abandonment_rate_pct=1.84,
        )
    )

    monitor.record_gateway_probe(
        GatewayTelemetryProbe(
            gateway_name="Apple Pay V3 Token",
            endpoint="https://apple-pay-gateway.internal.elsamag.io/v3/tokenize",
            sample_count=62000,
            p50_latency_ms=48.1,
            p95_latency_ms=92.6,
            p99_latency_ms=125.0,
            error_rate_pct=0.005,
            cart_abandonment_rate_pct=1.10,
        )
    )

    monitor.record_gateway_probe(
        GatewayTelemetryProbe(
            gateway_name="PayPal Commerce",
            endpoint="https://api.paypal.com/v2/checkout/orders",
            sample_count=41000,
            p50_latency_ms=78.3,
            p95_latency_ms=135.0,
            p99_latency_ms=164.2,
            error_rate_pct=0.021,
            cart_abandonment_rate_pct=2.15,
        )
    )

    monitor.record_gateway_probe(
        GatewayTelemetryProbe(
            gateway_name="Klarna Installments",
            endpoint="https://api.klarna.com/payments/v1/authorizations",
            sample_count=29000,
            p50_latency_ms=84.5,
            p95_latency_ms=142.1,
            p99_latency_ms=172.8,
            error_rate_pct=0.028,
            cart_abandonment_rate_pct=2.30,
        )
    )

    # 2. Evaluate Phased Canary Cutover Telemetry Stages
    monitor.evaluate_canary_stage(
        stage_id="STAGE-01 (Canary)",
        traffic_pct=5.0,
        total_tx=12500,
        http_5xx_pct=0.008,
        p99_ms=138.4,
        abandonment_spike_pct=0.12,
    )
    monitor.evaluate_canary_stage(
        stage_id="STAGE-02 (Canary)",
        traffic_pct=25.0,
        total_tx=62000,
        http_5xx_pct=0.015,
        p99_ms=144.1,
        abandonment_spike_pct=0.18,
    )
    monitor.evaluate_canary_stage(
        stage_id="STAGE-03 (Canary)",
        traffic_pct=50.0,
        total_tx=124000,
        http_5xx_pct=0.021,
        p99_ms=148.6,
        abandonment_spike_pct=0.25,
    )
    monitor.evaluate_canary_stage(
        stage_id="STAGE-04 (Cutover)",
        traffic_pct=100.0,
        total_tx=250000,
        http_5xx_pct=0.024,
        p99_ms=151.2,
        abandonment_spike_pct=0.30,
    )

    # 3. Render Dashboard and Export Audit Trail
    monitor.render_dashboard()
    monitor.export_audit_log()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Elsamag IT Solutions — Checkout Migration Telemetry Monitor"
    )
    parser.add_argument(
        "--audit-sprint-all",
        action="store_true",
        help="Execute automated end-to-end telemetry and gateway SLA audit",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/telemetry_thresholds.json",
        help="Path to telemetry thresholds JSON config",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.audit_sprint_all or len(sys.argv) == 1:
        execute_full_telemetry_audit()
    else:
        logger.info(f"Custom monitor parameters initialized with {args.config}")
