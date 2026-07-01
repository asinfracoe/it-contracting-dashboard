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
            # Rule-based fallback
            response_text = self._rule_based(category, phase, message)

        # Parse BOM JSON if present
        partial_bom, complete = self._extract_bom(response_text)

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

    def _rule_based(self, category: str, phase: int, message: str) -> str:
        """Minimal rule-based fallback when AI is unavailable."""
        phase_questions = {
            1: f"To start building your {category} BOM, I need a few details.\n\n"
               "**Phase 1 — Scope & Constraints**\n\n"
               "1. What is the Day 1 cutover date for this project?\n"
               "2. How many racks / physical sites are in scope?\n"
               "3. Are there any specialized hardware requirements (GPU, AS400, bare metal)?",
            2: "**Phase 2 — Seller Inventory**\n\n"
               "Please provide the current inventory:\n"
               "1. How many servers are being conveyed?\n"
               "2. Are any running EOL operating systems (Windows Server 2012 or older)?",
            3: "**Phase 3 — Compute Sizing**\n\n"
               "1. How many vCPUs does the largest workload require?\n"
               "2. What is the total RAM requirement across all workloads?\n"
               "3. Is VMware or Hyper-V the hypervisor?",
        }
        return phase_questions.get(phase,
            f"Tell me more about your {category} requirements so I can build the BOM.")
