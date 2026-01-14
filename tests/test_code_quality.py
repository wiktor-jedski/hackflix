"""Tests for code quality enforcement."""

import ast
from pathlib import Path

import pytest


class TestBareExceptDetection:
    """Tests verifying no bare except: blocks in production code."""

    def test_no_bare_except_blocks(self):
        """Verify no bare except: blocks in production code."""
        violations = []

        for py_file in Path("src").rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text())
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        lineno = node.lineno
                        violations.append(f"{py_file}:{lineno}")

        assert not violations, "Bare except: blocks found:\n" + "\n".join(violations)

    def test_no_bare_except_in_tests(self):
        """Verify no bare except: blocks in test code."""
        violations = []

        for py_file in Path("tests").rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text())
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        lineno = node.lineno
                        violations.append(f"{py_file}:{lineno}")

        assert not violations, "Bare except: blocks found in tests:\n" + "\n".join(
            violations
        )


class TestExceptionSpecificity:
    """Tests for proper exception handling specificity."""

    def test_exceptions_have_message_variables(self):
        """Verify exceptions use variable messages, not raw strings where appropriate."""
        violations = []

        for py_file in Path("src").rglob("*.py"):
            try:
                content = py_file.read_text()
                tree = ast.parse(content)
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Raise):
                    if isinstance(node.exc, ast.Call):
                        if hasattr(node.exc.func, "id"):
                            exc_name = node.exc.func.id
                            if exc_name.endswith("Error") or exc_name.endswith(
                                "Exception"
                            ):
                                if len(node.exc.args) == 0:
                                    violations.append(
                                        f"{py_file}:{node.lineno} {exc_name} raised without arguments"
                                    )

        assert not violations, "Exceptions raised without messages:\n" + "\n".join(
            violations[:10]
        )


class TestTypeHintsEnforcement:
    """Tests for type hints enforcement using ty type checker."""

    def test_type_hints_pass_ty_check(self):
        """Verify all production code passes ty type checking.

        This test runs the ty type checker on the src/ directory
        and ensures there are no type errors.
        """
        import shutil
        import subprocess

        uv_path = shutil.which("uv")
        if uv_path is None:
            pytest.skip("uv not found in PATH")

        result = subprocess.run(
            [uv_path, "run", "ty", "check", "src/"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert result.returncode == 0, (
            f"Type checking failed.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
