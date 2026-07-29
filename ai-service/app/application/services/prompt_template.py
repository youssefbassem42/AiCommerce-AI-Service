from typing import Any, Dict, List, Optional
from jinja2 import Template
from app.application.dto.ai_dto import MessageDTO

#TODO: Review the promot service and make it more efficient.

class PromptTemplateService:
    """
    Service to register, compile, and render message-based prompts
    using Jinja2 templates. Supports variables injection and mapping
    to MessageDTO objects.
    """

    def __init__(self):
        # In-memory template registry
        self._templates: Dict[str, Dict[str, str]] = {
            "customer_support": {
                "system": "You are a customer support agent for AI-Commerce. Be polite and helpful. "
                          "Customer context: {{ customer_name }}, history: {{ last_orders }}.",
                "user": "I am having an issue: {{ user_issue }}"
            },
            "sales_pitch": {
                "system": "You are an expert sales recommender. Target product category: {{ category }}.",
                "user": "Recommend me products matching: {{ preferences }}. Limit to {{ limit }} items."
            },
            "summarizer": {
                "system": "Summarize the provided text concisely. Output format: {{ format }}.",
                "user": "Text to summarize:\n{{ text }}"
            }
        }

    def register_template(self, name: str, templates: Dict[str, str]) -> None:
        """
        Register a new prompt template.
        templates: Dict mapping roles (system, user, developer, assistant) to template strings.
        """
        self._templates[name] = templates

    def render(self, template_name: str, variables: Dict[str, Any]) -> List[MessageDTO]:
        """
        Render a registered template with variables and return a list of MessageDTOs.
        """
        if template_name not in self._templates:
            raise KeyError(f"Prompt template '{template_name}' is not registered.")

        rendered_messages = []
        templates_dict = self._templates[template_name]

        for role, template_str in templates_dict.items():
            # Compile Jinja2 template
            template = Template(template_str)
            rendered_content = template.render(**variables)
            
            rendered_messages.append(
                MessageDTO(
                    role=role,
                    content=rendered_content
                )
            )

        return rendered_messages

    def render_raw_string(self, template_str: str, variables: Dict[str, Any]) -> str:
        """
        Compile and render a raw template string with variables.
        """
        template = Template(template_str)
        return template.render(**variables)
