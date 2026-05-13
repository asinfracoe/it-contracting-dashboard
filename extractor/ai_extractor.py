"""
AI Extractor with multi-LLM fallback chain:
  Groq (fast & free) → OpenAI (reliable) → Claude (premium fallback)
Auto-fails over when rate limits hit.
"""
import os
import json
import re
import time
from pathlib import Path
from llama_parse import LlamaParse

LLAMA_API_KEY = os.getenv("LLAMA_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")  # Optional

# Track which LLMs have been rate-limited (don't retry them this run)
LLM_BLOCKED = {"groq": False, "openai": False, "claude": False}

PROJECT_MAP = {
    "panasonic": "Panasonic",
    "idemia": "Idemia",
    "tenneco": "Tenneco",
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
    "germany": ("EMEA", "Germany"),
    "japan": ("APAC", "Japan"),
    "india": ("APAC", "India"),
    "singapore": ("APAC", "Singapore"),
    "malaysia": ("APAC", "Malaysia"),
    "czech republic": ("EMEA", "Czech Republic"),
    "united states": ("Americas", "United States"),
    "usa": ("Americas", "United States"),
    "us": ("Americas", "United States"),
    "global": ("Global", "Multi-Region"),
}


# ============================================================================
# CUSTOM EXCEPTION FOR RATE LIMITS
# ============================================================================

class AllLLMsExhausted(Exception):
    """Raised when ALL LLMs have hit rate limits — triggers safe save & exit."""
    pass


# ============================================================================
# LLAMAPARSE
# ============================================================================

def parse_with_llama(file_path: str) -> str:
    """Parse a document with LlamaParse → returns markdown text."""
    parser = LlamaParse(
        api_key=LLAMA_API_KEY,
        result_type="markdown",
        verbose=False,
        language="en",
    )
    docs = parser.load_data(file_path)
    return "\n\n".join([d.text for d in docs])


# ============================================================================
# PROMPT
# ============================================================================

def build_prompt(text: str, filename: str, project: str) -> str:
    return f"""You are an expert at extracting structured data from IT vendor quotations.

Analyze this quote document and return ONLY a valid JSON object (no markdown fences, no explanation):

{{
  "vendor": "vendor company name (e.g., NTT Data, CDW, SHI, Microsoft, Equinix)",
  "price": <total price in USD as number, no currency symbol>,
  "services": ["service 1", "service 2", ...],
  "country": "country name or 'Multi-Region'",
  "region": "EMEA / APAC / Americas / Global",
  "year": <year as 4-digit number>,
  "quarter": "Q1/Q2/Q3/Q4 or null"
}}

Filename: {filename}
Project context: {project}

Document content (truncated):
{text[:8000]}

Return ONLY the JSON object."""


def parse_llm_response(raw: str) -> dict:
    """Safely parse JSON from LLM response, stripping markdown fences."""
    raw = raw.strip()
    raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    raw = re.sub(r"^```\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to find JSON object in response
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except: pass
    return None


# ============================================================================
# LLM #1 — GROQ (fastest, free tier)
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
            print(f"  ⚠️ Groq rate-limited — failing over to OpenAI")
            LLM_BLOCKED["groq"] = True
        else:
            print(f"  ⚠️ Groq error: {str(e)[:100]}")
        return None


# ============================================================================
# LLM #2 — OPENAI (reliable fallback)
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
            print(f"  ⚠️ OpenAI rate-limited — failing over to Claude")
            LLM_BLOCKED["openai"] = True
        else:
            print(f"  ⚠️ OpenAI error: {str(e)[:100]}")
        return None


# ============================================================================
# LLM #3 — CLAUDE (premium final fallback)
# ============================================================================

def extract_with_claude(prompt: str) -> dict:
    if LLM_BLOCKED["claude"] or not CLAUDE_API_KEY:
        return None
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=CLAUDE_API_KEY)
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        return parse_llm_response(response.content[0].text)
    except Exception as e:
        err = str(e).lower()
        if "rate_limit" in err or "429" in err or "quota" in err:
            print(f"  ⚠️ Claude rate-limited — ALL LLMs exhausted")
            LLM_BLOCKED["claude"] = True
        else:
            print(f"  ⚠️ Claude error: {str(e)[:100]}")
        return None


# ============================================================================
# MAIN EXTRACTION ROUTER
# ============================================================================

def extract_with_llm(text: str, filename: str, project: str) -> dict:
    """Try Groq → OpenAI → Claude in sequence. Raise if ALL exhausted."""
    prompt = build_prompt(text, filename, project)
    
    # Try Groq first (fastest, free)
    result = extract_with_groq(prompt)
    if result: return result
    
    # Fallback to OpenAI
    result = extract_with_openai(prompt)
    if result: return result
    
    # Final fallback to Claude
    result = extract_with_claude(prompt)
    if result: return result
    
    # All LLMs failed — check if it's a rate-limit issue across all of them
    if all(LLM_BLOCKED.values()) or (LLM_BLOCKED["groq"] and not OPENAI_API_KEY and not CLAUDE_API_KEY):
        raise AllLLMsExhausted("All available LLMs are rate-limited. Saving progress and exiting.")
    
    return None


# ============================================================================
# CATEGORISATION
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
    """Parse + extract a single quote file. Raises AllLLMsExhausted if all LLMs blocked."""
    print(f"  📄 Processing: {file_path.name}")
    project = PROJECT_MAP.get(project_folder.lower(), project_folder.title())
    
    try:
        text = parse_with_llama(str(file_path))
    except Exception as e:
        print(f"  ❌ LlamaParse failed: {str(e)[:100]}")
        return None
    
    if not text or len(text) < 50:
        print(f"  ⚠️ Empty parse result")
        return None
    
    extracted = extract_with_llm(text, file_path.name, project)
    if not extracted:
        return None
    
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
        "price": int(extracted.get("price") or 0),
        "year": int(extracted.get("year") or 2025),
        "quarter": extracted.get("quarter") or "Q1",
    }
    print(f"  ✅ {record['vendor']} · {record['price']} · {len(services)} services")
    return record
