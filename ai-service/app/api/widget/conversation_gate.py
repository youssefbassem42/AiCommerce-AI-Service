"""Deterministic pre-routing conversation gate for the widget chat path.

Runs before retrieval/orchestration and rejects obviously invalid,
out-of-scope, or prompt-injection inputs without spending RAG/LLM resources.
The CoordinatorAgent remains the routing authority for valid store requests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class GateCategory(StrEnum):
    VALID_STORE_REQUEST = "VALID_STORE_REQUEST"
    GENERAL_GREETING = "GENERAL_GREETING"
    CONTEXTUAL_FOLLOW_UP = "CONTEXTUAL_FOLLOW_UP"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    UNSAFE_REQUEST = "UNSAFE_REQUEST"
    EMPTY_OR_INVALID = "EMPTY_OR_INVALID"


@dataclass(frozen=True)
class GateDecision:
    category: GateCategory
    reply: str | None = None


SCOPE_REPLY = (
    "I can help with questions about this store, its products, orders, policies, and support. What can I help you with?"
)

SAFE_REPLY = "I can help with this store's products, orders, policies, and support."

GREETING_REPLY = "Hello! How can I assist you today?"

ESCALATION_REPLY = "I've sent your request to our support team. We'll follow up with you here as soon as possible."

_INJECTION_PATTERNS: tuple[str, ...] = (
    r"\bignore\s+(all\s+|any\s+)?(previous|prior|earlier|above)\s+(instructions?|prompts?|messages|rules)\b",
    r"\b(disregard|forget|ignore)\s+(your\s+)?(previous|prior|earlier|system|developer|hidden)\s+(instructions?|prompts?|rules|role|settings?)\b",
    r"\b(reveal|show|display|print|output|leak|expose|dump)\s+(me\s+)?(your|the|system|developer|hidden|internal|full|entire)?\s*"
    r"(prompt|instructions?|system\s+prompt|developer\s+prompt|hidden\s+instructions?|tool\s+definitions?|"
    r"configuration|environment\s*variables?|api\s*keys?|secrets?|database|schema)\b",
    r"\b(system\s+prompt|developer\s+prompt|hidden\s+instructions?|your\s+instructions?)\b",
    r"\b(api\s*key|environment\s*variables?|mongodb|connection\s*string|admin\s*password|secret|secrets)\b",
    r"\bpretend\s+(you\s+are|to\s+be|you'?re)\s+(the\s+)?(admin|administrator|owner|boss|superuser)\b",
    r"\b(act|behave)\s+as\s+(an?\s+)?(admin|administrator|superuser|owner)\b",
    r"\b(bypass|override|disable|remove|ignore)\s+(your\s+)?(restrictions?|rules?|limits?|safety|filters?|guardrails?|instructions?|prompt)\b",
    r"\byou\s+are\s+now\b|\bnew\s+instructions?\b|\bchange\s+your\s+(role|instructions?|behavior|persona)\b",
    r"\bjailbreak\b|\bdan\b|\bdo\s+anything\s+now\b|\bignore\s+your\s+role\b|\bstop\s+being\s+(an?\s+)?(assistant|ai)\b",
    r"\breveal\s+(other\s+)?(stores?|tenants?|customers?|orders?)\s+(data|info|information)?\b",
    r"\b(act\s+as|pretend\s+to\s+be)\s+another\s+(store|tenant|customer)\b",
    r"\b(show|see|list|get|view|access|browse|recommend|search|find|look)\b.{0,40}\b(another|other)\s+stores?\b",
    r"\b(another|other)\s+stores?\b.{0,40}\b(products?|inventory|orders?|customers?|data|prices?|sales|stock)\b",
    r"\b(show|see|list|get|view)\b.{0,40}\b(another|other)\s+tenants?\b",
    r"\bsudo\b|\bexec(ute)?\s+(arbitrary|any)\s+(instructions?|commands?)\b",
    r"\banswer\s+in\s+base64\b|\bignore\s+the\s+above\b",
    r"\b(تجاهل|انسى|تجاوز)\s+(التعليمات|الأوامر|الرسائل\s+السابقة|القواعد|القيود)\b",
    r"\bكشف\s+(النظام|الأوامر|التعليمات|البيانات|الإعدادات)\b",
    r"\bأنت\s+(الآن|الان)\b",
)

_OUT_OF_SCOPE_PATTERNS: tuple[str, ...] = (
    r"\bwrite\s+(me\s+)?(a|an)?\s*(poem|story|essay|letter|email|resume|song|lyrics|haiku|joke|code|"
    r"python|javascript|java|c\+\+|program|app(lication)?|function|script|regex|sql|api|game)\b",
    r"\bsolve\s+(this|my|a|the)\s+(math|algebra|calculus|homework|equation|puzzle|problem)\b",
    r"\btranslate\s+(this|the|a|my)\s+(page|text|document|paragraph|sentence|article|file)\b",
    r"\bwhat\s+is\s+the\s+capital\s+of\b|\bcapital\s+of\s+(france|germany|italy|egypt|china|japan|spain|uk|usa|brazil|india)\b",
    r"\bwho\s+is\s+the\s+(president|prime\s+minister|king|queen|leader)\b",
    r"\b(stock\s+market|share\s+prices?|bitcoin\s+price|forex|trading\s+strategy)\b",
    r"\btell\s+me\s+a\s+(joke|riddle|story)\b|\b(weather|forecast)\s+(today|tomorrow|this\s+week)\b|\bnews\s+(today|headlines)\b",
    r"\brecipe\s+for\b|\bhow\s+to\s+(cook|bake|make)\s+[a-z]+\b",
    r"\b(history|summary|analysis)\s+of\s+(the\s+)?(world|wars?|ancient|modern|politics)\b",
    r"\bwhat\s+happened\s+in\s+(the\s+)?(stock\s+market|news|world)\b",
    r"\bmovie\s+recommendation\b|\bplay\s+(a\s+)?game\b|\btell\s+me\s+a\s+fact\b",
    r"\b(تكتب|اكتب|حل|ترجم)\s+(قصيدة|قصة|كود|برنامج|وظيفة|لغز|مسألة|معادلة)\b",
)

_GREETING_PATTERNS: tuple[str, ...] = (
    r"^(hi+|hello+|hey+|yo+|howdy|salut|bonjour|hallo)\b.*$",
    r"^(good\s+(morning|afternoon|evening)|good\s+day)\b.*$",
    r"^how\s+are\s+you(\?|!|\.)?$",
    r"^what'?s\s+up\s*[!.]?$",
    r"^(hi|hello|hey)\s+(there|everyone|guys)?\s*[!.]?$",
    r"^(thank\s+you|thanks|thankyou)\s*[!.]?$",
    r"^(مرحبا|أهلا|اهلا|هلا|هاي|السلام\s+عليكم|سلام)\b.*$",
    r"^(صباح\s+الخير|مساء\s+الخير)$",
    r"^(شكرا|تسلم|يسلمو)\s*$",
)

_FOLLOW_UP_PATTERNS: tuple[str, ...] = (
    r"\bshow\s+(me\s+)?(them|it|these|those|all\s+of\s+them)\b",
    r"\bshow\s+(me\s+)?the\s+(first|second|third|fourth|fifth|last|next|best|cheapest|most\s+expensive|top)\s+one\b",
    r"\b(the|this|that)\s+(first|second|third|fourth|fifth|last|next|best|cheapest|most\s+expensive)\s+one\b",
    r"\bwhich\s+(one|of\s+them)?\s*is\s+(the\s+)?(cheapest|best|most\s+expensive|better|more\s+affordable)\b",
    r"\bgive\s+me\s+(more\s+)?details\b",
    r"\btell\s+me\s+(more\s+about|about)\s+(it|them|the\s+[a-z]+\s+one)\b",
    r"\bhow\s+much\s+is\s+(it|this|the\s+[a-z]+\s+one)\b",
    r"\bdoes\s+it\s+come\s+in\b",
    r"\badd\s+(it|the\s+(first|second|third|last)\s+one)\b",
    r"\bcompare\s+(the\s+first\s+two|them|these|both)\b",
    r"\bi'?ll\s+(take|get|buy|go\s+with)\s+the\s+(first|second|third|last|best|cheapest)\s+one\b",
    r"\bwhat\s+about\s+(it|the\s+[a-z]+\s+one|them)\b",
)

_UNSAFE_PATTERNS: tuple[str, ...] = (
    r"\b(hack|crack|steal|scam|fraud|launder|forge|impersonate)\b",
    r"\bbuild\s+(a\s+)?(bomb|explosive)\b|\b(make|create)\s+(a\s+)?(bomb|explosive|poison)\b",
    r"\b(bomb|explosive|explosives|terrorist|terrorism|kidnap|hijack)\b",
    r"\b(shoot|stab|kill|murder|poison)\s+(someone|people|a\s+person|them|him|her|my\s+enemy)\b",
    r"\b(buy|order|purchase|how\s+to\s+get)\s+(a\s+)?(gun|weapon|firearm|rifle|knife)\b",
    r"\b(meth|heroin|cocaine|synthesize\s+drugs?|make\s+drugs?)\b",
    r"\b(يخترق|سرقة|احتيال|تزوير|انتحال)\b",
    r"\b(قنبلة|متفجرات|إرهاب|خطف|اختطاف|قتل|سلاح|مسدس)\b",
)

_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]
_OUT_OF_SCOPE_RE = [re.compile(p, re.IGNORECASE) for p in _OUT_OF_SCOPE_PATTERNS]
_GREETING_RE = [re.compile(p, re.IGNORECASE) for p in _GREETING_PATTERNS]
_FOLLOW_UP_RE = [re.compile(p, re.IGNORECASE) for p in _FOLLOW_UP_PATTERNS]
_UNSAFE_RE = [re.compile(p, re.IGNORECASE) for p in _UNSAFE_PATTERNS]

_STORE_KEYWORDS_RE = re.compile(
    r"\b(product|products|price|prices|order|orders|return|returns|refund|shipping|delivery|policy|"
    r"ticket|support|help|buy|purchase|cart|checkout|offer|discount|promo|bundle|available|stock|"
    r"size|color|spec|specs|model|warranty|payment|track|status|منتج|سعر|طلب|شحن|توصيل|استرجاع|"
    r"سياسة|تذكرة|دعم|شراء|خصم|عرض|مقاس|لون|مواصفات)\b",
    re.IGNORECASE,
)

_MAX_GREETING_LENGTH = 40


def _normalize(message: str) -> str:
    return re.sub(r"\s+", " ", message.strip())


def _matches(patterns: list[re.Pattern], message: str) -> bool:
    return any(p.search(message) for p in patterns)


def classify_widget_message(message: str) -> GateDecision:
    """Classify a raw widget chat message into a gate category.

    Deterministic and dependency-free; never invokes an LLM.
    """
    normalized = _normalize(message or "")

    if not normalized or len(normalized) < 2:
        return GateDecision(GateCategory.EMPTY_OR_INVALID)

    if len(normalized) > 2000:
        return GateDecision(GateCategory.EMPTY_OR_INVALID)

    if _matches(_INJECTION_RE, normalized):
        return GateDecision(GateCategory.PROMPT_INJECTION, SAFE_REPLY)

    if _matches(_UNSAFE_RE, normalized):
        return GateDecision(GateCategory.UNSAFE_REQUEST, SAFE_REPLY)

    if _matches(_OUT_OF_SCOPE_RE, normalized):
        return GateDecision(GateCategory.OUT_OF_SCOPE, SCOPE_REPLY)

    if _matches(_FOLLOW_UP_RE, normalized):
        return GateDecision(GateCategory.CONTEXTUAL_FOLLOW_UP)

    if (
        len(normalized) <= _MAX_GREETING_LENGTH
        and not _STORE_KEYWORDS_RE.search(normalized)
        and _matches(_GREETING_RE, normalized)
    ):
        return GateDecision(GateCategory.GENERAL_GREETING, GREETING_REPLY)

    return GateDecision(GateCategory.VALID_STORE_REQUEST)


_REPR_LEAK_RE = re.compile(
    r"\b(store_id|customer_id|ticket_id|conversation_id|assigned_to|issue_category|priority|eta|"
    r"rationale|latency_ms|latency)\s*[=:]",
    re.IGNORECASE,
)

_INTERNAL_LABEL_SCRUBS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\s*\(?\bpriority\s+p\d+\s*\)?", re.IGNORECASE), ""),
    (re.compile(r"\s*\(\s*p\d+\s*\)"), ""),
    (
        re.compile(
            r"\s*\(?\bassigned\s+to\s+(general|fulfillment|support|billing|escalation|sales|returns)\s*\)?",
            re.IGNORECASE,
        ),
        "",
    ),
    (re.compile(r"\bcaution\s*[:=]?\s*[^.,;)]{0,40}", re.IGNORECASE), ""),
)


def contains_internal_leak(text: str) -> bool:
    """True when assistant text carries an internal repr leak (e.g. str(Pydantic DTO))."""
    return bool(_REPR_LEAK_RE.search(text or ""))


def scrub_internal_labels(text: str) -> str:
    """Remove known internal labels from assistant text for consumer-safe output."""
    cleaned = text or ""
    for pattern, replacement in _INTERNAL_LABEL_SCRUBS:
        cleaned = pattern.sub(replacement, cleaned)
    return re.sub(r"\s{2,}", " ", cleaned).strip()
