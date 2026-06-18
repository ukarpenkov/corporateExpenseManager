import base64
import json
import re

from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from .config import MODEL, THRESHOLD


def parse_expense(event: dict) -> dict:
    raw = event.get("data", event)
    if isinstance(raw, str):
        raw = json.loads(base64.b64decode(raw))
    return raw


def auto_approve(expense: dict) -> dict:
    return {"status": "approved", "expense": expense, "route": "auto"}


def redact_pii(text: str) -> str:
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN-REDACTED]", text)
    text = re.sub(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[CARD-REDACTED]", text)
    return text


def is_injection(text: str) -> bool:
    patterns = [
        r"bypass\s+all\s+rules",
        r"auto[\s-]approve",
        r"ignore\s+(previous|all)\s+instructions",
        r"override",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def security_screen(expense: dict) -> dict:
    desc = expense.get("description", "")
    if is_injection(desc):
        return {"status": "escalated", "reason": "prompt_injection", "expense": expense}
    expense["description"] = redact_pii(desc)
    return {"status": "clean", "expense": expense}


root_agent = Agent(
    name="expense_agent",
    model=MODEL,
    description="Ambient expense-approval agent",
    instruction="You are an expense approval agent.",
)
