"""
AI Extractor — uses AI minimally.
Flow:
  1. Heuristic extraction (local, 0 tokens)
  2. If complete → use as-is
  3. If incomplete → AI fills gaps (minimal tokens)
  4. AI formats final JSON (small prompt)
"""
import os
import json
import re
from pathlib import Path
from file_processor import process_file
from heuristic_extractor import heuristic_extract, is_heuristic_complete

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

LLM_BLOCKED = {"openai": False, "groq": False}


class AllLLMsExhausted(Exception):
    pass


PROJECT_MAP = {
    "panasonic": "Panasonic", "idemia": "Idemia", "tenneco": "Tenneco",
}

CATEGORY_HINTS = {
    "Cybersecurity": ["zscaler", "trend", "cyberark", "knowbe4", "forescout", "endpoint", "phishing", "siem"],
    "Network & Telecom": ["cisco", "palo alto", "firewall", "switch", "router", "meraki", "equinix", "wan", "smartnet"],
    "Hosting": ["vmware", "netapp", "oracle", "datacenter", "colocation", "server", "storage", "ibm", "honeywell"],
    "M365 & Power Platform": ["m365", "microsoft 365", "office", "visio", "power bi", "copilot", "windows 365", "defender", "teams"],
    "IdAM": ["quest", "odm", "active directory", "ad migration", "identity", "iam"],
    "Service Management (SNow)": ["servicenow", "snow"],
}


# ============================================================================
# CATEGORISATION (local, no AI)
# ============================================================================

def categorise(services: list, filename: str, vendor: str) -> str:
    blob = (filename + " " + " ".join(services or []) + " " + vendor).lower()
    scores = {cat: sum(1 for kw in kws if kw in blob) for cat, kws in CATEGORY_HINTS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "Other"


# ============================================================================
# AI GAP-FILLER (only when heuristics incomplete)
# ============================================================================

def build_gap_fill_prompt(text: str, partial: dict, filename: str) -> str:
    """Small prompt — only asks AI to fill missing fields."""
    missing = []
    if partial.get("vendor") == "Unknown": missing.append("vendor")
    if partial.get("price", 0) == 0: missing.append("price")
    if not partial.get("services"): missing.append("services")
    
    return f"""From this quote document, find ONLY these missing fields: {', '.join(missing)}

Already extracted: {json.dumps({k: v for k, v in partial.items() if v and v != "Unknown"})}

Return JSON with just the missing fields:
{{
  {"'vendor': 'vendor name'," if "vendor" in missing else ""}
  {"'price': <total USD price as number>," if "price" in missing else ""}
  {"'services': ['service 1', 'service 2']" if "services" in missing else ""}
}}

Filename: {filename}

Document (first 6000 chars):
{text[:6000]}

Return ONLY JSON."""


def parse_llm_response(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    raw = re.sub(r"^```\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try: return json.loads(m.group())
            except: pass
    return {}


def call_openai(prompt: str) -> dict:
    if LLM_BLOCKED["openai"] or not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=600,  # small output
            response_format={"type": "json_object"},
        )
        return parse_llm_response(r.choices[0].message.content)
    except Exception as e:
        err = str(e).lower()
        if "rate_limit" in err or "429" in err or "quota" in err or "insufficient" in err:
            print(f"     ⚠️ OpenAI exhausted — failing to Groq")
            LLM_BLOCKED["openai"] = True
        else:
            print(f"     ⚠️ OpenAI error: {str(e)[:100]}")
        return None


def call_groq(prompt: str) -> dict:
    if LLM_BLOCKED["groq"] or not GROQ_API_KEY:
        return None
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=600,
        )
        return parse_llm_response(r.choices[0].message.content)
    except Exception as e:
        err = str(e).lower()
        if "rate_limit" in err or "429" in err or "quota" in err or "tpd" in err:
            print(f"     ⚠️ Groq exhausted — ALL LLMs blocked")
            LLM_BLOCKED["groq"] = True
        else:
            print(f"     ⚠️ Groq error: {str(e)[:100]}")
        return None


def ai_fill_gaps(text: str, partial: dict, filename: str) -> dict:
    """Only called when heuristic extraction is incomplete."""
    prompt = build_gap_fill_prompt(text, partial, filename)
    
    for fn in [call_openai, call_groq]:
        result = fn(prompt)
        if result:
            return result
    
    # Check if all blocked
    available = []
    if OPENAI_API_KEY: available.append("openai")
    if GROQ_API_KEY: available.append("groq")
    if available and all(LLM_BLOCKED[k] for k in available):
        raise AllLLMsExhausted("All LLMs rate-limited")
    
    return {}


# ============================================================================
# TOP-LEVEL EXTRACT
# ============================================================================

def extract_quote(file_path: Path, project_folder: str) -> dict:
    print(f"  📄 {file_path.name}")
    project = PROJECT_MAP.get(project_folder.lower(), project_folder.title())
    
    # Step 1: Parse locally
    parsed = process_file(file_path)
    if not parsed["ok"]:
        print(f"     ❌ Parse failed: {parsed.get('error', 'unknown')[:100]}")
        return None
    
    text = parsed["text"]
    if len(text.strip()) < 50:
        print(f"     ⚠️ Empty/scanned document ({len(text)} chars)")
        return None
    
    method = parsed.get("method", "default")
    print(f"     📊 Parsed: {len(text):,} chars ({method})")
    
    # Step 2: Heuristic extraction (NO AI)
    partial = heuristic_extract(text, file_path.name)
    
    # Step 3: Decide if AI is needed
    if is_heuristic_complete(partial):
        # 🎉 Got everything locally — ZERO tokens used
        print(f"     🎯 Heuristic complete — skipping AI")
        final = partial
    else:
        print(f"     🤖 Calling AI to fill gaps...")
        ai_data = ai_fill_gaps(text, partial, file_path.name)
        
        # Merge: AI fills gaps, but heuristics win when present
        final = dict(partial)
        for k, v in ai_data.items():
            if k == "vendor" and partial.get("vendor") == "Unknown" and v:
                final["vendor"] = v
            elif k == "price" and partial.get("price", 0) == 0 and v:
                try: final["price"] = int(float(v))
                except: pass
            elif k == "services" and not partial.get("services") and v:
                final["services"] = v if isinstance(v, list) else [v]
    
    # Step 4: Build final record
    services = final.get("services") or []
    cat = categorise(services, file_path.name, final.get("vendor", ""))
    
    record = {
        "proj": project,
        "region": final.get("region", "Global"),
        "country": final.get("country", "Multi-Region"),
        "cat": cat,
        "vendor": final.get("vendor", "Unknown"),
        "file": file_path.name,
        "services": services,
        "price": int(final.get("price") or 0),
        "year": int(final.get("year") or 2025),
        "quarter": final.get("quarter") or "Q1",
    }
    
    # Sanity check: reject if no useful data
    if record["vendor"] == "Unknown" and record["price"] == 0 and not record["services"]:
        print(f"     ⚠️ No data extracted — skipping")
        return None
    
    print(f"     ✅ {record['vendor']} · ${record['price']:,} · {len(services)} services")
    return record
