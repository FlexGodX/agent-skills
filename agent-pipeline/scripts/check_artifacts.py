#!/usr/bin/env python3
"""Программная проверка артефактов agent-pipeline перед воротами.

Запуск:
    python3 check_artifacts.py <папка задачи> --gate {3,4,6,10,s}

Ворота: 3 — спецификация, 4 — архитектура, 6 — план и тесты, 10 — ревью
кода, s — объединённое ревью до кода при размере S.

Первая строка вывода — итог: «OK …» или «НЕ ПРОЙДЕНО …». Дальше по строке на
ошибку и на предупреждение. Код возврата: 0 — ошибок нет, 1 — есть ошибки,
2 — неверный вызов или файл нельзя прочитать.

Проверяется только механика: шапки, разделы, статусы, трассируемость
AC → TC → шаг плана, таблицы «Входы из ревью», «Прогон» и «Мутации».
Смысл требований и качество решения проверяет ревьюер.
Нужен только Python 3.8+, сторонних пакетов нет.
"""
import argparse
import re
import sys
from pathlib import Path

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
SEPARATOR_RE = re.compile(r"^:?-{2,}:?$")
TASK_ID_RE = re.compile(r"^[A-ZА-ЯЁ][A-ZА-ЯЁ0-9]*-\d+$")
MERMAID_RE = re.compile(r"^\s*(```+|~~~+)\s*mermaid\b", re.MULTILINE)
EMPTY_CELLS = {"", "-", "—", "–", "?", "нет"}
RANGE_SEP = r"\s*(?:\.{2,3}|…|–|—|-)\s*"

SPEC_SECTIONS = [
    "Контекст", "Размер", "Варианты и выбор", "Соседние случаи",
    "Требования", "Критерии приёмки", "Не входит в задачу",
    "Входы из ревью", "Открытые вопросы",
]
SPEC_SECTIONS_S = ["Решение", "Тесты", "План"]
DESIGN_SECTIONS = [
    "Затронутые модули", "Данные", "Интерфейсы", "Поведение при ошибках",
    "Безопасность", "Решения",
]


class Unreadable(Exception):
    """Файл есть, но прочитать его как UTF-8 нельзя."""


def norm(text):
    """Приводит заголовок или ячейку к виду для сравнения."""
    text = text.replace("`", "").replace("*", "").replace("«", "").replace("»", "")
    text = re.sub(r"^[\d.\s]+", "", text.strip())
    return text.casefold().replace("ё", "е").strip()


def find_ids(text, prefix):
    """Идентификаторы AC-NN или TC-NN в тексте, по порядку и без повторов.

    Раскрывает диапазоны «TC-01..TC-03». Ссылку на критерий другой задачи
    («PERF-2/AC-05») своим идентификатором не считает.
    """
    if not text:
        return []
    one = rf"(?<![/\w-]){prefix}-(\d+)\b"
    found = []

    def add(number, width):
        ident = f"{prefix}-{str(number).zfill(width)}"
        if ident not in found:
            found.append(ident)

    pos = 0
    range_re = re.compile(one + RANGE_SEP + rf"{prefix}-(\d+)\b")
    single_re = re.compile(one)
    while True:
        m_range = range_re.search(text, pos)
        m_single = single_re.search(text, pos)
        if not m_single:
            break
        if m_range and m_range.start() == m_single.start():
            first, last = int(m_range.group(1)), int(m_range.group(2))
            width = len(m_range.group(1))
            if first <= last <= first + 500:
                for number in range(first, last + 1):
                    add(number, width)
            else:
                add(first, width)
                add(last, len(m_range.group(2)))
            pos = m_range.end()
        else:
            add(int(m_single.group(1)), len(m_single.group(1)))
            pos = m_single.end()
    return found


def id_number(ident):
    return int(ident.split("-")[1])


