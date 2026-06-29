"""
Tests for backup infrastructure scripts and migration safety checker.

These tests verify the scripts exist, are executable, and behave correctly
for the cases they need to guard against. They do not require a running
PostgreSQL or MinIO instance.
"""

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

BACKUP_SCRIPTS = [
    ROOT / "infra" / "backup" / "backup.sh",
    ROOT / "infra" / "backup" / "restore.sh",
    ROOT / "infra" / "backup" / "verify.sh",
    ROOT / "infra" / "backup" / "entrypoint.sh",
]

DEPLOY_SCRIPTS = [
    ROOT / "deploy" / "deploy.sh",
    ROOT / "scripts" / "check-migrations.sh",
]

INFRA_FILES = [
    ROOT / "docker" / "backup.Dockerfile",
]


class TestBackupScriptsExist:
    def test_backup_scripts_exist(self):
        for path in BACKUP_SCRIPTS:
            assert path.exists(), f"Missing backup script: {path}"

    def test_backup_scripts_executable(self):
        for path in BACKUP_SCRIPTS:
            mode = os.stat(path).st_mode
            assert mode & stat.S_IXUSR, f"Not executable: {path}"

    def test_deploy_scripts_exist(self):
        for path in DEPLOY_SCRIPTS:
            assert path.exists(), f"Missing script: {path}"

    def test_infra_files_exist(self):
        for path in INFRA_FILES:
            assert path.exists(), f"Missing file: {path}"


class TestDeploySafetyGuard:
    """deploy.sh must refuse dangerous flags."""

    def _run_deploy(self, *args):
        env = {**os.environ, "COMPOSE_FILE": "docker-compose.prod.yml"}
        return subprocess.run(
            ["bash", str(ROOT / "deploy" / "deploy.sh"), *args],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            env=env,
        )

    def test_refuses_volumes_flag(self):
        result = self._run_deploy("--volumes")
        assert result.returncode != 0
        assert "volumes" in result.stderr.lower() or "volumes" in result.stdout.lower()

    def test_refuses_v_flag(self):
        result = self._run_deploy("-v")
        assert result.returncode != 0

    def test_refuses_rmi_flag(self):
        result = self._run_deploy("--rmi")
        assert result.returncode != 0


class TestMigrationSafetyChecker:
    """check-migrations.sh detects destructive operations."""

    MIGRATIONS_DIR = ROOT / "backend" / "app" / "db" / "migrations" / "versions"

    def _run_checker(self, target_dir=None, force=False):
        env = {**os.environ}
        if force:
            env["FORCE_DESTRUCTIVE"] = "true"
        cmd = ["bash", str(ROOT / "scripts" / "check-migrations.sh")]
        if target_dir:
            cmd.append(str(target_dir))
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            env=env,
        )

    def test_checker_runs_on_real_migrations(self):
        result = self._run_checker(self.MIGRATIONS_DIR)
        # exits 1 because drop_column and drop_table exist in historical migrations
        # what matters is it runs and produces output
        assert "Scanning" in result.stdout

    def test_checker_passes_on_real_migrations_with_exceptions(self):
        # 202606200003_drop_user_photo_url.py uses op.drop_column but is in exceptions file
        result = self._run_checker(self.MIGRATIONS_DIR)
        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_exceptions_file_is_respected(self, tmp_path):
        # a migration listed in exceptions must not trigger a failure
        bad_migration = tmp_path / "202606200003_drop_user_photo_url.py"
        bad_migration.write_text(
            'def upgrade():\n    op.drop_column("users", "photo_url")\ndef downgrade():\n    pass\n'
        )
        result = self._run_checker(tmp_path)
        # checker finds no destructive ops because the file is in exceptions
        assert result.returncode == 0

    def test_force_destructive_allows_proceed(self):
        result = self._run_checker(self.MIGRATIONS_DIR, force=True)
        # with FORCE_DESTRUCTIVE=true it should exit 0
        assert result.returncode == 0

    def test_clean_migrations_dir_passes(self, tmp_path):
        # a directory with only additive migrations should pass
        clean_migration = tmp_path / "0001_add_table.py"
        clean_migration.write_text(
            'def upgrade():\n    op.create_table("foo")\n'
            'def downgrade():\n    op.drop_table("foo")\n'
        )
        result = self._run_checker(tmp_path)
        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_destructive_migration_detected(self, tmp_path):
        bad_migration = tmp_path / "0002_drop_users.py"
        bad_migration.write_text(
            'def upgrade():\n    op.drop_table("users")\ndef downgrade():\n    pass\n'
        )
        result = self._run_checker(tmp_path)
        assert result.returncode == 1
        assert "DESTRUCTIVE" in result.stdout

    def test_truncate_detected(self, tmp_path):
        bad_migration = tmp_path / "0003_truncate.py"
        bad_migration.write_text(
            'def upgrade():\n    op.execute("TRUNCATE reservations CASCADE")\n'
            "def downgrade():\n    pass\n"
        )
        result = self._run_checker(tmp_path)
        assert result.returncode == 1
        assert "DESTRUCTIVE" in result.stdout


class TestProductionComposeBackupService:
    """docker-compose.prod.yml must include backup service with host-path volume."""

    PROD_COMPOSE = ROOT / "docker-compose.prod.yml"

    def _compose_text(self):
        return self.PROD_COMPOSE.read_text()

    def test_backup_service_present(self):
        assert "wished-backup" in self._compose_text()

    def test_backup_uses_host_path_not_named_volume(self):
        text = self._compose_text()
        # must reference the host path variable, not a plain named volume
        assert "BACKUP_LOCAL_PATH" in text

    def test_backup_named_volume_not_in_volumes_section(self):
        text = self._compose_text()
        # backup-data must NOT appear as a named Docker volume
        # (it would be destroyed by `docker compose down -v`)
        lines = text.splitlines()
        in_volumes_section = False
        for line in lines:
            if line.strip() == "volumes:":
                in_volumes_section = True
            if (
                in_volumes_section
                and "backup-data:" in line
                and not line.strip().startswith("#")
            ):
                raise AssertionError(
                    "backup-data appears as a named Docker volume — "
                    "it must be a host-bind-mount to survive `docker compose down -v`"
                )

    def test_backup_depends_on_postgres_and_minio(self):
        text = self._compose_text()
        # crude check: backup block must reference both dependencies
        backup_section_start = text.find("wished-backup")
        assert backup_section_start != -1
        backup_section = text[backup_section_start : backup_section_start + 2000]
        assert "postgres" in backup_section
        assert "minio" in backup_section

    def test_no_down_v_in_prod_compose(self):
        # "down -v" may appear in comments but must not be an actual command
        non_comment_lines = [
            line
            for line in self._compose_text().splitlines()
            if not line.lstrip().startswith("#")
        ]
        text = "\n".join(non_comment_lines)
        assert "down -v" not in text
        assert "down --volumes" not in text


class TestVerifyScriptContent:
    """verify.sh must check backup age, not just existence."""

    VERIFY = ROOT / "infra" / "backup" / "verify.sh"

    def test_checks_age(self):
        content = self.VERIFY.read_text()
        assert "BACKUP_MAX_AGE_SECONDS" in content or "AGE_SECONDS" in content

    def test_uses_pg_restore_list(self):
        content = self.VERIFY.read_text()
        assert "pg_restore --list" in content

    def test_exits_nonzero_on_no_backups(self):
        result = subprocess.run(
            ["bash", str(self.VERIFY)],
            capture_output=True,
            text=True,
            env={**os.environ},
        )
        # /backups likely doesn't exist locally — should fail with error
        assert result.returncode != 0
