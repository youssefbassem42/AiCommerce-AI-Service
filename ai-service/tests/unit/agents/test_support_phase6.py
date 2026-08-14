"""Phase 6: store-aware, grounded, humanized customer service."""

from unittest.mock import AsyncMock, MagicMock

from app.agents.support.agent import SupportAgent
from app.agents.support.nodes import generate_response_node, retrieve_facts_node
from app.agents.support.state import SupportState
from app.agents.support.tools import (
    detect_topic,
    facts_from_context,
    product_to_card,
    retrieve_support_facts,
)


def _state(**overrides) -> SupportState:
    state: SupportState = {
        "user_query": "can I return this after 20 days?",
        "store_id": "store_1",
        "customer_id": "cust_1",
        "conversation_id": "conv_1",
        "history": [],
        "verified": True,
        "customer": MagicMock(),
        "issue_category": "returns",
        "order": None,
        "order_matches": [],
        "resolution_steps": [],
        "refund_info": None,
        "escalation_needed": False,
        "escalation_reason": None,
        "ticket_id": None,
        "priority": None,
        "assigned_to": None,
        "eta": None,
        "satisfaction_question": None,
        "response": None,
        "error": None,
        "verified_facts": [],
        "topic": "general",
        "product": None,
        "product_matches": [],
        "memory": {},
        "customer_profile": None,
        "context": {},
    }
    state.update(overrides)
    return state


def _llm(topic: str = "general", chat_text: str | None = None) -> AsyncMock:
    l = AsyncMock()
    l.structured_output.return_value.message.content = f'{{"topic": "{topic}", "product_mention": null}}'
    if chat_text is not None:
        l.chat.return_value = MagicMock(message=MagicMock(content=chat_text))
    return l


def _chunk(content: str, title: str = "Return Policy") -> dict:
    return {"document_title": title, "content": content, "metadata": {}}


class TestTopicDetection:
    async def test_detects_return_policy_topic(self):
        llm = _llm("return_policy")
        result = await detect_topic("Can I return this?", history="", llm=llm)
        assert result["topic"] == "return_policy"

    async def test_detects_product_topic_with_mention(self):
        llm = AsyncMock()
        llm.structured_output.return_value.message.content = (
            '{"topic": "product", "product_mention": "Aurora Headphones"}'
        )
        result = await detect_topic("What are the specs of the Aurora Headphones?", llm=llm)
        assert result["topic"] == "product"
        assert result["product_mention"] == "Aurora Headphones"

    async def test_no_llm_falls_back_to_general(self):
        result = await detect_topic("hello", llm=None)
        assert result["topic"] == "general"


class TestFactRetrieval:
    async def test_retrieves_facts_via_retriever(self):
        retriever = AsyncMock()
        retriever.search.return_value = MagicMock(
            results=[
                MagicMock(
                    model_dump=lambda: {
                        "document_title": "Return Policy",
                        "content": "Returns are accepted within 14 days of delivery.",
                        "metadata": {},
                    }
                )
            ]
        )
        facts = await retrieve_support_facts(
            "can I return this after 20 days?",
            "return_policy",
            "store_1",
            retriever_service=retriever,
        )
        assert len(facts) == 1
        assert "14 days" in facts[0]["content"]

        filters = retriever.search.call_args.kwargs["filters"]
        assert filters.store_id == "store_1"
        assert set(filters.entity_types) == {"knowledge", "policy", "faq"}

    async def test_falls_back_to_context_facts(self):
        context = {"knowledge_context": [_chunk("Free shipping on orders over $50.", "Shipping Policy")]}
        facts = await retrieve_support_facts("shipping?", "shipping", "store_1", context=context)
        assert facts[0]["content"] == "Free shipping on orders over $50."

    async def test_facts_from_context_includes_business_summary(self):
        context = {
            "knowledge_context": [_chunk("Policy fact A.")],
            "business_rules": {"business_summary": "This store sells outdoor gear."},
        }
        facts = facts_from_context(context)
        titles = [f["source"] for f in facts]
        assert "Store business summary" in titles


