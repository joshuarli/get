PIP := python -m pip --disable-pip-version-check

install:
	$(PIP) --require-virtualenv install --upgrade "pip<=20.3"
	$(PIP)  install -e ".[dev]"
	pre-commit install --install-hooks
