.PHONY: demo data agent evals ui test clean

demo: data
	python -m agent.run --learner auto

data:
	python -m datagen.generate --seed 42 --learners 80

agent:
	python -m agent.run --learner L003

evals:
	python -m evals.run_evals --reps 3

ui:
	python -m ui.app

test:
	python -m pytest -q

clean:
	rm -rf data/*.db data/*.jsonl evals/results .pytest_cache
