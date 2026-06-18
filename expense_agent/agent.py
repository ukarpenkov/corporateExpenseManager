import base64
import json
import re

from google.adk.agents import Agent
from google.adk.workflows import Workflow, FunctionNode, Edge, RequestInput, LlmNode

from .config import MODEL, THRESHOLD, LLM_INSTRUCTION


def parse_expense(state: dict) -> dict:
    event = state["event"]
    raw = event.get("data", event)
    if isinstance(raw, str):
        raw = json.loads(base64.b64decode(raw))
    state["expense"] = {
        "amount": raw.get("amount", 0),
        "submitter": raw.get("submitter", ""),
        "category": raw.get("category", ""),
        "description": raw.get("description", ""),
        "date": raw.get("date", ""),
    }
    return state


def redact_pii(text: str) -> tuple[str, list[str]]:
    redacted = []
    text, n = re.subn(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN-REDACTED]", text)
    if n:
        redacted.append("ssn")
    text, n = re.subn(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[CARD-REDACTED]", text)
    if n:
        redacted.append("credit_card")
    return text, redacted


def is_injection(text: str) -> bool:
    patterns = [
        r"bypass\s+all\s+rules",
        r"auto[\s-]approve",
        r"ignore\s+(previous|all)\s+instructions",
        r"override",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def security_screen(state: dict) -> dict:
    desc = state["expense"]["description"]

    if is_injection(desc):
        state["security_flag"] = "prompt_injection"
        state["risk_assessment"] = {
            "risk_level": "critical",
            "flags": ["prompt_injection_attempt"],
            "recommendation": "reject",
        }
        state["route"] = "human"
        return state

    clean_desc, categories = redact_pii(desc)
    state["expense"]["description"] = clean_desc
    state["security_flag"] = "clean"
    state["redacted_pii"] = categories
    return state


def route_by_threshold(state: dict) -> dict:
    amount = state["expense"].get("amount", 0)
    state["route"] = "auto" if amount < THRESHOLD else "human"
    return state


def auto_approve(state: dict) -> dict:
    state["result"] = {
        "status": "approved",
        "route": "auto",
        "amount": state["expense"]["amount"],
    }
    return state


def build_risk_prompt(state: dict) -> str:
    expense = state["expense"]
    return (
        f"Expense: ${expense['amount']:.2f} | {expense['category']} | "
        f"{expense['description']} | Submitted by: {expense['submitter']} | "
        f"Date: {expense['date']}\n"
        f"Security scan: {state.get('security_flag', 'clean')}\n"
        f"Assess risk and return JSON."
    )


def parse_llm_response(state: dict) -> dict:
    raw = state.get("llm_output", "{}")
    try:
        assessment = json.loads(raw)
    except json.JSONDecodeError:
        assessment = {
            "risk_level": "unknown",
            "flags": ["llm_parse_error"],
            "recommendation": "escalate",
        }
    state["risk_assessment"] = assessment
    return state


def record_human_decision(state: dict) -> dict:
    decision = state.get("decision", "rejected")
    state["result"] = {
        "status": decision,
        "route": "human",
        "amount": state["expense"]["amount"],
        "risk_assessment": state.get("risk_assessment", {}),
    }
    return state


parse_node = FunctionNode(func=parse_expense)
security_node = FunctionNode(func=security_screen)
route_node = FunctionNode(func=route_by_threshold)
auto_node = FunctionNode(func=auto_approve)
prompt_node = FunctionNode(func=build_risk_prompt)
review_node = LlmNode(model=MODEL, instruction=LLM_INSTRUCTION)
parse_llm_node = FunctionNode(func=parse_llm_response)
human_node = RequestInput(prompt="Review this expense and approve or reject:")
decision_node = FunctionNode(func=record_human_decision)

parse_node >> route_node
route_node.add_edge(Edge(condition=lambda s: s["route"] == "auto", target=auto_node))
route_node.add_edge(Edge(condition=lambda s: s["route"] == "human", target=security_node))
security_node >> prompt_node >> review_node >> parse_llm_node >> human_node >> decision_node

workflow = Workflow(
    name="expense_workflow",
    nodes=[
        parse_node, route_node, auto_node,
        security_node, prompt_node, review_node, parse_llm_node,
        human_node, decision_node,
    ],
    entry_node=parse_node,
)

root_agent = Agent(
    name="expense_agent",
    model=MODEL,
    description="Ambient expense-approval agent",
    instruction="You are an expense approval agent.",
    workflow=workflow,
)
