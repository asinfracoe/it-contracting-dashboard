# extractor/config.py

import os
from dotenv import load_dotenv

load_dotenv()

# SharePoint
SHAREPOINT_SITE_URL = os.environ.get(
    "SHAREPOINT_SITE_URL",
    "https://pwc.sharepoint.com/teams/GBL-ADV-DDVITInfraCoE"
)

SHAREPOINT_BASE_PATH = (
    "Shared Documents/General/"
    "06 - Reinvest Projects & Trainings/"
    "Vendor Contracting Repository"
)

# Azure App Registration
AZURE_CLIENT_ID     = os.environ.get("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
AZURE_TENANT_ID     = os.environ.get("AZURE_TENANT_ID", "")

# AI — Groq (Free)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# PDF Parsing — LlamaCloud (Free tier)
LLAMA_API_KEY = os.environ.get("LLAMA_API_KEY", "")

# GitHub
GITHUB_TOKEN = os.environ.get("G_TOKEN", "")
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "")

# Output Files
OUTPUT_FILE    = "catalog_data.json"
ERROR_LOG_FILE = "extraction_errors.json"
PROGRESS_FILE  = "extraction_progress.json"

# Folder to Category Mapping
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

# Supported File Types
SUPPORTED_EXTENSIONS = {
    ".pdf":  "pdf",
    ".xlsx": "excel",
    ".xls":  "excel",
    ".csv":  "csv",
    ".txt":  "text",
    ".docx": "word",
    ".doc":  "word",
}

# Known Vendors
KNOWN_VENDORS = [
    "NTT Data", "NTT DOCOMO", "TrendMicro", "KnowBe4",
    "SHI", "PC Connection", "CDW", "Equinix", "Quest",
    "Proquire LLC", "ServiceNow", "Microsoft", "Copeland LP",
    "Thrive", "Ricoh", "Honeywell", "Cisco", "Palo Alto",
    "CrowdStrike", "Zscaler", "CyberArk", "Forescout",
    "SolarWinds", "VMware", "NetApp", "Oracle", "IBM",
    "HPE", "Red Hat", "Pure Storage", "SailPoint", "Okta",
]

# Known Services
KNOWN_SERVICES = [
    "Trend Vision One Endpoint Security",
    "Apex One SaaS",
    "Trend Micro Email Security Advanced",
    "KnowBe4 PhishER Subscription",
    "Security Awareness Training",
    "CyberArk Privileged Access Management",
    "Forescout Network Access Control",
    "Zscaler ZIA Transformation Edition",
    "Palo Alto NGFW Firewall",
    "Cisco Catalyst C8300",
    "Cisco Catalyst 9800-L",
    "Cisco SMARTnet",
    "SolarWinds NPM",
    "Equinix Network Interconnect",
    "VMware Cloud Foundation",
    "NetApp AFF A30 HA System",
    "Oracle Database Enterprise Edition",
    "HPE ProLiant DL380 Gen12",
    "Red Hat Enterprise Linux",
    "M365 E5 License",
    "M365 E3 License",
    "M365 Copilot",
    "Power BI Premium",
    "Power Apps Per User",
    "Microsoft Defender",
    "Quest On-Demand Migration Suite",
    "ServiceNow ITSM Professional",
    "ServiceNow App Engine Enterprise",
    "ServiceNow Software Asset Management",
]

# LlamaCloud Settings
LLAMA_TIER   = "agentic"
LLAMA_EXPAND = ["markdown_full"]

# Price Validation
MIN_VALID_PRICE =        500
MAX_VALID_PRICE = 50_000_000

# Rate Limiting
DELAY_BETWEEN_FILES   = 1
DELAY_BETWEEN_FOLDERS = 2
MAX_RETRIES           = 3
