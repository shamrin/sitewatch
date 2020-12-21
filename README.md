# sitewatch

`sitewatch` is an experiment to play with:

- [Google Cloud](https://cloud.google.com/): 
- [GitHub Actions](https://github.com/features/actions)
- [Aiven](https://aiven.io)
- [Trio](https://trio.readthedocs.io/) - Python library for async concurrency
- [Kafka](https://kafka.apache.org/)
- [Retool](https://retool.com/) - build internal tools

## Dependencies

* Python 3.9
* [Aiven](https://aiven.io)
* Google Cloud: [Containers](https://cloud.google.com/compute/docs/containers)

## Start hacking

Prerequisites:

* Python 3.9
* [poetry](https://python-poetry.org/docs/#installation)
* Docker
* [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)

Setup:
```
poetry env use python3.9
poetry install
```

Start server directly:
```
./start
```

Build and start Docker container:
```
./docker-start
```

Lint and test:
```
./lint && ./test
```

To update the snapshots (in case of "snapshots failed" error):
```
./test.sh --snapshot-update
```

Format code with [black](https://github.com/ambv/black):
```
./format
```

## Deploy

Create Kafka and Postgres services on [Aiven](aiven.io). Add `report-topic` topic in Kafka. Note project name and services' names. For example: `project-12345`, `pg-123456`, `kafka-123456`.

Install [jq](https://stedolan.github.io/jq/).

Create Aiven access token and save it to `.env/`:

```
poetry run avn user access-token create --description 'google cloud container' --json | jq -r '.[0].full_token' > .env/AIVEN_TOKEN
```

Configure Google Cloud SDK:

```
gcloud init
gcloud config set run/region europe-north1
```
