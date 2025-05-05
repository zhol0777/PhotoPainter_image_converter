venv:
	uv venv

install:
	uv pip install -r requirements.txt

lint:
	ruff check convert.py
	mypy .