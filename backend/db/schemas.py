"""
Pydantic Models / Schemas
Data models for the IT BOM Creation System
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class BOMStatus(str, Enum):
    """BOM Status Enum"""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    APPROVED = "approved"
    SENT_TO_VENDOR = "sent_to_vendor"
    ARCHIVED = "archived"


class UserRole(str, Enum):
    """User Role Enum"""
    ADMIN = "admin"
    CREATOR = "creator"
    VIEWER = "viewer"


# ============================================================================
# BOM Models
# ============================================================================

class LineItem(BaseModel):
    """Individual line item in a BOM"""
    line_number: int
    description: str
    sku: Optional[str] = None
    specification: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    vendor: Optional[str] = None
    vendor_route: Optional[str] = None  # IBM BP, Cisco Direct, CDW, Entity
    quantity: float
    unit_price: float
    extended_price: float
    currency: str = "USD"
    term: Optional[str] = None  # 1-year, 3-year, etc.
    otc: Optional[float] = None  # One-time cost
    run_costs_annual: Optional[float] = None  # Annual recurring
    support_level: Optional[str] = None
    notes: Optional[str] = None
    explanation: Optional[str] = None  # AI-generated explanation
    dependencies: List[int] = []  # Line numbers of dependent items


class BOMTotals(BaseModel):
    """BOM totals and summary"""
    hardware: float = 0.0
    software: float = 0.0
    services: float = 0.0
    bundled: float = 0.0
    subtotal: float = 0.0
    total_otc: float = 0.0  # One-time costs
    total_run_costs_annual: float = 0.0  # Annual recurring
    tco_3year: float = 0.0  # 3-year total cost of ownership


class BOMVersion(BaseModel):
    """BOM version history"""
    version: int
    created_at: datetime
    created_by: str
    change_description: Optional[str] = None
    changes: List[Dict[str, Any]] = []  # List of changes made


class BOM(BaseModel):
    """Complete BOM document"""
    id: Optional[str] = Field(default=None, alias="_id")
    bom_id: str
    project_name: str
    category: str
    region: Optional[str] = None
    country: Optional[str] = None
    line_items: List[LineItem]
    totals: BOMTotals
    status: BOMStatus = BOMStatus.DRAFT
    version: int = 1
    versions: List[BOMVersion] = []
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_by: Optional[str] = None
    modified_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}
    
    class Config:
        use_enum_values = True
        populate_by_name = True


# ============================================================================
# Chat Session Models
# ============================================================================

class ChatMessage(BaseModel):
    """Individual chat message"""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}


class SessionContext(BaseModel):
    """Context maintained during BOM creation session"""
    category: Optional[str] = None
    requirements: Dict[str, Any] = {}
    template_id: Optional[str] = None
    questions_asked: int = 0
    questions_total: int = 5
    progress_percentage: float = 0.0
    partial_bom: Optional[Dict[str, Any]] = None


class ChatSession(BaseModel):
    """Chat session for BOM creation"""
    id: Optional[str] = Field(default=None, alias="_id")
    session_id: str
    user_id: str
    conversation: List[ChatMessage] = []
    context: SessionContext = Field(default_factory=SessionContext)
    status: str = "active"  # active, completed, abandoned
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    bom_id: Optional[str] = None  # Link to generated BOM
    
    class Config:
        populate_by_name = True


# ============================================================================
# Pattern Models
# ============================================================================

class BundleRule(BaseModel):
    """Bundle rule: if X then Y must be included"""
    if_item: str  # SKU or item type
    then_required: List[str]  # Required SKUs or item types
    confidence: float  # 0.0 to 1.0
    source_boms: List[str] = []  # Files where this pattern was found


class QuantityFormula(BaseModel):
    """Quantity relationship formula"""
    target_item: str  # SKU or item type
    formula: str  # e.g., "servers * 2" for CPUs
    description: str


class PricingPattern(BaseModel):
    """Pricing pattern"""
    pattern_type: str  # "support_percentage", "volume_discount", "term_discount"
    rule: Dict[str, Any]
    confidence: float


class Pattern(BaseModel):
    """Learned pattern from historical BOMs"""
    id: Optional[str] = Field(default=None, alias="_id")
    pattern_id: str
    category: Optional[str] = None
    pattern_type: str  # "bundle", "quantity", "pricing", "dependency"
    bundle_rules: List[BundleRule] = []
    quantity_formulas: List[QuantityFormula] = []
    pricing_patterns: List[PricingPattern] = []
    confidence: float
    source_count: int  # Number of BOMs this pattern was found in
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True


# ============================================================================
# Template Models
# ============================================================================

class TemplateQuestion(BaseModel):
    """Question to ask user"""
    question_id: str
    question_text: str
    question_type: str  # "text", "number", "choice", "multi_choice"
    options: List[str] = []
    validation: Optional[Dict[str, Any]] = None
    help_text: Optional[str] = None


class TemplateItem(BaseModel):
    """Template line item"""
    description: str
    sku: Optional[str] = None
    category: str
    quantity_formula: Optional[str] = None  # Formula or fixed number
    price_source: str  # "historical", "manual", "vendor_api"
    required: bool = True
    conditional: Optional[str] = None  # Condition for inclusion


class Template(BaseModel):
    """BOM Template"""
    id: Optional[str] = Field(default=None, alias="_id")
    template_id: str
    name: str
    category: str
    description: str
    questions: List[TemplateQuestion]
    base_items: List[TemplateItem]
    rules: Dict[str, Any] = {}  # Bundle rules, formulas, etc.
    example_boms: List[str] = []  # Reference BOM IDs
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True


# ============================================================================
# User Models
# ============================================================================

class User(BaseModel):
    """User account"""
    id: Optional[str] = Field(default=None, alias="_id")
    user_id: str
    email: str
    name: str
    role: UserRole = UserRole.CREATOR
    preferences: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
        populate_by_name = True


# ============================================================================
# Analytics Models
# ============================================================================

class AnalyticsMetric(BaseModel):
    """Analytics metric"""
    id: Optional[str] = Field(default=None, alias="_id")
    metric_id: str
    metric_type: str  # "spending", "vendor_performance", "pattern_insight", "trend"
    period: str  # "daily", "weekly", "monthly", "quarterly"
    period_start: datetime
    period_end: datetime
    data: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
