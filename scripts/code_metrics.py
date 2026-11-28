"""Метрики качества кода для ЛР-8 (метрики качества и технический долг).

Локальная альтернатива SonarCloud (методичка, раздел 4.3): скрипт на
чистом stdlib считает по каталогу исходников:

* LOC — физические строки кода по каждому файлу;
* цикломатическую сложность каждой функции (правила упрощённого radon:
  +1 за if/for/while/except/тернарник/assert, +1 за каждый ``and``/``or``
  сверх первого, +1 за ``if``-условие comprehensions и ветки match);
* дублирование кода — повторяющиеся окна из 8 непустых строк;
* структуру: число функций и API-маршрутов.

Запуск из корня репозитория::

    python scripts/code_metrics.py src

Вывод — Markdown-отчёт (можно перенаправить в файл).
"""

import ast
import hashlib
import json
import sys
from pathlib import Path

# --- цикломатическая сложность -------------------------------------------

_BRANCH_NODES = (
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp,
    ast.ExceptHandler, ast.Assert,
)
_MATCH_CASE = getattr(ast, "match_case", None)


def cyclomatic_complexity(func) -> int:
    """Цикломатическая сложность функции/метода по её AST."""
    cc = 1
    for node in ast.walk(func):
        if isinstance(node, _BRANCH_NODES):
            cc += 1
        elif isinstance(node, ast.BoolOp):
            cc += len(node.values) - 1
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            cc += sum(1 for c in node.generators if c.ifs)
        elif _MATCH_CASE and isinstance(node, _MATCH_CASE):
            cc += 1
    return cc


def iter_functions(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


# --- дублирование ---------------------------------------------------------

DUP_WINDOW = 8  # размер окна в непустых строках (методичка: повтор > 10 строк)


def normalized_lines(path: Path):
    """Непустые строки файла без docstring-заголовков, обрезанные до 80 симв."""
    lines = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line[:80])
    return lines


def duplicate_blocks(files):
    """Находит повторяющиеся окна строк между всеми файлами проекта."""
    index = {}  # hash -> [(файл, номер_строки)]
    for path in files:
        lines = normalized_lines(path)
        for i in range(len(lines) - DUP_WINDOW + 1):
            h = hashlib.md5("\n".join(lines[i:i + DUP_WINDOW]).encode()).hexdigest()
            index.setdefault(h, []).append((path.name, i + 1))

    dup_windows = {h: locs for h, locs in index.items() if len(locs) > 1}
    # грубая оценка объёма дублей: каждое повторение окна даёт 8 дублирующихся строк
    dup_lines = sum((len(locs) - 1) * DUP_WINDOW for locs in dup_windows.values())
    blocks = sorted(
        ((locs[0][0], locs[0][1], len(locs)) for locs in dup_windows.values()),
        key=lambda b: -b[2],
    )
    return blocks, dup_lines


# --- основной отчёт -------------------------------------------------------

def analyze(root: Path):
    files = sorted(root.rglob("*.py"))
    if not files:
        raise SystemExit(f"В каталоге {root} нет .py файлов")

    report = {"files": {}, "functions": [], "duplicates": [], "totals": {}}
    total_loc = total_dup = 0

    for path in files:
        src = path.read_text(encoding="utf-8", errors="replace")
        loc = sum(1 for raw in src.splitlines() if raw.strip())
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue

        funcs = list(iter_functions(tree))
        func_rows = []
        for f in funcs:
            cc = cyclomatic_complexity(f)
            if cc >= 8:  # порог «требует внимания» (методичка, табл. 2)
                func_rows.append((f"{path.name}:{f.lineno}", f.name, cc))

        routes = sum(
            1 for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(
                isinstance(d, ast.Call)
                and isinstance(d.func, ast.Attribute)
                and d.func.attr in ("get", "post", "put", "delete", "patch")
                for d in node.decorator_list
            )
        )

        report["files"][path.name] = {
            "loc": loc,
            "functions": len(funcs),
            "routes": routes,
            "max_cc": max((cyclomatic_complexity(f) for f in funcs), default=0),
        }
        report["functions"].extend(func_rows)
        total_loc += loc

    blocks, dup_lines = duplicate_blocks(files)
    report["duplicates"] = [
        {"file": f, "line": ln, "copies": n, "window": DUP_WINDOW} for f, ln, n in blocks
    ]
    total_dup = dup_lines
    report["totals"] = {
        "loc": total_loc,
        "duplicate_lines": total_dup,
        "duplicate_ratio_pct": round(100 * total_dup / total_loc, 1) if total_loc else 0,
        "functions_cc_ge_8": len(report["functions"]),
    }
    return report


def to_markdown(report) -> str:
    t = report["totals"]
    lines = [
        "# Профиль качества кода (скрипт scripts/code_metrics.py)",
        "",
        "| Файл | LOC | Функций | Маршрутов API | Max CC |",
        "|---|---|---|---|---|",
    ]
    for name, f in report["files"].items():
        lines.append(
            f"| {name} | {f['loc']} | {f['functions']} | {f['routes']} | {f['max_cc']} |")
    lines += [
        "",
        f"**Итого:** {t['loc']} строк кода; дублирование ≈ {t['duplicate_lines']} строк "
        f"({t['duplicate_ratio_pct']} % от объёма); функций с CC ≥ 8: {t['functions_cc_ge_8']}.",
        "",
        "## Топ функций по цикломатической сложности (CC ≥ 8)",
        "",
        "| Файл:строка | Функция | CC |",
        "|---|---|---|",
    ]
    for file_line, fname, cc in sorted(report["functions"], key=lambda x: -x[2]):
        lines.append(f"| {file_line} | `{fname}` | {cc} |")
    lines += [
        "",
        "## Дублирующиеся блоки (окно " + str(DUP_WINDOW) + " строк, ≥ 2 копий)",
        "",
        "| Файл | Строка первого вхождения | Копий |",
        "|---|---|---|",
    ]
    for d in report["duplicates"][:20]:
        lines.append(f"| {d['file']} | {d['line']} | {d['copies']} |")
    if not report["duplicates"]:
        lines.append("_Дублирующихся блоков не обнаружено._")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    # Windows-консоль часто работает в cp1251 — отчёт с юникодными символами
    # («≈», кириллица) печатаем в UTF-8.
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("src")
    result = analyze(target)
    print(to_markdown(result))
    if "--json" in sys.argv:
        out = Path("docs/lab8/metrics.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON: {out}")
