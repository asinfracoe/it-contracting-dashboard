"""
Heuristic (regex-based) primary extractor.
Extracts ALL data locally — vendor, price, services, country, region, year, quarter.
This is the MAIN extractor — AI is no longer called during extraction.
"""
import re
from typing import Dict, List
from collections import Counter


# ============================================================================
# KNOWN VENDORS (expand based on your existing 48-record dataset)
# ============================================================================

KNOWN_VENDORS = [
    # Tier 1 — Primary integrators
    ("NTT Data", ["ntt data", "ntt-data", "nttdata"]),
    ("NTT DOCOMO", ["ntt docomo", "docomo"]),
    ("CDW", ["cdw", "cdw·g", "cdw-g"]),
    ("SHI", ["shi international", "shi corp", "shi inc"]),
    ("Proquire LLC", ["proquire"]),
    ("PC Connection", ["pc connection", "pcconnection"]),
    ("Thrive", ["thrive networks", "thrive operations"]),
    ("Honeywell", ["honeywell"]),
    ("Copeland LP", ["copeland lp", "copeland l.p."]),
    ("Copeland", ["copeland"]),
    
    # Tier 2 — Software vendors
    ("Microsoft", ["microsoft corporation", "microsoft corp", "microsoft inc", "microsoft"]),
    ("ServiceNow", ["servicenow", "service-now", "service now"]),
    ("Cisco", ["cisco systems", "cisco"]),
    ("Trend Micro", ["trend micro", "trendmicro"]),
    ("KnowBe4", ["knowbe4", "know be 4"]),
    ("Zscaler", ["zscaler"]),
    ("CyberArk", ["cyberark", "cyber-ark"]),
    ("Palo Alto", ["palo alto networks", "palo alto"]),
    ("VMware", ["vmware", "vm-ware"]),
    ("Oracle", ["oracle corporation", "oracle"]),
    ("NetApp", ["netapp", "net app"]),
    ("Forescout", ["forescout"]),
    ("IBM", ["ibm corporation", "international business machines", "ibm"]),
    ("Pure Storage", ["pure storage"]),
    ("Quest", ["quest software", "quest"]),
    ("Equinix", ["equinix"]),
]


def extract_vendor(text: str, filename: str) -> str:
    """Score-based vendor matching — longer/more specific names win."""
    blob = (text[:5000] + " " + filename).lower()
    
    matches = []
    for canonical, aliases in KNOWN_VENDORS:
        for alias in aliases:
            if alias in blob:
                # Score: occurrence count × specificity (longer name = more specific)
                count = blob.count(alias)
                score = count * len(alias)
                matches.append((canonical, score, alias))
                break  # one alias match per vendor is enough
    
    if matches:
        matches.sort(key=lambda x: -x[1])
        return matches[0][0]
    
    # Fallback: try to extract from common header patterns
    header_patterns = [
        r"(?:from|vendor|supplier|seller|prepared by|quote from)[\s:]+([A-Z][A-Za-z0-9 &.,'-]{2,40})",
        r"^([A-Z][A-Z0-9 &.,'-]{3,40})(?:\s+(?:Inc|LLC|Corp|Ltd|GmbH|AG|Co))",
    ]
    for pat in header_patterns:
        m = re.search(pat, text[:2000], re.MULTILINE)
        if m:
            candidate = m.group(1).strip()
            if 3 < len(candidate) < 50:
                return candidate
    
    return "Unknown"


# ============================================================================
# SERVICES (expanded keyword catalog)
# ============================================================================

