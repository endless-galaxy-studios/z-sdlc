"""planning-services.sh's early exits: no database named (planning runs without production data), the TLS
decision (required off a private network), and a database named without its password. Starting pgbouncer itself needs the job container; factory-smoke covers it."""
import json
import os
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "planning-services.sh"


class PlanningServices(unittest.TestCase):
    def run_it(self, database, password=None):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = pathlib.Path(tmp) / "planning.json"
            cfg.write_text(json.dumps({"database": database}))
            env = {k: v for k, v in os.environ.items() if k != "FACTORY_DB_READER_PASSWORD"}
            if password is not None:
                env["FACTORY_DB_READER_PASSWORD"] = password
            return subprocess.run(["bash", str(SCRIPT), str(cfg), str(pathlib.Path(tmp) / "db")],
                                  capture_output=True, text=True, env=env)

    def test_no_database_is_not_an_error(self):
        for database in ({"host": "", "port": 5432, "name": "", "user": "factory_reader", "local_port": 6432}, {}):
            r = self.run_it(database)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("names no database", r.stdout)

    def test_a_named_database_needs_its_password(self):
        r = self.run_it({"host": "db.example", "port": 5432, "name": "app", "user": "reader", "local_port": 6432})
        self.assertEqual(r.returncode, 1)
        self.assertIn("no database password", r.stderr)

    def db(self, host, **extra):
        return {"host": host, "port": 5432, "name": "app", "user": "reader", "local_port": 6432, **extra}

    def test_tls_is_required_off_a_private_network(self):
        # The TLS decision comes before the password check, so it shows without starting pgbouncer.
        for host in ["db.example", "203.0.113.7"]:
            r = self.run_it(self.db(host))
            self.assertIn(f"TLS to {host}: require", r.stdout)
            for mode in ("prefer", "disable"):
                r = self.run_it(self.db(host, sslmode=mode))
                self.assertEqual(r.returncode, 1)
                self.assertIn("sslmode must be require", r.stderr)

    def test_tls_is_preferred_on_a_private_network(self):
        tailnet = ".".join(["100", "64", "0", "1"])  # the CGNAT range Tailscale uses
        for host in ["10.0.0.5", "192.168.1.20", "127.0.0.1", tailnet]:
            self.assertIn(f"TLS to {host}: prefer", self.run_it(self.db(host)).stdout)
        self.assertIn("TLS to 10.0.0.5: disable", self.run_it(self.db("10.0.0.5", sslmode="disable")).stdout)
        self.assertIn("TLS to 10.0.0.5: require", self.run_it(self.db("10.0.0.5", sslmode="require")).stdout)

    def test_an_unknown_sslmode_is_refused(self):
        r = self.run_it(self.db("db.example", sslmode="allow"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("must be require, prefer or disable", r.stderr)


if __name__ == "__main__":
    unittest.main()
