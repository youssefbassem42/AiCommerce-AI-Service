from app.application.context.shopping_state import (
    SESSION_STATE_KEY,
    ShoppingState,
    shopping_state_from_context,
)


class TestShoppingStateMerge:
    def test_empty_update_keeps_current(self):
        current = ShoppingState(category="dress", budget=50)
        merged = current.merge({})
        assert merged.category == "dress"
        assert merged.budget == 50

    def test_incremental_requirements_accumulate(self):
        state = ShoppingState()
        state = state.merge({"category": "dress"})
        assert state.to_dict() == {
            "intent": None,
            "category": "dress",
            "budget": None,
            "currency": None,
            "color": None,
            "size": None,
            "brand": None,
            "use_case": None,
        }

        state = state.merge({"budget": 50, "currency": "USD"})
        assert state.category == "dress"
        assert state.budget == 50
        assert state.currency == "USD"

        state = state.merge({"color": "black"})
        assert state.color == "black"
        assert state.budget == 50
        assert state.category == "dress"

    def test_latest_message_wins_per_field(self):
        state = ShoppingState(category="dress", budget=50)
        merged = state.merge({"budget": 80})
        assert merged.budget == 80
        assert merged.category == "dress"

    def test_category_change_resets_product_scoped_fields(self):
        state = ShoppingState(category="dress", budget=50, color="black", size="m", use_case="party")
        merged = state.merge({"category": "laptop"})
        assert merged.category == "laptop"
        assert merged.color is None
        assert merged.size is None
        assert merged.use_case is None
        assert merged.budget == 50

    def test_category_change_with_new_details_in_same_message(self):
        state = ShoppingState(category="dress", color="black")
        merged = state.merge({"category": "laptop", "use_case": "programming"})
        assert merged.category == "laptop"
        assert merged.color is None
        assert merged.use_case == "programming"

    def test_budget_rejects_non_positive_and_non_numeric(self):
        assert ShoppingState.from_dict({"budget": "fifty"}).budget is None
        assert ShoppingState.from_dict({"budget": 0}).budget is None
        assert ShoppingState.from_dict({"budget": -5}).budget is None
        assert ShoppingState.from_dict({"budget": "50"}).budget == 50

    def test_null_strings_are_cleaned(self):
        state = ShoppingState.from_dict({"category": "null", "color": "None", "size": "  "})
        assert state.category is None
        assert state.color is None
        assert state.size is None


class TestShoppingStateRequirements:
    def test_missing_requirements_order(self):
        state = ShoppingState()
        assert state.missing_requirements() == ["category", "budget", "use_case"]

    def test_missing_requirements_partial(self):
        state = ShoppingState(category="laptop", budget=800)
        assert state.missing_requirements() == ["use_case"]

    def test_missing_requirements_complete(self):
        state = ShoppingState(category="laptop", budget=800, use_case="programming")
        assert state.missing_requirements() == []

    def test_prompt_text_renders_only_known(self):
        state = ShoppingState(category="laptop", budget=800, color="black")
        assert "product type=laptop" in state.to_prompt_text()
        assert "budget=800" in state.to_prompt_text()
        assert "color=black" in state.to_prompt_text()
        assert "use_case" not in state.to_prompt_text()

    def test_is_empty(self):
        assert ShoppingState().is_empty() is True
        assert ShoppingState(category="dress").is_empty() is False


class TestShoppingStateFromContext:
    def test_reads_from_conversation_state(self):
        context = {"conversation": {SESSION_STATE_KEY: {"category": "dress", "budget": 50}}}
        state = shopping_state_from_context(context)
        assert state.category == "dress"
        assert state.budget == 50

    def test_reads_from_recalled_memory_entries(self):
        context = {
            "memory": {
                "recall_source": "merged",
                "entries": {SESSION_STATE_KEY: {"category": "laptop", "budget": 800}},
            }
        }
        state = shopping_state_from_context(context)
        assert state.category == "laptop"
        assert state.budget == 800

    def test_conversation_state_takes_precedence(self):
        context = {
            "conversation": {SESSION_STATE_KEY: {"category": "dress"}},
            "memory": {"entries": {SESSION_STATE_KEY: {"category": "stale"}}},
        }
        state = shopping_state_from_context(context)
        assert state.category == "dress"

    def test_empty_context_returns_empty_state(self):
        assert shopping_state_from_context({}).is_empty() is True
        assert shopping_state_from_context(None).is_empty() is True