SERVICE_KEYWORDS = {
    # Cybersecurity
    "Trend Vision One": ["trend vision one", "vision one"],
    "Apex One": ["apex one"],
    "Trend Micro Email Security": ["trend micro email security", "tm email security"],
    "Cloud App Security": ["cloud app security"],
    "KnowBe4": ["knowbe4"],
    "PhishER": ["phisher", "phish er"],
    "Security Awareness Training": ["security awareness training", "sat"],
    "Zscaler ZIA": ["zscaler zia", "zscaler internet access", "zia"],
    "Zero Trust Network Access": ["zero trust network access", "ztna"],
    "CyberArk PAM": ["cyberark pam", "privileged access management"],
    "Endpoint Privilege Manager": ["endpoint privilege manager", "epm"],
    "Forescout NAC": ["forescout", "network access control"],
    
    # Network
    "Cisco Catalyst C8300": ["catalyst c8300", "c8300"],
    "Cisco Catalyst 9800": ["catalyst 9800", "c9800"],
    "Cisco Catalyst 9200": ["catalyst 9200", "c9200"],
    "Cisco Catalyst 9400": ["catalyst 9400", "c9400"],
    "Cisco Catalyst 9500": ["catalyst 9500", "c9500"],
    "Cisco Nexus 9200": ["nexus 9200", "n9k-9200", "n9200"],
    "Cisco Nexus 9300": ["nexus 9300", "n9k-9300", "n9300"],
    "Cisco Nexus 9000": ["nexus 9000", "n9k"],
    "Cisco Wireless 9176I": ["9176i", "wireless 9176"],
    "Cisco Meraki MR46E": ["meraki mr46e", "mr46e"],
    "Cisco Meraki": ["meraki"],
    "Cisco SMARTnet": ["smartnet", "smart net"],
    "Cisco MDS9148T": ["mds9148t", "mds 9148"],
    "Cisco Firepower": ["firepower", "ftd"],
    "Palo Alto NGFW": ["palo alto", "pa-445", "ngfw"],
    "Equinix Network Interconnect": ["equinix network", "equinix interconnect", "equinix fabric"],
    "Global WAN Connectivity": ["global wan", "wan connectivity"],
    "Cloud Connectivity": ["cloud connectivity", "cloud connect"],
    
    # Hosting
    "VMware Cloud Foundation": ["vmware cloud foundation", "vcf"],
    "VMware vSphere": ["vsphere"],
    "NetApp AFF": ["netapp aff", "aff a-series"],
    "Oracle Database Appliance": ["oracle database appliance", "oda"],
    "Oracle Database Enterprise": ["oracle database enterprise", "oracle db enterprise"],
    "Colocation Power": ["colocation", "co-location", "colo "],
    "Internet Access": ["internet access", "internet bandwidth"],
    "Microsoft Windows Server": ["windows server"],
    "Microsoft SQL Server": ["sql server"],
    "Pure Storage FlashArray": ["pure storage", "flasharray"],
    "Data Center Build": ["data center build", "datacenter build", "dc build"],
    "IBM Power9": ["power9", "ibm power"],
    
    # M365
    "M365 E5": ["m365 e5", "microsoft 365 e5", "office 365 e5"],
    "M365 E3": ["m365 e3", "microsoft 365 e3", "office 365 e3"],
    "M365 F3": ["m365 f3", "microsoft 365 f3", "office 365 f3"],
    "O365 E1": ["o365 e1", "office 365 e1"],
    "Visio P1": ["visio plan 1", "visio p1"],
    "Visio P2": ["visio plan 2", "visio p2"],
    "Windows 365": ["windows 365", "w365"],
    "Microsoft Defender": ["microsoft defender", "ms defender"],
    "Power Platform": ["power platform"],
    "Power BI Premium": ["power bi premium"],
    "Power BI Pro": ["power bi pro"],
    "M365 Copilot": ["m365 copilot", "microsoft 365 copilot", "copilot for m365"],
    "Teams Essentials": ["teams essentials"],
    
    # ServiceNow
    "ServiceNow App Engine": ["app engine", "servicenow app engine"],
    "ServiceNow ITSM": ["it service management", "itsm"],
    "ServiceNow ITOM": ["it operations management", "itom"],
    
    # IdAM
    "Quest On-Demand Migration T5": ["on-demand migration t5", "odm t5"],
    "Quest On-Demand Migration M365": ["on-demand migration m365", "odm m365"],
    "Active Directory Migration": ["active directory migration", "ad migration"],
    "Quest Professional Services": ["quest professional services"],
}


