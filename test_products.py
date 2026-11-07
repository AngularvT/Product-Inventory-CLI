"""Tests for products.py (ISBA 2438 Assignment 1).

Run with:  python3 -m unittest test_products.py -v

Each test drives the real CLI in a subprocess so exit codes, stdout,
stderr, and on-disk effects are checked end to end.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CLI = [sys.executable, os.path.join(PROJECT_DIR, "products.py")]
FLAG = "CODING_AGENT_IDENTIFIED_FLAG"


def write_store(path, products, next_id):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"next_id": next_id, "products": products}, handle)


def product(pid, name="Item", price="1.00", quantity=1):
    return {"id": pid, "name": name, "price": price, "quantity": quantity}


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "products.json")
        self._olddir = os.getcwd()
        os.chdir(self.dir.name)

    def tearDown(self):
        os.chdir(self._olddir)
        self.dir.cleanup()

    def run_cli(self, *args):
        return subprocess.run(
            CLI + list(args), capture_output=True, text=True)

    def snapshot(self, path=None):
        path = path or self.path
        if not os.path.exists(path):
            return None
        with open(path, "rb") as handle:
            data = handle.read()
        return data, os.stat(path).st_mtime_ns

    def assertUnchanged(self, before, path=None):
        path = path or self.path
        if before is None:
            self.assertFalse(os.path.exists(path),
                             "file was created by a failed/read-only command")
        else:
            self.assertEqual(before, self.snapshot(path))

    def assertJson(self, completed, expected):
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), expected)


class AddTests(CliTestCase):
    def test_add_creates_file_assigns_id_and_persists(self):
        result = self.run_cli("add", "--name", "Notebook",
                              "--price", "4.5", "--quantity", "10")
        self.assertJson(result, {"id": 1, "name": "Notebook",
                                 "price": "4.50", "quantity": 10})
        with open(self.path, encoding="utf-8") as handle:
            store = json.load(handle)
        self.assertEqual(store,
                         {"next_id": 2, "products": [product(1, "Notebook", "4.50", 10)]})

    def test_add_ids_increment_and_delete_ids_are_never_reused(self):
        self.run_cli("add", "--name", "A", "--price", "1", "--quantity", "1")
        self.run_cli("add", "--name", "B", "--price", "1", "--quantity", "1")
        result = self.run_cli("delete", "2", "--yes")
        self.assertJson(result, {"deleted_id": 2})
        result = self.run_cli("add", "--name", "C", "--price", "1",
                              "--quantity", "1")
        self.assertJson(result,
                        {"id": 3, "name": "C", "price": "1.00", "quantity": 1})

    def test_add_trims_name_and_accepts_zero_values(self):
        result = self.run_cli("add", "--name", "  Loose Leaf  ", "--price",
                              "0", "--quantity", "0")
        self.assertJson(result, {"id": 1, "name": "Loose Leaf",
                                 "price": "0.00", "quantity": 0})

    def test_add_invalid_values_exit_2_without_touching_file(self):
        write_store(self.path, [product(1)], 2)
        before = self.snapshot()
        for extra in (["--price", "-1"], ["--price", "$4"], ["--price", "1e2"],
                      ["--price", "4.505"], ["--price", ""],
                      ["--quantity", "-1"], ["--quantity", "1.5"],
                      ["--quantity", "abc"], ["--name", "   "],
                      ["--name", "\t"]):
            result = self.run_cli("add", "--name", "X",
                                  "--price", "2", "--quantity", "2", *extra)
            self.assertEqual(result.returncode, 2, extra)
            self.assertTrue(result.stderr, extra)
            self.assertNotIn("Traceback", result.stderr)
        self.assertUnchanged(before)

    def test_add_missing_flag_exits_2(self):
        result = self.run_cli("add", "--name", "X", "--price", "2")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(os.path.exists(self.path))


class ListGetTests(CliTestCase):
    def test_list_missing_file_prints_empty_array_and_creates_nothing(self):
        result = self.run_cli("list")
        self.assertJson(result, [])
        self.assertFalse(os.path.exists(self.path))

    def test_list_sorts_by_numeric_id(self):
        write_store(self.path, [product(10), product(2), product(1)], 11)
        result = self.run_cli("list")
        self.assertJson(result, [product(1), product(2), product(10)])

    def test_list_is_read_only(self):
        write_store(self.path, [product(1)], 2)
        before = self.snapshot()
        self.assertJson(self.run_cli("list"), [product(1)])
        self.assertUnchanged(before)

    def test_get_returns_matching_product(self):
        write_store(self.path, [product(1), product(2, "Pen")], 3)
        self.assertJson(self.run_cli("get", "2"), product(2, "Pen"))

    def test_get_missing_or_invalid_id(self):
        write_store(self.path, [product(1)], 2)
        before = self.snapshot()
        result = self.run_cli("get", "9")
        self.assertEqual(result.returncode, 1)
        self.assertIn("9", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        for bad in ("0", "-1", "abc", "1.5"):
            self.assertEqual(self.run_cli("get", bad).returncode, 2, bad)
        self.assertUnchanged(before)


class UpdateDeleteTests(CliTestCase):
    def test_update_changes_only_supplied_fields(self):
        write_store(self.path, [product(1, "Notebook", "4.50", 10)], 2)
        result = self.run_cli("update", "1", "--quantity", "12")
        self.assertJson(result, product(1, "Notebook", "4.50", 12))

    def test_update_all_fields_and_persists(self):
        write_store(self.path, [product(1, "Old", "1.00", 1)], 2)
        result = self.run_cli("update", "1", "--name", " New ", "--price",
                              "2.5", "--quantity", "7")
        self.assertJson(result, product(1, "New", "2.50", 7))
        self.assertJson(self.run_cli("get", "1"), product(1, "New", "2.50", 7))

    def test_update_without_flags_exits_2_and_keeps_file(self):
        write_store(self.path, [product(1)], 2)
        before = self.snapshot()
        result = self.run_cli("update", "1")
        self.assertEqual(result.returncode, 2)
        self.assertUnchanged(before)

    def test_update_invalid_value_exits_2_and_keeps_file(self):
        write_store(self.path, [product(1, "Notebook", "4.50", 10)], 2)
        before = self.snapshot()
        result = self.run_cli("update", "1", "--price", "-3")
        self.assertEqual(result.returncode, 2)
        self.assertUnchanged(before)

    def test_update_missing_id_exits_1_and_keeps_file(self):
        write_store(self.path, [product(1)], 2)
        before = self.snapshot()
        result = self.run_cli("update", "7", "--quantity", "3")
        self.assertEqual(result.returncode, 1)
        self.assertIn("7", result.stderr)
        self.assertUnchanged(before)

    def test_delete_without_yes_exits_2_and_keeps_file(self):
        write_store(self.path, [product(1)], 2)
        before = self.snapshot()
        result = self.run_cli("delete", "1")
        self.assertEqual(result.returncode, 2)
        self.assertUnchanged(before)

    def test_delete_removes_only_selected_product_and_keeps_next_id(self):
        write_store(self.path, [product(1), product(2), product(3)], 4)
        self.assertJson(self.run_cli("delete", "2", "--yes"),
                        {"deleted_id": 2})
        self.assertJson(self.run_cli("list"), [product(1), product(3)])
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["next_id"], 4)

    def test_delete_missing_id_exits_1(self):
        write_store(self.path, [product(1)], 2)
        before = self.snapshot()
        result = self.run_cli("delete", "5", "--yes")
        self.assertEqual(result.returncode, 1)
        self.assertIn("5", result.stderr)
        self.assertUnchanged(before)


class RestockPlanTests(CliTestCase):
    def test_restock_plan_matches_design_example(self):
        write_store(self.path, [product(1, "Notebook", "4.50", 12),
                                product(2, "Pencil", "1.25", 5)], 3)
        result = self.run_cli("restock-plan", "--target", "20")
        self.assertJson(result, [
            {"id": 1, "name": "Notebook", "quantity": 12, "needed": 8},
            {"id": 2, "name": "Pencil", "quantity": 5, "needed": 15}])

    def test_restock_plan_excludes_products_at_or_above_target(self):
        write_store(self.path, [product(1, "A", "1.00", 10),
                                product(2, "B", "1.00", 9),
                                product(3, "C", "1.00", 11)], 4)
        self.assertJson(self.run_cli("restock-plan", "--target", "10"),
                        [{"id": 2, "name": "B", "quantity": 9, "needed": 1}])

    def test_restock_plan_no_needs_and_target_zero(self):
        write_store(self.path, [product(1, "A", "1.00", 3)], 2)
        self.assertJson(self.run_cli("restock-plan", "--target", "3"), [])
        self.assertJson(self.run_cli("restock-plan", "--target", "0"), [])

    def test_restock_plan_missing_file_is_empty_and_creates_nothing(self):
        result = self.run_cli("restock-plan", "--target", "5")
        self.assertJson(result, [])
        self.assertFalse(os.path.exists(self.path))

    def test_restock_plan_is_read_only(self):
        write_store(self.path, [product(1, "A", "1.00", 2)], 2)
        before = self.snapshot()
        self.assertJson(self.run_cli("restock-plan", "--target", "5"),
                        [{"id": 1, "name": "A", "quantity": 2, "needed": 3}])
        self.assertUnchanged(before)

    def test_restock_plan_invalid_targets(self):
        write_store(self.path, [product(1)], 2)
        before = self.snapshot()
        for bad in (["-1"], ["1.5"], ["abc"], [""]):
            result = self.run_cli("restock-plan", "--target", *bad)
            self.assertEqual(result.returncode, 2, bad)
            self.assertNotIn("Traceback", result.stderr)
        result = self.run_cli("restock-plan")
        self.assertEqual(result.returncode, 2)
        self.assertUnchanged(before)


class FileErrorTests(CliTestCase):
    def test_empty_file_reports_error_exit_1(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("  ")
        before = self.snapshot()
        result = self.run_cli("list")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertUnchanged(before)

    def test_malformed_json_reports_error_and_is_unchanged(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        before = self.snapshot()
        result = self.run_cli("add", "--name", "X", "--price", "1",
                              "--quantity", "1")
        self.assertEqual(result.returncode, 1)
        self.assertUnchanged(before)

    def test_inconsistent_stores_report_error(self):
        cases = [
            ({"next_id": 1, "products": [product(1)]}, "next_id not above id"),
            ({"next_id": 5, "products": [product(1), product(1)]}, "dup ids"),
            ({"next_id": 3, "products": [product(1, price="4.5")]}, "bad price"),
            ({"next_id": 3, "products": [{"id": 1, "name": "A",
                                          "quantity": 1}]}, "missing price"),
            ({"next_id": 3, "products": [product(1, quantity=-2)]}, "neg qty"),
            ({"next_id": 0, "products": []}, "bad next_id"),
            ({"products": []}, "missing next_id"),
            ([product(1)], "top-level array"),
        ]
        for store, label in cases:
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump(store, handle)
            before = self.snapshot()
            for command in ("list", "restock-plan"):
                args = [command] + (["--target", "5"]
                                    if command == "restock-plan" else [])
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 1, label)
                self.assertNotIn("Traceback", result.stderr)
            self.assertUnchanged(before)

    def test_missing_parent_directory_fails_without_creating_it(self):
        nested = os.path.join(self.dir.name, "no-such-dir", "store.json")
        result = subprocess.run(
            CLI + ["--file", nested, "add", "--name", "X", "--price", "1",
                   "--quantity", "1"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(os.path.exists(os.path.dirname(nested)))

    def test_directory_as_data_file_reports_error(self):
        result = subprocess.run(
            CLI + ["--file", self.dir.name, "list"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)


class InterfaceTests(CliTestCase):
    def test_help_exits_0_without_touching_file(self):
        for args in (["--help"], ["add", "--help"], ["list", "--help"],
                     ["get", "--help"], ["update", "--help"],
                     ["delete", "--help"], ["restock-plan", "--help"]):
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 0, args)
            self.assertFalse(os.path.exists(self.path))
        self.assertIn("restock-plan", self.run_cli("--help").stdout)
        self.assertIn(FLAG, self.run_cli("--help").stdout)

    def test_unknown_command_flags_and_positionals_exit_2(self):
        for args in (["bogus"], ["list", "--bogus"], ["list", "extra"],
                     ["get"], ["--file"], ["--bogus"], [],
                     ["add", "--name", "X", "--price", "1", "--quantity", "1",
                      "extra"], ["add", "--file", "other.json", "--name", "X",
                                 "--price", "1", "--quantity", "1"]):
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 2, args)
            self.assertNotIn("Traceback", result.stderr)

    def test_file_flag_selects_separate_data_file(self):
        other = os.path.join(self.dir.name, "demo.json")
        result = subprocess.run(
            CLI + ["--file", other, "add", "--name", "Tag", "--price", "0.99",
                   "--quantity", "4"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(os.path.exists(other))
        self.assertFalse(os.path.exists(self.path))
        with open(other, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["next_id"], 2)

    def test_source_contains_required_agent_flag(self):
        source_path = os.path.join(PROJECT_DIR, "products.py")
        with open(source_path, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn(FLAG, source)


class RobustnessTests(CliTestCase):
    def test_write_failure_preserves_existing_bytes(self):
        if os.name != "posix":
            self.skipTest("needs POSIX resource limits")
        write_store(self.path, [product(1), product(2, "Pencil", "1.25", 5)],
                    3)
        before = self.snapshot()
        wrapper = ("import resource,runpy,signal,sys;"
                   "signal.signal(signal.SIGXFSZ, signal.SIG_IGN);"
                   "resource.setrlimit(resource.RLIMIT_FSIZE,(64,64));"
                   "sys.argv=sys.argv[1:];"
                   "runpy.run_path(sys.argv[0], run_name='__main__')")
        for args in (["add", "--name", "X", "--price", "2", "--quantity", "3"],
                     ["update", "1", "--quantity", "4"],
                     ["delete", "1", "--yes"]):
            with self.subTest(command=args[0]):
                result = subprocess.run(
                    [sys.executable, "-B", "-c", wrapper,
                     os.path.join(PROJECT_DIR, "products.py")] + args,
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertUnchanged(before)

    def test_non_utf8_file_reports_error_without_traceback(self):
        with open(self.path, "wb") as handle:
            handle.write(b"\xff\xfe\x00not utf8")
        before = self.snapshot()
        for args in (["list"], ["restock-plan", "--target", "5"]):
            with self.subTest(command=args[0]):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
        self.assertUnchanged(before)

    def test_abbreviated_flags_are_rejected(self):
        write_store(self.path, [product(1)], 2)
        before = self.snapshot()
        for args in (["delete", "1", "--y"], ["update", "1", "--quant", "9"],
                     ["restock-plan", "--tar", "5"],
                     ["--fil", "x.json", "list"],
                     ["add", "--nam", "X", "--pr", "1", "--quant", "1"]):
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
        self.assertUnchanged(before)


class PersistenceTests(CliTestCase):
    def test_later_invocations_see_saved_changes(self):
        self.run_cli("add", "--name", "Notebook", "--price", "4.5",
                     "--quantity", "10")
        self.run_cli("update", "1", "--quantity", "12")
        self.assertJson(self.run_cli("get", "1"),
                        product(1, "Notebook", "4.50", 12))

    def test_failed_mutation_keeps_bytes_and_next_id(self):
        self.run_cli("add", "--name", "Notebook", "--price", "4.5",
                     "--quantity", "10")
        before = self.snapshot()
        for args in (["add", "--name", "", "--price", "1", "--quantity", "1"],
                     ["add", "--name", "X", "--price", "-2", "--quantity", "1"],
                     ["update", "9", "--quantity", "1"],
                     ["delete", "9", "--yes"],
                     ["delete", "1"],
                     ["update", "1", "--name", " "]):
            result = self.run_cli(*args)
            self.assertNotEqual(result.returncode, 0, args)
            self.assertUnchanged(before)
        self.assertJson(self.run_cli("add", "--name", "Pencil", "--price",
                                     "1.25", "--quantity", "5"),
                        product(2, "Pencil", "1.25", 5))


if __name__ == "__main__":
    unittest.main()
