venv:
	uv venv

install:
	uv pip install -r requirements.txt

lint:
	ruff check convert.py --config test/ruff.toml
	mypy convert.py --check-untyped-defs