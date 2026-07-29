SYSTEM_PROMPT = """You are a business documentation analyst. Your task is to analyze the provided business documents and generate structured business context sections. Each section must be accurate, detailed, and based solely on the provided content. Do not invent information not present in the documents."""

SECTION_DEFINITIONS = {
    "business_overview": "A comprehensive summary of the business, its products/services, mission, and value proposition.",
    "business_policies": "Key business policies including terms of service, data handling, privacy practices, and operational rules.",
    "faqs": "Frequently asked questions and their answers based on the document content.",
    "shipping_policy": "Shipping methods, delivery times, costs, restrictions, and international shipping details.",
    "refund_policy": "Return window, condition requirements, refund process, timeline, and exceptions.",
    "customer_service_guidelines": "Customer support channels, hours, response times, escalation process, and service standards.",
    "tone_of_voice": "The brand's communication style, language patterns, formality level, and key messaging themes.",
    "brand_identity": "Brand values, visual identity references, target audience, positioning, and unique differentiators.",
}


def build_generation_messages(merged_content: str) -> list[dict]:
    user_content = (
        "Generate a complete business context from the following documents.\n\n"
        "Return a JSON object with exactly these keys, each containing the generated text:\n"
        + "\n".join(f'  "{key}": "{desc}"' for key, desc in SECTION_DEFINITIONS.items())
        + "\n\nAlso include a key \"rag_context\" that contains a single optimized text combining all sections "
        "into a concise, searchable business context suitable for a RAG system. "
        "The rag_context should be a narrative text, not JSON.\n\n"
        "Documents:\n\n"
        f"{merged_content}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
