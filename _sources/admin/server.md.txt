# Set up a server

Arbiter runs as three Docker containers: the app, a PostgreSQL database and Redis, which carries the live discussions. This page sets them up on a Linux server of your own. All you need is a server with [Docker](https://docs.docker.com/engine/install/) and its Compose plugin.

The examples use `arbiter.example.org` as the server's address; use its domain name or its IP address instead.

## Get the code

```bash
git clone https://github.com/luerhard/arbiter.git
cd arbiter
```

## Configure it in `.env`

The settings of the server go into a file named `.env` in the `arbiter` folder. Docker Compose, the app and the database all read it.

```bash
# Docker Compose
COMPOSE_FILE=docker-compose.prod.yml

# Django
DJANGO_SECRET_KEY=paste-a-long-random-string-here
DJANGO_ALLOWED_HOSTS=arbiter.example.org

# PostgreSQL
POSTGRES_DB=arbiter
POSTGRES_USER=arbiter
POSTGRES_PASSWORD=another-long-random-string
```

| Variable                      | Required | What it does                                                                                                                                                                                                                           |
| ----------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `COMPOSE_FILE`                | yes      | Tells Docker Compose to use the production setup, `docker-compose.prod.yml`. Without it, `docker compose` starts the development setup (`docker-compose.yml`), and every command on this page would need `-f docker-compose.prod.yml`. |
| `DJANGO_SECRET_KEY`           | yes      | Signs the sign-in sessions. It must be long, random and secret: whoever knows it can sign in as anyone. The app does not start without it. Changing it signs everyone out.                                                             |
| `DJANGO_ALLOWED_HOSTS`        | yes      | The names and IP addresses the server answers to, separated by commas. Requests for any other name are refused. Default: `localhost,127.0.0.1`.                                                                                        |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | no       | Only with [HTTPS](#https): the addresses of the server as browsers see them, with `https://`, separated by commas.                                                                                                                     |
| `POSTGRES_DB`                 | yes      | The name of the database.                                                                                                                                                                                                              |
| `POSTGRES_USER`               | yes      | The database user.                                                                                                                                                                                                                     |
| `POSTGRES_PASSWORD`           | yes      | The database user's password.                                                                                                                                                                                                          |
| `DOCKER_MTU`                  | no       | The packet size of the containers' network. Leave it out unless downloads from inside the containers hang, which happens on some cloud and VPN networks; `1450` usually helps there. Default: `1500`.                                  |

The database is created with the three `POSTGRES_` values when it starts for the first time. Changing them later in `.env` does not change the existing database.

To create random strings for the key and the password:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Keep `.env` to yourself: it holds the server's secrets. It is not part of the repository.

## Start it

```bash
docker compose up -d --build
```

This builds the app and starts the three containers in the background. On the first start, and after every update, create or update the database tables:

```bash
docker compose exec web python manage.py migrate
```

Then create your own administrator account. It asks for a username and a password:

```bash
docker compose exec web python manage.py createsuperuser
```

Arbiter now runs at `http://arbiter.example.org:8000`. Sign in with the administrator account and continue with [Users and site settings](users.md).

## HTTPS

Without HTTPS, passwords and everything else travel unencrypted between the browsers and the server. That can be acceptable inside a protected network, such as a university network or a VPN, but not on a server anyone on the internet can reach.

For HTTPS, put a reverse proxy in front of Arbiter that handles it and forwards everything to port 8000, including the WebSocket connections of the discussions (`/ws/…`). [Caddy](https://caddyserver.com/) does both, and gets the certificate by itself. Its whole configuration (`/etc/caddy/Caddyfile`):

```text
arbiter.example.org {
    reverse_proxy localhost:8000
}
```

With nginx or Apache, make sure the proxy passes WebSocket upgrades on, or the discussion page waits forever.

Then add the HTTPS address to `.env` and restart with `docker compose up -d`:

```bash
DJANGO_CSRF_TRUSTED_ORIGINS=https://arbiter.example.org
```

Without it, every form sent over HTTPS is refused. Finally, close port 8000 to the outside with a firewall, so that nobody reaches Arbiter past the proxy.

## Update

```bash
git pull
docker compose up -d --build
docker compose exec web python manage.py migrate
```

## Back up

Everything Arbiter stores lives in two Docker volumes: the database in `pgdata`, and the codebooks with their history in `media`. Back up both:

```bash
docker compose exec web python manage.py backup
```

This writes a zip file to the folder `backups/` next to `.env`, named after the date and time. It contains

- `db.sql`, a dump of the whole database,
- `media/`, the codebooks with their complete git history,
- `manifest.json`, with when the backup was made and the state of the database tables (the last migration of each app), so you know which version of Arbiter it belongs to.

Copy the backups to another machine regularly. To restore one, start Arbiter at the version the backup belongs to, load `db.sql` into the database with `psql` (it replaces the tables that are there) and copy `media/` back into the `media` volume.

Never remove the volumes (`docker compose down -v`): that deletes all projects.
