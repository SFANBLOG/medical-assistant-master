#!/usr/bin/env python3
"""Deeper dead-code scan: find functions/methods that are defined (and possibly
imported) but never actually invoked anywhere in the backend package.

Excludes false positives:
- Flask/blueprint route handlers (decorated by *.route / *.get / *.post ...)
- Other framework-registered callbacks (jwt, socketio.on, errorhandler,
  before/after_request, celery.task, click/custom decorators)
- Main entrypoints guarded by __name__ == '__main__'
- Functions referenced as a value (callback, dict value, assignment RHS)
  or called by name / by method-attribute somewhere.
"""
import ast
import os
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..", "backend")
ROOT = os.path.abspath(ROOT)

# Decorator names that register a function with a framework (so it is "live"
# even if never referenced by name elsewhere).
REGISTER_DECORATORS = {
    "route", "get", "post", "put", "delete", "patch", "head", "options",
    "jwt_required", "jwt_optional", "fresh_jwt_required",
    "cross_origin", "login_required", "roles_required", "role_required",
    "permission_required", "cache", "celery", "task", "shared_task",
    "socketio", "on", "event", "cli", "command", "click", "app", "bp",
    "errorhandler", "before_request", "after_request", "teardown_request",
    "before_app_request", "after_app_request", "context_processor",
    "app_errorhandler", "register", "tool", "action", "mcp",
    "deprecated", "wraps", "staticmethod", "classmethod", "property",
    "lru_cache", "singleton", "inject", "transaction", "db", "atomic",
}

FRAMEWORK_CALL_PATTERNS = (
    "route", "get", "post", "put", "delete", "patch", "socketio", "on",
    "errorhandler", "before_request", "after_request", "cli", "command",
)

py_files = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    if ".venv" in dirpath or "__pycache__" in dirpath:
        continue
    for fn in filenames:
        if fn.endswith(".py"):
            py_files.append(os.path.join(dirpath, fn))
py_files.sort()

# Collect per-file ASTs
trees = {}
parse_errors = []
for path in py_files:
    try:
        with open(path, "r", encoding="utf-8") as f:
            trees[path] = ast.parse(f.read(), filename=path)
    except SyntaxError as e:
        parse_errors.append((path, str(e)))

# Globally collect "call" references:
#  - Name(id) used in Call position -> calls a top-level/imported function by name
#  - Attribute(attr) used in Call position -> calls a method by attr name
call_by_name = defaultdict(set)      # name -> set(files)
call_by_attr = defaultdict(set)      # attr -> set(files)

# All Name(Load) references and Attribute(Load) references (for value-usage
# detection, e.g. callback / dict value / assignment RHS).
name_loads = defaultdict(set)
attr_loads = defaultdict(set)

# Decorators per function are inspected separately via the FunctionDef nodes.

for path, tree in trees.items():
    rel = os.path.relpath(path, ROOT)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                call_by_name[f.id].add(rel)
            elif isinstance(f, ast.Attribute):
                call_by_attr[f.attr].add(rel)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            name_loads[node.id].add(rel)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            attr_loads[node.attr].add(rel)
        # Import targets / from-imports reference a name too.
        elif isinstance(node, ast.Import):
            for alias in node.names:
                tgt = alias.asname or alias.name.split(".")[0]
                name_loads[tgt].add(rel)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                tgt = alias.asname or alias.name
                name_loads[tgt].add(rel)


def decorator_is_registration(dec):
    """Heuristic: returns True if the decorator registers the function with a
    framework (so it is considered live regardless of name references)."""
    try:
        src = ast.unparse(dec)
    except Exception:
        src = ""
    # direct name match
    if isinstance(dec, ast.Name) and dec.id in REGISTER_DECORATORS:
        return True
    if isinstance(dec, ast.Attribute):
        if dec.attr in REGISTER_DECORATORS:
            return True
        if dec.attr in FRAMEWORK_CALL_PATTERNS:
            return True
    # things like app.route(...), bp.get(...), socketio.on(...)
    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
        if dec.func.attr in FRAMEWORK_CALL_PATTERNS:
            return True
    if "route" in src or "socketio" in src or "jwt" in src or src.endswith(".on("):
        return True
    return False