def split_row(line):
    """Режет строку таблицы по «|», не трогая «\\|» и код в обратных кавычках."""
    cells, current, in_code, i = [], [], False, 0
    text = line.strip()
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text) and text[i + 1] == "|":
            current.append("|")
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
        i += 1
    cells.append("".join(current).strip())
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def err(self, where, text):
        self.errors.append(f"{where}: {text}")

    def warn(self, where, text):
        self.warnings.append(f"{where}: {text}")


class Doc:
    """Один markdown-файл задачи."""

    def __init__(self, path):
        self.path = path
        self.name = path.name
        self.exists = path.is_file()
        text = ""
        if self.exists:
            try:
                text = path.read_bytes().decode("utf-8-sig")
            except UnicodeDecodeError:
                raise Unreadable(f"{path.name}: файл не в кодировке UTF-8")
        self.text = text
        self.raw_lines = text.splitlines()
        # Те же строки, но содержимое блоков кода заменено пустыми строками:
        # примеры в ``` не должны читаться как заголовки, таблицы и AC/TC.
        self.lines = []
        fence = None
        for line in self.raw_lines:
            m = FENCE_RE.match(line)
            if m:
                marker = m.group(1)[0]
                if fence is None:
                    fence = marker
                elif fence == marker:
                    fence = None
                self.lines.append("")
            else:
                self.lines.append("" if fence else line)
        self._headings = []  # (номер строки, уровень, нормализованный заголовок)
        for i, line in enumerate(self.lines):
            m = HEADING_RE.match(line)
            if m:
                self._headings.append((i, len(m.group(1)), norm(m.group(2))))

    @property
    def clean_text(self):
        return "\n".join(self.lines)

    def section(self, title, raw=False):
        """Текст раздела до следующего заголовка того же или старшего уровня."""
        want = norm(title)
        source = self.raw_lines if raw else self.lines
        for idx, (line_no, level, name) in enumerate(self._headings):
            if name == want or name.startswith(want):
                end = len(source)
                for next_line, next_level, _ in self._headings[idx + 1:]:
                    if next_level <= level:
                        end = next_line
                        break
                return "\n".join(source[line_no + 1:end])
        return None

    def header_value(self, key):
        for line in self.raw_lines[:12]:
            m = re.match(rf"^\s*{key}\s*:\s*(.+?)\s*$", line)
            if m:
                return m.group(1)
        return None

    def status(self):
        value = self.header_value("Статус")
        if value is None:
            return None
        return "APPROVED" if value.upper().startswith("APPROVED") else "DRAFT"

    def tables(self):
        """Таблицы файла: список (заголовок, строки)."""
        result, block = [], []
        for line in self.lines + [""]:
            if line.strip().startswith("|"):
                block.append(split_row(line))
                continue
            if block:
                rows = [r for r in block
                        if not all(SEPARATOR_RE.match(c) or c == "" for c in r)]
                if rows:
                    result.append((rows[0], rows[1:]))
                block = []
        return result


def column(header, *needles, exact=False):
    """Номер колонки, заголовок которой совпадает с одним из образцов."""
    for i, cell_text in enumerate(header):
        cell_n = norm(cell_text)
        for needle in needles:
            if (cell_n == needle) if exact else (needle in cell_n):
                return i
    return None


def cell(row, index):
    return row[index] if index is not None and index < len(row) else ""


# --------------------------------------------------------------------------
# Разбор содержимого
# --------------------------------------------------------------------------

def check_header(doc, rep):
    rev = doc.header_value("Ревизия")
    if rev is None or not rev.isdigit():
        rep.err(doc.name, "в шапке нет строки «Ревизия: N»")
    if doc.header_value("Статус") is None:
        rep.err(doc.name, "в шапке нет строки «Статус: DRAFT | APPROVED (…)»")
    task = doc.header_value("Задача")
    if task is None:
        rep.err(doc.name, "в шапке нет строки «Задача: <ТЕГ>-<номер>»")
    elif not TASK_ID_RE.match(task):
        rep.err(doc.name, f"идентификатор задачи «{task}» не вида <ТЕГ>-<номер>")
    return task


