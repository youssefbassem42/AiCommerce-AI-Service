"""Canonical AI context carried from the API layer into the coordinator and sub-agents.

One object carries every piece of information a sub-agent may need:

    tenant           — tenant identity (organization/store/version)
    store            — store profile & capabilities
    conversation     — conversation identity + structured context
    history          — conversation transcript messages
    memory           — recalled customer/session memory
    intent           — classified intent (reused, never re-classified)
    entities         — extracted entities (topics, preferences, ...)
    knowledge_context — retrieved knowledge chunks (RAG)
    products         — retrieved product cards
    business_rules  — business summary / policies / promotions
    customer        — customer profile when known

The coordinator MERGES this context instead of replacing it, so the RAG
context built here always reaches the sub-agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.application.knowledge.retrieval.dto import RetrievedChunkDTO


@dataclass
class AIContext:
    """Canonical context object built once per request by the Context Builder."""

    tenant: dict[str, Any] | None = None
    store: dict[str, Any] = field(default_factory=dict)
    conversation: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    memory: dict[str, Any] = field(default_factory=dict)
    intent: str | None = None
    confidence: float | None = None
    entities: dict[str, Any] = field(default_factory=dict)
    knowledge_context: list[dict[str, Any]] = field(default_factory=list)
    products: list[dict[str, Any]] = field(default_factory=list)
    business_rules: dict[str, Any] = field(default_factory=dict)
    customer: dict[str, Any] | None = None

    def chunks(self) -> list[RetrievedChunkDTO]:
        """Parse the serialized knowledge context back into retrieval DTOs."""
        return [RetrievedChunkDTO.model_validate(c) for c in self.knowledge_context if isinstance(c, dict)]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the plain-dict shape consumed by the coordinator state."""
        return {
            "tenant": self.tenant,
            "store": self.store,
            "conversation": self.conversation,
            "history": self.history,
            "memory": self.memory,
            "intent": self.intent,
            "confidence": self.confidence,
            "entities": self.entities,
            "knowledge_context": self.knowledge_context,
            "products": self.products,
            "business_rules": self.business_rules,
            "customer": self.customer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AIContext:
        """Rehydrate from the serialized dict shape (e.g. coordinator state)."""
        if not data:
            return cls()
        return cls(
            tenant=data.get("tenant"),
            store=data.get("store") or {},
            conversation=data.get("conversation") or {},
            history=data.get("history") or [],
            memory=data.get("memory") or {},
            intent=data.get("intent"),
            confidence=data.get("confidence"),
            entities=data.get("entities") or {},
            knowledge_context=data.get("knowledge_context") or [],
            products=data.get("products") or [],
            business_rules=data.get("business_rules") or {},
            customer=data.get("customer"),
        )

    def merge(self, other: dict[str, Any] | AIContext | None) -> AIContext:
        """Merge another context on top of this one (existing values win).

        Used by the coordinator so router-built context (RAG, intent, history)
        is preserved instead of being overwritten by later extraction steps.
        """
        if other is None:
            return self
        incoming = other if isinstance(other, AIContext) else AIContext.from_dict(other)
        merged = AIContext(
            tenant=self.tenant or incoming.tenant,
            store={**incoming.store, **self.store},
            conversation={**incoming.conversation, **self.conversation},
            history=self.history or incoming.history,
            memory={**incoming.memory, **self.memory},
            intent=self.intent or incoming.intent,
            confidence=self.confidence if self.confidence is not None else incoming.confidence,
            entities={**incoming.entities, **self.entities},
            knowledge_context=self.knowledge_context or incoming.knowledge_context,
            products=self.products or incoming.products,
            business_rules={**incoming.business_rules, **self.business_rules},
            customer=self.customer or incoming.customer,
        )
        return merged
