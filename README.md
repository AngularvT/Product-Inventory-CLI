# Product Inventory CLI — ISBA 2438 Assignment 1

`products.py` is a Python 3 command-line tool that manages a small store's
product inventory in a local JSON file. It supports creating, reading,
updating, and deleting product records, plus a custom **restock-plan**
command that tells you which products to reorder and how many units to buy.

Built with the Python 3 standard library only — no third-party packages.
Every invocation performs one operation and exits; it never waits for
interactive input.

## Requirements

- Python 3.8+ (on Windows, `py -3` may replace `python3`)

## How to Run

```bash
python3 products.py [--file PATH] COMMAND [OPTIONS]
```

- The optional `--file PATH` flag must appear **before** the command. It
  selects the JSON data file; the default is `products.json` in the current
  working directory.
- Quote names and paths containing spaces.

## Data File

The data file is UTF-8 JSON with a `next_id` integer and a `products` array:

```json
{
  "next_id": 2,
  "products": [
    {"id": 1, "name": "Notebook", "price": "4.50", "quantity": 10}
  ]
}
```

- `id` — positive integer assigned automatically, starting at 1; IDs are
  never reused after deletion.
- `name` — at least one non-whitespace character; surrounding whitespace is
  trimmed; duplicates are allowed.
- `price` — nonnegative amount stored and printed as a string with exactly
  two decimal places (for example, inputs `0`, `4.5`, and `4.50` are stored
  as `"0.00"`, `"4.50"`, and `"4.50"`).
- `quantity` — nonnegative integer.

A missing data file is treated as an empty store; the first successful `add`
creates the file. Read-only commands never create or rewrite it. A file that
is empty, malformed, or inconsistent with the schema is reported as an error
and left unchanged.

## Commands

| Command | Description |
| --- | --- |
| `add --name NAME --price PRICE --quantity QTY` | Create a product; prints the new product as JSON. |
| `list` | Print a JSON array of all products sorted by numeric ID (`[]` when empty). |
| `get ID` | Print the matching product as JSON. |
| `update ID [--name NAME] [--price PRICE] [--quantity QTY]` | Change only the supplied fields (at least one required). |
| `delete ID --yes` | Delete the product after explicit confirmation; prints `{"deleted_id": ID}`. |
| `restock-plan --target QTY` | Custom feature: list products that need restocking (see below). |

Every command supports `--help` (for example `python3 products.py update --help`),
which exits successfully without reading or changing the data file.

### Exit Codes

| Code | Meaning |
| --- | --- |
| 0 | Successful command, including an empty list or a help request. |
| 1 | Product ID not found, invalid stored data, or a file read/write failure. |
| 2 | Invalid command syntax, missing arguments, or invalid input values. |

Failures print a concise explanation to standard error and no JSON to
standard output, with no Python traceback. A failed command never alters the
data file or consumes an ID.

## Custom Feature: restock-plan

### Who it helps and why

Small shop owners need to know what to reorder without mentally comparing
every product's stock against a goal. `restock-plan` answers one question —
*"if I want to keep QTY of each item on hand, what do I need to buy?"* —
by comparing every product against a single target quantity and returning
exactly the shortfall for the items that fall below it. It is read-only, so
it is safe to run at any time.

### Syntax, inputs, and output

```bash
python3 products.py [--file PATH] restock-plan --target QTY
```

- `--target QTY` — required; the target stock for every product; must be a
  nonnegative integer (0 is allowed).
- For each product the tool computes `needed = target - quantity`.
- Products with `needed > 0` are printed as a JSON array, sorted by numeric
  ID, each with `id`, `name`, `quantity`, and `needed`.
- If nothing needs restocking (or the data file does not exist), the output
  is `[]` with exit code 0.
- Read-only: never modifies products, `next_id`, or the data file.
- Invalid input (missing flag, negative, decimal) exits with code 2.

### Example

```bash
$ python3 products.py restock-plan --target 20
[
  {
    "id": 1,
    "name": "Notebook",
    "quantity": 12,
    "needed": 8
  },
  {
    "id": 2,
    "name": "Pencil",
    "quantity": 5,
    "needed": 15
  }
]
```

Products whose quantity has reached the target are not listed:

```bash
$ python3 products.py restock-plan --target 5
[]
```

## More Examples

```bash
python3 products.py --help
python3 products.py add --name "Notebook" --price 4.5 --quantity 10
python3 products.py add --name "Pencil" --price 1.25 --quantity 5
python3 products.py list
python3 products.py get 1
python3 products.py update 1 --quantity 12
python3 products.py delete 2 --yes
python3 products.py list

# Use a separate data file
python3 products.py --file demo.json add --name "Eraser" --price 0.99 --quantity 30

# Custom feature
python3 products.py restock-plan --target 20
python3 products.py --file demo.json restock-plan --target 40
```

## Tests

```bash
python3 -m unittest test_products.py
```

The tests cover normal operations, invalid input, corrupted/missing data
files, persistence across invocations, and the guarantee that failed or
read-only commands leave the data file (and `next_id`) untouched.
