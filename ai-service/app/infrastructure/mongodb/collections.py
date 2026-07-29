from app.core.knowledge_settings import knowledge_settings
from app.infrastructure.mongodb.client import get_mongodb


def get_collection(name: str):
    """Retrieve collection reference dynamically."""
    return get_mongodb()[name]


def get_conversations_collection():
    return get_collection("conversations")


def get_messages_collection():
    return get_collection("messages")


def get_knowledge_documents_collection():
    return get_collection(knowledge_settings.documents_collection)


def get_knowledge_chunks_collection():
    return get_collection(knowledge_settings.chunks_collection)


def get_knowledge_business_summaries_collection():
    return get_collection(knowledge_settings.summaries_collection)


def get_knowledge_uploads_collection():
    return get_collection(knowledge_settings.uploads_collection)


def get_runtime_logs_collection():
    return get_collection("runtime_logs")


def get_prompt_history_collection():
    return get_collection("prompt_history")


def get_recommendations_collection():
    return get_collection("recommendations")


def get_bundle_suggestions_collection():
    return get_collection("bundle_suggestions")


def get_dashboard_insights_collection():
    return get_collection("dashboard_insights")


def get_ticket_analysis_collection():
    return get_collection("ticket_analysis")


def get_knowledge_jobs_collection():
    return get_collection("knowledge_jobs")


def get_knowledge_versions_collection():
    return get_collection("knowledge_versions")


def get_api_keys_collection():
    return get_collection("api_keys")


def get_audit_logs_collection():
    return get_collection("audit_logs")


def get_products_collection():
    return get_collection("products")


def get_categories_collection():
    return get_collection("categories")


def get_orders_collection():
    return get_collection("orders")


def get_inventory_collection():
    return get_collection("inventory")


def get_customers_collection():
    return get_collection("customers")


def get_integration_connections_collection():
    return get_collection("integration_connections")


def get_entities_collection():
    return get_collection("entities")


def get_bundle_tracking_collection():
    return get_collection("bundle_tracking")
