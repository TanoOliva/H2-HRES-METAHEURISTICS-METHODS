"""Execute the thesis notebook reproducibly from the repository root.

The notebook has a single configuration cell with the literal ``MODO = "completo"``.
That cell is located by content, not by index, so inserting or moving cells does not
break the fast mode switch.
"""

import argparse
from pathlib import Path

import nbformat
from nbclient import NotebookClient


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "notebooks" / "H2_HRES_trabajo.ipynb"
MODE_LITERAL = 'MODO = "completo"'


def find_mode_cell(notebook):
    matches = [cell for cell in notebook.cells
               if cell.cell_type == "code" and MODE_LITERAL in cell.source]
    if len(matches) != 1:
        raise RuntimeError(
            "expected exactly one code cell containing {!r}, found {}".format(
                MODE_LITERAL, len(matches)))
    return matches[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("rapido", "completo"), default="completo")
    parser.add_argument("--output", type=Path, default=SOURCE)
    parser.add_argument("--timeout", type=int, default=18000,
                        help="per-cell timeout in seconds (the brute force of the "
                             "largest instance takes about 90 minutes)")
    args = parser.parse_args()

    notebook = nbformat.read(SOURCE, as_version=4)
    if args.mode == "rapido":
        cell = find_mode_cell(notebook)
        cell.source = cell.source.replace(MODE_LITERAL, 'MODO = "rapido"')

    client = NotebookClient(
        notebook,
        timeout=args.timeout,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT / "notebooks")}},
    )
    client.execute()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, args.output)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
