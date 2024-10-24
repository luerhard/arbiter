# A guide for devs

We currently use a couple of techonologies that are required to contribute.

## Installation

### 1. Install python dependencies

To manage our python environment, we use `poetry`. Install poetry in your system or any other python installation or (better) via `pipx`.

```bash
pipx install poetry
```

I would strongly advise to keep your virtual environment close to your source code.
You can configure `poetry` in that way by running

```bash
poetry config --global virtualenvs.in-project true
```

To create the virtual environment and install all requirements, run (from the root of the repo):

```
poetry install
```

### 2. Install node requirements

For everything JavaScript and SCSS, we use npm as a package manager.
[Click here](https://nodejs.org/en/learn/getting-started/how-to-install-nodejs) for installation instructions.

Once node (and npm) are installed, run (from the root of the repo):

```bash
npm install
```

### 3. Copy the sqlite Test-DB

The test database is necessary to have some sample data in your database while developing locally.
The file below will (more or less) be kept up-to-date with a running version that does not need to many migrations to get running.
You can download the sqlite test database from here: <path:db.sqlite3>

Download it to the root of the repo and you should be good to go.

In case django tells you that migrations are unapplied, run (from the root of the repo):
```bash
cd core

# either
poetry run python manage.py migrate
# or
poetry shell
python manage.py migrate
```

## Running the app locally

### 1. Run webpack

We currently use webpack to compile our SCSS files to CSS and to bundle all CSS and JavaScript files.

To run webpack, run
```bash
npm start
```

Initially, this will create the `dist/` folder and put all necessary static files in it.
If you do not intend to change any CSS, SCSS or .js files, you can just kill the server by `Ctrl+C` in the terminal.
However, I would strongly recommend to just keep it running.
It will automatically recompile all necessary files if they change.

### 2. Run Django Server

To run the django server that actually serves the site, there are a couple of options.

First, you can run (from the root of the directory):

```bash
npm run django
```

This is just a shortcut for

```bash
cd core
poetry run python manage.py runserver
```

Whenever the output tells you that there are **unapplied migrations**, run:

```bash
cd core
poetry run python manage.py migrate
```
