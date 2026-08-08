from typing import Any

CONVERSATION_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["customer_id", "store_id", "status", "created_at", "updated_at"],
        "properties": {
            "customer_id": {"bsonType": "string", "description": "Must be a string and is required"},
            "store_id": {"bsonType": "string", "description": "Must be a string and is required"},
            "status": {
                "enum": ["active", "ended", "archived"],
                "description": "Must be one of active, ended, archived",
            },
            "created_at": {"bsonType": "date", "description": "Creation timestamp"},
            "updated_at": {"bsonType": "date", "description": "Last update timestamp"},
            "deleted_at": {"bsonType": ["date", "null"], "description": "Soft delete timestamp"},
        },
    }
}

MESSAGE_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["conversation_id", "role", "content", "sender", "timestamp"],
        "properties": {
            "conversation_id": {"bsonType": "string", "description": "Associated conversation ID"},
            "role": {"enum": ["user", "assistant", "system"], "description": "Role of the author"},
            "content": {"bsonType": "string", "description": "Message content"},
            "sender": {"bsonType": "string", "description": "Sender of the message"},
            "sentiment": {"bsonType": ["string", "null"], "description": "Sentiment of the message"},
            "intent": {"bsonType": ["string", "null"], "description": "Intent of the message"},
            "timestamp": {"bsonType": "date"},
            "metadata": {"bsonType": "object"},
        },
    }
}

KNOWLEDGE_DOCUMENT_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["store_id", "title", "status", "language", "chunking_strategy", "created_at", "updated_at"],
        "properties": {
            "store_id": {"bsonType": "string"},
            "title": {"bsonType": "string"},
            "source_url": {"bsonType": ["string", "null"]},
            "status": {"enum": ["processing", "active", "error"]},
            "language": {"bsonType": "string"},
            "metadata": {"bsonType": "object"},
            "chunking_strategy": {"bsonType": "string"},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    }
}

KNOWLEDGE_CHUNK_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["document_id", "content", "chunk_index"],
        "properties": {
            "document_id": {"bsonType": "string"},
            "content": {"bsonType": "string"},
            "chunk_index": {"bsonType": "int"},
            "embedding_id": {"bsonType": ["string", "null"]},
            "metadata": {"bsonType": "object"},
        },
    }
}

KNOWLEDGE_UPLOAD_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "original_filename",
            "stored_filename",
            "file_path",
            "file_size",
            "mime_type",
            "extension",
            "checksum",
            "content_type",
            "uploaded_by",
            "organization_id",
            "store_id",
            "status",
            "virus_scan_status",
            "created_at",
            "updated_at",
        ],
        "properties": {
            "original_filename": {"bsonType": "string"},
            "stored_filename": {"bsonType": "string"},
            "file_path": {"bsonType": "string"},
            "file_size": {"bsonType": "int"},
            "mime_type": {"bsonType": "string"},
            "extension": {"bsonType": "string"},
            "checksum": {"bsonType": "string"},
            "content_type": {"bsonType": "string"},
            "uploaded_by": {"bsonType": "string"},
            "organization_id": {"bsonType": "string"},
            "store_id": {"bsonType": "string"},
            "knowledge_scope": {"bsonType": "string"},
            "status": {"enum": ["pending", "uploading", "uploaded", "failed", "rejected"]},
            "document_metadata": {"bsonType": "object"},
            "virus_scan_status": {"enum": ["pending", "clean", "infected", "skipped"]},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
            "deleted_at": {"bsonType": ["date", "null"]},
        },
    }
}


KNOWLEDGE_BUSINESS_SUMMARY_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["document_id", "title", "summary"],
        "properties": {
            "document_id": {"bsonType": "string"},
            "version_number": {"bsonType": "int"},
            "title": {"bsonType": "string"},
            "summary": {"bsonType": "string"},
            "metadata": {"bsonType": "object"},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    }
}

