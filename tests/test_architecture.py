"""Tests for architectural compliance."""

import ast
from pathlib import Path


def _is_type_checking_block(node: ast.AST) -> bool:
    """Check if an AST node is a TYPE_CHECKING conditional block."""
    if isinstance(node, ast.If):
        test = node.test
        if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
            return True
        if isinstance(test, ast.BoolOp):
            return any(
                isinstance(e, ast.Name) and e.id == "TYPE_CHECKING" for e in test.values
            )
    return False


class TestArchitectureCompliance:
    """Tests verifying architectural boundaries."""

    def test_ui_components_do_not_import_services(self):
        """Verify UI components don't import from src.services."""
        ui_dir = Path("src/ui")
        forbidden_imports = ["src.services"]

        violations = []
        for py_file in ui_dir.rglob("*.py"):
            with open(py_file) as f:
                try:
                    tree = ast.parse(f.read())
                except SyntaxError:
                    continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if any(
                            forbidden in alias.name for forbidden in forbidden_imports
                        ):
                            violations.append(f"{py_file}: imports {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and any(
                        forbidden in node.module for forbidden in forbidden_imports
                    ):
                        violations.append(f"{py_file}: imports from {node.module}")

        assert not violations, "UI components have forbidden imports:\n" + "\n".join(
            violations
        )

    def test_ui_components_do_not_import_database(self):
        """Verify UI components don't import from src.database."""
        ui_dir = Path("src/ui")
        forbidden_imports = ["src.database"]

        violations = []
        for py_file in ui_dir.rglob("*.py"):
            with open(py_file) as f:
                try:
                    tree = ast.parse(f.read())
                except SyntaxError:
                    continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if any(
                            forbidden in alias.name for forbidden in forbidden_imports
                        ):
                            violations.append(f"{py_file}: imports {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and any(
                        forbidden in node.module for forbidden in forbidden_imports
                    ):
                        violations.append(f"{py_file}: imports from {node.module}")

        assert not violations, "UI components have forbidden imports:\n" + "\n".join(
            violations
        )

    def test_ui_components_do_not_import_controllers(self):
        """Verify UI components don't import from src.controllers (except TYPE_CHECKING)."""
        ui_dir = Path("src/ui")
        forbidden_imports = ["src.controllers"]

        violations = []
        for py_file in ui_dir.rglob("*.py"):
            with open(py_file) as f:
                try:
                    content = f.read()
                except SyntaxError:
                    continue

            tree = ast.parse(content)
            in_type_checking = False
            for node in ast.walk(tree):
                if _is_type_checking_block(node):
                    in_type_checking = True

                if isinstance(node, ast.ImportFrom):
                    if node.module and any(
                        forbidden in node.module for forbidden in forbidden_imports
                    ):
                        if not in_type_checking:
                            violations.append(f"{py_file}: imports from {node.module}")

        assert not violations, "UI components have forbidden imports:\n" + "\n".join(
            violations
        )

    def test_no_cross_layer_imports(self):
        """Verify no imports across architectural layers."""
        ui_dir = Path("src/ui")
        controller_dir = Path("src/controllers")

        violations = []

        for py_file in ui_dir.rglob("*.py"):
            with open(py_file) as f:
                try:
                    content = f.read()
                except SyntaxError:
                    continue

            tree = ast.parse(content)

            class ImportChecker(ast.NodeVisitor):
                def __init__(self) -> None:
                    self.in_type_checking = False
                    self.violations: list[str] = []

                def visit_If(self, node: ast.If) -> None:
                    if _is_type_checking_block(node):
                        old_state = self.in_type_checking
                        self.in_type_checking = True
                        self.generic_visit(node)
                        self.in_type_checking = old_state
                    else:
                        self.generic_visit(node)

                def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
                    if node.module and any(
                        layer in node.module
                        for layer in ["src.controllers", "src.services", "src.database"]
                    ):
                        if not self.in_type_checking:
                            self.violations.append(
                                f"{py_file}: imports from {node.module}"
                            )
                    self.generic_visit(node)

            checker = ImportChecker()
            checker.visit(tree)
            violations.extend(checker.violations)

        for py_file in controller_dir.glob("*.py"):
            content = py_file.read_text()
            if "from src.services" in content or "from src.database" in content:
                if "TYPE_CHECKING" not in content:
                    violations.append(
                        f"{py_file}: controller imports from service/database layer"
                    )

        assert not violations, "Cross-layer imports found:\n" + "\n".join(violations)


BLOCKING_PATTERNS = [
    "open(",
    ".read(",
    ".write(",
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.delete",
    "urllib",
    "httpx.",
    "http.client",
]


class TestUIThreadSafety:
    """Tests verifying UI components don't perform blocking I/O operations."""

    def test_ui_methods_do_not_call_blocking_io(self):
        """Verify UI components don't perform blocking I/O operations."""
        ui_dir = Path("src/ui")

        violations: list[tuple[str, str, int]] = []

        for py_file in ui_dir.rglob("*.py"):
            content = py_file.read_text()
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            lines = content.split("\n")

            for idx, line in enumerate(lines, start=1):
                stripped = line.strip()

                if stripped.startswith("#"):
                    continue

                in_type_checking = "TYPE_CHECKING" in line
                if in_type_checking:
                    continue

                for pattern in BLOCKING_PATTERNS:
                    if pattern in line:
                        if not _is_string_in_code(line, pattern):
                            violations.append((str(py_file), pattern, idx))

        report_lines = [
            f"{path}:{line} contains blocking I/O pattern '{pattern}'"
            for path, pattern, line in violations
        ]

        assert not violations, (
            "UI components have blocking I/O operations:\n" + "\n".join(report_lines)
        )


def _is_string_in_code(line: str, pattern: str) -> bool:
    """Check if pattern is inside a string literal rather than actual code."""
    import re

    string_pattern = r'(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"]*"|\'[^\']*\')'

    for match in re.finditer(string_pattern, line):
        if pattern in match.group():
            return True

    return False
