"""Tests for backup/restore recovery tooling.

Covers deterministic logic in three scripts:
  - app.scripts.check_restore  (HTTP-based post-restore verification)
  - app.scripts.check_artifacts (artifact reconciliation)
  - app.scripts.db_backup       (pg_dump DSN parsing and command construction)

All tests are pure unit tests — no real database, no real S3, no real HTTP.
Network and filesystem I/O is replaced with lightweight fakes or monkeypatches.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ===========================================================================
# check_restore
# ===========================================================================


class TestCheckRestoreCheckResult:
    def test_passed_renders_checkmark(self):
        from app.scripts.check_restore import CheckResult

        r = CheckResult("liveness probe", True)
        assert "\u2713" in str(r)
        assert "liveness probe" in str(r)

    def test_failed_renders_cross(self):
        from app.scripts.check_restore import CheckResult

        r = CheckResult("readiness probe", False, "degraded: [db]")
        assert "\u2717" in str(r)
        assert "degraded: [db]" in str(r)

    def test_detail_omitted_when_empty(self):
        from app.scripts.check_restore import CheckResult

        r = CheckResult("stats overview", True)
        rendered = str(r)
        assert "\u2014" not in rendered


class TestCheckRestoreHTTPHelper:
    def test_get_returns_status_and_parsed_json(self):
        from app.scripts.check_restore import _get

        fake_resp = MagicMock()
        fake_resp.status = 200
        fake_resp.read.return_value = b'{"status": "ok"}'
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=fake_resp):
            status, body = _get("http://localhost:8000/health/live")

        assert status == 200
        assert body == {"status": "ok"}

    def test_get_returns_zero_on_connection_error(self):
        from app.scripts.check_restore import _get

        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            status, body = _get("http://localhost:8000/health/live")

        assert status == 0
        assert "connection refused" in body

    def test_get_returns_http_error_code(self):
        import urllib.error

        from app.scripts.check_restore import _get

        exc = urllib.error.HTTPError(
            url="http://x/y", code=404, msg="Not Found", hdrs=MagicMock(), fp=MagicMock()  # type: ignore[arg-type]
        )
        exc.read = lambda: b'{"error": "not found"}'
        with patch("urllib.request.urlopen", side_effect=exc):
            status, _body = _get("http://localhost:8000/missing")

        assert status == 404


class TestCheckRestoreChecks:
    def _mock_get(self, status: int, body):
        return patch("app.scripts.check_restore._get", return_value=(status, body))

    def test_check_liveness_passes_on_ok(self):
        from app.scripts.check_restore import check_liveness

        with self._mock_get(200, {"status": "ok"}):
            result = check_liveness("http://localhost:8000")
        assert result.passed is True

    def test_check_liveness_fails_on_wrong_body(self):
        from app.scripts.check_restore import check_liveness

        with self._mock_get(200, {"status": "degraded"}):
            result = check_liveness("http://localhost:8000")
        assert result.passed is False

    def test_check_liveness_fails_on_non_200(self):
        from app.scripts.check_restore import check_liveness

        with self._mock_get(503, None):
            result = check_liveness("http://localhost:8000")
        assert result.passed is False

    def test_check_readiness_passes_all_checks_ok(self):
        from app.scripts.check_restore import check_readiness

        body = {"checks": {"db": True, "redis": True}}
        with self._mock_get(200, body):
            result = check_readiness("http://localhost:8000")
        assert result.passed is True

    def test_check_readiness_fails_when_check_degraded(self):
        from app.scripts.check_restore import check_readiness

        body = {"checks": {"db": False, "redis": True}}
        with self._mock_get(200, body):
            result = check_readiness("http://localhost:8000")
        assert result.passed is False
        assert "db" in result.detail

    def test_check_stats_passes_with_benchmark_count(self):
        from app.scripts.check_restore import check_stats

        with self._mock_get(200, {"total_benchmarks": 42}):
            result = check_stats("http://localhost:8000")
        assert result.passed is True
        assert "42" in result.detail

    def test_check_recent_submissions_passes_on_list(self):
        from app.scripts.check_restore import check_recent_submissions

        with self._mock_get(200, [{"id": "a"}, {"id": "b"}]):
            result = check_recent_submissions("http://localhost:8000")
        assert result.passed is True
        assert "2" in result.detail

    def test_check_search_passes_with_items(self):
        from app.scripts.check_restore import check_search

        with self._mock_get(200, {"items": [{"slug": "mmlu"}], "total": 1}):
            result = check_search("http://localhost:8000")
        assert result.passed is True

    def test_check_seeded_benchmark_passes(self):
        from app.scripts.check_restore import check_seeded_benchmark

        body = {"name": "MMLU", "is_verified": True}
        with self._mock_get(200, body):
            result = check_seeded_benchmark("http://localhost:8000", slug="mmlu")
        assert result.passed is True
        assert "MMLU" in result.detail

    def test_check_seeded_benchmark_fails_on_404(self):
        from app.scripts.check_restore import check_seeded_benchmark

        with self._mock_get(404, None):
            result = check_seeded_benchmark("http://localhost:8000", slug="missing")
        assert result.passed is False

    def test_check_benchmark_versions_passes_when_versions_present(self):
        from app.scripts.check_restore import check_benchmark_versions

        with self._mock_get(200, [{"version": "1.0.0"}]):
            result = check_benchmark_versions("http://localhost:8000", slug="mmlu")
        assert result.passed is True

    def test_check_benchmark_versions_fails_when_empty_list(self):
        from app.scripts.check_restore import check_benchmark_versions

        with self._mock_get(200, []):
            result = check_benchmark_versions("http://localhost:8000", slug="mmlu")
        assert result.passed is False
        assert "no versions" in result.detail

    def test_check_citation_passes_with_citation_string(self):
        from app.scripts.check_restore import check_citation

        body = {"citation_string": "@article{mmlu2021,...}"}
        with self._mock_get(200, body):
            result = check_citation("http://localhost:8000", slug="mmlu", version="0.0.0")
        assert result.passed is True

    def test_check_citation_passes_with_nested_bibtex(self):
        from app.scripts.check_restore import check_citation

        body = {"citations": {"bibtex": "@article{test,...}"}}
        with self._mock_get(200, body):
            result = check_citation("http://localhost:8000")
        assert result.passed is True

    def test_check_citation_fails_when_no_citation(self):
        from app.scripts.check_restore import check_citation

        with self._mock_get(200, {"name": "MMLU"}):
            result = check_citation("http://localhost:8000")
        assert result.passed is False

    def test_check_audit_activity_passes_on_list(self):
        from app.scripts.check_restore import check_audit_activity

        with self._mock_get(200, [{"action": "benchmark.verified"}]):
            result = check_audit_activity("http://localhost:8000", slug="mmlu")
        assert result.passed is True

    def test_check_admin_queue_passes_on_200_list(self):
        from app.scripts.check_restore import check_admin_queue

        with self._mock_get(200, []):
            result = check_admin_queue("http://localhost:8000", api_key="secret")
        assert result.passed is True

    def test_check_admin_queue_fails_on_403(self):
        from app.scripts.check_restore import check_admin_queue

        with self._mock_get(403, {"error": "forbidden"}):
            result = check_admin_queue("http://localhost:8000", api_key="bad-key")
        assert result.passed is False
        assert "auth error" in result.detail


class TestRunChecks:
    def test_run_checks_omits_admin_when_no_api_key(self):
        from app.scripts.check_restore import run_checks

        with patch("app.scripts.check_restore._get", return_value=(200, {"status": "ok"})):
            # Most checks expect specific bodies; just check count — admin not included.
            results = run_checks("http://localhost:8000", api_key=None)
        # 9 public checks, no admin
        assert len(results) == 9

    def test_run_checks_includes_admin_when_api_key_provided(self):
        from app.scripts.check_restore import run_checks

        with patch("app.scripts.check_restore._get", return_value=(200, [])):
            results = run_checks("http://localhost:8000", api_key="secret")
        assert len(results) == 10


# ===========================================================================
# check_artifacts — storage checkers
# ===========================================================================


class TestCheckLocalPath:
    def test_returns_true_for_existing_file(self, tmp_path: Path):
        from app.scripts.check_artifacts import _check_local_path

        f = tmp_path / "artifact.json"
        f.write_bytes(b"data")
        exists, error = _check_local_path(str(f))
        assert exists is True
        assert error == ""

    def test_returns_false_for_missing_file(self, tmp_path: Path):
        from app.scripts.check_artifacts import _check_local_path

        exists, error = _check_local_path(str(tmp_path / "missing.json"))
        assert exists is False
        assert error == ""

    def test_returns_error_on_invalid_path(self):
        from app.scripts.check_artifacts import _check_local_path

        # Null bytes in path raise ValueError on most platforms.
        exists, _error = _check_local_path("\x00invalid")
        # Either False+error or raises — either way it should not propagate.
        assert isinstance(exists, bool)


class TestCheckS3Key:
    def test_returns_true_when_object_exists(self):
        from app.scripts.check_artifacts import _check_s3_key

        mock_client = MagicMock()
        mock_client.head_object.return_value = {"ContentLength": 100}

        with patch("boto3.client", return_value=mock_client):
            exists, error = _check_s3_key(
                "artifacts/foo.json",
                bucket="mybucket",
                endpoint_url="https://s3.example.com",
                access_key_id="key",
                secret_access_key="secret",
            )
        assert exists is True
        assert error == ""

    def test_returns_false_when_object_missing(self):
        from botocore.exceptions import ClientError

        from app.scripts.check_artifacts import _check_s3_key

        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )

        with patch("boto3.client", return_value=mock_client):
            exists, error = _check_s3_key(
                "artifacts/missing.json",
                bucket="mybucket",
                endpoint_url="https://s3.example.com",
                access_key_id="key",
                secret_access_key="secret",
            )
        assert exists is False
        assert error == ""

    def test_returns_error_on_unexpected_s3_error(self):
        from botocore.exceptions import ClientError

        from app.scripts.check_artifacts import _check_s3_key

        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "Access Denied"}}, "HeadObject"
        )

        with patch("boto3.client", return_value=mock_client):
            exists, error = _check_s3_key(
                "artifacts/restricted.json",
                bucket="mybucket",
                endpoint_url="https://s3.example.com",
                access_key_id="key",
                secret_access_key="secret",
            )
        assert exists is False
        assert "403" in error


class TestReconciliationReport:
    def test_found_increments_on_existing_entry(self):
        from app.scripts.check_artifacts import ArtifactEntry, ReconciliationReport

        report = ReconciliationReport()
        report.add(ArtifactEntry("benchmark_version", "abc", "/path/to/file", exists=True))
        assert report.found == 1
        assert report.missing == 0
        assert report.errors == 0
        assert report.ok is True

    def test_missing_increments_on_absent_entry(self):
        from app.scripts.check_artifacts import ArtifactEntry, ReconciliationReport

        report = ReconciliationReport()
        report.add(ArtifactEntry("benchmark_version", "abc", "/missing", exists=False))
        assert report.missing == 1
        assert report.ok is False
        assert report.missing_entries[0].storage_key == "/missing"

    def test_errors_increments_when_error_set(self):
        from app.scripts.check_artifacts import ArtifactEntry, ReconciliationReport

        report = ReconciliationReport()
        report.add(ArtifactEntry("corpus_index", "xyz", "/bad", exists=False, error="S3 error 403"))
        assert report.errors == 1
        assert report.ok is False

    def test_to_dict_includes_all_fields(self):
        from app.scripts.check_artifacts import ArtifactEntry, ReconciliationReport

        report = ReconciliationReport()
        report.add(ArtifactEntry("benchmark_version", "id1", "/path", exists=True))
        report.add(ArtifactEntry("benchmark_version", "id2", "/gone", exists=False))
        d = report.to_dict()
        assert d["total"] == 2
        assert d["found"] == 1
        assert d["missing"] == 1
        assert len(d["missing_entries"]) == 1

    def test_total_counts_all_entries(self):
        from app.scripts.check_artifacts import ArtifactEntry, ReconciliationReport

        report = ReconciliationReport()
        for i in range(5):
            report.add(ArtifactEntry("benchmark_version", str(i), f"/path/{i}", exists=True))
        assert report.total == 5


class TestReconcile:
    def test_local_reconcile_all_found(self, tmp_path: Path):
        from app.scripts.check_artifacts import reconcile

        f = tmp_path / "artifact.json"
        f.write_bytes(b"data")
        version_refs = [("version-id-1", str(f))]
        corpus_refs: list = []
        report = reconcile(version_refs, corpus_refs, s3_config=None)
        assert report.found == 1
        assert report.missing == 0

    def test_local_reconcile_detects_missing(self, tmp_path: Path):
        from app.scripts.check_artifacts import reconcile

        version_refs = [("version-id-1", str(tmp_path / "gone.json"))]
        corpus_refs: list = []
        report = reconcile(version_refs, corpus_refs, s3_config=None)
        assert report.missing == 1

    def test_s3_reconcile_calls_head_object(self):
        from app.scripts.check_artifacts import reconcile

        mock_client = MagicMock()
        mock_client.head_object.return_value = {}

        s3_config = {
            "bucket": "mybucket",
            "endpoint_url": "https://s3.example.com",
            "access_key_id": "key",
            "secret_access_key": "secret",
            "region": "us-east-1",
        }
        with patch("boto3.client", return_value=mock_client):
            report = reconcile([("v1", "artifacts/a.json")], [], s3_config=s3_config)

        assert report.found == 1
        mock_client.head_object.assert_called_once_with(Bucket="mybucket", Key="artifacts/a.json")


# ===========================================================================
# db_backup — DSN parsing and command construction
# ===========================================================================


class TestParseDSN:
    def test_parse_asyncpg_url(self):
        from app.scripts.db_backup import _parse_dsn

        dsn = _parse_dsn("postgresql+asyncpg://alice:secret@db.host:5433/mydb")
        assert dsn.host == "db.host"
        assert dsn.port == "5433"
        assert dsn.dbname == "mydb"
        assert dsn.user == "alice"
        assert dsn.password == "secret"

    def test_parse_psycopg_url(self):
        from app.scripts.db_backup import _parse_dsn

        dsn = _parse_dsn("postgresql+psycopg://user:pass@localhost:5432/evalledger")
        assert dsn.host == "localhost"
        assert dsn.dbname == "evalledger"

    def test_parse_bare_postgres_url(self):
        from app.scripts.db_backup import _parse_dsn

        dsn = _parse_dsn("postgres://user:pass@host/dbname")
        assert dsn.host == "host"
        assert dsn.dbname == "dbname"

    def test_parse_plain_postgresql_url(self):
        from app.scripts.db_backup import _parse_dsn

        dsn = _parse_dsn("postgresql://u:p@h:5432/db")
        assert dsn.port == "5432"

    def test_parse_defaults_port_5432(self):
        from app.scripts.db_backup import _parse_dsn

        dsn = _parse_dsn("postgresql://user:pass@host/db")
        assert dsn.port == "5432"

    def test_parse_raises_on_empty_url(self):
        from app.scripts.db_backup import _parse_dsn

        with pytest.raises(ValueError, match="not set"):
            _parse_dsn("")

    def test_parse_raises_on_invalid_url(self):
        from app.scripts.db_backup import _parse_dsn

        with pytest.raises(ValueError, match="Could not parse host"):
            _parse_dsn("not-a-url")


class TestBuildPgDumpCommand:
    def _dsn(self, **kwargs):
        from app.scripts.db_backup import ParsedDSN

        defaults = {
            "host": "localhost",
            "port": "5432",
            "dbname": "evalledger",
            "user": "evalledger",
            "password": "secret",
        }
        return ParsedDSN(**{**defaults, **kwargs})

    def test_command_starts_with_pg_dump(self):
        from app.scripts.db_backup import build_pg_dump_command

        cmd = build_pg_dump_command(self._dsn())
        assert cmd[0] == "pg_dump"

    def test_command_includes_host_and_port(self):
        from app.scripts.db_backup import build_pg_dump_command

        cmd = build_pg_dump_command(self._dsn(host="db.host", port="5433"))
        assert "--host" in cmd
        assert "db.host" in cmd
        assert "--port" in cmd
        assert "5433" in cmd

    def test_command_includes_dbname_and_user(self):
        from app.scripts.db_backup import build_pg_dump_command

        cmd = build_pg_dump_command(self._dsn(dbname="mydb", user="alice"))
        assert "--dbname" in cmd
        assert "mydb" in cmd
        assert "--username" in cmd
        assert "alice" in cmd

    def test_command_does_not_include_password(self):
        from app.scripts.db_backup import build_pg_dump_command

        cmd = build_pg_dump_command(self._dsn(password="supersecret"))
        assert "supersecret" not in cmd

    def test_command_includes_no_password_flag(self):
        from app.scripts.db_backup import build_pg_dump_command

        cmd = build_pg_dump_command(self._dsn())
        assert "--no-password" in cmd

    def test_command_includes_output_when_provided(self):
        from app.scripts.db_backup import build_pg_dump_command

        cmd = build_pg_dump_command(self._dsn(), output_path="/tmp/backup.sql")
        assert "--file" in cmd
        assert "/tmp/backup.sql" in cmd

    def test_command_omits_file_when_output_not_set(self):
        from app.scripts.db_backup import build_pg_dump_command

        cmd = build_pg_dump_command(self._dsn())
        assert "--file" not in cmd

    def test_command_uses_custom_format(self):
        from app.scripts.db_backup import build_pg_dump_command

        cmd = build_pg_dump_command(self._dsn(), fmt="custom")
        assert "--format" in cmd
        idx = cmd.index("--format")
        assert cmd[idx + 1] == "custom"

    def test_command_defaults_to_plain_format(self):
        from app.scripts.db_backup import build_pg_dump_command

        cmd = build_pg_dump_command(self._dsn())
        idx = cmd.index("--format")
        assert cmd[idx + 1] == "plain"