def extract_services(text: str) -> List[str]:
    """Match service keywords against text."""
    found = set()
    text_lower = text.lower()
    
    for canonical, aliases in SERVICE_KEYWORDS.items():
        for alias in aliases:
            if alias in text_lower:
                found.add(canonical)
                break
    
    return sorted(found)


# ============================================================================
# COUNTRIES
# ============================================================================

COUNTRIES = [
    ("Germany", ["germany", "deutschland", "frankfurt", "langen", "hamburg",
                 "munich", "münchen", "neumunster", "neumünster", "ottobrunn", "berlin"]),
    ("Japan", ["japan", "tokyo", "osaka", "yokohama", "nagoya"]),
    ("India", ["india", "gurgaon", "gurugram", "mumbai", "bangalore", "bengaluru", 
               "delhi", "chennai", "hyderabad", "pune"]),
    ("Singapore", ["singapore", "singapor"]),
    ("Malaysia", ["malaysia", "kuala lumpur", "kl ", "selangor", "penang"]),
    ("Czech Republic", ["czech republic", "czechia", "czech", "prague", "praha", "brno"]),
    ("United States", ["united states", "u.s.a.", " usa ", " us ", "u.s.", 
                       "new york", "california", "texas", "illinois"]),
    ("United Kingdom", ["united kingdom", " uk ", "england", "london", "manchester"]),
    ("France", ["france", "paris", "lyon", "marseille"]),
]

REGION_FOR_COUNTRY = {
    "Germany": "EMEA",
    "Czech Republic": "EMEA",
    "United Kingdom": "EMEA",
    "France": "EMEA",
    "Japan": "APAC",
    "India": "APAC",
    "Singapore": "APAC",
    "Malaysia": "APAC",
    "United States": "Americas",
    "Multi-Region": "Global",
}


def extract_country_region(text: str, filename: str) -> tuple:
    blob = (text[:5000] + " " + filename).lower()
    
    # Score each country by keyword hits
    scores = {}
    for country, keywords in COUNTRIES:
        count = 0
        for kw in keywords:
            count += blob.count(kw.lower())
        if count > 0:
            scores[country] = count
    
    if scores:
        best = max(scores.items(), key=lambda x: x[1])
        country = best[0]
        return (country, REGION_FOR_COUNTRY.get(country, "Global"))
    
    return ("Multi-Region", "Global")


# ============================================================================
# PRICE EXTRACTION (smart total detection)
# ============================================================================

def extract_price(text: str) -> int:
    """Find the most likely TOTAL price."""
    candidates = []
    
    # Highest priority: explicit "grand total", "total amount", etc.
    high_priority_patterns = [
        r"(?:grand\s*total|total\s*amount|total\s*price|total\s*cost|net\s*total|"
        r"contract\s*total|order\s*total|total\s*due|amount\s*due|invoice\s*total)"
        r"[\s:]*(?:USD|US\$|\$)?\s*([\d,]+(?:\.\d{1,2})?)",
    ]
    for pat in high_priority_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            try:
                val = float(m.group(1).replace(",", ""))
                if 100 <= val <= 100_000_000:
                    candidates.append((val, 100))
            except: pass
    
    # Medium priority: lines starting with "Total"
    for m in re.finditer(r"\btotal\b[\s:]+(?:USD|US\$|\$)?\s*([\d,]+(?:\.\d{1,2})?)", text, re.IGNORECASE):
        try:
            val = float(m.group(1).replace(",", ""))
            if 100 <= val <= 100_000_000:
                candidates.append((val, 50))
        except: pass
    
    # Low priority: any USD/$ amount
    for m in re.finditer(r"(?:USD|US\$|\$)\s*([\d,]+(?:\.\d{1,2})?)", text):
        try:
            val = float(m.group(1).replace(",", ""))
            if 1000 <= val <= 100_000_000:
                candidates.append((val, 5))
        except: pass
    
    # Lowest: number followed by USD
    for m in re.finditer(r"([\d,]+(?:\.\d{1,2})?)\s*USD", text):
        try:
            val = float(m.group(1).replace(",", ""))
            if 1000 <= val <= 100_000_000:
                candidates.append((val, 3))
        except: pass
    
    if not candidates:
        return 0
    
    # Best candidate = highest priority. Tie-break by largest value.
    candidates.sort(key=lambda x: (-x[1], -x[0]))
    return int(candidates[0][0])


