import datetime
from typing import Any

from app.db.mongodb import get_mongodb


class ConversationRepository:
    """
    MongoDB repository to store and retrieve conversation history,
    token usage, model metrics, and metadata.
    """

    def __init__(self):
        # Retrieve db instance lazily
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_mongodb()
        return self._db

    @property
    def collection(self):
        return self.db["conversations"]

    async def get_conversation(self, conversation_id: str, store_id: str | None = None) -> dict[str, Any] | None:
        """Retrieve a conversation by its ID.

        When `store_id` is provided, a store-tagged conversation is only returned
        when it belongs to that store (tenant-aware access). Conversations created
        before store tagging (no `store_id` field) keep working for backward
        compatibility.
        """
        doc = await self.collection.find_one({"conversation_id": conversation_id})
        if doc is None:
            return None
        if store_id is not None and doc.get("store_id") is not None and doc["store_id"] != store_id:
            return None
        return doc

    async def owner_store_id(self, conversation_id: str) -> str | None:
        """Store that owns the conversation, or None when unknown (legacy/absent)."""
        doc = await self.collection.find_one(
            {"conversation_id": conversation_id},
            {"store_id": 1},
        )
        if doc is None:
            return None
        return doc.get("store_id")

    async def create_conversation(
        self,
        conversation_id: str,
        provider: str,
        model: str,
        metadata: dict[str, Any] | None = None,
        store_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a new conversation document.
        """
        doc = {
            "conversation_id": conversation_id,
            "provider": provider,
            "model": model,
            "messages": [],
            "total_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost": 0.0,
            },
            "avg_latency_ms": 0.0,
            "interaction_count": 0,
            "metadata": metadata or {},
            "customer_id": "",
            "status": "active",
            "created_at": datetime.datetime.now(datetime.UTC),
            "updated_at": datetime.datetime.now(datetime.UTC),
        }
        if store_id is not None:
            doc["store_id"] = store_id
        await self.collection.update_one({"conversation_id": conversation_id}, {"$setOnInsert": doc}, upsert=True)
        return doc

    async def add_message(
        self,
        conversation_id: str,
        message: dict[str, Any],
        usage: dict[str, Any] | None = None,
        latency_ms: float | None = None,
        store_id: str | None = None,
    ) -> None:
        """
        Add a message to an existing conversation and update usage metrics.
        """
        now = datetime.datetime.now(datetime.UTC)

        # Build update query
        update_doc: dict[str, Any] = {
            "$push": {"messages": message},
            "$set": {"updated_at": now},
        }
        if store_id is not None:
            update_doc["$setOnInsert"] = {"store_id": store_id}

        # Update running usage and averages if provided
        if usage or latency_ms:
            inc_fields: dict[str, Any] = {}
            if usage:
                inc_fields["total_usage.prompt_tokens"] = usage.get("prompt_tokens", 0)
                inc_fields["total_usage.completion_tokens"] = usage.get("completion_tokens", 0)
                inc_fields["total_usage.total_tokens"] = usage.get("total_tokens", 0)
                inc_fields["total_usage.cost"] = usage.get("cost", 0.0)

            inc_fields["interaction_count"] = 1
            update_doc["$inc"] = inc_fields

        await self.collection.update_one({"conversation_id": conversation_id}, update_doc, upsert=True)

        # Re-estimate average latency if latency is passed
        if latency_ms is not None:
            conv = await self.get_conversation(conversation_id)
            if conv:
                count = conv.get("interaction_count", 1)
                # Weighted average update
                current_avg = conv.get("avg_latency_ms", 0.0)
                new_avg = ((current_avg * (count - 1)) + latency_ms) / count
                await self.collection.update_one(
                    {"conversation_id": conversation_id}, {"$set": {"avg_latency_ms": new_avg}}
                )

    async def update_context(
        self,
        conversation_id: str,
        context: dict[str, Any],
        store_id: str | None = None,
    ) -> bool:
        """Merge structured conversation context (tenant-scoped)."""
        query: dict[str, Any] = {"conversation_id": conversation_id}
        if store_id is not None:
            query["store_id"] = store_id
        result = await self.collection.update_one(query, {"$set": {"context": context}})
        return result.modified_count > 0
