import json
import re

from google.adk.agents import LlmAgent
from google.adk.events import RequestInput
from google.adk.tools import FunctionTool

from .config import MODEL, THRESHOLD


EXPENSE_SCHEMA = """{
  "amount": <number>,
  "submitter": "<email>",
  "category": "<travel|meals|office|software|hardware|other>",
  "description": "<what was purchased>",
  "date": "<YYYY-MM-DD>"
}"""

COLLECTOR_INSTRUCTION = f"""You are a friendly expense collection assistant. Your job is to collect expense data from the user through natural conversation.

When the user tells you about an expense, extract what you can and ask for missing fields.

Required fields:
{EXPENSE_SCHEMA}

Rules:
- Be conversational and helpful
- REMEMBER everything the user told you in this conversation
- If the user provides all fields in one message, call submit_expense immediately
- If fields are missing, ask for them ONE AT A TIME (don't overwhelm)
- For amount, extract the number (e.g. "$130" -> 130)
- For date, default to today if not specified
- For category, infer from context or ask
- For submitter, ask for their email if not provided
- Once you have ALL required fields, call submit_expense
- If submit_expense returns status "submitted_for_approval", call request_approval with the expense data

IMPORTANT: You MUST remember all information from previous messages in this conversation. If the user already told you something, do NOT ask for it again."""


def _security_check(description: str) -> dict:
    cleaned = description
    pii = []
    cleaned, n = re.subn(r"\b\d{3}-?\d{2}-?\d{4}\b", "[SSN-REDACTED]", cleaned)
    if n: pii.append("ssn")
    cleaned, n = re.subn(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[CARD-REDACTED]", cleaned)
    if n: pii.append("credit_card")

    injection_patterns = [
        r"bypass\s+all\s+rules", r"auto[\s-]approve",
        r"ignore\s+(previous|all)\s+instructions", r"override",
    ]
    for p in injection_patterns:
        if re.search(p, description, re.IGNORECASE):
            return {"flag": "injection", "cleaned": cleaned, "pii": pii}

    return {"flag": "clean", "cleaned": cleaned, "pii": pii}


async def submit_expense(amount: float, submitter: str, category: str,
                         description: str, date: str) -> dict:
    """Submit an expense for processing. Call this ONLY when ALL required fields are collected."""
    expense = {"amount": amount, "submitter": submitter, "category": category,
               "description": description, "date": date}

    screen = _security_check(description)
    if screen["flag"] == "injection":
        return {"status": "rejected", "reason": "Security check failed", "expense": expense}

    expense["description"] = screen["cleaned"]

    if amount < THRESHOLD:
        return {"status": "auto_approved", "expense": expense,
                "message": f"${amount} < ${THRESHOLD} threshold — auto-approved!"}

    return {"status": "submitted_for_approval", "expense": expense,
            "message": f"${amount} >= ${THRESHOLD} — sent to manager for approval."}


async def request_approval(amount: float, submitter: str, category: str,
                           description: str, date: str) -> dict:
    """Request manager approval for a high-value expense. Call this AFTER submit_expense returns 'submitted_for_approval'."""
    return {
        "status": "pending_approval",
        "expense": {"amount": amount, "submitter": submitter, "category": category,
                     "description": description, "date": date},
        "message": "Waiting for manager approval. Check the dashboard."
    }


submit_tool = FunctionTool(func=submit_expense)
approval_tool = FunctionTool(func=request_approval)

root_agent = LlmAgent(
    name="expense_agent",
    model=MODEL,
    description="Conversational expense assistant that collects expense data through chat",
    instruction=COLLECTOR_INSTRUCTION,
    tools=[submit_tool, approval_tool],
)

from google.adk.apps import App

app = App(root_agent=root_agent, name="expense_agent")