# Build the set of functions to examine.
candidates = []  # list of dicts
for path, tree in trees.items():
    rel = os.path.relpath(path, ROOT)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            lineno = node.lineno
            # Determine enclosing class
            cls = None
            for parent in ast.walk(tree):
                pass  # not used; we compute class via a separate pass below
            # skip dunders / magic except __init__ (init can be dead if class unused, skip for now)
            is_dunder = name.startswith("__") and name.endswith("__")
            # decorator info
            decs = node.decorator_list
            reg_dec = any(decorator_is_registration(d) for d in decs)
            candidates.append({
                "file": rel, "name": name, "line": lineno,
                "is_method": False,  # set later
                "class": None,
                "decos": [ast.unparse(d) if hasattr(ast, "unparse") else "" for d in decs],
                "reg_dec": reg_dec,
                "is_dunder": is_dunder,
                "node": node,
            })

# Second pass: attach class context to methods
for path, tree in trees.items():
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for c in candidates:
                        if c["node"] is sub:
                            c["is_method"] = True
                            c["class"] = node.name

# Now decide liveness. A function is considered "live" if it is referenced in
# ANY way across the package: called by name, called as a method attribute,
# referenced as a value (callback/dict-value/decorator/alias), or registered by
# a framework decorator. Only functions with ZERO references of any kind are
# truly dead.
for c in candidates:
    name = c["name"]
    called = False
    reasons = []

    if name in call_by_name:
        called = True
        reasons.append("called by name in: " + ", ".join(sorted(call_by_name[name])))
    if name in call_by_attr:
        called = True
        reasons.append("called as attr/method in: " + ", ".join(sorted(call_by_attr[name])))
    if name in name_loads:
        reasons.append("referenced (value/alias/decorator) in: " + ", ".join(sorted(name_loads[name])))
    if c["reg_dec"]:
        called = True
        reasons.append("framework-registered via: " + "; ".join(c["decos"]))
    if name == "__main__":
        called = True

    c["called"] = called
    c["reasons"] = reasons
    c["ref_any"] = bool(reasons)

dead_exact = [c for c in candidates if not c["ref_any"]]
# value-only = referenced somewhere but never directly called (review, likely live)
dead_value_only = [c for c in candidates if c["ref_any"] and not c["called"]]

print("=" * 90)
print("PY FILES ANALYZED:", len(py_files))
if parse_errors:
    print("PARSE ERRORS:", parse_errors)
print("TOTAL FUNCTIONS/METHODS:", len(candidates))
print("=" * 90)

print("\n### A. TRUE DEAD-CODE CANDIDATES (zero references anywhere in package) ###")
shown = 0
for c in sorted(dead_exact, key=lambda x: (x["file"], x["line"])):
    if c["is_dunder"]:
        continue
    qual = (c["class"] + "." if c["class"] else "") + c["name"]
    kind = "method" if c["is_method"] else "func"
    print(f"  [{c['file']}:{c['line']}] {qual}  ({kind})")
    shown += 1
if shown == 0:
    print("  (none)")

print("\n### B. REFERENCED-BUT-NEVER-CALLED (review; likely live via dispatch) ###")
for c in sorted(dead_value_only, key=lambda x: (x["file"], x["line"])):
    if c["is_dunder"]:
        continue
    qual = (c["class"] + "." if c["class"] else "") + c["name"]
    kind = "method" if c["is_method"] else "func"
    print(f"  [{c['file']}:{c['line']}] {qual}  ({kind})  -> {c['reasons'][0][:80]}")

print("\n### C. DEAD DUNDERS (possible unused class magic) ###")
for c in sorted(dead_exact, key=lambda x: (x["file"], x["line"])):
    if c["is_dunder"] and c["name"] != "__init__":
        qual = (c["class"] + "." if c["class"] else "") + c["name"]
        print(f"  [{c['file']}:{c['line']}] {qual}")

