"""Ticket Simulator — 合成工单数据生成器

基于 Northstar Systems 业务世界观生成真实感工单数据。
遵循 contracts/data/ticket_contract.json 的 schema。

使用方式:
    python ticket_simulator.py --count 500 --output tickets-seed.jsonl
"""

import argparse
import json
import random
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── 业务世界观配置 ─────────────────────────────────────────────────────────────

PRODUCT_LINES = [
    "northstar_workspace",
    "northstar_edge_gateway",
    "northstar_studio",
]

PRODUCT_VERSIONS = {
    "northstar_workspace": ["3.2.0", "3.1.5", "3.0.2", "2.9.1"],
    "northstar_edge_gateway": ["FW-2.4.1", "FW-2.3.0", "FW-2.2.5"],
    "northstar_studio": ["1.5.0", "1.4.2", "1.3.8"],
}

CATEGORIES = [
    "installation", "configuration", "connectivity", "authentication",
    "billing", "feature_request", "bug_report", "documentation",
    "performance", "security", "other",
]

PRIORITIES = [
    ("p1_critical", 0.05),
    ("p2_high", 0.15),
    ("p3_medium", 0.50),
    ("p4_low", 0.30),
]

SLA_TIERS = [
    ("enterprise", 0.15),
    ("professional", 0.35),
    ("standard", 0.40),
    ("free", 0.10),
]

ERROR_CODES_BY_PRODUCT = {
    "northstar_workspace": [
        "WS-AUTH-001", "WS-PERM-002", "WS-SYNC-003",
        "WS-API-404", "WS-WEBHOOK-005", "WS-QUOTA-006",
    ],
    "northstar_edge_gateway": [
        "EG-CONN-001", "EG-FW-002", "EG-SENSOR-003",
        "EG-BOOT-004", "EG-CERT-005", "EG-TEMP-006",
    ],
    "northstar_studio": [
        "ST-FLOW-001", "ST-EXEC-002", "ST-MONITOR-003",
        "ST-INTEG-004", "ST-SCHED-005",
    ],
}

SUBJECTS_BY_CATEGORY = {
    "installation": [
        "Installation fails at step 3 with error {error_code}",
        "Cannot complete setup after factory reset",
        "Silent install returns exit code 1",
    ],
    "configuration": [
        "SSO configuration not working after update",
        "Custom webhook endpoint not receiving events",
        "Rate limit configuration not applied correctly",
    ],
    "connectivity": [
        "Device {error_code} unreachable after network change",
        "WebSocket connection drops every 30 minutes",
        "VPN tunnel cannot establish with {product} gateway",
    ],
    "authentication": [
        "MFA device removed but account still requires it",
        "Service account token expired, rotation failing",
        "LDAP sync users cannot login — {error_code}",
    ],
    "bug_report": [
        "{error_code} thrown on empty data export",
        "UI freezes when filtering with more than 500 results",
        "Scheduled job runs twice in some timezones",
    ],
    "performance": [
        "Query latency increased 5x after v{version} upgrade",
        "Memory leak in background sync process",
        "Dashboard load time exceeds 30 seconds",
    ],
    "security": [
        "Suspicious login attempts from unknown IPs",
        "Audit log shows privilege escalation attempt",
        "Certificate validation bypass in API client",
    ],
    "other": [
        "Question about {product} pricing for additional seats",
        "Need help migrating data from legacy system",
        "Documentation unclear for advanced {category} use case",
    ],
}

ORG_NAMES = [
    "Acme Corp", "Zenith Industries", "Meridian Tech", "Apex Solutions",
    "Nova Systems", "Summit Analytics", "Crest Digital", "Vertex Cloud",
    "Pinnacle Ops", "Horizon Networks", "Cobalt Engineering", "Prism Data",
]


def weighted_choice(choices: list[tuple]) -> str:
    """按权重随机选择"""
    items, weights = zip(*choices)
    return random.choices(items, weights=weights, k=1)[0]


