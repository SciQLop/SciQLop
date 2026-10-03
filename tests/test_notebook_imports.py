"""Every bundled notebook cell imports what it uses.

Readers jump between sections, so a cell may reuse an earlier cell's variables (the
running panel, data) but not its imports. Static: no notebook is run.
"""
import ast
import builtins
import json
import pathlib

import pytest

EXAMPLES = pathlib.Path(__file__).parent.parent / "SciQLop" / "examples"
NOTEBOOKS = sorted(p for p in EXAMPLES.rglob("*.ipynb") if ".ipynb_checkpoints" not in p.parts)
# Names the %%vp and %%layer magics put in the cell's namespace themselves.
MAGIC_NAMES = {"vp": {"Scalar", "Vector", "MultiComponent", "Spectrogram", "Colored"},
               "layer": {"Marker", "Span", "HLine"}}
ALWAYS_THERE = set(dir(builtins)) | {"display", "get_ipython"}


def _python_part(cell):
    src = cell["source"] if isinstance(cell["source"], str) else "".join(cell["source"])
    lines = src.split("\n")
    magic = lines[0][2:].split()[0] if lines[0].startswith("%%") else None
    body = lines[1:] if magic else lines
    return magic, "\n".join("" if l.lstrip().startswith(("%", "!")) else l for l in body)


class _Names(ast.NodeVisitor):
    def __init__(self):
        self.defined, self.imported, self.used = set(), set(), set()

    def _import(self, name):
        self.defined.add(name)
        self.imported.add(name)

    def visit_Import(self, node):
        for a in node.names:
            self._import((a.asname or a.name).split(".")[0])

    def visit_ImportFrom(self, node):
        for a in node.names:
            self._import(a.asname or a.name)

    def visit_FunctionDef(self, node):
        self.defined.add(node.name)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_ClassDef = visit_FunctionDef

    def visit_arg(self, node):
        self.defined.add(node.arg)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        if node.name:
            self.defined.add(node.name)
        self.generic_visit(node)

    def visit_Name(self, node):
        (self.used if isinstance(node.ctx, ast.Load) else self.defined).add(node.id)


def _cells(path):
    nb = json.loads(path.read_text())
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] == "code":
            magic, code = _python_part(cell)
            names = _Names()
            names.visit(ast.parse(code))
            yield i, magic, names


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: str(p.relative_to(EXAMPLES)))
def test_cells_import_what_they_use(path):
    cells = list(_cells(path))
    imported_somewhere = set().union(*(names.imported for _, _, names in cells))
    missing = {}
    for i, magic, names in cells:
        free = names.used - names.defined - ALWAYS_THERE - MAGIC_NAMES.get(magic, set())
        if free & imported_somewhere:
            missing[i] = sorted(free & imported_somewhere)
    assert not missing, f"cells using names imported only in other cells: {missing}"
