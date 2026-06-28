.DEFAULT_GOAL := help

.PHONY: help setup

help:
	@echo "Usage:"
	@echo "  make setup     Install dependencies"

setup:
	pip install -r requirements.txt