"""
BOM Orchestrator — Sprint 2
Routes conversation to the correct specialist agent based on category and current phase.
Entry point called by backend/api/chat.py → _process_message().
"""
import logging
import json
import re
from typing import Dict, Any, Optional, Tuple

from ai.client import call_ai
from ai.prompts.system_base import SYSTEM_BASE, CATEGORY_ADDENDA

logger = logging.getLogger(__name__)


class BOMOrchestrator:
    """
    Stateless orchestrator — all state lives in the SessionContext dict.
    Call process(session_dict, user_message) → (response_text, partial_bom, progress, complete)
    """

    def process(
        self,
        session: Dict[str, Any],
        message: str,
    ) -> Tuple[str, Optional[Dict], int, bool]:
        """
        Main entry point. Returns (response_text, partial_bom, progress_pct, complete).
        """
        context = session.get("context", {})
        category = context.get("category") or "Data Center / COLO"
        phase = context.get("current_phase", 1)
        phase_data = context.get("phase_data", {})
        requirements = context.get("requirements", {})
        history = session.get("conversation", [])

        # Build system prompt: base + category addendum + current state
        addendum = CATEGORY_ADDENDA.get(category, "")
        system = (
            SYSTEM_BASE
            + f"\n\n{'═'*60}\nCURRENT SESSION\n{'═'*60}\n"
            + f"Category: {category}\n"
            + f"Project: {requirements.get('project', 'New Project')}\n"
            + f"Current Phase: {phase}/10\n"
            + f"Phase data collected: {json.dumps(phase_data, default=str)}\n"
            + f"Requirements: {json.dumps(requirements, default=str)}\n"
            + (f"\nCategory guidance: {addendum}" if addendum else "")
        )

        # Build conversation history (last 14 messages)
        msgs = [{"role": m["role"], "content": m["content"]}
                for m in history[-14:]]

        # Call AI
        response_text = call_ai(msgs, system=system)
        if response_text is None:
            # Rule-based fallback — pass history length so it knows if user is answering
            # user_turn_count = number of user messages already in history
            user_turns = sum(1 for m in history if m.get("role") == "user")
            response_text = self._rule_based(category, phase, message, user_turns)

        # Parse BOM JSON if present
        partial_bom, complete = self._extract_bom(response_text)

        # Remove the raw ```json block from the text the user sees — the BOM is
        # already extracted into partial_bom and will be rendered by the frontend.
        if partial_bom:
            response_text = re.sub(r"```json[\s\S]*?```", "", response_text).strip()
            # If stripping leaves only whitespace, put a clean summary line
            if not response_text:
                response_text = "BOM generated. See the panel on the right for all line items."

        # Advance phase heuristically (AI confirms progress in text)
        new_phase = self._detect_phase_advance(response_text, phase, message)
        context["current_phase"] = new_phase

        # Progress 0–100%: phases 1–7 = 70%, phase 8 = 85%, 9 = 95%, 10 = 100%
        progress = self._phase_to_progress(new_phase, complete)

        return response_text, partial_bom, progress, complete

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _extract_bom(self, text: str) -> Tuple[Optional[Dict], bool]:
        match = re.search(r"```json\s*([\s\S]*?)```", text)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                if "line_items" in data and len(data["line_items"]) > 0:
                    return data, True
            except json.JSONDecodeError:
                pass
        return None, False

    def _detect_phase_advance(self, response: str, current_phase: int, message: str) -> int:
        """Simple heuristic: if AI mentions 'Phase X' in response, advance to that phase."""
        for p in range(current_phase + 1, 11):
            if f"Phase {p}" in response or f"phase {p}" in response:
                return p
        return current_phase

    def _phase_to_progress(self, phase: int, complete: bool) -> int:
        if complete:
            return 100
        phase_map = {1: 5, 2: 15, 3: 25, 4: 35, 5: 45, 6: 55, 7: 70, 8: 80, 9: 90, 10: 95}
        return phase_map.get(phase, 5)

    def _rule_based(self, category: str, phase: int, message: str, user_turns: int = 0) -> str:
        """
        Rule-based fallback when AI is unavailable.
        Detects BOM-creation intent and returns a fully-formed template BOM JSON
        so the frontend can render it immediately.
        """
        import re, datetime

        msg = message.lower()

        # ── Detect project name ───────────────────────────────────────────
        project_map = {
            "panasonic": "Panasonic", "idemia": "Idemia", "tenneco": "Tenneco",
            "honeywell": "Honeywell", "pwc": "PwC", "cisco": "Cisco",
            "microsoft": "Microsoft", "oracle": "Oracle",
        }
        project = next((v for k, v in project_map.items() if k in msg), "New Project")

        # ── BOM creation intent OR user is answering questions ──────────────
        # user_turns >= 1 means user already answered Phase 1 questions once;
        # generate the BOM now instead of asking the same question again.
        create_pat = re.compile(
            r"\b(create|build|generate|make|prepare|draft)\b.*\bbom\b"
            r"|\bnew bom\b"
            r"|\bbuild.*bom\b|\bbom.*build\b"
            r"|\bcreate.*bom\b|\bbom.*create\b",
            re.I,
        )
        # Also detect clear creation intent even without the word "bom"
        strong_intent = bool(create_pat.search(msg)) or (
            re.search(r"\b(create|build|generate|make|draft)\b", msg, re.I)
            and (category or project)
        )
        if strong_intent or phase >= 4 or user_turns >= 1:
            bom = self._build_template_bom(category, project)
            bom_json = json.dumps(bom, indent=2)
            return (
                f"I've built a **{category}** BOM for **{project}** "
                f"using industry-standard templates.\n\n"
                f"The BOM contains **{len(bom['line_items'])} line items** "
                f"totalling **${bom['total_value']:,.0f}**.\n\n"
                f"Review the items in the right panel. You can ask me to:\n"
                f"- Add or remove specific items\n"
                f"- Adjust quantities or pricing\n"
                f"- Change vendors\n"
                f"- Export or save the BOM\n\n"
                f"```json\n{bom_json}\n```"
            )

        # ── Phase questions (phases 1–3, before creation intent detected) ──
        phase_questions = {
            1: (
                f"I'll help you build a **{category}** BOM for **{project}**.\n\n"
                "**Phase 1 — Scope & Constraints**\n\n"
                "1. What is the Day 1 cutover date for this project?\n"
                "2. How many racks / physical sites are in scope?\n"
                "3. Are there any specialized hardware requirements (GPU, AS400, bare metal)?\n\n"
                "*Or just say **\"create the BOM\"** and I will generate a complete template immediately.*"
            ),
            2: (
                "**Phase 2 — Seller Inventory**\n\n"
                "1. How many servers are being conveyed?\n"
                "2. Are any running EOL operating systems (Windows Server 2012 or older)?\n\n"
                "*Tip: say **\"create the BOM now\"** to skip to a full template.*"
            ),
            3: (
                "**Phase 3 — Compute Sizing**\n\n"
                "1. How many vCPUs does the largest workload require?\n"
                "2. What is the total RAM requirement across all workloads?\n"
                "3. Is VMware or Hyper-V the hypervisor?\n\n"
                "*Tip: say **\"create the BOM now\"** to skip to a full template.*"
            ),
        }
        return phase_questions.get(
            phase,
            f"Tell me more about your **{category}** requirements, or say "
            f"**\"create the BOM\"** to generate a complete template now.",
        )

    # ── Template BOM builder (rule-based, no AI needed) ───────────────────

    def _build_template_bom(self, category: str, project: str) -> dict:
        """Return a vendor-ready template BOM dict for the given category."""
        templates = {
            "Data Center / COLO": [
                {"description": "Dell PowerEdge R750 Server (2x Xeon Gold, 512GB RAM)",
                 "category": "Compute", "qty": 8, "unit_price": 28500, "vendor": "Dell Technologies"},
                {"description": "NetApp AFF A400 All-Flash Storage Array (50TB raw)",
                 "category": "Storage", "qty": 2, "unit_price": 125000, "vendor": "NetApp"},
                {"description": "Cisco Nexus 93180YC-FX Switch (48x25G + 6x100G)",
                 "category": "Network", "qty": 4, "unit_price": 18750, "vendor": "Cisco"},
                {"description": "Cisco ASR 1002-X Edge Router",
                 "category": "Network", "qty": 2, "unit_price": 22000, "vendor": "Cisco"},
                {"description": "APC Smart-UPS SRT 10kVA UPS",
                 "category": "Power & Physical", "qty": 4, "unit_price": 9800, "vendor": "APC by Schneider"},
                {"description": "42U Server Rack Cabinet with Cable Management",
                 "category": "Power & Physical", "qty": 8, "unit_price": 3200, "vendor": "Panduit"},
                {"description": "VMware vSphere Enterprise Plus (per CPU, 3-yr)",
                 "category": "Software & Licensing", "qty": 16, "unit_price": 5500, "vendor": "VMware"},
                {"description": "Veeam Backup & Replication Enterprise (50 VMs)",
                 "category": "Software & Licensing", "qty": 1, "unit_price": 12000, "vendor": "Veeam"},
                {"description": "Data Center Colocation — Full Cabinet (monthly)",
                 "category": "Managed Services", "qty": 8, "unit_price": 2200, "vendor": "Equinix"},
                {"description": "Remote Hands & Smart Hands Support (40 hrs/mo)",
                 "category": "Managed Services", "qty": 1, "unit_price": 4800, "vendor": "Equinix"},
            ],
            "SD-WAN / Network": [
                {"description": "Cisco Catalyst SD-WAN Edge (2x WAN, 4x LAN)",
                 "category": "Network", "qty": 30, "unit_price": 4200, "vendor": "Cisco"},
                {"description": "Cisco SD-WAN Manager (vManage) — Cloud Hosted",
                 "category": "Software & Licensing", "qty": 1, "unit_price": 45000, "vendor": "Cisco"},
                {"description": "MPLS WAN Circuit 100Mbps (monthly per site)",
                 "category": "Connectivity", "qty": 30, "unit_price": 1800, "vendor": "AT&T"},
                {"description": "Broadband Internet Circuit 500Mbps (monthly)",
                 "category": "Connectivity", "qty": 30, "unit_price": 350, "vendor": "Comcast Business"},
                {"description": "Cisco Umbrella DNS Security (per user/yr)",
                 "category": "Security", "qty": 500, "unit_price": 24, "vendor": "Cisco"},
                {"description": "SD-WAN Professional Services & Deployment",
                 "category": "Professional Services", "qty": 1, "unit_price": 85000, "vendor": "CDW"},
            ],
            "Cybersecurity": [
                {"description": "Palo Alto PA-3220 NGFW (10Gbps throughput)",
                 "category": "Security", "qty": 4, "unit_price": 42000, "vendor": "Palo Alto Networks"},
                {"description": "CrowdStrike Falcon Complete (endpoint, per device/yr)",
                 "category": "Security", "qty": 500, "unit_price": 180, "vendor": "CrowdStrike"},
                {"description": "Splunk Enterprise Security (indexing, 10GB/day)",
                 "category": "Security", "qty": 1, "unit_price": 95000, "vendor": "Splunk"},
                {"description": "Okta Identity Cloud — SSO + MFA (per user/yr)",
                 "category": "Security", "qty": 500, "unit_price": 72, "vendor": "Okta"},
                {"description": "Tenable.sc Vulnerability Management (500 assets)",
                 "category": "Security", "qty": 1, "unit_price": 28000, "vendor": "Tenable"},
                {"description": "Security Awareness Training Platform (per user/yr)",
                 "category": "Security", "qty": 500, "unit_price": 15, "vendor": "KnowBe4"},
                {"description": "SOC-as-a-Service — 24×7 MDR (monthly)",
                 "category": "Managed Services", "qty": 12, "unit_price": 18500, "vendor": "Arctic Wolf"},
            ],
        }
        # Pick closest matching template
        items_raw = templates.get(category)
        if items_raw is None:
            for key in templates:
                if any(w in category.lower() for w in key.lower().split("/")):
                    items_raw = templates[key]
                    break
        if items_raw is None:
            items_raw = templates["Data Center / COLO"]

        line_items = []
        for i, item in enumerate(items_raw, 1):
            ext = item["qty"] * item["unit_price"]
            line_items.append({
                "line_number": i,
                "description": item["description"],
                "category": item["category"],
                "unit": "/unit",
                "qty": item["qty"],
                "unit_price": item["unit_price"],
                "ext_price": ext,
                "vendor": item["vendor"],
                "status": "draft",
            })

        total = sum(li["ext_price"] for li in line_items)
        return {
            "project": project,
            "category": category,
            "total_value": total,
            "currency": "USD",
            "line_items": line_items,
        }
