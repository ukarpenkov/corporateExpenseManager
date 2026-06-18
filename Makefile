.PHONY: install playground serve generate-traces grade eval

install:
	pip install -e .

playground:
	adk web expense_agent

serve:
	python -m expense_agent.fast_api_app

generate-traces:
	python tests/eval/generate_traces.py

grade:
	python tests/eval/grade.py

eval: generate-traces grade
