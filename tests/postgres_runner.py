"""Run the unit tests against a disposable local PostgreSQL database.

Usage (from the project folder):
    set VOXEL1_TEST_DATABASE_URL=postgresql://postgres:<password>@127.0.0.1:55432/voxel1_test
    python tests/postgres_runner.py

Safety: only a localhost/127.0.0.1 URL whose database name ends in "_test" is accepted, so the
production DATABASE_URL can never be used by mistake. The public schema of that database is
dropped and recreated before every test.
"""
import os
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def safe_url():
    url = os.environ.get("VOXEL1_TEST_DATABASE_URL", "")
    parsed = urlparse(url)
    if parsed.scheme not in ("postgresql", "postgres") or parsed.hostname not in ("127.0.0.1", "localhost", "::1") \
            or not parsed.path.strip("/").endswith("_test"):
        raise SystemExit("Set VOXEL1_TEST_DATABASE_URL to a local PostgreSQL database whose name ends in _test.")
    return url


def main():
    url = safe_url()
    os.environ.pop("DATABASE_URL", None)  # Never inherit a real database URL.
    import psycopg
    import server
    server.DATABASE_URL = url

    def reset_schema():
        with psycopg.connect(url, autocommit=True) as db:
            db.execute("DROP SCHEMA public CASCADE")
            db.execute("CREATE SCHEMA public")

    class ResettingResult(unittest.TextTestResult):
        def startTest(self, test):
            reset_schema()
            super().startTest(test)

    with psycopg.connect(url) as db:
        version = db.execute("SHOW server_version").fetchone()[0]
    print(f"PostgreSQL {version} at {urlparse(url).hostname}:{urlparse(url).port}/{urlparse(url).path.strip('/')}", flush=True)
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT / "tests"))
    result = unittest.TextTestRunner(resultclass=ResettingResult, verbosity=int(os.environ.get("VERBOSITY", "1"))).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
