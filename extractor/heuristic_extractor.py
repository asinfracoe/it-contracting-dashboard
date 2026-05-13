"""
Heuristic (regex-based) pre-extractor.
Pulls candidate vendor, price, services, year, country from raw text.
Sends only FINDINGS to AI for cleanup/formatting — not full document.
"""
import re
from typing import Dict, List


# ============================================================================
# KNOWN VENDORS (from your existing 48-record dataset)
# ============================================================================

KNOWN_VENDORS = [
    "NTT Data", "NTT DOCOMO", "NTT", "CDW", "SHI", "TrendMicro", "Trend Micro",
    "KnowBe4", "Microsoft", "ServiceNow", "Equinix", "Quest", "Proquire LLC",
    "Copeland LP", "Copeland", "Thrive", "PC Connection", "Honeywell",
    "Cisco", "Zscaler", "CyberArk", "Palo Alto", "VMware", "Oracle", "NetApp",
    "Forescout", "IBM", "Pure Storage",
]

# ============================================================================
# KNOWN SERVICES (keywords indicating a service line)
# ============================================================================

SERVICE_KEYWORDS = [
    # Cybersecurity
    "Trend Vision One", "Apex One", "Trend Micro Email Security", "Cloud App Security",
    "KnowBe4", "PhishER", "Security Awareness Training",
    "Zscaler ZIA", "Zero Trust Network Access", "Zscaler Internet Access",
    "CyberArk", "Privileged Access Management", "Endpoint Privilege",
    "Forescout", "Network Access Control",
    # Network
    "Cisco Catalyst C8300", "Cisco Catalyst 9800", "Cisco Catalyst 9200",
    "Cisco Catalyst 9400", "Cisco Nexus 9200", "Cisco Nexus 9300", "Cisco Nexus 9000",
    "Cisco Wireless 9176I", "Cisco Meraki MR46E", "Cisco SMARTnet", "Cisco MDS9148T",
    "Cisco Firepower", "Palo Alto PA 445", "Palo Alto NGFW",
    "Equinix Network Interconnect", "Global WAN Connectivity", "Cloud Connectivity",
    # Hosting
    "VMware Cloud Foundation", "VMware vSphere", "NetApp AFF", "Oracle Database Appliance",
    "Oracle Database Enterprise", "Colocation Power", "Internet Access",
    "Microsoft Windows Server", "Microsoft SQL Server", "Pure Storage FlashArray",
    "Data Center Build", "IBM Power9",
    # M365
    "M365 E5", "M365 E3", "M365 F3", "O365 E1", "Visio P1", "Visio P2",
    "Windows 365", "Microsoft Defender", "Power Platform", "Power BI Premium",
    "Power BI Pro", "M365 Copilot", "Teams Essentials",
    # ServiceNow
    "ServiceNow App Engine", "ServiceNow IT Service Management",
    "ServiceNow IT Operations Management",
    # IdAM
    "Quest On-Demand Migration Suite T5", "Quest On-Demand Migration M365",
    "Active Directory Migration", "Quest Professional Services",
]

# ============================================================================
# COUNTRIES
# ============================================================================

COUNTRIES = {
    "Germany": ["germany", "deutschland", "frankfurt", "langen", "hamburg", "munich", "neumunster", "ottobrunn"],
    "Japan": ["japan", "tokyo", "osaka", "yokohama"],
    "India": ["india", "gurgaon", "mumbai", "bangalore", "delhi"],
    "Singapore": ["singapore"],
    "Malaysia": ["malaysia", "kuala lumpur"],
    "Czech Republic": ["czech", "czechia", "prague"],
    "United States": ["united states", "usa", " us ", "u.s.", "american"],
    "Multi-Region": ["global", "multi-region", "worldwide"],
}

REGION_FOR_COUNTRY = {
    "Germany": "EMEA", "Czech Republic": "EMEA",
    "Japan": "APAC", "India": "APAC", "Singapore": "APAC", "Malaysia": "APAC",
    "United States": "Americas",
    "Multi-Region": "Global",
}


# ============================================================================
# PRICE EXTRACTION
# ============================================================================

