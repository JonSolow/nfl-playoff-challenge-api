FROM python:3.8-buster

RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/2aab9bcd495e11e5f4491aa72a9510773cc4a90e/get-poetry.py | python -
ENV PATH="/root/.poetry/bin:$PATH"

RUN poetry config virtualenvs.in-project false

ENV PYTHONPATH=/opt/src/
WORKDIR /opt/src/

COPY pyproject.toml .
COPY poetry.lock .
RUN poetry install

COPY ./service ./service
WORKDIR /opt/src/service/

CMD ["poetry", "run", "gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "service.app:app"]