RUNTIME_LOG_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["conversation_id", "model", "prompt_tokens", "latency", "level", "message", "timestamp"],
        "properties": {
            "conversation_id": {"bsonType": "string"},
            "model": {"bsonType": "string"},
            "prompt_tokens": {"bsonType": "string"},
            "latency": {"bsonType": "double"},
            "level": {"enum": ["INFO", "WARN", "ERROR"]},
            "message": {"bsonType": "string"},
            "details": {"bsonType": "object"},
            "timestamp": {"bsonType": "date"},
        },
    }
}

PROMPT_HISTORY_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "runtimeId",
            "provider",
            "context",
            "model",
            "system_prompt",
            "user_prompt",
            "llm_response",
            "token_used",
            "timestamp",
        ],
        "properties": {
            "runtimeId": {"bsonType": "string"},
            "provider": {"bsonType": "string"},
            "context": {"bsonType": "string"},
            "model": {"bsonType": "string"},
            "system_prompt": {"bsonType": "string"},
            "user_prompt": {"bsonType": "string"},
            "llm_response": {"bsonType": "string"},
            "token_used": {"bsonType": "int"},
            "timestamp": {"bsonType": "date"},
        },
    }
}

RECOMMENDATION_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "conversation_id",
            "customer_id",
            "recommended_product_ids",
            "store_id",
            "accepted",
            "rationale",
            "created_at",
        ],
        "properties": {
            "conversation_id": {"bsonType": "string"},
            "customer_id": {"bsonType": "string"},
            "recommended_product_ids": {"bsonType": "array", "items": {"bsonType": "string"}},
            "store_id": {"bsonType": "string"},
            "accepted": {"bsonType": "bool"},
            "rationale": {"bsonType": "string"},
            "created_at": {"bsonType": "date"},
        },
    }
}

BUNDLE_SUGGESTION_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["store_id", "title", "product_ids", "total_price", "discount_percentage", "status"],
        "properties": {
            "store_id": {"bsonType": "string"},
            "title": {"bsonType": "string"},
            "product_ids": {"bsonType": "array", "items": {"bsonType": "string"}},
            "total_price": {"bsonType": "double"},
            "discount_percentage": {"bsonType": "double"},
            "status": {"enum": ["active", "draft", "expired"]},
        },
    }
}

DASHBOARD_INSIGHT_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["store_id", "recommendations"],
        "properties": {
            "store_id": {"bsonType": "string"},
            "recommendations": {"bsonType": "array", "items": {"bsonType": "string"}},
            "metadata": {"bsonType": "object"},
        },
    }
}

TICKET_ANALYSIS_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "ticket_id",
            "store_id",
            "customer_id",
            "sentiment",
            "category",
            "summary",
            "priority",
            "suggested_response",
            "analyzed_at",
        ],
        "properties": {
            "ticket_id": {"bsonType": "string"},
            "store_id": {"bsonType": "string"},
            "customer_id": {"bsonType": "string"},
            "sentiment": {"enum": ["positive", "neutral", "negative"]},
            "category": {"bsonType": "string"},
            "summary": {"bsonType": "string"},
            "priority": {"enum": ["low", "medium", "high", "urgent"]},
            "status": {"enum": ["open", "in_progress", "resolved", "closed"]},
            "suggested_response": {"bsonType": "string"},
            "analyzed_at": {"bsonType": "date"},
        },
    }
}

TICKET_NOTIFICATION_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["ticket_id", "store_id", "customer_id", "message", "read", "created_at"],
        "properties": {
            "ticket_id": {"bsonType": "string"},
            "store_id": {"bsonType": "string"},
            "customer_id": {"bsonType": "string"},
            "message": {"bsonType": "string"},
            "eta": {"bsonType": ["date", "null"]},
            "read": {"bsonType": "bool"},
            "read_at": {"bsonType": ["date", "null"]},
            "created_at": {"bsonType": "date"},
        },
    }
}

