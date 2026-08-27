"""Smoke tests for the standalone Mac Tinker Lab utilities."""
from __future__ import annotations
import csv
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def run_tool(name: str, *args: str) -> dict:
    result = subprocess.run([sys.executable, str(ROOT / "tools" / f"{name}.py"), *args, "--json"], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)

class MacTinkerSmokeTests(unittest.TestCase):
    def test_hash_and_encoding_labs(self):
        self.assertEqual(run_tool("hash_lab", "--text", "hello")["digest"], "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")
        self.assertEqual(run_tool("base64_lab", "--encode", "hello")["result"], "aGVsbG8=")
        self.assertEqual(run_tool("url_encode_lab", "--decode", "caf%C3%A9+tea")["result"], "café tea")

    def test_json_csv_and_calendar(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "data.json"
            data.write_text('{"person":{"name":"Ada","items":[1,2]}}')
            self.assertEqual(run_tool("json_flatten", str(data))["person.items[1]"], 2)
            csv_path = root / "data.csv"
            with csv_path.open("w", newline="") as f:
                writer = csv.writer(f); writer.writerow(["name", "score"]); writer.writerow(["Ada", "10"]); writer.writerow(["Bob", ""])
            profile = run_tool("csv_profile", str(csv_path))
            self.assertEqual(profile["rows"], 2)
            self.assertEqual(profile["profile"]["score"]["missing"], 1)
        cal = run_tool("calendar_month", "2026", "8", "--day", "28")
        self.assertEqual(cal["date_valid"], "2026-08-28")

    def test_filesystem_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "a.txt").write_text("same"); (root / "b.txt").write_text("same"); (root / "c.txt").write_text("different")
            duplicates = run_tool("duplicate_finder", str(root), "--min-size", "1B")
            self.assertTrue(any(set(x["files"]) == {str(root / "a.txt"), str(root / "b.txt")} for x in duplicates))
            manifest = run_tool("backup_manifest", str(root))
            self.assertEqual(len(manifest["files"]), 3)
            comparison = run_tool("directory_compare", str(root), str(root))
            self.assertEqual(comparison["diff_files"], [])

    def test_sqlite_inspector(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "demo.db"
            con = sqlite3.connect(db); con.execute("create table notes (id integer, body text)"); con.executemany("insert into notes values (?,?)", [(1,"one"),(2,"two")]); con.commit(); con.close()
            result = run_tool("sqlite_inspector", str(db))
            self.assertEqual(result["tables"][0]["table"], "notes")
            self.assertEqual(result["tables"][0]["rows"], 2)

    def test_wrapper_help_contract(self):
        wrappers = sorted((ROOT / "tools").glob("*.py"))
        self.assertGreaterEqual(len(wrappers), 54)
        for wrapper in wrappers:
            result = subprocess.run([sys.executable, str(wrapper), "--help"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, wrapper.name)

if __name__ == "__main__":
    unittest.main()
