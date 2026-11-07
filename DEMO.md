# Demonstration Script — ISBA 2438 Assignment 1

Record the steps below in order. Every block starts from the state produced
by the previous block. Expected output is shown after each command.

## 1. Help (no data file exists yet)

```bash
rm -f products.json
ls products.json          # confirm: does not exist
python3 products.py --help
```

Expected: usage text listing `add, list, get, update, delete, restock-plan`
and the `--file PATH` flag; exit code 0; `products.json` still absent.

## 2. Required success sequence (creates products.json)

```bash
python3 products.py add --name "Notebook" --price 4.5 --quantity 10
```
Expected: `{"id": 1, "name": "Notebook", "price": "4.50", "quantity": 10}`

```bash
python3 products.py add --name "Pencil" --price 1.25 --quantity 5
```
Expected: `{"id": 2, "name": "Pencil", "price": "1.25", "quantity": 5}`

```bash
python3 products.py list
```
Expected: JSON array with products 1 and 2, sorted by ID.

```bash
python3 products.py get 1
python3 products.py update 1 --quantity 12
python3 products.py delete 2 --yes
python3 products.py list
cat products.json
```
Expected: `get` shows Notebook; `update` shows quantity 12; `delete` prints
`{"deleted_id": 2}`; final `list` contains only Notebook
(`"price": "4.50"`, `"quantity": 12`); the file shows `"next_id": 3`.

## 3. Persistence

Run any command again in a new terminal invocation, e.g.:

```bash
python3 products.py get 1
python3 products.py add --name "Pencil" --price 1.25 --quantity 5
```

Expected: the first `get` reads the saved data (quantity 12); the new `add`
gets ID 3 (`next_id` was 3), proving deleted ID 2 is never reused and the
later invocation sees saved changes.

## 4. Error checks (data unchanged after each failure)

```bash
python3 products.py get 99
```
Expected: exit code 1, stderr explains product 99 was not found, no JSON.

```bash
python3 products.py add --name "Bad" --price 4.505 --quantity 3
python3 products.py update 1 --price -1
python3 products.py update 1
```
Expected: all exit code 2 with a clear stderr message (invalid price, sign
rejected, update without a field flag).

```bash
python3 products.py delete 1
```
Expected: exit code 2 — `--yes` is required.

```bash
python3 products.py list && cat products.json
```
Expected: data identical to before the failed commands (no ID consumed).

## 5. Corrupted data file (shown on a separate file)

The tool refuses to touch a corrupt file, so demonstrate the corruption on a
copy and keep `products.json` usable for the rest of the recording:

```bash
cp products.json broken.json
printf 'not json' > broken.json
python3 products.py --file broken.json list
cat broken.json
```

Expected: exit code 1, stderr reports invalid JSON, `broken.json` bytes
unchanged. The main `products.json` is not involved. (If a real data file
ever becomes corrupt, the tool will keep rejecting it; recover by deleting
that file and rebuilding the store with `add` commands.)

## 6. Separate data file with --file

```bash
python3 products.py --file demo.json add --name "Eraser" --price 0.99 --quantity 30
python3 products.py --file demo.json list
python3 products.py list
cat demo.json
```
Expected: `demo.json` is created and used; the default `products.json` is
not touched. (Also show that `--file` placed after the command, e.g.
`products.py list --file demo.json`, is rejected with exit code 2.)

## 7. Custom feature: restock-plan

Successful use:

```bash
python3 products.py restock-plan --target 20
```
Expected (with Notebook 12 and Pencil 5 on hand; Pencil was re-added in
step 3 and received ID 3 because ID 2 is never reused):

```json
[
  {"id": 1, "name": "Notebook", "quantity": 12, "needed": 8},
  {"id": 3, "name": "Pencil", "quantity": 5, "needed": 15}
]
```

Edge cases:

```bash
python3 products.py restock-plan --target 0
```
Expected: `[]` (every quantity >= 0 needs nothing), exit code 0.

```bash
python3 products.py restock-plan --target -1
python3 products.py restock-plan --target 2.5
python3 products.py restock-plan
```
Expected: all exit code 2 (negative, decimal, missing `--target`).

```bash
rm -f empty.json
python3 products.py --file empty.json restock-plan --target 20
ls empty.json
```
Expected: `[]` with exit code 0 and no file created — the feature is
read-only.

Finish by showing that the core commands still work
(`python3 products.py list`) and explaining the code in your own words:
command parsing (`build_parser`), input validation (`parse_*`), the
file read/write flow (`load_store` / `save_store`), ID assignment in
`cmd_add`, and the `needed = target - quantity` computation in
`cmd_restock_plan`.
