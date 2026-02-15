#!/usr/bin/env python3
"""Imports Checker.

Ensures all imports are at module level, not inside functions or classes.
"""

import ast
import sys
from pathlib import Path


class ImportChecker(ast.NodeVisitor):
    """AST visitor to check for function-scoped imports."""

    def __init__(self):
        self.violations = []
        self.scope_depth = 0
        self.current_file = ""
        self.in_function = False
        self.in_class = False

    def set_current_file(self, filepath):
        self.current_file = filepath

    def add_violation(self, node, import_name):
        scope_type = "function" if self.in_function else "class"
        self.violations.append(
            f"{self.current_file}:{node.lineno}: "
            f"Import '{import_name}' found inside {scope_type}. "
            f"All imports must be at module level."
        )

    def visit_FunctionDef(self, node):
        was_in_function = self.in_function
        self.in_function = True
        self.scope_depth += 1
        self.generic_visit(node)
        self.scope_depth -= 1
        self.in_function = was_in_function

    def visit_AsyncFunctionDef(self, node):
        was_in_function = self.in_function
        self.in_function = True
        self.scope_depth += 1
        self.generic_visit(node)
        self.scope_depth -= 1
        self.in_function = was_in_function

    def visit_ClassDef(self, node):
        was_in_class = self.in_class
        self.in_class = True
        self.scope_depth += 1
        self.generic_visit(node)
        self.scope_depth -= 1
        self.in_class = was_in_class

    def visit_Import(self, node):
        if self.scope_depth > 0:
            names = [alias.name for alias in node.names]
            import_name = ", ".join(names)
            self.add_violation(node, f"import {import_name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if self.scope_depth > 0:
            if node.names:
                if any(alias.name == "*" for alias in node.names):
                    import_name = f"from {node.module} import *"
                else:
                    names = [alias.name for alias in node.names]
                    import_name = f"from {node.module} import {', '.join(names)}"
            else:
                import_name = f"from {node.module} import"
            self.add_violation(node, import_name)
        self.generic_visit(node)


def check_file(filepath):
    try:
        with open(filepath, encoding="utf-8") as file:
            content = file.read()
        tree = ast.parse(content, filename=str(filepath))
        checker = ImportChecker()
        checker.set_current_file(str(filepath))
        checker.visit(tree)
        return checker.violations
    except SyntaxError as e:
        return [f"{filepath}:{e.lineno}: Syntax error: {e.msg}"]
    except OSError as e:
        return [f"{filepath}: Error reading file: {e}"]


def find_python_files(directory):
    return list(directory.rglob("*.py"))


def main():
    directories = [
        Path("src"),
        Path("infra"),
        Path("edge"),
        Path("tests"),
        Path("edge_tests"),
        Path("infra_tests"),
    ]

    all_violations = []
    for directory in directories:
        if directory.exists():
            python_files = find_python_files(directory)
            for filepath in python_files:
                violations = check_file(filepath)
                all_violations.extend(violations)

    if all_violations:
        print("Import violations found:")
        for violation in sorted(all_violations):
            print(f"  {violation}")
        print("")
        print("Fix: Move all imports to the top of the file.")
        return 1

    print("All imports are at module level")
    return 0


if __name__ == "__main__":
    sys.exit(main())