def check_sections(doc, names, rep):
    for name in names:
        body = doc.section(name, raw=True)
        if body is None:
            rep.err(doc.name, f"нет раздела «{name}»")
        elif not body.strip():
            rep.err(doc.name, f"раздел «{name}» пуст")


def read_size(spec, rep):
    """Размер S, M или L; буква после «не» или «ни» размером не считается."""
    body = spec.section("Размер")
    if body is None:
        return None
    for m in re.finditer(r"(?<![A-Za-z])([SML])(?![A-Za-z])", body):
        before = body[max(0, m.start() - 3):m.start()].casefold()
        if before in ("не ", "ни "):
            continue
        return m.group(1)
    rep.err(spec.name, "в разделе «Размер» не найдено S, M или L")
    return None


def read_acs(spec, rep):
    body = spec.section("Критерии приёмки")
    if body is None:
        return []
    acs = sorted(find_ids(body, "AC"), key=id_number)
    if not acs:
        rep.err(spec.name, "в разделе «Критерии приёмки» нет ни одного AC-NN")
    return acs


def read_tests(docs):
    """TC → множество AC из таблиц, где первая колонка TC и есть колонка AC."""
    tests, found = {}, False
    for doc in docs:
        for header, rows in doc.tables():
            tc_col = column(header, "tc", exact=True)
            ac_col = column(header, "ac", exact=True)
            if tc_col != 0 or ac_col is None:
                continue
            found = True
            for row in rows:
                ids = find_ids(cell(row, tc_col), "TC")
                if ids:
                    tests.setdefault(ids[0], set()).update(find_ids(cell(row, ac_col), "AC"))
    return tests, found


def read_plan(docs):
    """Шаги плана: первая колонка «Шаг» и есть колонка AC, TC или «Зависит от»."""
    steps, found = [], False
    for doc in docs:
        for header, rows in doc.tables():
            if not header or not norm(header[0]).startswith("шаг"):
                continue
            ac_col = column(header, "ac", exact=True)
            tc_col = column(header, "tc")
            dep_col = column(header, "завис")
            if ac_col is None and tc_col is None and dep_col is None:
                continue  # таблица шагов воспроизведения, а не план
            found = True
            file_col = column(header, "файл")
            for row in rows:
                m = re.search(r"\d+", cell(row, 0))
                if not m:
                    continue
                steps.append({
                    "id": int(m.group()),
                    "acs": set(find_ids(cell(row, ac_col), "AC")),
                    "tcs": set(find_ids(cell(row, tc_col), "TC")),
                    "deps": {int(d) for d in re.findall(r"\d+", cell(row, dep_col))},
                    "has_dep_col": dep_col is not None,
                    "files": set(re.findall(r"`([^`]+)`", cell(row, file_col))),
                })
    return steps, found


def read_run(docs):
    """Строки таблицы «Прогон»: (TC или None, подпись, результат)."""
    rows_out, found = [], False
    for doc in docs:
        for header, rows in doc.tables():
            tc_col = column(header, "tc", exact=True)
            res_col = column(header, "результат", exact=True)
            if tc_col != 0 or res_col is None or column(header, "ac", exact=True) is not None:
                continue
            found = True
            for row in rows:
                ids = find_ids(cell(row, tc_col), "TC")
                label = " ".join(c for c in row[:2] if c)[:50]
                rows_out.append((ids[0] if ids else None, label, cell(row, res_col)))
    return rows_out, found


def read_mutations(docs):
    """AC → исход из таблицы «Мутации» (первая колонка AC, есть «Упавший»)."""
    result, found = {}, False
    for doc in docs:
        for header, rows in doc.tables():
            if not header or norm(header[0]) != "ac":
                continue
            out_col = column(header, "упавш")
            if out_col is None:
                continue
            found = True
            for row in rows:
                ids = find_ids(cell(row, 0), "AC")
                if ids:
                    result[ids[0]] = cell(row, out_col)
    return result, found


