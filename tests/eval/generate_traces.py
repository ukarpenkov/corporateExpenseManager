"""Trace generator for the expense agent evaluation.

Runs each scenario from the dataset through the ADK Workflow,
intercepts human-in-the-loop approval steps, and serializes
the resulting traces to artifacts/traces/generated_traces.json.
"""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from google.adk.agents import LlmAgent
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.events.event import Event
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from expense_agent.agent import root_agent

DATASET_PATH = Path(__file__).parent / "datasets" / "basic-dataset.json"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "traces"
OUTPUT_FILE = OUTPUT_DIR / "generated_traces.json"

APPROVE_DECISIONS = {
    "auto_approve_low_cost": "approved",
    "high_value_manual_review": "approved",
    "pii_in_description": "approved",
    "prompt_injection_attack": "rejected",
    "exact_threshold": "approved",
}


def _event_to_dict(event: Event) -> dict:
    d = {
        "author": event.author,
        "timestamp": event.timestamp,
    }
    if event.output is not None:
        d["output"] = event.output
    if event.content and event.content.parts:
        texts = []
        for part in event.content.parts:
            if part.text:
                texts.append(part.text)
            if part.function_call:
                d["function_call"] = {
                    "name": part.function_call.name,
                    "args": dict(part.function_call.args) if part.function_call.args else {},
                }
            if part.function_response:
                d["function_response"] = {
                    "name": part.function_response.name,
                    "response": dict(part.function_response.response) if part.function_response.response else {},
                }
        if texts:
            d["text"] = "\n".join(texts)
    if event.actions:
        if event.actions.route is not None:
            d["route"] = event.actions.route
        if event.actions.state_delta:
            d["state_delta"] = dict(event.actions.state_delta)
    if event.error_code:
        d["error_code"] = event.error_code
    if event.error_message:
        d["error_message"] = event.error_message
    return d


async def run_scenario(scenario: dict) -> dict:
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    memory_service = InMemoryMemoryService()

    session_id = str(uuid.uuid4())
    user_id = scenario["eval_id"]

    session = await session_service.create_session(
        app_name=root_agent.name,
        user_id=user_id,
        session_id=session_id,
    )

    runner = Runner(
        agent=root_agent,
        app_name=root_agent.name,
        session_service=session_service,
        artifact_service=artifact_service,
        memory_service=memory_service,
    )

    expense = scenario["expense"]
    user_message = types.Content(
        role="user",
        parts=[types.Part(text=json.dumps(expense))],
    )

    trace_events = []
    intercepted_human_input = False

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message,
    ):
        trace_events.append(_event_to_dict(event))

        if event.actions and event.actions.requested_tool_confirmations:
            decision = APPROVE_DECISIONS.get(scenario["eval_id"], "approved")
            intercepted_human_input = True

            resume_message = types.Content(
                role="user",
                parts=[types.Part(text=decision)],
            )
            async for resume_event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=resume_message,
            ):
                trace_events.append(_event_to_dict(resume_event))

    session = await session_service.get_session(
        app_name=root_agent.name,
        user_id=user_id,
        session_id=session_id,
    )
    final_state = dict(session.state) if session else {}

    return {
        "eval_id": scenario["eval_id"],
        "description": scenario["description"],
        "input_expense": expense,
        "expected_routing": scenario["expected_routing"],
        "expected_pii_redacted": scenario["expected_pii_redacted"],
        "expected_injection_detected": scenario["expected_injection_detected"],
        "intercepted_human_input": intercepted_human_input,
        "events": trace_events,
        "final_state": final_state,
    }


async def main():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    traces = []
    for scenario in dataset:
        print(f"Running: {scenario['eval_id']}...")
        try:
            trace = await run_scenario(scenario)
            traces.append(trace)
            print(f"  OK — {len(trace['events'])} events")
        except Exception as e:
            print(f"  FAILED: {e}")
            traces.append({
                "eval_id": scenario["eval_id"],
                "error": str(e),
                "events": [],
            })

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(traces, f, indent=2, ensure_ascii=False)

    print(f"\nTraces written to {OUTPUT_FILE}")
    return traces


if __name__ == "__main__":
    asyncio.run(main())