# ============================================================================
# YEAR & QUARTER
# ============================================================================

def extract_year(text: str, filename: str) -> int:
    blob = text[:3000] + " " + filename
    years = re.findall(r"\b(202[3-7])\b", blob)
    if years:
        return int(Counter(years).most_common(1)[0][0])
    return 2025


MONTH_TO_QUARTER = {
    "january": "Q1", "jan": "Q1", "february": "Q1", "feb": "Q1", "march": "Q1", "mar": "Q1",
    "april": "Q2", "apr": "Q2", "may": "Q2", "june": "Q2", "jun": "Q2",
    "july": "Q3", "jul": "Q3", "august": "Q3", "aug": "Q3", "september": "Q3", "sep": "Q3", "sept": "Q3",
    "october": "Q4", "oct": "Q4", "november": "Q4", "nov": "Q4", "december": "Q4", "dec": "Q4",
}


def extract_quarter(text: str, filename: str) -> str:
    blob = (text[:3000] + " " + filename).lower()
    
    # Direct Q1-Q4 mention
    m = re.search(r"\bq([1-4])\b", blob)
    if m:
        return f"Q{m.group(1)}"
    
    # Find from month names
    month_hits = []
    for month, quarter in MONTH_TO_QUARTER.items():
        if re.search(rf"\b{month}\b", blob):
            month_hits.append(quarter)
    
    if month_hits:
        return Counter(month_hits).most_common(1)[0][0]
    
    return "Q1"


# ============================================================================
# CATEGORY (smart category detection)
# ============================================================================

CATEGORY_RULES = [
    ("Cybersecurity", ["zscaler", "trend micro", "cyberark", "knowbe4", "forescout",
                       "endpoint", "phishing", "siem", "antivirus", "edr", "xdr", "ngfw",
                       "vision one", "apex one", "phisher", "security awareness"]),
    ("Network & Telecom", ["cisco catalyst", "cisco nexus", "cisco meraki", "cisco wireless",
                            "cisco smartnet", "cisco mds", "firepower", "palo alto",
                            "firewall", "switch", "router", "equinix", "wan", "interconnect",
                            "smartnet"]),
    ("Hosting", ["vmware", "netapp", "oracle database", "datacenter", "data center",
                 "colocation", "co-location", "server", "storage", "ibm", "honeywell",
                 "vsphere", "vcf", "flasharray", "power9", "windows server", "sql server"]),
    ("M365 & Power Platform", ["m365", "microsoft 365", "office 365", "o365", "visio",
                                "power bi", "copilot", "windows 365", "defender", "teams",
                                "power platform", "power apps"]),
    ("IdAM", ["quest", "odm", "on-demand migration", "active directory", "ad migration",
              "identity", "iam", "privileged"]),
    ("Service Management (SNow)", ["servicenow", "service-now", "snow", "itsm", "itom",
                                    "app engine"]),
]


def categorise(text: str, filename: str, services: list, vendor: str) -> str:
    """Score-based category matching."""
    blob = (
        text[:5000].lower() + " " +
        filename.lower() + " " +
        " ".join(services).lower() + " " +
        vendor.lower()
    )
    
    scores = {}
    for cat, keywords in CATEGORY_RULES:
        score = 0
        for kw in keywords:
            score += blob.count(kw)
        if score > 0:
            scores[cat] = score
    
    if scores:
        return max(scores.items(), key=lambda x: x[1])[0]
    
    return "Other"


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def heuristic_extract(text: str, filename: str) -> Dict:
    """Extract everything we can locally — NO AI CALLS."""
    vendor = extract_vendor(text, filename)
    services = extract_services(text)
    country, region = extract_country_region(text, filename)
    
    return {
        "vendor": vendor,
        "price": extract_price(text),
        "services": services,
        "country": country,
        "region": region,
        "year": extract_year(text, filename),
        "quarter": extract_quarter(text, filename),
        "category": categorise(text, filename, services, vendor),
    }
