"""
Configuration loader and validator for the AP Rules Engine.
Loads policy configuration from backend/data/policy_config.json.
Supports runtime updates without server restart.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "policy_config.json"

_CURRENT_CONFIG: Optional[Dict[str, Any]] = None


def validate_policy_config(config: Dict[str, Any]) -> None:
    """
    Validates the structure and data types of a policy configuration.
    Raises ValueError with descriptive messages if validation fails.
    """
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object.")

    # 1. Categories validation
    if "categories" not in config or not isinstance(config["categories"], dict):
        raise ValueError("Configuration missing required 'categories' object.")

    for cat_name, cat_rule in config["categories"].items():
        if not isinstance(cat_rule, dict):
            raise ValueError(f"Category '{cat_name}' must be an object.")
        if "limit" not in cat_rule or not isinstance(cat_rule["limit"], (int, float)):
            raise ValueError(f"Category '{cat_name}' missing numeric 'limit'.")
        if cat_rule["limit"] < 0:
            raise ValueError(f"Category '{cat_name}' limit cannot be negative.")
        if "po_required" not in cat_rule or not isinstance(cat_rule["po_required"], bool):
            raise ValueError(f"Category '{cat_name}' missing boolean 'po_required'.")

    # 2. Approval ladder validation
    if "approval_ladder" not in config or not isinstance(config["approval_ladder"], list):
        raise ValueError("Configuration missing required 'approval_ladder' list.")

    for item in config["approval_ladder"]:
        if not isinstance(item, dict) or "role" not in item:
            raise ValueError("Each item in 'approval_ladder' must have a 'role'.")
        max_amt = item.get("max_amount")
        if max_amt is not None and not isinstance(max_amt, (int, float)):
            raise ValueError(f"Approver '{item['role']}' max_amount must be a number or null.")
        if max_amt is not None and max_amt < 0:
            raise ValueError(f"Approver '{item['role']}' max_amount cannot be negative.")

    # 3. Duplicate matching validation
    if "duplicate_matching" not in config or not isinstance(config["duplicate_matching"], dict):
        raise ValueError("Configuration missing required 'duplicate_matching' object.")

    dup = config["duplicate_matching"]
    for field in ("fuzzy_similarity_threshold", "amount_tolerance_percent", "date_window_days"):
        if field not in dup or not isinstance(dup[field], (int, float)):
            raise ValueError(f"Duplicate matching missing numeric '{field}'.")

    # 4. Other thresholds
    if "po_tolerance_percent" not in config or not isinstance(config["po_tolerance_percent"], (int, float)):
        raise ValueError("Configuration missing numeric 'po_tolerance_percent'.")

    if "confidence_threshold_auto_flag" not in config or not isinstance(config["confidence_threshold_auto_flag"], (int, float)):
        raise ValueError("Configuration missing numeric 'confidence_threshold_auto_flag'.")


def load_policy_config(config_path: Optional[str | Path] = None) -> Dict[str, Any]:
    """
    Loads and validates the policy configuration from disk.
    Caches the configuration in memory.
    """
    global _CURRENT_CONFIG
    target_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not target_path.exists():
        raise FileNotFoundError(f"Policy configuration file not found at: {target_path}")

    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    validate_policy_config(data)
    _CURRENT_CONFIG = data
    return _CURRENT_CONFIG


def get_policy_config() -> Dict[str, Any]:
    """
    Returns the current in-memory policy configuration, loading it if not yet loaded.
    """
    global _CURRENT_CONFIG
    if _CURRENT_CONFIG is None:
        return load_policy_config()
    return _CURRENT_CONFIG


def save_policy_config(new_config: Dict[str, Any], config_path: Optional[str | Path] = None) -> Dict[str, Any]:
    """
    Validates, saves to disk, and updates the in-memory policy configuration.
    """
    global _CURRENT_CONFIG
    validate_policy_config(new_config)
    target_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(new_config, f, indent=2)

    _CURRENT_CONFIG = new_config
    return _CURRENT_CONFIG


def reload_policy_config() -> Dict[str, Any]:
    """Forces reloading from disk."""
    return load_policy_config()


# --- Normalized helper getters for rules engine components ---

def get_category_policy() -> Dict[str, Dict[str, Any]]:
    cfg = get_policy_config()
    return cfg.get("categories", {})


def get_approval_ladder() -> Dict[str, float]:
    """
    Returns ladder as a dict mapping role to authority ceiling (float).
    CFO or null max_amount maps to float('inf').
    """
    cfg = get_policy_config()
    ladder_list = cfg.get("approval_ladder", [])
    ladder_dict: Dict[str, float] = {}
    for item in ladder_list:
        role = item["role"]
        max_amt = item.get("max_amount")
        ladder_dict[role] = float("inf") if max_amt is None else float(max_amt)
    return ladder_dict


def get_po_tolerance_percent() -> float:
    """
    Returns PO tolerance as a fraction (e.g. 5% -> 0.05).
    """
    cfg = get_policy_config()
    val = cfg.get("po_tolerance_percent", 5)
    return float(val) / 100.0 if float(val) > 0.5 else float(val)


def get_duplicate_date_window_days() -> int:
    cfg = get_policy_config()
    dup = cfg.get("duplicate_matching", {})
    return int(dup.get("date_window_days", 7))


def get_fuzzy_vendor_similarity_threshold() -> float:
    """
    Returns rapidfuzz score threshold (0 - 100 scale, e.g. 90.0).
    """
    cfg = get_policy_config()
    dup = cfg.get("duplicate_matching", {})
    val = float(dup.get("fuzzy_similarity_threshold", 0.90))
    return val * 100.0 if val <= 1.0 else val


def get_fuzzy_amount_tolerance_percent() -> float:
    """
    Returns amount difference tolerance as a fraction (e.g. 1% -> 0.01).
    """
    cfg = get_policy_config()
    dup = cfg.get("duplicate_matching", {})
    val = float(dup.get("amount_tolerance_percent", 1))
    return val / 100.0 if val > 0.05 else val


def get_confidence_threshold_auto_flag() -> float:
    cfg = get_policy_config()
    return float(cfg.get("confidence_threshold_auto_flag", 0.8))
