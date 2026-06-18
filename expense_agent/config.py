THRESHOLD = 100
MODEL = "deepseek/deepseek-chat"
LLM_INSTRUCTION = (
    "You are a financial risk analyst. Review this expense and assess risk. "
    "Return a JSON object with: risk_level (low/medium/high), "
    "flags (list of concerns), recommendation (approve/reject/escalate)."
    "The expense data is provided as a JSON object."
)