# --------------------------------------------------------------------------
# Проверки
# --------------------------------------------------------------------------

def check_trace(acs, docs, rep, where):
    tests, found_tests = read_tests(docs)
    if not found_tests:
        rep.err(where, "не найдена таблица тестов с колонками TC и AC")
        return tests
    known = set(acs)
    for ac in acs:
        if not any(ac in linked for linked in tests.values()):
            rep.err(where, f"у {ac} нет ни одного TC")
    for tc, linked in sorted(tests.items(), key=lambda kv: id_number(kv[0])):
        if not linked:
            rep.err(where, f"у {tc} не указан AC")
        for ac in sorted(linked - known, key=id_number):
            rep.err(where, f"{tc} ссылается на {ac}, которого нет в критериях приёмки")

    steps, found_plan = read_plan(docs)
    if not found_plan:
        rep.err(where, "не найдена таблица плана (первая колонка «Шаг»)")
        return tests
    ids = [s["id"] for s in steps]
    order = {step_id: pos for pos, step_id in enumerate(ids)}
    covered = set()
    if steps and not all(s["has_dep_col"] for s in steps):
        rep.err(where, "в таблице плана нет колонки «Зависит от»")
    for s in steps:
        name = f"шаг {s['id']}"
        covered |= s["tcs"]
        if not s["acs"]:
            rep.err(where, f"{name}: не указан AC")
        for ac in sorted(s["acs"] - known, key=id_number):
            rep.err(where, f"{name}: {ac} нет в критериях приёмки")
        for tc in sorted(s["tcs"] - set(tests), key=id_number):
            rep.err(where, f"{name}: {tc} нет в таблице тестов")
        for dep in sorted(s["deps"]):
            if dep not in order:
                rep.err(where, f"{name}: зависит от шага {dep}, которого нет")
            elif order[dep] >= order[s["id"]]:
                rep.err(where, f"{name}: зависит от шага {dep}, который идёт не раньше него")
    for tc in sorted(set(tests) - covered, key=id_number):
        rep.err(where, f"{tc} не проходит ни после одного шага плана")
    if len(ids) != len(set(ids)):
        rep.err(where, "номера шагов плана повторяются")

    # Шаги без связи через «Зависит от» могут пойти параллельно: общий файл опасен.
    reach = {s["id"]: set(s["deps"]) for s in steps}
    changed = True
    while changed:
        changed = False
        for deps in reach.values():
            extra = set()
            for d in deps:
                extra |= reach.get(d, set())
            if not extra <= deps:
                deps |= extra
                changed = True
    for i, a in enumerate(steps):
        for b in steps[i + 1:]:
            shared = a["files"] & b["files"]
            linked = a["id"] in reach.get(b["id"], set()) or b["id"] in reach.get(a["id"], set())
            if shared and not linked:
                rep.warn(where, f"шаги {a['id']} и {b['id']} правят {', '.join(sorted(shared))} "
                                f"и не зависят друг от друга: параллельно их запускать нельзя")
    return tests


def check_inputs(spec, tests, rep):
    for header, rows in spec.tables():
        if column(header, "вход") != 0 or column(header, "ожидаем") is None:
            continue
        for row in rows:
            first = cell(row, 0)
            if norm(first) in EMPTY_CELLS:
                continue
            verdict = " ".join(row[2:]) if len(row) > 2 else ""
            if norm(verdict) in EMPTY_CELLS:
                rep.err(spec.name, f"«Входы из ревью»: у входа «{first[:50]}» нет ни TC, ни причины")
            for tc in find_ids(verdict, "TC"):
                if tests and tc not in tests:
                    rep.err(spec.name, f"«Входы из ревью»: {tc} нет в таблице тестов")


