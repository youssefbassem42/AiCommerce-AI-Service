"""Prompts used by the Memory Agent."""

SUMMARIZE_SESSION_PROMPT = """
You are a memory summarizer. Given the conversation transcript below, produce a
concise JSON object that captures what should be remembered about this customer.

Return STRICT JSON with this exact shape:
{{
  "key_topics": ["topic1", "topic2"],
  "preferences": {{"preferred_brand": "value", ...}},
  "facts": {{"location": "value", ...}},
  "intents": ["intent1", "intent2"],
  "follow_up_items": ["item1", "item2"]
}}

Conversation transcript:
{transcript}
"""

MEMORY_SUMMARY_PROMPT = SUMMARIZE_SESSION_PROMPT

EXTRACT_SHOPPING_STATE_PROMPT = """
You are a shopping requirements tracker for an e-commerce assistant.
You maintain the customer's current shopping state across a multi-turn conversation.

Current shopping state (fields already known; null means unknown):
{current_state}

Conversation history (most recent last):
{history}

Latest customer message:
{user_input}

Update the shopping state using ONLY what the latest message adds or changes.
Terse answers must be interpreted in context: e.g. "$50" is the budget,
"Black" is the color, "Programming" is the use case.

Return STRICT JSON with ONLY these fields (use null when the message does not
provide a value):
{{
  "intent": "product_recommendation" or null,
  "category": "the product type the customer wants, e.g. dress or laptop, or null",
  "budget": "a positive number if the customer states a budget or price, otherwise null",
  "currency": "currency code such as USD if stated, otherwise null",
  "color": "color if stated, otherwise null",
  "size": "size if stated, otherwise null",
  "brand": "brand if stated, otherwise null",
  "use_case": "how the product will be used if stated, otherwise null"
}}

Rules:
- When the customer switches to a different product, put the NEW category in
  "category" (the old one is replaced automatically).
- Never invent values that are not in the latest message.
- Return only valid JSON. No markdown, no explanation.
"""
