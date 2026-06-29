.DEFAULT_GOAL := help

.PHONY: help setup

help:
	@echo "Usage:"
	@echo "  make setup     Install dependencies"
	@echo "  make pipeline  Initialize database and run bob's analysis"
	@echo "  make dashboard     Start the local server on port 8080"

setup:
	pip install -r requirements.txt

pipeline:
	python load_data.py
	python bobs_analysis.py

dashboard:
	python dashboard.py