def classify_result(value):
    """PASS, FAIL, SKIP, MIXED или None для значения из колонки «Результат»."""
    text = norm(value)
    has_pass = re.search(r"\bpass", text) is not None
    has_fail = re.search(r"\bfail", text) is not None
    if has_pass and has_fail:
        return "MIXED"
    if text.startswith("fail") or has_fail:
        return "FAIL"
    if text.startswith("pass"):
        return "PASS"
    if text.startswith("не запущен"):
        return "SKIP"
    return None


def check_run(tests, docs, rep, where):
    rows, found = read_run(docs)
    if not found:
        rep.err(where, "не найдена таблица «Прогон» (колонки TC и Результат)")
        return
    results, skipped = {}, []
    for tc, label, value in rows:
        if tc is not None:
            results[tc] = value
            continue
        kind = classify_result(value)
        if kind in ("FAIL", "MIXED"):
            rep.err(where, f"«Прогон»: строка «{label}» — FAIL")
    for tc in sorted(tests, key=id_number):
        if tc not in results:
            rep.err(where, f"«Прогон»: нет строки для {tc}")
            continue
        kind = classify_result(results[tc])
        if kind == "PASS":
            continue
        if kind == "FAIL":
            rep.err(where, f"«Прогон»: {tc} — FAIL")
        elif kind == "MIXED":
            rep.err(where, f"«Прогон»: у {tc} в результате и PASS, и FAIL — нужен один итог")
        elif kind == "SKIP":
            skipped.append(tc)
        else:
            rep.err(where, f"«Прогон»: у {tc} результат «{results[tc][:40]}» — "
                           f"не PASS, FAIL или НЕ ЗАПУЩЕН")
    if skipped:
        rep.warn(where, f"«Прогон»: НЕ ЗАПУЩЕН — {', '.join(skipped)}; "
                        f"нужно явное согласие пользователя")


def check_mutations(acs, tests, docs, rep, where):
    mutations, found = read_mutations(docs)
    if not found:
        rep.err(where, "не найдена таблица «Мутации» (колонки AC и «Упавший TC»)")
        return
    for ac in acs:
        if ac not in mutations:
            rep.err(where, f"«Мутации»: нет строки для {ac}")
            continue
        value = mutations[ac]
        value_n = norm(value)
        named = find_ids(value, "TC")
        if "ни один" in value_n:
            rep.err(where, f"«Мутации»: {ac} — НИ ОДИН тест не упал")
        elif named:
            for tc in named:
                if tc not in tests:
                    rep.err(where, f"«Мутации»: у {ac} назван {tc}, которого нет в таблице тестов")
        elif "не применимо" not in value_n:
            rep.err(where, f"«Мутации»: у {ac} исход «{value[:40]}» — "
                           f"не TC, НИ ОДИН или НЕ ПРИМЕНИМО")


def require_approved(doc, rep):
    if doc.exists and doc.status() != "APPROVED":
        rep.err(doc.name, "статус не APPROVED, а документ идёт на вход этим воротам")


def approved_by_human(doc):
    value = norm(doc.header_value("Статус") or "")
    if not value.startswith("approved") or "ждет человека" in value:
        return False
    return "человек" in value or "пользовател" in value


def check_design(design, spec_task, size, acs, rep):
    if not design.exists:
        rep.err("DESIGN.md", "файла нет")
        return
    if check_header(design, rep) not in (None, spec_task):
        rep.err("DESIGN.md", "идентификатор задачи не совпадает с SPEC.md")
    check_sections(design, DESIGN_SECTIONS, rep)
    if size in ("M", "L"):
        diagrams = design.section("Диаграммы", raw=True)
        if diagrams is None:
            rep.err("DESIGN.md", f"при размере {size} нужен раздел «Диаграммы»")
        elif not MERMAID_RE.search(diagrams):
            rep.err("DESIGN.md", "в разделе «Диаграммы» нет блока mermaid")
    mentioned = set(find_ids(design.text, "AC"))
    for ac in acs:
        if ac not in mentioned:
            rep.warn("DESIGN.md", f"{ac} нигде не упомянут")


