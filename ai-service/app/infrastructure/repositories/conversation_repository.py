import datetime
from typing import Any, Dict, List, Optional
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

    async def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a conversation by its ID.
        """
        return await self.collection.find_one({"conversation_id": conversation_id})

    async def create_conversation(
        self,
        conversation_id: str,
        provider: str,
        model: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "updated_at": datetime.datetime.now(datetime.timezone.utc),
        }
        await self.collection.update_one(
            {"conversation_id": conversation_id},
            {"$setOnInsert": doc},
            upsert=True
        )
        return doc

    async def add_message(
        self,
        conversation_id: str,
        message: Dict[str, Any],
        usage: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[float] = None,
    ) -> None:
        """
        Add a message to an existing conversation and update usage metrics.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Build update query
        update_doc: Dict[str, Any] = {
            "$push": {"messages": message},
            "$set": {"updated_at": now},
        }

        # Update running usage and averages if provided
        if usage or latency_ms:
            inc_fields: Dict[str, Any] = {}
            if usage:
                inc_fields["total_usage.prompt_tokens"] = usage.get("prompt_tokens", 0)
                inc_fields["total_usage.completion_tokens"] = usage.get("completion_tokens", 0)
                inc_fields["total_usage.total_tokens"] = usage.get("total_tokens", 0)
                inc_fields["total_usage.cost"] = usage.get("cost", 0.0)
            
            inc_fields["interaction_count"] = 1
            update_doc["$inc"] = inc_fields

        await self.collection.update_one(
            {"conversation_id": conversation_id},
            update_doc,
            upsert=True
        )

        # Re-estimate average latency if latency is passed
        if latency_ms is not None:
            conv = await self.get_conversation(conversation_id)
            if conv:
                count = conv.get("interaction_count", 1)
                # Weighted average update
                current_avg = conv.get("avg_latency_ms", 0.0)
                new_avg = ((current_avg * (count - 1)) + latency_ms) / count
                await self.collection.update_one(
                    {"conversation_id": conversation_id},
                    {"$set": {"avg_latency_ms": new_avg}}
                )