KNOWLEDGE_JOB_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["job_type", "status", "payload", "retry_count", "max_retries"],
        "properties": {
            "job_type": {
                "enum": [
                    "document_processing",
                    "chunk_generation",
                    "summary_generation",
                    "embedding_generation",
                    "vector_sync",
                ],
            },
            "status": {
                "enum": ["pending", "running", "completed", "failed", "retrying", "dead_letter"],
            },
            "progress": {
                "bsonType": "double",
                "minimum": 0.0,
                "maximum": 1.0,
            },
            "payload": {"bsonType": "object"},
            "result": {"bsonType": ["object", "null"]},
            "error_message": {"bsonType": ["string", "null"]},
            "retry_count": {"bsonType": "int", "minimum": 0},
            "max_retries": {"bsonType": "int", "minimum": 0},
            "store_id": {"bsonType": ["string", "null"]},
            "organization_id": {"bsonType": ["string", "null"]},
            "triggered_by": {"bsonType": ["string", "null"]},
            "celery_task_id": {"bsonType": ["string", "null"]},
            "started_at": {"bsonType": ["date", "null"]},
            "completed_at": {"bsonType": ["date", "null"]},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    }
}

BUNDLE_TRACKING_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "store_id",
            "bundle_key",
            "product_ids",
            "discount_pct",
            "total_original",
            "total_discount",
            "promo_code",
            "copy_count",
            "is_top",
            "first_copied_at",
            "last_copied_at",
        ],
        "properties": {
            "store_id": {"bsonType": "string"},
            "bundle_key": {"bsonType": "string"},
            "product_ids": {"bsonType": "array", "items": {"bsonType": "string"}},
            "discount_pct": {"bsonType": "double"},
            "total_original": {"bsonType": "double"},
            "total_discount": {"bsonType": "double"},
            "promo_code": {"bsonType": "string"},
            "copy_count": {"bsonType": "int", "minimum": 1},
            "is_top": {"bsonType": "bool"},
            "promoted_at": {"bsonType": ["date", "null"]},
            "first_copied_at": {"bsonType": "date"},
            "last_copied_at": {"bsonType": "date"},
        },
    }
}

PROMPTS_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["key", "type", "content", "version", "is_active"],
        "properties": {
            "key": {"bsonType": "string", "description": "Unique prompt key"},
            "type": {"enum": ["system", "user", "template"]},
            "content": {"bsonType": "string"},
            "description": {"bsonType": "string"},
            "tags": {"bsonType": "array", "items": {"bsonType": "string"}},
            "version": {"bsonType": "int", "minimum": 1},
            "is_active": {"bsonType": "bool"},
            "variables": {"bsonType": "array", "items": {"bsonType": "string"}},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    }
}

STORE_CAPABILITIES_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["store_id", "capabilities"],
        "properties": {
            "store_id": {"bsonType": "string"},
            "capabilities": {"bsonType": "object"},
            "auto_detected": {"bsonType": "object"},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    }
}

API_KEYS_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["key_hash", "key_prefix", "name", "store_id", "scopes", "is_active"],
        "properties": {
            "key_hash": {"bsonType": "string"},
            "key_prefix": {"bsonType": "string"},
            "name": {"bsonType": "string"},
            "store_id": {"bsonType": "string"},
            "scopes": {"bsonType": "array", "items": {"bsonType": "string"}},
            "is_active": {"bsonType": "bool"},
            "expires_at": {"bsonType": ["date", "null"]},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
            "deleted_at": {"bsonType": ["date", "null"]},
        },
    }
}

AUDIT_LOGS_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["action", "resource_type", "outcome", "timestamp"],
        "properties": {
            "action": {"bsonType": "string"},
            "actor_id": {"bsonType": ["string", "null"]},
            "actor_type": {"bsonType": "string"},
            "resource_type": {"bsonType": "string"},
            "resource_id": {"bsonType": ["string", "null"]},
            "tenant_id": {"bsonType": ["string", "null"]},
            "details": {"bsonType": "object"},
            "ip_address": {"bsonType": ["string", "null"]},
            "user_agent": {"bsonType": ["string", "null"]},
            "outcome": {"enum": ["success", "failure"]},
            "failure_reason": {"bsonType": ["string", "null"]},
            "timestamp": {"bsonType": "date"},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    }
}