class TestHumanizedResponse:
    async def test_llm_text_used_as_rationale(self):
        llm = _llm(chat_text="I'm sorry the product didn't work out. Our return window is 14 days from delivery.")
        result = await generate_response_node(
            _state(
                verified_facts=[_chunk("Returns are accepted within 14 days of delivery.")],
                resolution_steps=["You can request a return from the order page."],
            ),
            llm=llm,
        )
        assert result["response"].rationale.startswith("I'm sorry the product didn't work out")
        assert result["response"].resolution_steps == ["You can request a return from the order page."]

    async def test_prompt_contains_facts_conversation_and_memory(self):
        llm = _llm(chat_text="Here is the policy.")
        await generate_response_node(
            _state(
                verified_facts=[_chunk("Returns are accepted within 14 days of delivery.")],
                memory={"entries": {"name": "Sam", "last_exchange": {"user": "hi", "assistant": "hello"}}},
                history=[
                    {"role": "user", "content": "earlier question"},
                    {"role": "assistant", "content": "earlier answer"},
                ],
                user_query="can I return this after 20 days?",
            ),
            llm=llm,
        )
        prompt = llm.chat.call_args.args[0].messages[0].content
        assert "14 days of delivery" in prompt
        assert "earlier question" in prompt
        assert "can I return this after 20 days?" in prompt
        assert "Never invent policies" in prompt

    async def test_empty_llm_reply_falls_back_to_template(self):
        llm = _llm(chat_text="   ")
        result = await generate_response_node(
            _state(verified_facts=[_chunk("Returns are accepted within 14 days.")]),
            llm=llm,
        )
        assert result["response"].rationale  # honest fallback, not an error

    async def test_no_llm_uses_fallback_template(self):
        result = await generate_response_node(
            _state(verified_facts=[_chunk("Returns are accepted within 14 days.")]),
            llm=None,
        )
        assert "How else can I help you today?" in result["response"].rationale


class TestProductAware:
    def test_product_to_card(self):
        product = MagicMock(
            id="p1",
            title="Aurora Headphones",
            description="Wireless noise cancelling",
            price=MagicMock(amount=199.0, currency="USD"),
            vendor="Acme",
            product_type="Audio",
            tags=["wireless"],
            inventory_quantity=5,
            images=[MagicMock(url="https://img/x.jpg")],
            variants=[
                MagicMock(
                    sku="AH-BLK",
                    title="Black",
                    price=MagicMock(amount=199.0, currency="USD"),
                    inventory_quantity=3,
                )
            ],
        )
        card = product_to_card(product)
        assert card["product_id"] == "p1"
        assert card["title"] == "Aurora Headphones"
        assert card["price"] == 199.0
        assert card["variants"][0]["sku"] == "AH-BLK"

    async def test_retrieve_facts_resolves_product(self):
        llm = AsyncMock()
        llm.structured_output.return_value.message.content = (
            '{"topic": "product", "product_mention": "Aurora Headphones"}'
        )
        product_repo = AsyncMock()
        product_repo.search.return_value = [
            MagicMock(
                id="p1",
                title="Aurora Headphones",
                description="Wireless noise cancelling",
                price=MagicMock(amount=199.0, currency="USD"),
                vendor="Acme",
                product_type="Audio",
                tags=["wireless"],
                inventory_quantity=5,
                images=[MagicMock(url="https://img/x.jpg")],
                variants=[],
            )
        ]
        result = await retrieve_facts_node(
            _state(user_query="What are the specs of the Aurora Headphones?"),
            llm=llm,
            product_repo=product_repo,
        )
        assert result["topic"] == "product"
        assert result["product"]["product_id"] == "p1"
        assert result["product_matches"][0]["title"] == "Aurora Headphones"

    async def test_product_fact_included_in_reply_prompt(self):
        llm = _llm("product", chat_text="The Aurora Headphones have wireless noise cancelling.")
        state = _state(
            user_query="What are the specs?",
            issue_category="general",
            product={
                "product_id": "p1",
                "title": "Aurora Headphones",
                "description": "Wireless noise cancelling",
                "price": 199.0,
                "currency": "USD",
                "variants": [],
            },
            verified_facts=[],
        )
        await generate_response_node(state, llm=llm)
        prompt = llm.chat.call_args.args[0].messages[0].content
        assert "Aurora Headphones" in prompt
        assert "Wireless noise cancelling" in prompt


class TestAgentEndToEnd:
    async def test_support_run_grounded_in_store_facts(self):
        llm = _llm("return_policy", chat_text="Our return policy allows returns within 14 days.")
        agent = SupportAgent(llm=llm)
        response = await agent.run(
            query="Can I return this after 20 days?",
            store_id="store_1",
            customer_id=None,
            context={
                "knowledge_context": [_chunk("Returns are accepted within 14 days of delivery.")],
                "memory": {"entries": {"name": "Sam"}},
                "customer": {"email": "sam@x.com"},
            },
        )
        assert response.rationale.startswith("Our return policy allows returns within 14 days.")
        assert response.issue_category is not None

    async def test_support_run_honest_when_no_facts(self):
        llm = _llm("general")
        agent = SupportAgent(llm=llm)
        response = await agent.run(query="tell me about your planet policy", store_id="store_1")
        assert "contact the store's support team" in response.rationale
        assert "transfer" not in response.rationale.lower()
