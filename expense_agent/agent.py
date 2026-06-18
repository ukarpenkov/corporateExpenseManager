import base64
import json
import re

from google.adk.agents import LlmAgent
from google.adk.events import Event, RequestInput
from google.adk.workflow import START, Workflow, node

from .config import MODEL, THRESHOLD, LLM_INSTRUCTION


@node
def parse_expense(node_input):
    if isinstance(node_input, dict):
        raw = node_input
    elif isinstance(node_input, str):
        try:
            raw = json.loads(base64.b64decode(node_input))
        except Exception:
            try:
                raw = json.loads(node_input)
            except Exception:
                return {"error": "Could not parse expense data"}
    else:
        from google.genai import types
        if isinstance(node_input, types.Content):
            text = "".join(p.text for p in (node_input.parts or []) if p.text)
            try:
                raw = json.loads(base64.b64decode(text))
            except Exception:
                try:
                    raw = json.loads(text)
                except Exception:
                    return {"error": "Could not parse expense data"}
        else:
            return {"error": "Unexpected input type"}
    return {
        "amount": raw.get("amount", 0),
        "submitter": raw.get("submitter", ""),
        "category": raw.get("category", ""),
        "description": raw.get("description", ""),
        "date": raw.get("date", ""),
    }


@node
def security_screen(node_input):
    description = node_input.get("description", "") if isinstance(node_input, dict) else str(node_input)
    cleaned = description
    pii_found = []

    cleaned, n = re.subn(r"\b\d{3}-?\d{2}-?\d{4}\b", "[SSN-REDACTED]", cleaned)
    if n:
        pii_found.append("ssn")
    cleaned, n2 = re.subn(r"\b\d{9,11}\b", "[SSN-REDACTED]", cleaned)
    if n2:
        pii_found.append("ssn")
    cleaned, n = re.subn(
        r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[CARD-REDACTED]", cleaned
    )
    if n:
        pii_found.append("credit_card")

    injection_patterns = [
        r"bypass\s+all\s+rules",
        r"auto[\s-]approve",
        r"ignore\s+(previous|all)\s+instructions",
        r"override",
    ]
    for p in injection_patterns:
        if re.search(p, description, re.IGNORECASE):
            return Event(
                output={
                    "flag": "prompt_injection",
                    "risk_level": "critical",
                    "recommendation": "reject",
                    "cleaned_description": cleaned,
                    "redacted_pii": pii_found,
                    "expense": node_input,
                },
                route="injection",
            )

    return Event(
        output={
            "flag": "clean",
            "cleaned_description": cleaned,
            "redacted_pii": pii_found,
            "expense": node_input,
        },
        route="clean",
    )


@node
def route_by_amount(node_input):
    expense = node_input.get("expense", node_input) if isinstance(node_input, dict) else {}
    amount = expense.get("amount", 0) if isinstance(expense, dict) else 0
    if amount < THRESHOLD:
        return Event(
            output={"route": "auto", "expense": node_input, "reason": f"${amount:.2f} < ${THRESHOLD}"},
            route="auto",
        )
    return Event(
        output={"route": "human", "expense": node_input, "reason": f"${amount:.2f} >= ${THRESHOLD}"},
        route="human",
    )


@node
def auto_approve(node_input) -> dict:
    expense = node_input.get("expense", node_input) if isinstance(node_input, dict) else node_input
    return {"status": "approved", "expense": expense, "method": "automatic"}


@node(rerun_on_resume=True)
def human_approval(node_input, ctx):
    interrupt_id = "approval_decision"
    if interrupt_id in ctx.resume_inputs:
        decision = ctx.resume_inputs[interrupt_id]
        return Event(
            output={"decision": decision, "expense": node_input},
            route=decision,
        )
    expense_data = node_input.get("expense", node_input) if isinstance(node_input, dict) else node_input
    yield RequestInput(
        interrupt_id=interrupt_id,
        message=(
            f"Expense requires your approval:\n"
            f"{json.dumps(expense_data, indent=2)}\n"
            f"Reply 'approved' or 'rejected'."
        ),
    )


llm_reviewer = LlmAgent(
    name="llm_risk_reviewer",
    model=MODEL,
    description="LLM-based risk analyst for high-value expenses",
    instruction=LLM_INSTRUCTION,
    mode="single_turn",
)

root_agent = Workflow(
    name="expense_agent",
    description="Ambient expense-approval agent (ADK 2.0 Graph Workflow)",
    edges=[
        (START, parse_expense),
        (parse_expense, security_screen),
        (security_screen, {"clean": route_by_amount, "injection": human_approval}),
        (route_by_amount, {"auto": auto_approve, "human": llm_reviewer}),
        (llm_reviewer, human_approval),
    ],
)