INTEGRATION_CONNECTIONS_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["store_id", "organization_id", "name", "platform_name", "status"],
        "properties": {
            "store_id": {"bsonType": "string"},
            "organization_id": {"bsonType": "string"},
            "name": {"bsonType": "string"},
            "platform_name": {"bsonType": "string"},
            "status": {"enum": ["inactive", "connected", "active", "error", "syncing"]},
            "spec_version": {"bsonType": "string"},
            "raw_spec": {"bsonType": "object"},
            "auth_config": {"bsonType": "object"},
            "encrypted_credentials": {"bsonType": ["string", "null"]},
            "entity_mappings": {"bsonType": "array"},
            "discovered_endpoints": {"bsonType": "array"},
            "discovered_schemas": {"bsonType": "object"},
            "last_sync_at": {"bsonType": ["date", "null"]},
            "last_sync_status": {"bsonType": ["string", "null"]},
            "error_message": {"bsonType": ["string", "null"]},
            "audit": {"bsonType": "object"},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
            "deleted_at": {"bsonType": ["date", "null"]},
        },
    }
}

CUSTOMERS_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["store_id", "external_id"],
        "properties": {
            "store_id": {"bsonType": "string"},
            "external_id": {"bsonType": "string"},
            "email": {"bsonType": ["string", "null"]},
            "first_name": {"bsonType": ["string", "null"]},
            "last_name": {"bsonType": ["string", "null"]},
            "phone": {"bsonType": ["string", "null"]},
            "metadata": {"bsonType": "object"},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    }
}

KNOWLEDGE_VERSIONS_SCHEMA: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["organization_id", "store_id", "status"],
        "properties": {
            "organization_id": {"bsonType": "string"},
            "store_id": {"bsonType": "string"},
            "knowledge_scope": {"bsonType": "string"},
            "version_number": {"bsonType": "int"},
            "status": {"enum": ["active", "archived"]},
            "metadata": {"bsonType": "object"},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    }
}

VALIDATORS_MAP: dict[str, dict[str, Any]] = {
    "conversations": CONVERSATION_SCHEMA,
    "messages": MESSAGE_SCHEMA,
    "knowledge_documents": KNOWLEDGE_DOCUMENT_SCHEMA,
    "knowledge_chunks": KNOWLEDGE_CHUNK_SCHEMA,
    "knowledge_business_summaries": KNOWLEDGE_BUSINESS_SUMMARY_SCHEMA,
    "knowledge_uploads": KNOWLEDGE_UPLOAD_SCHEMA,
    "runtime_logs": RUNTIME_LOG_SCHEMA,
    "prompt_history": PROMPT_HISTORY_SCHEMA,
    "recommendations": RECOMMENDATION_SCHEMA,
    "bundle_suggestions": BUNDLE_SUGGESTION_SCHEMA,
    "dashboard_insights": DASHBOARD_INSIGHT_SCHEMA,
    "ticket_analysis": TICKET_ANALYSIS_SCHEMA,
    "ticket_notifications": TICKET_NOTIFICATION_SCHEMA,
    "knowledge_jobs": KNOWLEDGE_JOB_SCHEMA,
    "bundle_tracking": BUNDLE_TRACKING_SCHEMA,
    "prompts": PROMPTS_SCHEMA,
    "store_capabilities": STORE_CAPABILITIES_SCHEMA,
    "api_keys": API_KEYS_SCHEMA,
    "audit_logs": AUDIT_LOGS_SCHEMA,
    "integration_connections": INTEGRATION_CONNECTIONS_SCHEMA,
    "customers": CUSTOMERS_SCHEMA,
    "knowledge_versions": KNOWLEDGE_VERSIONS_SCHEMA,
}


async def setup_collection_validators(db) -> None:
    """Apply schema validation rules to all collections."""
    existing_collections = await db.list_collection_names()

    for coll_name, schema in VALIDATORS_MAP.items():
        if coll_name not in existing_collections:
            await db.create_collection(coll_name, validator=schema)
        else:
            await db.command("collMod", coll_name, validator=schema)
