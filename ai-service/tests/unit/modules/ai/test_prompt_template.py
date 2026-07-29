import pytest
from app.application.services.prompt_template import PromptTemplateService


@pytest.fixture
def template_service():
    return PromptTemplateService()


def test_render_existing_template(template_service):
    messages = template_service.render("customer_support", {
        "customer_name": "John",
        "last_orders": "Laptop, Mouse",
        "user_issue": "Broken screen",
    })
    assert len(messages) == 2
    assert messages[0].role == "system"
    assert "John" in messages[0].content
    assert "Broken screen" in messages[1].content


def test_render_nonexistent_template(template_service):
    with pytest.raises(KeyError):
        template_service.render("nonexistent", {})


def test_register_and_render(template_service):
    template_service.register_template("greeting", {
        "system": "You are a {{tone}} assistant.",
        "user": "Say hello to {{name}}",
    })
    messages = template_service.render("greeting", {"tone": "friendly", "name": "Alice"})
    assert len(messages) == 2
    assert "friendly" in messages[0].content
    assert "Alice" in messages[1].content


def test_render_raw_string(template_service):
    result = template_service.render_raw_string("Hello {{name}}!", {"name": "World"})
    assert result == "Hello World!"
