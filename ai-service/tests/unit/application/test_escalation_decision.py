"""Phase 7 escalation decision engine tests.

Exit criteria:
- "What's your return policy?" -> answer (no escalation)
- "Where is my order?" -> attempt resolution (no escalation)
- "I want to talk to a human." -> ticket (escalation)
- "I've asked this three times and nobody helps me!" -> escalation
- "Your product is terrible." -> empathy/resolution, NOT a ticket
"""

from app.application.escalation.decision import (
    ALWAYS_ESCALATE_CATEGORIES,
    BUSINESS_RULE,
    EXPLICIT_HUMAN_REQUEST,
    FRUSTRATION_THRESHOLD,
    KNOWLEDGE_UNAVAILABLE,
    REPEATED_FAILURE,
    STRONG_FRUSTRATION,
    detect_business_rule,
    detect_frustration,
    detect_human_request,
    detect_problem,
    detect_repeated_failure,
    evaluate_escalation,
    is_inquiry,
)


class TestExplicitHumanRequest:
    def test_detects_human_request_phrases(self):
        for phrase in [
            "I want to talk to a human.",
            "I want to speak to a human",
            "Talk to support please",
            "Can you connect me to a real person?",
            "Please escalate this",
            "I need a human agent",
            "Open a ticket for me",
            "Transfer me to someone",
        ]:
            assert detect_human_request(phrase), phrase

    def test_does_not_detect_ordinary_questions(self):
        for phrase in ["What's your return policy?", "Where is my order?", "How do I track shipping?"]:
            assert not detect_human_request(phrase), phrase

    def test_exit_criteria_talk_to_human(self):
        decision = evaluate_escalation(user_input="I want to talk to a human.")
        assert decision.should_escalate is True
        assert EXPLICIT_HUMAN_REQUEST in decision.signals
        assert decision.confidence >= 0.9
        assert decision.priority in ("p1", "p2", "p3", "p4")


class TestRepeatedFailure:
    def test_detects_repeated_failure_in_message(self):
        for phrase in [
            "I've asked this three times and nobody helps me!",
            "I asked twice already and still nothing",
            "Nobody is helping me, this is the third time",
            "I keep asking and no one responds",
        ]:
            assert detect_repeated_failure(phrase), phrase

    def test_detects_repeated_failure_from_history(self):
        history = [
            {"role": "user", "content": "Where is my order? It's been a week."},
            {"role": "assistant", "content": "Let me check that for you."},
            {"role": "user", "content": "Where is my order? It's been a week now."},
            {"role": "assistant", "content": "I'm still checking."},
        ]
        assert detect_repeated_failure("Where is my order? It's been a week.", history)

    def test_no_repeated_failure_on_first_ask(self):
        assert not detect_repeated_failure("Where is my order?")
        assert not detect_repeated_failure("Where is my order?", [{"role": "user", "content": "hi"}])

    def test_exit_criteria_asked_three_times(self):
        decision = evaluate_escalation(user_input="I've asked this three times and nobody helps me!")
        assert decision.should_escalate is True
        assert REPEATED_FAILURE in decision.signals

    def test_repeated_failure_with_history_triggers(self):
        history = [
            {"role": "user", "content": "My package never arrived, what do I do?"},
            {"role": "assistant", "content": "Let me look into the shipment."},
            {"role": "user", "content": "My package never arrived, I still have nothing."},
            {"role": "assistant", "content": "I'm sorry, I can't find tracking."},
        ]
        decision = evaluate_escalation(
            user_input="My package never arrived and nobody is helping me.",
            history=history,
            category="order_status",
        )
        assert decision.should_escalate is True
        assert REPEATED_FAILURE in decision.signals


