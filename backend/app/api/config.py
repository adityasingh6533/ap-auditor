"""
API routes for viewing and updating configurable AP audit policies and rules.
Allows runtime modification without server restart.
"""

from typing import Any, Dict
from fastapi import APIRouter, HTTPException, status
from ..rules_engine.config_loader import (
    get_policy_config,
    save_policy_config,
    validate_policy_config,
)
from ..rules_engine.constants import refresh_constants

router = APIRouter(prefix="/api/config", tags=["Configuration"])


@router.get("", response_model=Dict[str, Any])
def get_config() -> Dict[str, Any]:
    """
    Returns the current policy configuration: category spend limits,
    approval ladder, duplicate matching tolerances, and confidence thresholds.
    """
    try:
        return get_policy_config()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read policy configuration: {str(e)}",
        )


@router.put("", response_model=Dict[str, Any])
def update_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts updated policy config JSON, validates schema and values,
    saves to disk, and immediately reloads rules engine thresholds in memory.
    """
    try:
        validate_policy_config(payload)
        updated = save_policy_config(payload)
        refresh_constants()
        return {
            "message": "Policy configuration successfully updated and reloaded.",
            "config": updated,
        }
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid configuration: {str(ve)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save policy configuration: {str(e)}",
        )
