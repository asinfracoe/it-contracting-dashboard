"""
AI Extractor - Uses LlamaParse for parsing + Groq for structured extraction
"""
import os
import json
import re
from pathlib import Path
from llama_parse import LlamaParse
from groq import Groq

LLAMA_API_KEY = os.getenv("LLAMA_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Project folder → project name mapping
PROJECT_MAP = {
    "panasonic": "Panasonic",
    "idemia": "Idemia",
    "tenneco": "Tenneco",
}

# Categorisation hints (from your existing dashboard)
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
    "united states": ("Americas", "United States"),
    "usa": ("Americas", "United States"),
    "us": ("Americas", "United States"),
    "global": ("Global", "Multi-Region"),
}


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


def extract_with_groq(text: str, filename: str, project: str) -> dict:
    """Use Groq LLM to extract structured fields from parsed text."""
    client = Groq(api_key=GROQ_API_KEY)
    
    prompt = f"""You are an expert at extracting structured data from IT vendor quotations.

Analyze this quote document and return ONLY a valid JSON object (no markdown, no explanation):

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

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1500,
    )
    
    raw = response.choices[0].message.content.strip()
    # Strip markdown fences if present
    raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    raw = re.sub(r"^```\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ⚠️ JSON parse failed for {filename}: {e}")
        print(f"  Raw: {raw[:300]}")
        return None


def categorise(services: list, filename: str) -> str:
    """Heuristic category detection from services + filename."""
    blob = (filename + " " + " ".join(services or [])).lower()
    scores = {cat: sum(1 for kw in kws if kw in blob) for cat, kws in CATEGORY_HINTS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "Other"


def normalise_region_country(country: str, region: str) -> tuple:
    """Map free-text country to (region, country) standard."""
    if not country:
        return (region or "Global", "Multi-Region")
    key = country.lower().strip()
    if key in REGION_MAP:
        return REGION_MAP[key]
    return (region or "Global", country)


def extract_quote(file_path: Path, project_folder: str) -> dict:
    """Top-level: parse a single quote file → returns dashboard record."""
    print(f"  📄 Processing: {file_path.name}")
    project = PROJECT_MAP.get(project_folder.lower(), project_folder.title())
    
    try:
        text = parse_with_llama(str(file_path))
    except Exception as e:
        print(f"  ❌ LlamaParse failed: {e}")
        return None
    
    if not text or len(text) < 50:
        print(f"  ⚠️ Empty parse result")
        return None
    
    extracted = extract_with_groq(text, file_path.name, project)
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
