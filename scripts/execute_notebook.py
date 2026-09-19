"""Execute the thesis notebook reproducibly from the repository root."""

import argparse
from pathlib import Path

import nbformat
from nbclient import NotebookClient


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "notebooks" / "H2_HRES_trabajo.ipynb"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("rapido", "completo"), default="completo")
    parser.add_argument("--output", type=Path, default=SOURCE)
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()

    notebook = nbformat.read(SOURCE, as_version=4)
    if args.mode == "rapido":
        notebook.cells[2].source = notebook.cells[2].source.replace(
            'MODO = "completo"', 'MODO = "rapido"'
        )

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
