FROM python:3.9.1-alpine AS dependencies

RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev
RUN pip install poetry==1.1.4
RUN mkdir /app
COPY poetry.toml pyproject.toml poetry.lock /app/
WORKDIR /app
RUN poetry install --no-dev

FROM python:3.9.1-alpine
RUN apk add --no-cache bash
RUN mkdir /app
COPY --from=dependencies /app/.venv /app/.venv
COPY sitewatch/ /app/sitewatch/
COPY app.py /app/
COPY start /app/

WORKDIR /app
ENTRYPOINT [ "./start" ]
