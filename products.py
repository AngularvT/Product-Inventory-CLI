"""ISBA 2438 Assignment 1: product inventory command-line tool.

CODING_AGENT_IDENTIFIED_FLAG -- this tool was built with a coding agent
for ISBA 2438 (AI Assisted Software Development), Fall 2026.

Entry point: products.py. Python 3 standard library only.

Usage:
    python3 products.py [--file PATH] COMMAND [OPTIONS]

Commands: add, list, get, update, delete, restock-plan.
"""

import argparse
import json
import os
import re
import sys
import tempfile

# Assignment-required marker for coding-agent-built source code.
CODING_AGENT_IDENTIFIED_FLAG = "CODING_AGENT_IDENTIFIED_FLAG"

DEFAULT_FILE = "products.json"

# Input forms (checked with fullmatch against the whole value).
NAME_CHAR = re.compile(r"\S")
PRICE_INPUT = re.compile(r"\d+(?:\.\d{1,2})?")  # digits, optional . + 1-2 digits
NONNEG_INT = re.compile(r"\d+")
# Stored price must have exactly two decimal places, e.g. "4.50".
PRICE_STORED = re.compile(r"\d+\.\d\d")


class AppError(Exception):
    """A handled failure: printed to stderr, no traceback.

    exit_code 1 -- product not found, invalid stored data, file error.
    exit_code 2 -- invalid syntax, missing arguments, invalid input values.
    """

    def __init__(self, message, exit_code=1):
        super().__init__(message)
        self.exit_code = exit_code


# ---------------------------------------------------------------------------
# Input validation (argparse calls these while parsing; any failure there
# exits with code 2 before the data file is ever touched).
# CODING_AGENT_IDENTIFIED_FLAG
# ---------------------------------------------------------------------------

def parse_name(value):
    """Trim whitespace; require at least one non-whitespace character."""
    name = value.strip()
    if not NAME_CHAR.search(name):
        raise argparse.ArgumentTypeError(
            "name must contain at least one non-whitespace character")
    return name


def parse_price(value):
    """Accept 0, 4.5, 4.50 ...; store as a string with two decimals."""
    if not PRICE_INPUT.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "price must be a nonnegative amount: digits optionally followed "
            "by a decimal point and one or two digits (e.g. 0, 4.5, 4.50)")
    whole, _, frac = value.partition(".")
    return "{}.{}".format(whole, (frac + "00")[:2])


def parse_nonneg_int(value):
    """Accept nonnegative integers only: no sign, no decimal point."""
    if not NONNEG_INT.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "value must be a nonnegative integer")
    return int(value)


def parse_positive_int(value):
    """IDs must be positive integers (1, 2, 3, ...)."""
    if not NONNEG_INT.fullmatch(value) or int(value) == 0:
        raise argparse.ArgumentTypeError("ID must be a positive integer")
    return int(value)


# ---------------------------------------------------------------------------
# Stored-data validation. Any inconsistency with the required schema makes
# the whole store invalid, so every command fails with exit code 1.
# CODING_AGENT_IDENTIFIED_FLAG
# ---------------------------------------------------------------------------

def validate_store(data, path):
    """Raise AppError unless data matches the required store schema."""
    def bad(detail):
        return AppError("data file {} is inconsistent with the required "
                        "schema: {}".format(path, detail))

    if not isinstance(data, dict):
        raise bad("top level must be a JSON object")
    next_id = data.get("next_id")
    products = data.get("products")
    if isinstance(next_id, bool) or not isinstance(next_id, int) or next_id < 1:
        raise bad("next_id must be a positive integer")
    if not isinstance(products, list):
        raise bad("products must be a JSON array")
    seen_ids = set()
    for entry in products:
        if not isinstance(entry, dict):
            raise bad("each product must be a JSON object")
        pid = entry.get("id")
        if isinstance(pid, bool) or not isinstance(pid, int) or pid < 1:
            raise bad("product id must be a positive integer")
        if pid in seen_ids:
            raise bad("duplicate product id {}".format(pid))
        seen_ids.add(pid)
        if pid >= next_id:
            raise bad("next_id must be greater than every existing product id")
        name = entry.get("name")
        if not isinstance(name, str) or not NAME_CHAR.search(name):
            raise bad("product {} has an invalid name".format(pid))
        price = entry.get("price")
        if not isinstance(price, str) or not PRICE_STORED.fullmatch(price):
            raise bad('product {} has an invalid price (expected a string '
                      'with exactly two decimal places)'.format(pid))
        quantity = entry.get("quantity")
        if isinstance(quantity, bool) or not isinstance(quantity, int) \
                or quantity < 0:
            raise bad("product {} has an invalid quantity".format(pid))


# ---------------------------------------------------------------------------
# File read/write flow.
# CODING_AGENT_IDENTIFIED_FLAG
# ---------------------------------------------------------------------------

def empty_store():
    return {"next_id": 1, "products": []}


