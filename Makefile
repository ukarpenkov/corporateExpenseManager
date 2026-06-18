.PHONY: install playground serve

install:
	pip install -e .

playground:
	adk web expense_agent

serve:
	python -m expense_agent.fast_api_app
