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
