"""
BOM management API endpoints
"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import io
import json

from db import get_cosmos_client, BOM, BOMStatus

router = APIRouter(prefix="/api/bom", tags=["bom"])


# Request/Response Models
class BOMListRequest(BaseModel):
    user_id: Optional[str] = None
    category: Optional[str] = None
    status: Optional[BOMStatus] = None
    limit: int = 50


class BOMResponse(BaseModel):
    bom: BOM


class BOMListResponse(BaseModel):
    boms: List[BOM]
    count: int


class BOMUpdateRequest(BaseModel):
    line_items: Optional[List[Dict[str, Any]]] = None
    status: Optional[BOMStatus] = None
    notes: Optional[str] = None


class ValidateResponse(BaseModel):
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []


@router.get("/{bom_id}", response_model=BOMResponse)
async def get_bom(bom_id: str):
    """
    Get a specific BOM by ID
    """
    try:
        cosmos_client = get_cosmos_client()
        
        bom_data = cosmos_client.get_bom(bom_id)
        if not bom_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="BOM not found"
            )
        
        return BOMResponse(bom=BOM(**bom_data))
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get BOM: {str(e)}"
        )


@router.get("", response_model=BOMListResponse)
async def list_boms(
    user_id: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
):
    """
    List BOMs with optional filters
    """
    try:
        cosmos_client = get_cosmos_client()
        
        # Build query
        filters = {}
        if user_id:
            filters["user_id"] = user_id
        if category:
            filters["category"] = category
        if status:
            filters["status"] = status
        
        boms_data = cosmos_client.list_boms(filters, limit)
        boms = [BOM(**bom) for bom in boms_data]
        
        return BOMListResponse(
            boms=boms,
            count=len(boms)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list BOMs: {str(e)}"
        )


@router.put("/{bom_id}", response_model=BOMResponse)
async def update_bom(bom_id: str, request: BOMUpdateRequest):
    """
    Update a BOM
    """
    try:
        cosmos_client = get_cosmos_client()
        
        # Get existing BOM
        bom_data = cosmos_client.get_bom(bom_id)
        if not bom_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="BOM not found"
            )
        
        bom = BOM(**bom_data)
        
        # Update fields
        if request.line_items is not None:
            bom.line_items = request.line_items
        if request.status is not None:
            bom.status = request.status
        if request.notes is not None:
            bom.notes = request.notes
        
        bom.updated_at = datetime.utcnow()
        
        # Save
        cosmos_client.update_bom(bom_id, bom.model_dump())
        
        return BOMResponse(bom=bom)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update BOM: {str(e)}"
        )


@router.post("/validate", response_model=ValidateResponse)
async def validate_bom(bom: BOM):
    """
    Validate a BOM for completeness and correctness
    """
    try:
        errors = []
        warnings = []
        
        # Check required fields
        if not bom.line_items:
            errors.append("BOM must have at least one line item")
        
        # Check line items
        for idx, item in enumerate(bom.line_items):
            if not item.description:
                errors.append(f"Line {idx + 1}: Missing description")
            if item.qty <= 0:
                errors.append(f"Line {idx + 1}: Quantity must be greater than 0")
            if item.unit_price < 0:
                errors.append(f"Line {idx + 1}: Unit price cannot be negative")
        
        # Check totals
        if bom.totals:
            calculated_total = sum(item.extended_price for item in bom.line_items)
            if abs(calculated_total - bom.totals.total_otc) > 0.01:
                warnings.append(
                    f"Total mismatch: Line items sum to ${calculated_total:.2f} "
                    f"but totals show ${bom.totals.total_otc:.2f}"
                )
        
        return ValidateResponse(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate BOM: {str(e)}"
        )


@router.post("/export/excel")
async def export_bom_excel(bom_id: str):
    """
    Export BOM to Excel format
    TODO: Implement actual Excel generation with openpyxl
    """
    try:
        cosmos_client = get_cosmos_client()
        
        bom_data = cosmos_client.get_bom(bom_id)
        if not bom_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="BOM not found"
            )
        
        # For now, return JSON (will implement Excel later)
        json_data = json.dumps(bom_data, indent=2, default=str)
        
        return StreamingResponse(
            io.BytesIO(json_data.encode()),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=bom_{bom_id}.json"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export BOM: {str(e)}"
        )


@router.post("/export/pdf")
async def export_bom_pdf(bom_id: str):
    """
    Export BOM to PDF format
    TODO: Implement PDF generation
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="PDF export not yet implemented"
    )
