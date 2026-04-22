"""AIL agentic projects — INTENT.md-centered project layout.

A non-developer creates a project with `ail init <name>`, edits the
generated INTENT.md in any text editor, then runs `ail up` to author
+ test + serve. The AI agent owns app.ail and the .ail/ state dir.

Design: runtime/01-agentic-projects.md.
"""
from .intent_md import IntentSpec, parse_intent_md, render_intent_template
from .project import Project
from .agent import bring_up
from .chat import chat_apply

__all__ = [
    "IntentSpec",
    "parse_intent_md",
    "render_intent_template",
    "Project",
    "bring_up",
    "chat_apply",
]
