FROM python:3.9.1-alpine AS dependencies
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev
RUN pip install poetry==1.1.4
ARG APP=/app
WORKDIR $APP
COPY poetry.toml pyproject.toml poetry.lock $APP/
RUN poetry install --no-dev

FROM python:3.9.1-alpine
RUN apk add --no-cache bash
ARG APP=/app
WORKDIR $APP
COPY --from=dependencies $APP/.venv $APP/.venv
COPY sitewatch/ $APP/sitewatch/
COPY app.py $APP/
COPY start $APP/

ENV PYTHONUNBUFFERED True
ENTRYPOINT [ "./start" ]
