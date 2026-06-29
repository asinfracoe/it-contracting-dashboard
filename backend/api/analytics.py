"""
Analytics API endpoints
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# Response Models
class SpendingDataPoint(BaseModel):
    category: str
    amount: float


class SpendingResponse(BaseModel):
    period: str
    data: List[SpendingDataPoint]
    total: float


class VendorPerformance(BaseModel):
    vendor: str
    total_spend: float
    bom_count: int
    avg_delivery_time_days: int


class VendorPerformanceResponse(BaseModel):
    vendors: List[VendorPerformance]


class PatternData(BaseModel):
    pattern_id: str
    description: str
    frequency: int
    avg_cost: float


class PatternsResponse(BaseModel):
    patterns: List[PatternData]


class TrendDataPoint(BaseModel):
    month: str
    spending: float


class TrendsResponse(BaseModel):
    data: List[TrendDataPoint]


@router.get("/spending", response_model=SpendingResponse)
async def get_spending(period: str = "monthly"):
    """
    Get spending breakdown by category
    TODO: Query real data from Cosmos DB
    """
    try:
        # Dummy data for now
        dummy_data = [
            SpendingDataPoint(category="Network", amount=850000),
            SpendingDataPoint(category="Compute", amount=650000),
            SpendingDataPoint(category="Storage", amount=400000),
            SpendingDataPoint(category="Software", amount=350000),
            SpendingDataPoint(category="Services", amount=250000),
        ]
        
        total = sum(d.amount for d in dummy_data)
        
        return SpendingResponse(
            period=period,
            data=dummy_data,
            total=total
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get spending data: {str(e)}"
        )


@router.get("/vendors", response_model=VendorPerformanceResponse)
async def get_vendor_performance():
    """
    Get vendor performance metrics
    TODO: Query real data from Cosmos DB
    """
    try:
        # Dummy data
        vendors = [
            VendorPerformance(
                vendor="CDW",
                total_spend=1200000,
                bom_count=15,
                avg_delivery_time_days=12
            ),
            VendorPerformance(
                vendor="Entity",
                total_spend=950000,
                bom_count=12,
                avg_delivery_time_days=10
            ),
            VendorPerformance(
                vendor="Cisco Direct",
                total_spend=650000,
                bom_count=8,
                avg_delivery_time_days=15
            ),
            VendorPerformance(
                vendor="Dell",
                total_spend=450000,
                bom_count=6,
                avg_delivery_time_days=14
            ),
            VendorPerformance(
                vendor="IBM BP",
                total_spend=300000,
                bom_count=4,
                avg_delivery_time_days=18
            ),
        ]
        
        return VendorPerformanceResponse(vendors=vendors)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get vendor performance: {str(e)}"
        )


@router.get("/patterns", response_model=PatternsResponse)
async def get_patterns():
    """
    Get common patterns and bundles
    TODO: Query real patterns from Cosmos DB
    """
    try:
        # Dummy data
        patterns = [
            PatternData(
                pattern_id="pat_001",
                description="Cisco Nexus HA Pair",
                frequency=23,
                avg_cost=85000
            ),
            PatternData(
                pattern_id="pat_002",
                description="VMware + Veeam Bundle",
                frequency=19,
                avg_cost=125000
            ),
            PatternData(
                pattern_id="pat_003",
                description="Dell Server Cluster",
                frequency=15,
                avg_cost=95000
            ),
        ]
        
        return PatternsResponse(patterns=patterns)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get patterns: {str(e)}"
        )


@router.get("/trends", response_model=TrendsResponse)
async def get_trends():
    """
    Get spending trends over time
    TODO: Query real data from Cosmos DB
    """
    try:
        # Generate dummy 6-month trend
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
        spending = [420000, 380000, 450000, 520000, 480000, 550000]
        
        data = [
            TrendDataPoint(month=month, spending=spend)
            for month, spend in zip(months, spending)
        ]
        
        return TrendsResponse(data=data)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trends: {str(e)}"
        )
