# sitewatch

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

Build container image:

```
gcloud builds submit --tag gcr.io/$(gcloud config get-value project)/sitewatch
```

Deploy container on Google Cloud Compute Engine. Replace with `project-1234`, `pg-123456` and `kafka-123456` with correct Aiven project and service names, and `user@example.com` with your email (registered at Aiven):

```
gcloud compute instances update-container sitewatch --container-image gcr.io/$(gcloud config get-value project)/sitewatch --container-env AIVEN_TOKEN=$(cat .env/AIVEN_TOKEN) --container-env AIVEN_EMAIL=user@example.com --container-env AIVEN_PROJECT=project-1234 --container-env AIVEN_PG_SERVICE=pg-123456 --container-env AIVEN_KAFKA_SERVICE=kafka-123456
```
