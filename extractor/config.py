# extractor/config.py
# ═══════════════════════════════════════════════
# Central configuration for all settings,
# folder mappings, service patterns, vendors
# ═══════════════════════════════════════════════

import os
from dotenv import load_dotenv

load_dotenv()

# ── SharePoint ──────────────────────────────────
SHAREPOINT_SITE_URL = os.environ.get(
    "SHAREPOINT_SITE_URL",
    "https://pwc.sharepoint.com/teams/GBL-ADV-DDVITInfraCoE"
)

SHAREPOINT_BASE_PATH = (
    "Shared Documents/General/"
    "06 - Reinvest Projects & Trainings/"
    "Vendor Contracting Repository"
)

# ── Azure App Registration ───────────────────────
AZURE_CLIENT_ID     = os.environ.get("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
AZURE_TENANT_ID     = os.environ.get("AZURE_TENANT_ID", "")

# ── AI APIs ─────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLAMA_API_KEY     = os.environ.get("LLAMA_API_KEY", "")

# ── GitHub ───────────────────────────────────────
GITHUB_TOKEN = os.environ.get("G_TOKEN", "")
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "")

# ── Output ───────────────────────────────────────
OUTPUT_FILE      = "catalog_data.json"
ERROR_LOG_FILE   = "extraction_errors.json"
PROGRESS_FILE    = "extraction_progress.json"

# ── SharePoint Folder → Category Mapping ────────
FOLDER_TO_CATEGORY = {
    "Cybersecurity":             "Cybersecurity",
    "Hosting":                   "Hosting",
    "Network & Telecom":         "Network & Telecom",
    "Service Management (SNow)": "Service Management (SNow)",
    "IdAM":                      "IdAM",
    "M365 & Power Platform":     "M365 & Power Platform",
    "MSP":                       "MSP",
    "Summaries & Reporting":     "Summaries & Reporting",
}

# ── Supported File Extensions ────────────────────
SUPPORTED_EXTENSIONS = {
    ".pdf":  "pdf",
    ".xlsx": "excel",
    ".xls":  "excel",
    ".csv":  "csv",
    ".txt":  "text",
    ".docx": "word",
    ".doc":  "word",
}

# ── Known Vendors (for matching) ─────────────────
KNOWN_VENDORS = [
    "NTT Data",
    "NTT DOCOMO",
    "TrendMicro",
    "KnowBe4",
    "SHI",
    "PC Connection",
    "CDW",
    "Equinix",
    "Quest",
    "Proquire LLC",
    "ServiceNow",
    "Microsoft",
    "Copeland LP",
    "Thrive",
    "Ricoh",
    "Honeywell",
    "Cisco",
    "Palo Alto",
    "CrowdStrike",
    "Zscaler",
    "CyberArk",
    "Forescout",
    "SolarWinds",
    "VMware",
    "NetApp",
    "Oracle",
    "IBM",
    "HPE",
    "Red Hat",
    "Pure Storage",
    "SailPoint",
    "Okta",
]

# ── Known Services (for matching) ────────────────
KNOWN_SERVICES = [
    # Cybersecurity
    "Trend Vision One Endpoint Security",
    "Apex One SaaS",
    "Trend Micro Email Security Advanced",
    "Cloud App Security XDR",
    "Vision One XDR Add-on Email",
    "Vision One Credits ASRM",
    "KnowBe4 PhishER Subscription",
    "Security Awareness Training",
    "CyberArk Secure IT Ops Standard",
    "Privileged Access Management",
    "CyberArk Endpoint Privilege Manager",
    "Forescout Network Access Control",
    "Endpoint Visibility",
    "Forescout eyeInspect",
    "Zscaler ZIA Transformation Edition",
    "Zero Trust Network Access",
    "Zscaler Internet Access",
    "Palo Alto NGFW Firewall",
    "Palo Alto PA 445",
    # Network
    "Cisco Catalyst C8300",
    "Cisco Catalyst 9800-L",
    "Cisco Catalyst 9200-L",
    "Cisco Wireless 9176I",
    "Cisco Nexus 9300L",
    "Cisco Meraki MR46E",
    "Cisco ISE Virtual Machine",
    "Cisco SMARTnet",
    "Cisco DNA Advantage Cloud Lic 3Y",
    "Cisco License and Maintenance",
    "SolarWinds NPM",
    "Equinix Network Interconnect Lines",
    "Global WAN Connectivity",
    # Hosting
    "VMware Cloud Foundation 3-Year",
    "VMware vSphere Enterprise",
    "NetApp AFF A30 HA System",
    "NetApp AFF A250 HA pair",
    "Oracle Database Appliance X11-L",
    "Oracle Database Enterprise Edition",
    "HPE ProLiant DL380 Gen12",
    "IBM Power9 Server 924",
    "Red Hat Enterprise Linux",
    "Microsoft Windows Server Datacenter Edition",
    "Microsoft SQL Server Standard Core Edition",
    # M365
    "M365 E5 License",
    "M365 E3 License",
    "M365 F3 License",
    "M365 Copilot",
    "Power BI Premium",
    "Power BI Pro",
    "Power Apps Per User",
    "Power Automate Per User",
    "Microsoft Defender",
    "Windows 365",
    "Visio P1",
    "Visio P2",
    "Project P1",
    "Project P3",
    "ShareGate Migrate Enterprise 25 Seats",
    # IdAM
    "Quest On-Demand Migration Suite T5",
    "Quest On-Demand Migration M365",
    "Active Directory Migration",
    "Quest Professional Services",
    # ServiceNow
    "ServiceNow IT Service Management Professional",
    "ServiceNow App Engine Enterprise",
    "ServiceNow Business Stakeholder",
    "ServiceNow IT Operations Management Visibility",
    "ServiceNow Software Asset Management Professional",
    "ServiceNow Integration Hub Professional",
    "ServiceNow Strategic Portfolio Management Standard",
    "ServiceNow Workplace Service Delivery Enterprise",
    "ServiceNow Impact Guided v3",
]

# ── Claude Model ──────────────────────────────────
CLAUDE_MODEL      = "claude-opus-4-5"
CLAUDE_MAX_TOKENS = 1000

# ── LlamaCloud ────────────────────────────────────
LLAMA_TIER   = "agentic"
LLAMA_EXPAND = ["markdown_full"]

# ── Price Validation ──────────────────────────────
MIN_VALID_PRICE =        1_000   # $1K minimum
MAX_VALID_PRICE = 50_000_000     # $50M maximum

# ── Rate Limiting ─────────────────────────────────
DELAY_BETWEEN_FILES    = 2   # seconds
DELAY_BETWEEN_FOLDERS  = 3   # seconds
MAX_RETRIES            = 3
