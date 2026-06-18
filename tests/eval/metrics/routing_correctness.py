"""Custom metric: routing correctness.

Evaluates whether expenses are routed correctly:
- Under $100 → auto_approved (no LLM, no human review)
- $100+ → goes to human review, never auto-approved
"""

from typing import Optional

from google.adk.evaluation.eval_case import ConversationScenario
from google.adk.evaluation.eval_case import Invocation
from google.adk.evaluation.eval_metrics import EvalMetric
from google.adk.evaluation.evaluator import EvaluationResult
from google.adk.evaluation.evaluator import EvalStatus
from google.adk.evaluation.evaluator import PerInvocationResult

THRESHOLD = 100


def _extract_expense_from_invocation(invocation: Invocation) -> dict:
    if invocation.user_content and invocation.user_content.parts:
        for part in invocation.user_content.parts:
            if part.text:
                import json
                try:
                    return json.loads(part.text)
                except Exception:
                    pass
    return {}


def _check_routing(invocation: Invocation, expected: str) -> float:
    expense = _extract_expense_from_invocation(invocation)
    amount = expense.get("amount", 0)

    events = []
    if invocation.intermediate_data and hasattr(invocation.intermediate_data, "invocation_events"):
        events = invocation.intermediate_data.invocation_events

    if amount < THRESHOLD:
        has_llm_call = any(
            hasattr(e, "content") and e.content and e.content.parts
            and any(p.function_call for p in e.content.parts if p.function_call)
            for e in events
        )
        if not has_llm_call:
            return 5.0
        return 2.0
    else:
        has_human_review = any(
            hasattr(e, "content") and e.content and e.content.parts
            and any(
                getattr(p, "function_call", None) and p.function_call.name == "human_approval"
                for p in e.content.parts
            )
            for e in events
        )
        if has_human_review:
            return 5.0
        return 3.0


def routing_correctness(
    eval_metric: EvalMetric,
    actual_invocations: list[Invocation],
    expected_invocations: Optional[list[Invocation]] = None,
    conversation_scenario: Optional[ConversationScenario] = None,
) -> EvaluationResult:
    results = []
    for inv in actual_invocations:
        score = _check_routing(inv, "")
        results.append(
            PerInvocationResult(
                actual_invocation=inv,
                score=score,
                eval_status=EvalStatus.PASSED if score >= 4.0 else EvalStatus.FAILED,
            )
        )

    scores = [r.score for r in results if r.score is not None]
    overall = sum(scores) / len(scores) if scores else 0.0

    return EvaluationResult(
        overall_score=overall,
        overall_eval_status=EvalStatus.PASSED if overall >= 4.0 else EvalStatus.FAILED,
        per_invocation_results=results,
    )
