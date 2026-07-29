"""
Sample questions for the RAG Pipeline Playground.

These questions cover common e-commerce domains that a business
knowledge base should be able to answer after processing the
business's PDF documents through the playground pipeline.

Usage:
    python scripts/rag_playground.py

Then copy/paste any of these questions at the >> prompt.
"""

PRODUCT_AND_SERVICE_QUESTIONS = [
    "What products does this business sell?",
    "What services do you offer?",
    "What are your most popular products?",
    "Do you offer customized or personalized products?",
    "What product categories are available?",
    "Are there any product bundles or kits?",
]
"""Questions about products, services, and catalog."""

POLICY_AND_RETURN_QUESTIONS = [
    "What are your refund policies?",
    "Can I return opened products?",
    "What is your return window?",
    "Do you offer exchanges?",
    "Who pays for return shipping?",
    "How long do refunds take to process?",
]
"""Questions about return, refund, and exchange policies."""

SHIPPING_AND_DELIVERY_QUESTIONS = [
    "How long is shipping?",
    "What shipping options do you offer?",
    "Do you offer free shipping?",
    "What are your shipping costs?",
    "Do you ship internationally?",
    "How can I track my order?",
]
"""Questions about shipping, delivery, and fulfillment."""

PAYMENT_QUESTIONS = [
    "What payment methods are supported?",
    "Do you offer installment payments?",
    "Is my payment information secure?",
    "Do you accept cryptocurrency?",
    "Can I pay with PayPal?",
    "Do you offer buy now pay later?",
]
"""Questions about payment methods and billing."""

SUPPORT_AND_CONTACT_QUESTIONS = [
    "How do I contact customer support?",
    "What are your business hours?",
    "Do you have a physical store?",
    "How do I file a complaint?",
    "Do you offer live chat support?",
]
"""Questions about customer support and contact."""

ALL_QUESTIONS = (
    PRODUCT_AND_SERVICE_QUESTIONS
    + POLICY_AND_RETURN_QUESTIONS
    + SHIPPING_AND_DELIVERY_QUESTIONS
    + PAYMENT_QUESTIONS
    + SUPPORT_AND_CONTACT_QUESTIONS
)

if __name__ == "__main__":
    print("Sample Questions for RAG Playground")
    print("=" * 50)
    for i, q in enumerate(ALL_QUESTIONS, 1):
        print(f"{i:2d}. {q}")