def run_gate(folder, gate):
    rep = Report()
    spec = Doc(folder / "SPEC.md")
    design = Doc(folder / "DESIGN.md")
    qa = Doc(folder / "QA.md")
    plan = Doc(folder / "PLAN.md")

    if not spec.exists:
        rep.err("SPEC.md", "файла нет")
        return rep, {}

    task = check_header(spec, rep)
    check_sections(spec, SPEC_SECTIONS, rep)
    size = read_size(spec, rep)
    acs = read_acs(spec, rep)
    info = {"task": task or "?", "size": size or "?", "ac": len(acs)}

    if gate == "s" and size not in (None, "S"):
        rep.err("SPEC.md", f"ворота s — только для размера S, а в документе {size}")
        return rep, info
    if gate in ("4", "6") and size == "S":
        rep.err("SPEC.md", f"при размере S ворот {gate} нет: используй --gate s")
        return rep, info
    if gate == "3":
        return rep, info

    one_file = size == "S" or gate == "s"
    if one_file:
        check_sections(spec, SPEC_SECTIONS_S, rep)
        docs = [spec]
        where = "SPEC.md"
    else:
        require_approved(spec, rep)
        check_design(design, task, size, acs, rep)
        if gate == "4":
            return rep, info
        require_approved(design, rep)
        for doc in (qa, plan):
            if not doc.exists:
                rep.err(doc.name, "файла нет")
            elif check_header(doc, rep) not in (None, task):
                rep.err(doc.name, "идентификатор задачи не совпадает с SPEC.md")
        if not (qa.exists and plan.exists):
            return rep, info
        docs = [spec, qa, plan]
        where = "QA.md и PLAN.md"

    tests = check_trace(acs, docs, rep, where)
    check_inputs(spec, tests, rep)
    info["tc"] = len(tests)

    if gate == "10":
        check_run(tests, docs, rep, where)
        if size in ("M", "L"):
            check_mutations(acs, tests, docs, rep, where)
            for doc in (qa, plan):
                require_approved(doc, rep)
        if size == "L":
            for doc in (spec, design):
                if doc.exists and not approved_by_human(doc):
                    rep.err(doc.name, "при размере L нужен статус "
                                      "«APPROVED (ревьюер и человек, …)»")
    return rep, info


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Проверка артефактов agent-pipeline перед воротами")
    parser.add_argument("folder", help="папка задачи с SPEC.md")
    parser.add_argument("--gate", required=True, choices=["3", "4", "6", "10", "s"],
                        help="ворота: 3, 4, 6, 10 или s (ревью до кода при размере S)")
    args = parser.parse_args(argv)
    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"НЕ ПРОЙДЕНО: папки {folder} нет")
        return 2

    try:
        rep, info = run_gate(folder, args.gate)
    except Unreadable as exc:
        print(f"НЕ ПРОЙДЕНО: {exc}")
        return 2

    label = "ревью S до кода" if args.gate == "s" else f"ворота {args.gate}"
    facts = ", ".join(f"{k} {v}" for k, v in (
        ("задача", info.get("task")), ("размер", info.get("size")),
        ("AC", info.get("ac")), ("TC", info.get("tc"))) if v is not None)
    facts = f" ({facts})" if facts else ""
    if rep.errors:
        print(f"НЕ ПРОЙДЕНО {label}: ошибок {len(rep.errors)}{facts}")
        for line in rep.errors:
            print(f"- {line}")
    else:
        print(f"OK {label}:{facts}")
    for line in rep.warnings:
        print(f"ВНИМАНИЕ {line}")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
