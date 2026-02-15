#!/usr/bin/env python3
"""Abbreviation Checker.

Checks for the most problematic abbreviations that hurt code readability.
Supports escape hatch: # noqa: ABBREV001
"""

import ast
import sys
from pathlib import Path


class AbbreviationChecker(ast.NodeVisitor):
    """Check for forbidden abbreviations in code."""

    FORBIDDEN = {
        "usr": "user",
        "pwd": "password",
        "passwd": "password",
        "auth": "authentication",
        "authn": "authentication",
        "authz": "authorization",
        "msg": "message",
        "req": "request",
        "res": "response",
        "resp": "response",
        "ctx": "context",
        "cfg": "config",
        "conf": "config",
        "db": "database",
        "conn": "connection",
        "mgr": "manager",
        "proc": "process",
        "val": "value",
        "num": "number",
        "addr": "address",
        "str": "string",
        "obj": "object",
        "impl": "implementation",
        "spec": "specification",
        "arg": "argument",
        "param": "parameter",
        "env": "environment",
        "temp": "temporary",
        "tmp": "temporary",
        "curr": "current",
        "prev": "previous",
        "cnt": "count",
        "idx": "index",
        "len": "length",
        "calc": "calculate",
        "util": "utility",
        "cmd": "command",
        "telem": "telemetry",
        "nav": "navigation",
        "pos": "position",
        "vel": "velocity",
        "alt": "altitude",
        "lat": "latitude",
        "lon": "longitude",
        "lng": "longitude",
    }

    def __init__(self):
        self.violations = []
        self.current_file = ""
        self.file_lines = []

    def set_file_context(self, filepath, content):
        self.current_file = filepath
        self.file_lines = content.split("\n")

    def has_noqa(self, lineno):
        if 0 <= lineno - 1 < len(self.file_lines):
            line = self.file_lines[lineno - 1]
            return "# noqa: ABBREV" in line or "# noqa" in line
        return False

    def check_name(self, name, lineno, context):
        if name in ("self", "cls", "args", "kwargs"):
            return
        if self.has_noqa(lineno):
            return
        if name.isupper() and (name.startswith("MAX_") or name.startswith("MIN_")):
            return
        if name in ("str", "len") and context == "function_call":
            return

        name_lower = name.lower()
        parts = name_lower.split("_")
        for part in parts:
            if part in self.FORBIDDEN:
                suggestion = self.FORBIDDEN[part]
                self.violations.append(
                    f"{self.current_file}:{lineno}: {context} '{name}' "
                    f"contains '{part}' - use '{suggestion}' instead"
                )
                break

    def visit_FunctionDef(self, node):
        if node.name.startswith("__") and node.name.endswith("__"):
            self.generic_visit(node)
            return
        self.check_name(node.name, node.lineno, "Function")
        for argument in node.args.args:
            self.check_name(argument.arg, node.lineno, "Parameter")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node):
        self.check_name(node.name, node.lineno, "Class")
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.check_name(target.id, node.lineno, "Variable")
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        if isinstance(node.target, ast.Name):
            self.check_name(node.target.id, node.lineno, "Variable")
        self.generic_visit(node)


def check_file(filepath):
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=str(filepath))
        checker = AbbreviationChecker()
        checker.set_file_context(str(filepath), content)
        checker.visit(tree)
        return checker.violations
    except SyntaxError as e:
        return [f"{filepath}:{e.lineno}: Syntax error: {e.msg}"]
    except OSError as e:
        return [f"{filepath}: Error reading file: {e}"]


def main():
    if len(sys.argv) > 1:
        all_violations = []
        for filepath in sys.argv[1:]:
            if filepath.endswith(".py"):
                violations = check_file(Path(filepath))
                all_violations.extend(violations)
    else:
        directories = [Path("src"), Path("infra"), Path("edge")]
        all_violations = []
        for directory in directories:
            if directory.exists():
                for filepath in directory.rglob("*.py"):
                    violations = check_file(filepath)
                    all_violations.extend(violations)

    if all_violations:
        print("Forbidden abbreviations found:\n")
        for violation in sorted(all_violations):
            print(f"  {violation}")
        print(f"\nTotal violations: {len(all_violations)}")
        print("\nTip: Use '# noqa: ABBREV001' to skip specific cases")
        return 1

    print("No forbidden abbreviations found!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