def load_store(path):
    """Read the data file.

    Missing file  -> treated as an empty store (nothing is created).
    Bad/empty file or read failure -> AppError, exit code 1.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = handle.read()
    except FileNotFoundError:
        return empty_store()
    except UnicodeDecodeError:
        raise AppError("data file {} is not valid UTF-8 text".format(path))
    except OSError as exc:
        raise AppError("cannot read data file {}: {}".format(path, exc.strerror or exc))
    if not raw.strip():
        raise AppError("data file {} is empty".format(path))
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise AppError("data file {} is not valid JSON: {}".format(path, exc))
    validate_store(data, path)
    return data


def save_store(path, store):
    """Serialize fully in memory, then write. UTF-8 JSON.

    The payload goes to a temporary file in the same directory first and is
    then moved over the target with os.replace. If writing fails midway, the
    temporary file is removed and the existing data file keeps its old bytes.
    """
    payload = json.dumps(store, indent=2, ensure_ascii=False) + "\n"
    directory = os.path.dirname(path) or "."
    temp_path = None
    try:
        descriptor, temp_path = tempfile.mkstemp(
            prefix=".products-", suffix=".tmp", dir=directory)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(temp_path, path)
        temp_path = None
    except OSError as exc:
        raise AppError("cannot write data file {}: {}".format(
            path, exc.strerror or exc))
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def find_product(store, product_id, path):
    for entry in store["products"]:
        if entry["id"] == product_id:
            return entry
    raise AppError("product {} not found in {}".format(product_id, path))


# ---------------------------------------------------------------------------
# Command handlers. Successful data commands print only JSON to stdout.
# CODING_AGENT_IDENTIFIED_FLAG
# ---------------------------------------------------------------------------

def product_view(entry):
    """The four contract fields, in order, for output."""
    return {
        "id": entry["id"],
        "name": entry["name"],
        "price": entry["price"],
        "quantity": entry["quantity"],
    }


def print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_add(args):
    store = load_store(args.file)
    entry = {
        "id": store["next_id"],
        "name": args.name,
        "price": args.price,
        "quantity": args.quantity,
    }
    store["products"].append(entry)
    store["next_id"] += 1
    save_store(args.file, store)
    print_json(product_view(entry))


def cmd_list(args):
    store = load_store(args.file)
    rows = sorted(store["products"], key=lambda entry: entry["id"])
    print_json([product_view(entry) for entry in rows])


def cmd_get(args):
    store = load_store(args.file)
    entry = find_product(store, args.id, args.file)
    print_json(product_view(entry))


def cmd_update(args):
    if args.name is None and args.price is None and args.quantity is None:
        raise AppError("update requires at least one of --name, --price, "
                       "--quantity", exit_code=2)
    store = load_store(args.file)
    entry = find_product(store, args.id, args.file)
    if args.name is not None:
        entry["name"] = args.name
    if args.price is not None:
        entry["price"] = args.price
    if args.quantity is not None:
        entry["quantity"] = args.quantity
    save_store(args.file, store)
    print_json(product_view(entry))


def cmd_delete(args):
    if not args.yes:
        raise AppError("delete requires --yes to confirm removal",
                       exit_code=2)
    store = load_store(args.file)
    entry = find_product(store, args.id, args.file)
    store["products"].remove(entry)
    save_store(args.file, store)
    print_json({"deleted_id": entry["id"]})


def cmd_restock_plan(args):
    """Custom feature: restock-plan. Read-only; never writes the file."""
    store = load_store(args.file)
    plan = []
    for entry in sorted(store["products"], key=lambda item: item["id"]):
        needed = args.target - entry["quantity"]
        if needed > 0:
            plan.append({
                "id": entry["id"],
                "name": entry["name"],
                "quantity": entry["quantity"],
                "needed": needed,
            })
    print_json(plan)


# ---------------------------------------------------------------------------
# Command-line interface.
# CODING_AGENT_IDENTIFIED_FLAG
# ---------------------------------------------------------------------------

def build_parser():
    # allow_abbrev=False so flags like --y or --quant are rejected:
    # only the exact flag names from the handout are accepted.
    parser = argparse.ArgumentParser(
        prog="products.py", allow_abbrev=False,
        description="Product inventory CLI for a small store "
                    "(ISBA 2438 Assignment 1). {}".format(CODING_AGENT_IDENTIFIED_FLAG))
    parser.add_argument(
        "--file", metavar="PATH", default=DEFAULT_FILE,
        help="JSON data file to use, before the command "
             "(default: {})".format(DEFAULT_FILE))
    subparsers = parser.add_subparsers(
        dest="command", metavar="COMMAND", required=True)

    sub = subparsers.add_parser(
        "add", help="create a product (ID assigned automatically)",
        allow_abbrev=False)
    sub.add_argument("--name", required=True, type=parse_name, metavar="NAME")
    sub.add_argument("--price", required=True, type=parse_price, metavar="PRICE")
    sub.add_argument("--quantity", required=True, type=parse_nonneg_int,
                     metavar="QTY")
    sub.set_defaults(func=cmd_add)

    sub = subparsers.add_parser("list", help="print all products by ID",
                                allow_abbrev=False)
    sub.set_defaults(func=cmd_list)

    sub = subparsers.add_parser("get", help="print one product by ID",
                                allow_abbrev=False)
    sub.add_argument("id", type=parse_positive_int, metavar="ID")
    sub.set_defaults(func=cmd_get)

    sub = subparsers.add_parser("update", help="change fields of one product",
                                allow_abbrev=False)
    sub.add_argument("id", type=parse_positive_int, metavar="ID")
    sub.add_argument("--name", type=parse_name, metavar="NAME")
    sub.add_argument("--price", type=parse_price, metavar="PRICE")
    sub.add_argument("--quantity", type=parse_nonneg_int, metavar="QTY")
    sub.set_defaults(func=cmd_update)

    sub = subparsers.add_parser("delete", help="remove one product by ID",
                                allow_abbrev=False)
    sub.add_argument("id", type=parse_positive_int, metavar="ID")
    sub.add_argument("--yes", action="store_true",
                     help="confirm the deletion")
    sub.set_defaults(func=cmd_delete)

    sub = subparsers.add_parser(
        "restock-plan",
        help="list products that need restocking to reach a target quantity",
        allow_abbrev=False)
    sub.add_argument("--target", required=True, type=parse_nonneg_int,
                     metavar="QTY",
                     help="target quantity for every product")
    sub.set_defaults(func=cmd_restock_plan)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except AppError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return exc.exit_code
    return 0


if __name__ == "__main__":
    sys.exit(main())
