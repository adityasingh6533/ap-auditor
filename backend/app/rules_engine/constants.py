"""
Configuration rules and constants for the AP Rules Engine.
Delegates to config_loader for dynamic, non-hardcoded policy configuration.
"""

from .config_loader import (
    load_policy_config,
    get_policy_config,
    save_policy_config,
    reload_policy_config,
    get_category_policy,
    get_approval_ladder,
    get_po_tolerance_percent,
    get_duplicate_date_window_days,
    get_fuzzy_vendor_similarity_threshold,
    get_fuzzy_amount_tolerance_percent,
    get_confidence_threshold_auto_flag,
)

CATEGORY_POLICY = get_category_policy()
APPROVER_LADDER = get_approval_ladder()
PO_TOLERANCE_PERCENT = get_po_tolerance_percent()
DUPLICATE_DATE_WINDOW_DAYS = get_duplicate_date_window_days()
FUZZY_VENDOR_SIMILARITY_THRESHOLD = get_fuzzy_vendor_similarity_threshold()
FUZZY_AMOUNT_TOLERANCE_PERCENT = get_fuzzy_amount_tolerance_percent()
CONFIDENCE_THRESHOLD_AUTO_FLAG = get_confidence_threshold_auto_flag()


def refresh_constants() -> None:
    """Refreshes module variables after policy config reload."""
    global CATEGORY_POLICY, APPROVER_LADDER, PO_TOLERANCE_PERCENT
    global DUPLICATE_DATE_WINDOW_DAYS, FUZZY_VENDOR_SIMILARITY_THRESHOLD
    global FUZZY_AMOUNT_TOLERANCE_PERCENT, CONFIDENCE_THRESHOLD_AUTO_FLAG

    reload_policy_config()
    CATEGORY_POLICY = get_category_policy()
    APPROVER_LADDER = get_approval_ladder()
    PO_TOLERANCE_PERCENT = get_po_tolerance_percent()
    DUPLICATE_DATE_WINDOW_DAYS = get_duplicate_date_window_days()
    FUZZY_VENDOR_SIMILARITY_THRESHOLD = get_fuzzy_vendor_similarity_threshold()
    FUZZY_AMOUNT_TOLERANCE_PERCENT = get_fuzzy_amount_tolerance_percent()
    CONFIDENCE_THRESHOLD_AUTO_FLAG = get_confidence_threshold_auto_flag()
