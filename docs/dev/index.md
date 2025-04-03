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
To create testdata into your database, go to the root of the git repository and execute:

```bash
rm db.sqlite3
cd core/
python manage.py migrate
python manage.py populatedb
```

## Running the app locally

### 1. Run webpack

We currently use webpack to compile our SCSS files to CSS and to bundle all CSS and JavaScript files.

Webpack is a powerful module bundler for JavaScript applications. The --watch option in Webpack is used to keep the build process running in the background, watching for any changes in the source files. When a file is modified, Webpack automatically recompiles the changes, which is useful for speeding up the development process by providing near-instant feedback on changes.


To run webpack, run

```bash
npm run start
```

Initially, this will create the `dist/` folder and put all necessary static files in it.
If you do not intend to change any CSS, SCSS or .js files, you can just kill the server by `Ctrl+C` in the terminal.
However, I would strongly recommend to just keep it running.
It will automatically recompile all necessary files if they change.

To run webpack continuously and watch for file changes, run

```bash
npm run watch
```

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

This should spawn a webserver that is accessible in the browser via [http://127.0.0.1:8000](http://127.0.0.1:8000).

### Run tests

To run the tests, run

```bash
cd core
poetry run pytest
```

## Development Server

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
