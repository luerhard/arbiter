from datetime import UTC
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

import django
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = (
        "Create a zip archive containing a full database dump (db.sql), the media "
        "folder including all codebook git repositories, and a manifest.json."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "-o",
            "--output",
            default=None,
            help="Target directory or full path of the .zip file. "
            "Defaults to <BASE_DIR>/backups/backup_<timestamp>.zip.",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        created_at = datetime.now(tz=UTC)
        archive_path = self._archive_path(options["output"], created_at)
        archive_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            dump_path = Path(tmp_dir) / "db.sql"
            self._dump_database(dump_path)

            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(dump_path, "db.sql")
                media_files = self._add_media(archive, archive_path)
                manifest = self._build_manifest(created_at, media_files)
                archive.writestr("manifest.json", json.dumps(manifest, indent=2))

        size_mb = archive_path.stat().st_size / (1024 * 1024)
        self.stdout.write(
            self.style.SUCCESS(
                f"Backup written to {archive_path} ({size_mb:.1f} MiB, {media_files} media files).",
            ),
        )

    def _archive_path(self, output, created_at):
        timestamp = created_at.strftime("%Y%m%d_%H%M%S")
        default_name = f"backup_{timestamp}.zip"
        if output is None:
            return (settings.BASE_DIR / "backups" / default_name).resolve()
        output = Path(output)
        if output.suffix == ".zip":
            return output.resolve()
        return (output / default_name).resolve()

    def _dump_database(self, dump_path):
        db = settings.DATABASES["default"]
        cmd = [
            "pg_dump",
            "--format=plain",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            f"--host={db['HOST']}",
            f"--port={db['PORT']}",
            f"--username={db['USER']}",
            f"--dbname={db['NAME']}",
            f"--file={dump_path}",
        ]
        env = {**os.environ, "PGPASSWORD": db["PASSWORD"] or ""}
        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
        except FileNotFoundError as exc:
            msg = (
                "pg_dump not found. Install the postgres client "
                "(apk add postgresql16-client) or rebuild the docker image."
            )
            raise CommandError(msg) from exc
        if result.returncode != 0:
            msg = f"pg_dump failed: {result.stderr.strip()}"
            raise CommandError(msg)

    def _add_media(self, archive, archive_path):
        media_root = Path(settings.MEDIA_ROOT)
        count = 0
        for path in sorted(media_root.rglob("*")):
            if path == archive_path:
                continue
            arcname = Path("media") / path.relative_to(media_root)
            if path.is_dir():
                # Keep empty directories: codebook git repos need e.g. refs/ to exist.
                if not any(path.iterdir()):
                    archive.writestr(f"{arcname}/", "")
                continue
            archive.write(path, arcname)
            count += 1
        return count

    def _build_manifest(self, created_at, media_files):
        applied = sorted(MigrationRecorder(connection).applied_migrations())
        latest_migrations = dict(applied)
        return {
            "created_at": created_at.isoformat(),
            "database": settings.DATABASES["default"]["NAME"],
            "django_version": django.get_version(),
            "media_files": media_files,
            "latest_migrations": latest_migrations,
        }
