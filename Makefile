format:
	python -m isort src/ setup.py
	python -m black src/ setup.py
	python -m flake8 src/ setup.py

install:
	pip --require-virtualenv --disable-pip-version-check install pip --upgrade "pip<=20.3"
	pip --disable-pip-version-check install -e ".[dev]"
