.PHONY: help setup demo doctor test lint clean idea batch

PY ?= python3

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup:          ## Install Python dependencies
	$(PY) -m pip install -r requirements-dev.txt

doctor:         ## Check ffmpeg, fonts, keys and the b-roll library
	$(PY) -m shorts doctor

demo:           ## Render one short with zero API keys
	$(PY) -m shorts make --seed 42

idea:           ## Print 10 premises without rendering anything
	$(PY) -m shorts idea -n 10

pitch:          ## Write 5 scripts for review, render nothing
	$(PY) -m shorts pitch -n 5 --out-dir pitches/local --markdown pitches/local.md

broll:          ## Download clips listed in assets/broll/sources.txt
	$(PY) -m shorts fetch-broll

batch:          ## Render 5 shorts
	$(PY) -m shorts batch -n 5

test:           ## Run the test suite
	$(PY) -m pytest tests/ -q

test-fast:      ## Run everything except the end-to-end renders
	$(PY) -m pytest tests/ -q --ignore=tests/test_pipeline.py

clean:          ## Remove rendered output and caches
	rm -rf out cache .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
