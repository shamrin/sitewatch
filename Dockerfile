FROM python:3.9.1-alpine AS dependencies
RUN pip install poetry==1.1.4
RUN mkdir /app
COPY poetry.toml pyproject.toml poetry.lock /app/
WORKDIR /app
RUN poetry install --no-dev

FROM python:3.9.1-alpine
RUN mkdir /app
COPY deps/ /app/deps/
COPY --from=dependencies /app/.venv /app/.venv
COPY sitewatch/ /app/sitewatch/

WORKDIR /app
ENTRYPOINT [ "start" ]
