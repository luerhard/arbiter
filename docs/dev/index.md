# A guide for devs

We currently use a couple of techonologies that are required to contribute.

## Requirements

We use docker to manage requirements.

The docker-compose.yaml file contains the necessary services.

Currently, these are:

web: web app
vite: for compilation of js, css, and npm to manage the packages
redis: key,value storage that allows access from multiple processes. This is necessary for the discussion between annotators.
Postgres: Database

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
# stop all containers
docker compose down

# remove the docker volume that contains the database data
docker volume rm annotationtool_pgdata
```

To start fresh:

```bash
# stop all containers
docker compose down

# remove all volumes
docker compose down --volumes

# start fresh
docker compose up --build
```

To delete the db, recreate it and reapply all migrations (build the table structure) without deleting the docker volume.

```bash
# reset
docker exec annotationtool-web-1 uv run manage.py resetdb --noinput
```

## The .env

For everything to work properly, it is necessary to create a `.env` file in the root directory with the following variables defined:

- user, password, and db can changed.
- do NOT change host or port.

```bash
DJANGO_DEBUG=1

POSTGRES_DB=annotationtool
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypassword
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

REDIS_HOST=localhost
```

## Run tests

To run the tests locally, there are two options:

1. run tests from command line within in the docker container:

```
docker compose run --rm web uv run pytest -v
```

`-v` is optional here but gives some more infos on all tests.

2. run tests locally. This is nice to use, e.g. the test runner in VSCode to run / debug single tests. These, however, require a working installation of the virtual environment outside the container. The docker containers still have to be running to give access to the PostgresDB where a test database is created to run the tests.

So to do this

1. make sure the docker compose containers are running
2. make sure the virtual environment is installed (run `uv sync` to make sure)
3. now, either run `uv run pytest` from the command-line or use the built-in test runner in VSCode.

## Debugging with VS Code

You can debug the code with VSCode, which is helpful because it offers breakpoint and inspection of variables.
To do so, you need to open the directory in VSCode. In the debugging tab, click the green play-button icon that says "Attach to Django in Docker".
You can then place breakpoints in the code.
When the app is running, and you navigate with the GUI to a breakpoint, the code will stop there, and you can start debugging/inspecting.

## Build documentation locally

```bash
docker compose run --rm web sh -c "cd ../docs; make html"
```

This will create `docs/_build/html/index.html` which is the starting page of the documentation.

To open it: 
```bash
docker compose run --rm --service-ports web sh -c "cd ../docs/_build/html && python -m http.server 8080"
```

## Overview and starting point

### Django web app

The web app is built with Django. A starting point is here: https://docs.djangoproject.com/en/6.0/intro/tutorial01/

The Django web framework is based on modular apps.
Our tool (currently) consists of the following apps

- annotation
- codebook
- discuss
- expert
- projects
- users
  and
- data

The apps represent modular parts of the tool.
They each consist of apps.py, models.py, urls.py and views.py files.
The models.py contains classes for the database models.
The views.py contain the logic for what to display.
The urls.py contain the URL declarations for the app.

Data is a bit different from the others, because it contains the connecting bits.

For each app, there also is a template in the templates directory, which contains the html.
This follows Django's principle to seperate the design from the view functionality.

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
