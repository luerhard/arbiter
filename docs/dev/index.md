# A guide for devs

We currently use a couple of techonologies that are required to contribute.

## Installation

to start everything for the first time:

```bash
# start the services
docker compose up

# create all tables in the database
docker exec annotationtool-web-1 uv run manage.py migrate

# populate the DB with test data
docker exec annotationtool-web-1 uv run manage.py populatedb
```

This should spawn a webserver that is accessible in the browser via [http://127.0.0.1:8000](http://127.0.0.1:8000).

To delete to everything, including the database:

```bash
# stop all ccontainers
docker compose down

# remove the docker volume that contains the database data
docker volume rm annotationtool_pgdata
```


## Run tests

to run the tests locally, use:

```
docker compose run --rm -e SQLITE_FOR_TESTS=1 web uv run pytest -v
```

`-v` is optional here but gives some more infos on all tests.

## Build documentation locally

```bash
docker compose run --rm web bash -c "cd ../docs; make html"
```

This will create `docs/_build/html/index.html` which is the starting page of the documentation.


# Development Server

### Access

We now have a development Server which serves as a showcase of the current state of the project.

The adress is: [http://193.196.54.251](http://193.196.54.251)

To access it, you need to be in the University of Stuttgart VPN (or physically on campus).

### Current Users

#### admin
- can log in to the admin page where all the adding of project, batches, users etc. happens. This is available on [http://193.196.54.251/admin](http://193.196.54.251/admin). If you are not logged in, you might are currently referred to the wrong page, so you might have to use the link twice.

#### annotator1
- default annotator without special permissions

#### annotator2
- same as annotator1. Exists because we want 2 annotators for each project

#### expert1

- A role to show the expert interface.

#### expert2

- A second expert.
- expert2 should behave the same as expert1.

#### Passwords

every user has a password of "123".