def generate_ticket_id(created_at: datetime, seq: int) -> str:
    return f"TKT-{created_at.strftime('%Y%m%d')}-{seq:06d}"


def generate_ticket(seq: int, start_date: datetime) -> dict:
    """生成单条合成工单"""
    product_line = random.choice(PRODUCT_LINES)
    versions = PRODUCT_VERSIONS[product_line]
    version = random.choice(versions)
    category = random.choice(CATEGORIES)
    priority = weighted_choice(PRIORITIES)
    sla_tier = weighted_choice(SLA_TIERS)

    # 时间生成（最近 180 天内）
    days_ago = random.randint(0, 180)
    created_at = start_date - timedelta(days=days_ago, hours=random.randint(0, 23))

    # SLA 到期时间（按 tier 不同）
    sla_hours = {"enterprise": 4, "professional": 8, "standard": 24, "free": 72}
    sla_due_at = created_at + timedelta(hours=sla_hours[sla_tier])

    # 状态（已关闭的工单有 resolved_at）
    status = random.choices(
        ["open", "pending", "in_progress", "resolved", "closed"],
        weights=[0.2, 0.15, 0.25, 0.25, 0.15], k=1
    )[0]
    resolved_at = None
    if status in ("resolved", "closed"):
        resolve_hours = random.uniform(1, sla_hours[sla_tier] * 2)
        resolved_at = (created_at + timedelta(hours=resolve_hours)).isoformat()

    # 错误码
    error_pool = ERROR_CODES_BY_PRODUCT.get(product_line, [])
    error_codes = random.sample(error_pool, k=random.randint(0, min(2, len(error_pool))))

    # Subject
    subject_templates = SUBJECTS_BY_CATEGORY.get(category, SUBJECTS_BY_CATEGORY["other"])
    subject_tpl = random.choice(subject_templates)
    subject = subject_tpl.format(
        error_code=error_codes[0] if error_codes else "UNKNOWN-001",
        product=product_line.replace("_", " ").title(),
        version=version,
        category=category,
    )

    org_name = random.choice(ORG_NAMES)
    org_id = f"org-{abs(hash(org_name)):08x}"
    customer_id = f"cust-{abs(hash(org_name + str(seq % 20))):08x}"

    ticket_id = generate_ticket_id(created_at, seq)

    return {
        "ticket_id": ticket_id,
        "schema_version": "ticket_v1",
        "source_id": f"structured:tickets:seed_batch_001",
        "ingest_batch_id": "batch-20260331-001",
        "customer_id": customer_id,
        "org_id": org_id,
        "status": status,
        "priority": priority,
        "category": category,
        "product_line": product_line,
        "product_version": version,
        "subject": subject,
        "description": (
            f"Customer from {org_name} reports: {subject}. "
            f"Affecting {product_line.replace('_', ' ').title()} v{version}."
        ),
        "error_codes": error_codes,
        "asset_ids": [],
        "assignee_id": None,
        "sla_tier": sla_tier,
        "sla_due_at": sla_due_at.isoformat(),
        "created_at": created_at.isoformat(),
        "updated_at": created_at.isoformat(),
        "resolved_at": resolved_at,
        "pii_level": "low",
        "pii_redacted": False,
        "quality_gate": "pass",
        "owner": "course-team",
        "tags": [product_line, category, priority],
    }


def generate_batch(count: int, output_path: Path, seed: int = 42):
    random.seed(seed)
    start_date = datetime.now(timezone.utc)

    print(f"Generating {count} synthetic tickets...")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for i in range(1, count + 1):
            ticket = generate_ticket(seq=i, start_date=start_date)
            f.write(json.dumps(ticket, ensure_ascii=False) + "\n")
            if i % 100 == 0:
                print(f"  Generated {i}/{count}")

    print(f"Done. Output: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="OmniSupport Ticket Simulator")
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--output", type=Path, default=Path("tickets-seed-batch-001.jsonl"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    generate_batch(args.count, args.output, args.seed)


if __name__ == "__main__":
    main()
