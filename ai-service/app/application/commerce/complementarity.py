"""Deterministic complementarity engine for bundle composition (Domain 5 / B16).

A bundle is only commercially meaningful when its products belong together for
the shopper's use case. This module provides a centralized, deterministic
compatibility hierarchy (no LLM, no embeddings, no per-pair inference):

    1. Explicit catalog compatibility metadata  (product.metadata)
    2. Explicit complementary-product relationships
    3. Category complementarity rules            (centralized rule table)
    4. Product attributes / structured metadata
    5. Conservative title/category heuristics    (accessory vocabulary)

The engine is store-agnostic by design: category names are resolved by the
caller from the store's own taxonomy and passed in as ``category_names``, so
merchant-specific categories keep working without hard-coding. Rules are
keyed by canonical product-type/category tokens from a fixed vocabulary; the
table below is intentionally conservative and extensible for future
merchant configuration.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

# Canonical tokens are matched against normalized product types, titles and
# category names. Keep the vocabulary small and generic.
_CANONICAL_KEYS = frozenset(
    (
        "laptop",
        "computer",
        "desktop",
        "monitor",
        "camera",
        "phone",
        "smartphone",
        "tablet",
        "tv",
        "television",
        "console",
        "gaming console",
        "mouse",
        "keyboard",
        "headset",
        "headphones",
        "earbuds",
        "speakers",
        "soundbar",
        "controller",
        "webcam",
        "microphone",
        "printer",
        "router",
        "watch",
        "smartwatch",
        "desk",
        "chair",
        "office chair",
        "lamp",
        "lighting",
        "furniture",
        "kitchenware",
        "appliance",
        "home appliance",
        "accessories",
        "accessory",
        "bag",
        "backpack",
    )
)

# Category complementarity rules (level 3): canonical primary key -> compatible
# canonical keys. Conservative and centralized; merchant-specific extension
# belongs here, not scattered across the codebase.
CATEGORY_COMPLEMENTS: dict[str, tuple[str, ...]] = {
    "laptop": ("mouse", "keyboard", "headset", "monitor", "bag", "backpack", "webcam", "speakers", "accessories"),
    "computer": ("mouse", "keyboard", "headset", "monitor", "bag", "backpack", "speakers", "accessories"),
    "desktop": ("monitor", "mouse", "keyboard", "headset", "speakers", "accessories"),
    "monitor": ("keyboard", "mouse", "webcam", "speakers", "headset", "headphones", "accessories"),
    "camera": ("memory", "tripod", "bag", "backpack", "battery", "charger", "case", "lens", "accessories"),
    "phone": ("case", "charger", "earbuds", "headphones", "holder", "cable", "accessories"),
    "smartphone": ("case", "charger", "earbuds", "headphones", "holder", "cable", "accessories"),
    "tablet": ("case", "keyboard", "stylus", "charger", "accessories"),
    "tv": ("soundbar", "speakers", "stand", "mount", "remote", "accessories"),
    "television": ("soundbar", "speakers", "stand", "mount", "remote", "accessories"),
    "console": ("controller", "headset", "headphones", "microphone", "charging", "accessories"),
    "gaming console": ("controller", "headset", "headphones", "microphone", "charging", "accessories"),
    "mouse": ("keyboard", "mousepad", "monitor", "accessories"),
    "keyboard": ("mouse", "mousepad", "monitor", "accessories"),
    "headset": ("microphone", "webcam", "monitor", "accessories"),
    "headphones": ("earbuds", "case", "cable", "accessories"),
    "earbuds": ("case", "charger", "accessories"),
    "speakers": ("soundbar", "subwoofer", "cable", "accessories"),
    "soundbar": ("speakers", "subwoofer", "cable", "accessories"),
    "webcam": ("microphone", "headset", "lighting", "accessories"),
    "microphone": ("webcam", "headset", "stand", "accessories"),
    "watch": ("strap", "charger", "case", "accessories"),
    "smartwatch": ("strap", "charger", "case", "accessories"),
    "desk": ("chair", "lamp", "monitor", "organizer", "accessories"),
    "chair": ("desk", "lamp", "cushion", "accessories"),
    "office chair": ("desk", "lamp", "cushion", "accessories"),
    "furniture": ("lighting", "decoration", "accessories"),
    "kitchenware": ("appliance", "home appliance", "accessories"),
    "appliance": ("kitchenware", "cleaning", "accessories"),
    "home appliance": ("kitchenware", "cleaning", "accessories"),
    "lighting": ("furniture", "decoration", "accessories"),
    "printer": ("ink", "toner", "paper", "cable", "accessories"),
    "router": ("cable", "adapter", "accessories"),
}

# Accessory vocabulary (level 5/6): products whose title/type/category signal
# add-on semantics complement a "device" primary without a specific rule.
_ACCESSORY_KEYWORDS = (
    "bag",
    "backpack",
    "case",
    "cover",
    "charger",
    "cable",
    "stand",
    "sleeve",
    "strap",
    "mount",
    "holder",
    "protector",
    "screen protector",
    "tripod",
    "memory",
    "card",
    "filter",
    "adapter",
    "dock",
    "stylus",
    "mousepad",
    "cooling",
    "battery",
    "keyboard cover",
)

# Device primaries: products of these keys may pair with accessory items
# (weaker signal than a category rule).
_DEVICE_KEYS = frozenset(
    {
        "laptop",
        "computer",
        "desktop",
        "monitor",
        "camera",
        "phone",
        "smartphone",
        "tablet",
        "tv",
        "television",
        "console",
        "gaming console",
        "mouse",
        "keyboard",
        "headset",
        "headphones",
        "earbuds",
        "speakers",
        "soundbar",
        "controller",
        "webcam",
        "microphone",
        "watch",
        "smartwatch",
        "printer",
        "router",
    }
)

# Explicit compatibility metadata keys (level 1/2), read from product.metadata.
_EXPLICIT_KEYS = (
    "compatible_with",
    "compatible_product_ids",
    "recommended_with",
    "complementary_to",
)

_WS_RE = re.compile(r"[^a-z0-9]+")


def _tokens(*values: Any) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        if not value:
            continue
        for token in _WS_RE.split(str(value).lower()):
            if token:
                tokens.add(token)
    return tokens


def _canonical_keys(*values: Any) -> set[str]:
    """Map raw tokens onto the canonical vocabulary (deterministic)."""
    tokens = _tokens(*values)
    keys: set[str] = set()
    for token in tokens:
        if token in _CANONICAL_KEYS:
            keys.add(token)
    joined = " ".join(sorted(tokens))
    for key in _CANONICAL_KEYS:
        if " " in key and key in joined:
            keys.add(key)
    return keys


@dataclass(frozen=True)
class PairComplementarity:
    """Deterministic complementarity between two products."""

    score: float
    label: str
    matched_key: str | None = None

    def __bool__(self) -> bool:
        return self.score > 0


class ComplementarityRules:
    """Centralized complementarity engine.

    Products are compared with a fixed hierarchy: explicit metadata first,
    then category rules, then the accessory heuristic, then same-category.
    Unrelated products score 0.0.
    """

    def __init__(self, category_names: dict[str, str] | None = None):
        self._category_names = dict(category_names or {})

    def category_name(self, category_id: str | None) -> str:
        if not category_id:
            return ""
        return self._category_names.get(str(category_id), "")

    def type_keys(self, product: Any) -> set[str]:
        """Canonical TYPE keys for a product: product_type + store category.

        Deliberately excludes the title: "Laptop Backpack" is a bag, not a
        laptop — a title containing the primary's name must not make two
        products "the same category" (B16 same-category gating).
        """
        return _canonical_keys(
            getattr(product, "product_type", None),
            self.category_name(getattr(product, "category_id", None)),
        )

    def product_keys(self, product: Any) -> set[str]:
        """Canonical keys for a product: explicit metadata + category + title/type."""
        keys: set[str] = set()

        metadata = getattr(product, "metadata", None) or {}
        for key in _EXPLICIT_KEYS:
            value = metadata.get(key)
            if isinstance(value, (str, list, tuple, set)):
                values = [value] if isinstance(value, str) else list(value)
                for v in values:
                    keys.add(str(v).strip().lower())

        category_name = self.category_name(getattr(product, "category_id", None))
        keys |= _canonical_keys(
            getattr(product, "product_type", None),
            getattr(product, "title", None),
            category_name,
        )
        return keys

    def explicit_partners(self, product: Any) -> set[str]:
        """Product ids / titles the catalog explicitly declares compatible."""
        partners: set[str] = set()
        metadata = getattr(product, "metadata", None) or {}
        for key in _EXPLICIT_KEYS:
            value = metadata.get(key)
            if isinstance(value, (str, list, tuple, set)):
                values = [value] if isinstance(value, str) else list(value)
                partners.update(str(v).strip().lower() for v in values if str(v).strip())
        return partners

    def pair_complementarity(self, primary: Any, other: Any) -> PairComplementarity:
        """Score ``other`` against ``primary`` (directed: primary drives rules)."""
        primary_id = str(getattr(primary, "id", "") or "").lower()
        other_id = str(getattr(other, "id", "") or "").lower()
        other_title = str(getattr(other, "title", "") or "").lower()

        # Level 1/2: explicit catalog compatibility wins over everything.
        primary_partners = self.explicit_partners(primary)
        other_partners = self.explicit_partners(other)
        if primary_partners and (other_id in primary_partners or other_title in primary_partners):
            return PairComplementarity(1.0, "explicit_compatibility")
        if other_partners and (
            primary_id in other_partners or str(getattr(primary, "title", "") or "").lower() in other_partners
        ):
            return PairComplementarity(1.0, "explicit_compatibility")

        primary_keys = self.product_keys(primary)
        other_keys = self.product_keys(other)

        # Level 3: category complementarity rules.
        for key in primary_keys:
            compatible = CATEGORY_COMPLEMENTS.get(key)
            if compatible and (other_keys & set(compatible)):
                matched = sorted(other_keys & set(compatible))[0]
                return PairComplementarity(0.7, "category_complement", matched)

        # Level 5/6: accessory heuristic for device primaries.
        other_tokens = _tokens(
            getattr(other, "product_type", None),
            getattr(other, "title", None),
            self.category_name(getattr(other, "category_id", None)),
        )
        is_accessory = any(kw in other_tokens for kw in _ACCESSORY_KEYWORDS)
        primary_is_device = bool(primary_keys & _DEVICE_KEYS) and bool(primary_keys & _CANONICAL_KEYS)
        if is_accessory and primary_is_device:
            return PairComplementarity(0.55, "accessory_complement")

        # Level 6 fallback: same category is a weak (not forbidden) signal.
        if primary_keys and other_keys and (primary_keys & other_keys):
            return PairComplementarity(0.15, "same_category")

        return PairComplementarity(0.0, "unrelated")

    def bundle_complementarity(self, products: list[Any]) -> float:
        """Mean pairwise complementarity of a bundle (deterministic).

        A single-product bundle scores 0.5: valid but minimal — it can never
        beat a genuinely complementary multi-item bundle, but stays competitive
        when nothing else exists. For multi-item bundles the mean is taken over
        the *positive* pairwise relationships: one unrelated pair must not
        erase the complementary relationships the primary has with every other
        item.
        """
        if not products:
            return 0.0
        if len(products) == 1:
            return 0.5
        scores: list[float] = []
        for i in range(len(products)):
            for j in range(i + 1, len(products)):
                forward = self.pair_complementarity(products[i], products[j])
                reverse = self.pair_complementarity(products[j], products[i])
                scores.append(max(forward.score, reverse.score))
        return sum(scores) / len(scores) if scores else 0.0

    def bundle_labels(self, products: list[Any]) -> list[str]:
        """Explainability: the relationship labels used inside this bundle."""
        if len(products) < 2:
            return []
        labels: list[str] = []
        for i in range(len(products)):
            for j in range(i + 1, len(products)):
                forward = self.pair_complementarity(products[i], products[j])
                reverse = self.pair_complementarity(products[j], products[i])
                labels.append(forward.label if forward.score >= reverse.score else reverse.label)
        return labels


def build_rules(category_names: dict[str, str] | None = None) -> ComplementarityRules:
    return ComplementarityRules(category_names=category_names)


def products_compatible(primary: Any, other: Any, rules: ComplementarityRules) -> bool:
    """True when ``other`` is a compatible addition to ``primary`` (score > 0)."""
    return rules.pair_complementarity(primary, other).score > 0


def iter_compatible(
    primary: Any,
    candidates: Iterable[Any],
    rules: ComplementarityRules,
) -> list[Any]:
    """Deterministic, stable subset of ``candidates`` compatible with ``primary``."""
    compatible = [c for c in candidates if products_compatible(primary, c, rules)]
    compatible.sort(key=lambda c: str(getattr(c, "id", "") or ""))
    return compatible