class TestStrongFrustration:
    def test_detects_frustration(self):
        assert detect_frustration("Your product is terrible!") >= FRUSTRATION_THRESHOLD
        assert detect_frustration("I am furious about this") >= FRUSTRATION_THRESHOLD
        assert detect_frustration("I'm fed up with the delays") >= FRUSTRATION_THRESHOLD
        assert detect_frustration("What are your opening hours?") < FRUSTRATION_THRESHOLD

    def test_detects_concrete_problem(self):
        for phrase in [
            "My order never arrived",
            "I was charged twice",
            "The product I got is broken",
            "I can't log into my account",
            "My refund hasn't been processed",
        ]:
            assert detect_problem(phrase), phrase

    def test_vague_venting_is_not_a_problem(self):
        assert not detect_problem("Your product is terrible.")
        assert not detect_problem("I hate this company.")
        assert not detect_problem("What's your return policy?")

    def test_exit_criteria_product_terrible_no_escalation(self):
        decision = evaluate_escalation(user_input="Your product is terrible.")
        assert decision.should_escalate is False
        assert decision.signals == []

    def test_frustration_plus_problem_escalates(self):
        decision = evaluate_escalation(
            user_input="I am furious, my order never arrived and nobody is helping.",
            category="order_status",
        )
        assert decision.should_escalate is True
        assert STRONG_FRUSTRATION in decision.signals

    def test_frustration_without_problem_does_not_escalate(self):
        decision = evaluate_escalation(user_input="This is ridiculous, I'm so frustrated.")
        assert decision.should_escalate is False


class TestKnowledgeUnavailable:
    def test_knowledge_question_without_grounding_escalates(self):
        decision = evaluate_escalation(
            user_input="What is your return policy?",
            category="support",
            knowledge_available=False,
            answered=False,
        )
        assert decision.should_escalate is True
        assert KNOWLEDGE_UNAVAILABLE in decision.signals

    def test_knowledge_available_answers_without_escalation(self):
        decision = evaluate_escalation(
            user_input="What is your return policy?",
            category="support",
            knowledge_available=True,
            answered=True,
        )
        assert decision.should_escalate is False

    def test_exit_criteria_return_policy(self):
        decision = evaluate_escalation(user_input="What's your return policy?", category="support")
        assert decision.should_escalate is False

    def test_chit_chat_never_triggers_knowledge_escalation(self):
        decision = evaluate_escalation(
            user_input="hello",
            knowledge_available=False,
            answered=False,
        )
        assert decision.should_escalate is False


class TestBusinessRule:
    def test_always_escalate_categories(self):
        assert "account_security" in ALWAYS_ESCALATE_CATEGORIES
        assert detect_business_rule("account_security")
        assert detect_business_rule("technical")
        assert not detect_business_rule("order_status")
        assert not detect_business_rule("general")
        assert not detect_business_rule(None)

    def test_business_rule_escalates_even_when_answered(self):
        decision = evaluate_escalation(
            user_input="Someone accessed my account",
            category="account_security",
            knowledge_available=True,
            answered=True,
        )
        assert decision.should_escalate is True
        assert BUSINESS_RULE in decision.signals
        assert decision.priority == "p1"


class TestDoNotEscalate:
    def test_null_customer_id_never_triggers(self):
        for message in [
            "What's your return policy?",
            "Where is my order?",
            "Your product is terrible.",
            "How do I return an item?",
        ]:
            decision = evaluate_escalation(
                user_input=message,
                category="support",
                customer_id=None,
                knowledge_available=True,
                answered=True,
            )
            assert decision.should_escalate is False, message

    def test_support_question_alone_does_not_escalate(self):
        decision = evaluate_escalation(user_input="Can you help me with my order?", category="support")
        assert decision.should_escalate is False

    def test_exit_criteria_where_is_my_order(self):
        decision = evaluate_escalation(user_input="Where is my order?", category="order_status")
        assert decision.should_escalate is False

    def test_escalation_respects_answer_state(self):
        decision = evaluate_escalation(
            user_input="My order never arrived",
            category="order_status",
            answered=True,
        )
        assert decision.should_escalate is False


class TestIsInquiry:
    def test_question_forms(self):
        assert is_inquiry("What is your return policy?")
        assert is_inquiry("How do I track my order?")
        assert is_inquiry("Where is my package?")
        assert not is_inquiry("hello")
        assert not is_inquiry("thanks")
        assert is_inquiry("My order is missing")
