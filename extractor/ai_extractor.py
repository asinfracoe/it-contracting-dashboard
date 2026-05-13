"""
AI Extractor — LLM structuring with OpenAI primary, Groq fallback.
"""
import os
import json
import re
from pathlib import Path
from file_processor import process_file

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

LLM_BLOCKED = {"openai": False, "groq": False}


class AllLLMsExhausted(Exception):
    pass


# ============================================================================
# MAPPINGS
# ============================================================================

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

REGION_MAP = {
    "germany": ("EMEA", "Germany"), "japan": ("APAC", "Japan"),
    "india": ("APAC", "India"), "singapore": ("APAC", "Singapore"),
    "malaysia": ("APAC", "Malaysia"), "czech republic": ("EMEA", "Czech Republic"),
    "united states": ("Americas", "United States"), "usa": ("Americas", "United States"),
    "us": ("Americas", "United States"), "global": ("Global", "Multi-Region"),
}


# ============================================================================
# PROMPT
# ============================================================================

def build_prompt(text: str, filename: str, project: str) -> str:
    return f"""You are an expert at extracting structured data from IT vendor quotations.

Analyze this quote document and return ONLY a valid JSON object:

{{
  "vendor": "vendor company name (e.g., NTT Data, CDW, SHI, Microsoft, Equinix)",
  "price": <total price in USD as number, no currency symbol, no commas>,
  "services": ["service 1", "service 2", ...],
  "country": "country name or 'Multi-Region'",
  "region": "EMEA / APAC / Americas / Global",
  "year": <year as 4-digit number>,
  "quarter": "Q1/Q2/Q3/Q4 or null"
}}

Filename: {filename}
Project context: {project}

Document content:
{text[:12000]}

Return ONLY the JSON object, no markdown, no explanation."""


def parse_llm_response(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    raw = re.sub(r"^```\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try: return json.loads(match.group())
            except: pass
    return None


# ============================================================================
# LLM #1 — OPENAI (primary)
# ============================================================================

def extract_with_openai(prompt: str) -> dict:
    if LLM_BLOCKED["openai"] or not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )
        return parse_llm_response(response.choices[0].message.content)
    except Exception as e:
        err = str(e).lower()
        if "rate_limit" in err or "429" in err or "quota" in err or "insufficient" in err:
            print(f"  ⚠️ OpenAI rate-limited — failing over to Groq")
            LLM_BLOCKED["openai"] = True
        else:
            print(f"  ⚠️ OpenAI error: {str(e)[:150]}")
        return None


# ============================================================================
# LLM #2 — GROQ (fallback)
# ============================================================================

def extract_with_groq(prompt: str) -> dict:
    if LLM_BLOCKED["groq"] or not GROQ_API_KEY:
        return None
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1500,
        )
        return parse_llm_response(response.choices[0].message.content)
    except Exception as e:
        err = str(e).lower()
        if "rate_limit" in err or "429" in err or "quota" in err or "tpd" in err:
            print(f"  ⚠️ Groq rate-limited — ALL LLMs exhausted")
            LLM_BLOCKED["groq"] = True
        else:
            print(f"  ⚠️ Groq error: {str(e)[:150]}")
        return None


# ============================================================================
# MAIN EXTRACTION ROUTER
# ============================================================================

def extract_with_llm(text: str, filename: str, project: str) -> dict:
    """Try OpenAI → Groq. Raise if both exhausted."""
    prompt = build_prompt(text, filename, project)
    
    for fn in [extract_with_openai, extract_with_groq]:
        result = fn(prompt)
        if result:
            return result
    
    # Check if all available LLMs are blocked
    available = []
    if OPENAI_API_KEY: available.append("openai")
    if GROQ_API_KEY: available.append("groq")
    
    if available and all(LLM_BLOCKED[k] for k in available):
        raise AllLLMsExhausted("All available LLMs are rate-limited. Saving progress and exiting.")
    
    return None


# ============================================================================
# HELPERS
# ============================================================================

def categorise(services: list, filename: str) -> str:
    blob = (filename + " " + " ".join(services or [])).lower()
    scores = {cat: sum(1 for kw in kws if kw in blob) for cat, kws in CATEGORY_HINTS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "Other"


def normalise_region_country(country: str, region: str) -> tuple:
    if not country:
        return (region or "Global", "Multi-Region")
    key = country.lower().strip()
    if key in REGION_MAP:
        return REGION_MAP[key]
    return (region or "Global", country)


# ============================================================================
# TOP-LEVEL EXTRACT
# ============================================================================

def extract_quote(file_path: Path, project_folder: str) -> dict:
    """Full pipeline: local parse → LLM structure → dashboard record."""
    print(f"  📄 {file_path.name}")
    project = PROJECT_MAP.get(project_folder.lower(), project_folder.title())
    
    # Step 1: Local parsing (no API call)
    parsed = process_file(file_path)
    if not parsed["ok"]:
        err = parsed.get("error", "unknown")
        print(f"     ❌ Parse failed: {err[:100]}")
        return None
    
    text = parsed["text"]
    if len(text.strip()) < 50:
        print(f"     ⚠️ Empty/scanned document")
        return None
    
    print(f"     📊 Parsed: {parsed['pages']} page(s), {len(text):,} chars")
    
    # Step 2: LLM structuring
    extracted = extract_with_llm(text, file_path.name, project)
    if not extracted:
        return None
    
    # Step 3: Build record
    services = extracted.get("services") or []
    cat = categorise(services, file_path.name)
    region, country = normalise_region_country(
        extracted.get("country"), extracted.get("region")
    )
    
    record = {
        "proj": project,
        "region": region,
        "country": country,
        "cat": cat,
        "vendor": extracted.get("vendor", "Unknown"),
        "file": file_path.name,
        "services": services,
        "price": int(float(extracted.get("price") or 0)),
        "year": int(extracted.get("year") or 2025),
        "quarter": extracted.get("quarter") or "Q1",
    }
    print(f"     ✅ {record['vendor']} · ${record['price']:,} · {len(services)} services")
    return record
