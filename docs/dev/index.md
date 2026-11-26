# Development setup

Arbiter is developed in Docker Compose. The development setup runs four containers:

| Service | Port | What it does                                                                                      |
| ------- | ---- | ------------------------------------------------------------------------------------------------- |
| `web`   | 8000 | the Django app, restarting by itself when Python code changes; a debugger can attach on port 5678 |
| `vite`  | 5173 | builds the JavaScript and CSS and serves them to the browser, updating the page when they change  |
| `db`    | 5432 | PostgreSQL                                                                                        |
| `redis` | 6379 | Redis, which carries the live discussions                                                         |

The code folder is mounted into the containers: changes take effect without rebuilding. You need [Docker](https://docs.docker.com/get-docker/) with its Compose plugin; for the formatting hooks also [uv](https://docs.astral.sh/uv/) and [Node.js](https://nodejs.org/).

## Get the code and configure it

```bash
git clone https://github.com/luerhard/arbiter.git
cd arbiter
```

Create a file `.env` in this folder with the credentials of the development database. The values are up to you:

```bash
POSTGRES_DB=arbiter
POSTGRES_USER=arbiter
POSTGRES_PASSWORD=arbiter
```

Leave out `COMPOSE_FILE`: that is for servers and would start the production setup (see [Set up a server](../admin/server.md)).

## Start it

```bash
docker compose up --build
```

The first start takes a few minutes. Once it runs, create the database tables and an administrator account in a second terminal:

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Arbiter now runs at <http://localhost:8000>, the admin at <http://localhost:8000/admin/>. Run `migrate` again whenever you pull changes that bring new migrations.

## Demo data

To see Arbiter with something in it, create the demo projects:

```bash
docker compose exec web python manage.py demodata --stage discussion
```

This creates two projects, "Populist Communication" (labels for the whole text) and "Offensive Language" (spans in the text), and three accounts with the password `demo`: the annotators `anna.berger` and `tom.keller` and the expert `lena.hoffmann`. `--stage` sets how far the running batch of each project has got: `annotation`, `discussion`, `expert` or `final`. Running the command again replaces the two demo projects and resets the three accounts; everything else in the database stays.

The screenshots of this documentation are taken from the demo data, see [Screenshots](testing.md#screenshots).

## Start over

To delete all data and recreate the empty tables:

```bash
docker compose exec web python manage.py resetdb --noinput
```

This also clears the state of the discussions in Redis. The codebooks' git repositories stay on disk; to remove those as well, remove the volumes:

```bash
docker compose down --volumes
docker compose up
```

## Debug with VS Code

The `web` container runs Django with the [debugpy](https://github.com/microsoft/debugpy) debugger listening on port 5678. In VS Code, open the repository folder and start **Attach to Django in Docker (debugpy)** in the Run and Debug view; breakpoints in the code then stop the running app.

## Formatting

Python is formatted and checked with [ruff](https://docs.astral.sh/ruff/), templates, CSS, JavaScript, Markdown and YAML with [Prettier](https://prettier.io/). Install the git hooks once, and both run on every commit:

```bash
npm install
uvx pre-commit install
```

GitHub Actions runs the same tools on every push and commits their fixes.
