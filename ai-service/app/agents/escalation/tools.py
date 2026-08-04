import logging

logger = logging.getLogger(__name__)

# Tier keywords looked up in Customer.tags / metadata before falling back to "standard".
TIER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "platinum": ("platinum", "tier:platinum"),
    "vip": ("vip", "tier:vip", "premium"),
    "gold": ("gold", "tier:gold"),
    "silver": ("silver", "tier:silver"),
    "bronze": ("bronze", "tier:bronze"),
}

TIER_RANK = {"platinum": 5, "vip": 4, "gold": 3, "silver": 2, "bronze": 1, "standard": 0}

# Issue categories mapped to the team that owns them.
CATEGORY_TEAMS: dict[str, str] = {
    "account_security": "security",
    "payment_failure": "billing",
    "refund": "billing",
    "order_status": "fulfillment",
    "returns": "fulfillment",
    "product_quality": "fulfillment",
    "technical": "technical",
    "account": "account",
    "general": "general",
}

# Expected resolution ETA (hours) per priority.
PRIORITY_ETA_HOURS: dict[str, int] = {
    "p1": 2,
    "p2": 8,
    "p3": 24,
    "p4": 48,
}

# Critical categories always escalate to P1 regardless of tier.
CRITICAL_CATEGORIES = {"account_security"}

# Priority matrix: category -> tier group -> priority.
PRIORITY_MATRIX: dict[str, dict[str, str]] = {
    "account_security": {"high": "p1", "standard": "p1"},
    "payment_failure": {"high": "p1", "standard": "p2"},
    "refund": {"high": "p2", "standard": "p3"},
    "order_status": {"high": "p2", "standard": "p3"},
    "returns": {"high": "p3", "standard": "p3"},
    "technical": {"high": "p3", "standard": "p4"},
    "account": {"high": "p3", "standard": "p4"},
    "product_quality": {"high": "p4", "standard": "p4"},
    "general": {"high": "p4", "standard": "p4"},
}


def determine_tier(customer) -> str:
    """Derive the customer tier from tags/metadata. Falls back to 'standard'."""
    if customer is None:
        return "standard"
    tags = [t.lower() for t in (getattr(customer, "tags", None) or [])]
    metadata = getattr(customer, "metadata", None) or {}
    metadata_values = [str(v).lower() for v in metadata.values()]
    haystack = " ".join(tags + metadata_values)
    for tier, keywords in TIER_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            return tier
    return "standard"


def resolve_priority(category: str | None, tier: str | None) -> str:
    """Calculate P1-P4 priority based on issue category and customer tier."""
    category = (category or "general").lower()
    tier = (tier or "standard").lower()
    if category in CRITICAL_CATEGORIES:
        return "p1"
    tier_group = "high" if TIER_RANK.get(tier, 0) >= 3 else "standard"
    return PRIORITY_MATRIX.get(category, PRIORITY_MATRIX["general"]).get(tier_group, "p4")


def assign_team(category: str | None) -> str:
    """Route the escalation to the owning team based on the issue category."""
    return CATEGORY_TEAMS.get((category or "general").lower(), "general")


def eta_hours_for_priority(priority: str | None) -> int:
    """Expected resolution hours for a priority level."""
    return PRIORITY_ETA_HOURS.get((priority or "p4").lower(), 48)
