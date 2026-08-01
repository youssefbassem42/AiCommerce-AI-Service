SUMMARIZATION_PROMPT = """You are a support escalation assistant. Condense the following customer support
conversation into a concise summary for a human agent handoff.

Include:
- The customer's core issue in one sentence
- What the AI assistant has already tried
- Why this conversation needs a human (the escalation reason)
- Any relevant context (order IDs, amounts, account problems)

Conversation:
{transcript}

Escalation reason: {reason}

Return only the summary text. Max 150 words. No markdown."""

NOTIFICATION_TEMPLATE = """Your request has been escalated to our {team} team{eta_suffix}. \
We will follow up with you via this conversation once we have an update."""

PRIORITY_GUIDANCE = """Priority levels:
- P1: critical (account security, payment failures) - resolve within 2 hours
- P2: high (refunds, order problems for high-value customers) - resolve within 8 hours
- P3: normal (returns, technical issues) - resolve within 24 hours
- P4: low (general inquiries) - resolve within 48 hours
"""