def extract_price(text: str) -> int:
    """Find the most likely TOTAL price (highest $ amount near 'total', 'grand total', etc.)."""
    candidates = []
    
    # Pattern 1: After 'total' keyword
    total_patterns = [
        r"(?:grand\s*total|total\s*amount|total\s*price|total\s*cost|net\s*total|contract\s*total|order\s*total)[\s:]*\$?\s*([\d,]+(?:\.\d{2})?)",
        r"total[\s:]+\$?\s*([\d,]+(?:\.\d{2})?)",
        r"amount\s*due[\s:]+\$?\s*([\d,]+(?:\.\d{2})?)",
    ]
    for pat in total_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            try:
                val = float(m.group(1).replace(",", ""))
                if 100 <= val <= 50_000_000:
                    candidates.append((val, 10))  # high priority
            except: pass
    
    # Pattern 2: Any $ amount
    for m in re.finditer(r"\$\s*([\d,]+(?:\.\d{2})?)", text):
        try:
            val = float(m.group(1).replace(",", ""))
            if 1000 <= val <= 50_000_000:
                candidates.append((val, 1))  # low priority
        except: pass
    
    # Pattern 3: USD prefix/suffix
    for m in re.finditer(r"USD\s*([\d,]+(?:\.\d{2})?)|([\d,]+(?:\.\d{2})?)\s*USD", text):
        try:
            val = float((m.group(1) or m.group(2)).replace(",", ""))
            if 1000 <= val <= 50_000_000:
                candidates.append((val, 5))
        except: pass
    
    if not candidates:
        return 0
    
    # Weight by priority × value (biggest total-labelled wins)
    candidates.sort(key=lambda x: (-x[1], -x[0]))
    return int(candidates[0][0])


# ============================================================================
# VENDOR EXTRACTION
# ============================================================================

def extract_vendor(text: str, filename: str) -> str:
    """Find vendor name from text or filename."""
    blob = (text[:3000] + " " + filename).lower()
    
    # Score each known vendor by occurrences
    scores = {}
    for v in KNOWN_VENDORS:
        count = len(re.findall(re.escape(v.lower()), blob))
        if count > 0:
            scores[v] = count
    
    if scores:
        # Prefer longer, more specific names (e.g., "NTT Data" over "NTT")
        best = max(scores.items(), key=lambda x: (x[1], len(x[0])))
        return best[0]
    
    return "Unknown"


# ============================================================================
# SERVICES EXTRACTION
# ============================================================================

def extract_services(text: str) -> List[str]:
    """Find services by matching keyword catalog."""
    found = set()
    text_lower = text.lower()
    
    for kw in SERVICE_KEYWORDS:
        if kw.lower() in text_lower:
            found.add(kw)
    
    return sorted(found)


# ============================================================================
# YEAR, COUNTRY, PROJECT
# ============================================================================

def extract_year(text: str, filename: str) -> int:
    blob = text[:2000] + " " + filename
    years = re.findall(r"\b(202[3-7])\b", blob)
    if years:
        # Most common year wins
        from collections import Counter
        return int(Counter(years).most_common(1)[0][0])
    return 2025


def extract_quarter(text: str) -> str:
    m = re.search(r"\bQ([1-4])\b", text[:2000])
    if m:
        return f"Q{m.group(1)}"
    # Guess from month
    m = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", text[:2000], re.IGNORECASE)
    if m:
        month_map = {"january": "Q1", "february": "Q1", "march": "Q1",
                     "april": "Q2", "may": "Q2", "june": "Q2",
                     "july": "Q3", "august": "Q3", "september": "Q3",
                     "october": "Q4", "november": "Q4", "december": "Q4"}
        return month_map.get(m.group(1).lower(), "Q1")
    return "Q1"


def extract_country_region(text: str, filename: str) -> tuple:
    blob = (text[:3000] + " " + filename).lower()
    for country, keywords in COUNTRIES.items():
        for kw in keywords:
            if kw in blob:
                return (country, REGION_FOR_COUNTRY.get(country, "Global"))
    return ("Multi-Region", "Global")


# ============================================================================
# MAIN HEURISTIC EXTRACTOR
# ============================================================================

def heuristic_extract(text: str, filename: str) -> Dict:
    """Extract everything we can locally — NO AI CALLS HERE."""
    country, region = extract_country_region(text, filename)
    return {
        "vendor": extract_vendor(text, filename),
        "price": extract_price(text),
        "services": extract_services(text),
        "country": country,
        "region": region,
        "year": extract_year(text, filename),
        "quarter": extract_quarter(text),
    }


def is_heuristic_complete(data: Dict) -> bool:
    """Decide if we even NEED AI. If we got vendor + price + ≥1 service, we're good."""
    return (
        data.get("vendor") != "Unknown"
        and data.get("price", 0) > 0
        and len(data.get("services", [])) >= 1
    )
