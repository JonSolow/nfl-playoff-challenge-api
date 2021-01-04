set -e
black --check --diff /opt/service/
flake8 --config /opt/tests/tox.ini /opt/service/
mypy /opt/service --config-file /opt/tests/tox.ini
pytest /opt/tests/