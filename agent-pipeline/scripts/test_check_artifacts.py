#!/usr/bin/env python3
"""Тесты check_artifacts.py. Запуск: python3 test_check_artifacts.py"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import check_artifacts  # noqa: E402

HEAD = "Задача: PERF-3\nРевизия: 1\nСтатус: {status}\n\n"

SPEC = HEAD + """# Спецификация

## Контекст
Просьба пользователя: ускорить загрузку.

## Размер
{size} — меняется несколько файлов.

## Варианты и выбор
Выбран вариант 1.

## Соседние случаи
| Случай | Входит | Причина |
|--------|--------|---------|
| мобильный веб | да | AC-02 |

## Требования
Страница открывается быстрее.

## Критерии приёмки
- AC-01: первый кадр быстрее двух секунд.
- AC-02: на мобильном то же.

## Не входит в задачу
Офлайн-режим.

## Входы из ревью
| Вход | Ожидаемый результат | TC или причина |
|------|---------------------|----------------|
| пустой кэш | страница открывается | TC-03 |

## Открытые вопросы
нет
"""

DESIGN = HEAD + """# Архитектура

## Затронутые модули
Загрузчик.

## Данные
не затрагивается — схема не меняется.

## Интерфейсы
не затрагивается — API прежний.

## Поведение при ошибках
Повтор запроса.

## Безопасность
не затрагивается — доступа не касается.

## Решения
Хеши в именах файлов — AC-01, AC-02.

## Диаграммы
```mermaid
sequenceDiagram
  Браузер->>Сервер: index.html
```
"""

QA = HEAD + """# Тесты

| TC | AC | Тип | Команда или шаги | Ожидаемый результат |
|----|----|-----|------------------|---------------------|
| TC-01 | AC-01 | unit | `run a` | быстрее двух секунд |
| TC-02 | AC-02 | unit | `run b` | быстрее двух секунд |
| TC-03 | AC-01 | unit | `run c` | открывается с пустым кэшем |

## Прогон
| TC | Команда | Результат | Дата |
|----|---------|-----------|------|
| TC-01 | `run a` | PASS | 2026-11-24 |
| TC-02 | `run b` | PASS | 2026-11-24 |
| TC-03 | `run c` | PASS | 2026-11-24 |
| — | тесты вызывающего кода | PASS | 2026-11-24 |

### Мутации
| AC | Что сломано | Упавший TC |
|----|-------------|------------|
| AC-01 | `a.dart:42` — `>` заменён на `<` | TC-01 |
| AC-02 | `b.dart:7` — убрана ветка | TC-02 |
"""

PLAN = HEAD + """# План

| Шаг | Что меняется | Файлы | AC | TC, которые проходят после шага | Зависит от |
|-----|--------------|-------|----|---------------------------------|------------|
| 1 | хеши | `a.dart` | AC-01 | TC-01, TC-03 | — |
| 2 | мобильный | `b.dart` | AC-02 | TC-02 | 1 |
"""

SPEC_S_TAIL = """
## Решение
Одна строка.

## Тесты
| TC | AC | Тип | Команда или шаги | Ожидаемый результат |
|----|----|-----|------------------|---------------------|
| TC-01 | AC-01 | unit | `run a` | ок |
| TC-02 | AC-02 | unit | `run b` | ок |
| TC-03 | AC-01 | unit | `run c` | ок |

## План
| Шаг | Что меняется | Файлы | AC | TC, которые проходят после шага | Зависит от |
|-----|--------------|-------|----|---------------------------------|------------|
| 1 | правка | `a.dart` | AC-01, AC-02 | TC-01, TC-02, TC-03 | — |

## Ход работ
- [x] Шаг 1

## Прогон
| TC | Команда | Результат | Дата |
|----|---------|-----------|------|
| TC-01 | `run a` | PASS | 2026-11-24 |
| TC-02 | `run b` | PASS | 2026-11-24 |
| TC-03 | `run c` | PASS | 2026-11-24 |
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.files = {
            "SPEC.md": SPEC.format(status="APPROVED (ревьюер, ревизия 1)", size="M"),
            "DESIGN.md": DESIGN.format(status="APPROVED (ревьюер, ревизия 1)"),
            "QA.md": QA.format(status="APPROVED (ревьюер, ревизия 1)"),
            "PLAN.md": PLAN.format(status="APPROVED (ревьюер, ревизия 1)"),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def run_gate(self, gate):
        for name, text in self.files.items():
            (self.dir / name).write_text(text, encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            code = check_artifacts.main([str(self.dir), "--gate", gate])
        return code, out.getvalue()

    def replace(self, name, old, new):
        self.assertIn(old, self.files[name])
        self.files[name] = self.files[name].replace(old, new)

    def assert_fails(self, gate, fragment):
        code, out = self.run_gate(gate)
        self.assertEqual(code, 1, out)
        self.assertIn(fragment, out)

    def assert_ok(self, gate):
        code, out = self.run_gate(gate)
        self.assertEqual(code, 0, f"ворота {gate}:\n{out}")
        self.assertTrue(out.startswith("OK"), out)
        return out

    def use_s(self):
        self.files = {"SPEC.md": SPEC.format(status="DRAFT", size="S") + SPEC_S_TAIL}

    def edit_all(self, old, new):
        for name in self.files:
            self.files[name] = self.files[name].replace(old, new)


class Case(Base):
    def test_good_m_passes_every_gate(self):
        for gate in ("3", "4", "6", "10"):
            code, out = self.run_gate(gate)
            self.assertEqual(code, 0, f"ворота {gate}:\n{out}")
            self.assertTrue(out.startswith("OK"), out)

    def test_missing_task_id(self):
        self.replace("SPEC.md", "Задача: PERF-3\n", "")
        self.assert_fails("3", "Задача")

    def test_missing_section(self):
        self.replace("SPEC.md", "## Соседние случаи", "## Прочее")
        self.assert_fails("3", "нет раздела «Соседние случаи»")

    def test_ac_without_tc(self):
        self.replace("QA.md", "| TC-02 | AC-02 | unit | `run b` | быстрее двух секунд |\n", "")
        self.replace("PLAN.md", "TC-02", "TC-01")
        self.assert_fails("6", "у AC-02 нет ни одного TC")

    def test_tc_without_plan_step(self):
        self.replace("PLAN.md", "TC-01, TC-03", "TC-01")
        self.assert_fails("6", "TC-03 не проходит ни после одного шага")

    def test_step_depends_on_later_step(self):
        self.replace("PLAN.md", "| TC-01, TC-03 | — |", "| TC-01, TC-03 | 2 |")
        self.assert_fails("6", "зависит от шага 2")

    def test_input_without_tc_or_reason(self):
        self.replace("SPEC.md", "| страница открывается | TC-03 |", "| страница открывается | — |")
        self.assert_fails("6", "нет ни TC, ни причины")

    def test_unapproved_input_document(self):
        self.replace("DESIGN.md", "Статус: APPROVED (ревьюер, ревизия 1)", "Статус: DRAFT")
        self.assert_fails("6", "DESIGN.md: статус не APPROVED")

    def test_design_without_diagrams(self):
        self.replace("DESIGN.md", "## Диаграммы", "## Картинки")
        self.assert_fails("4", "нужен раздел «Диаграммы»")

    def test_run_with_fail(self):
        self.replace("QA.md", "| TC-02 | `run b` | PASS |", "| TC-02 | `run b` | FAIL |")
        self.assert_fails("10", "TC-02 — FAIL")

    def test_run_missing_row_catches_partial_run(self):
        self.replace("QA.md", "| TC-03 | `run c` | PASS | 2026-11-24 |\n", "")
        self.assert_fails("10", "нет строки для TC-03")

    def test_not_run_is_warning_only(self):
        self.replace("QA.md", "| TC-03 | `run c` | PASS |", "| TC-03 | `run c` | НЕ ЗАПУЩЕН: нет БД |")
        code, out = self.run_gate("10")
        self.assertEqual(code, 0, out)
        self.assertIn("ВНИМАНИЕ", out)
        self.assertIn("TC-03", out)

    def test_mutation_none_fails(self):
        self.replace("QA.md", "— убрана ветка | TC-02 |", "— убрана ветка | НИ ОДИН |")
        self.assert_fails("10", "AC-02 — НИ ОДИН")

    def test_mutation_not_applicable_passes(self):
        self.replace("QA.md", "| `b.dart:7` — убрана ветка | TC-02 |", "| — | НЕ ПРИМЕНИМО: только ручной TC |")
        code, out = self.run_gate("10")
        self.assertEqual(code, 0, out)

    def test_size_l_needs_human_approval(self):
        self.replace("SPEC.md", "M — меняется", "L — меняется схема, а также")
        self.assert_fails("10", "ревьюер и человек")

    def test_parallel_steps_sharing_file_warn(self):
        self.replace("PLAN.md", "| 2 | мобильный | `b.dart` | AC-02 | TC-02 | 1 |",
                     "| 2 | мобильный | `a.dart` | AC-02 | TC-02 | — |")
        code, out = self.run_gate("6")
        self.assertEqual(code, 0, out)
        self.assertIn("шаги 1 и 2 правят a.dart", out)

    def test_size_s_single_document(self):
        self.files = {"SPEC.md": SPEC.format(status="DRAFT", size="S") + SPEC_S_TAIL}
        for gate in ("s", "10"):
            code, out = self.run_gate(gate)
            self.assertEqual(code, 0, f"ворота {gate}:\n{out}")

    def test_size_s_rejects_gate_6(self):
        self.files = {"SPEC.md": SPEC.format(status="DRAFT", size="S") + SPEC_S_TAIL}
        self.assert_fails("6", "используй --gate s")

    def test_missing_folder(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = check_artifacts.main([str(self.dir / "нет"), "--gate", "3"])
        self.assertEqual(code, 2)


class SizeS(Base):
    """Размер S: всё в одном SPEC.md."""

    def setUp(self):
        super().setUp()
        self.use_s()

    def test_missing_tests_section(self):
        self.replace("SPEC.md", "## Тесты", "## Проверки")
        self.assert_fails("s", "нет раздела «Тесты»")

    def test_missing_solution_and_plan_sections(self):
        self.replace("SPEC.md", "## Решение", "## Идея")
        self.replace("SPEC.md", "## План", "## Порядок")
        code, out = self.run_gate("s")
        self.assertEqual(code, 1, out)
        self.assertIn("нет раздела «Решение»", out)
        self.assertIn("нет раздела «План»", out)

    def test_ac_without_tc(self):
        self.replace("SPEC.md", "| TC-02 | AC-02 | unit | `run b` | ок |\n", "")
        self.replace("SPEC.md", "TC-01, TC-02, TC-03 | —", "TC-01, TC-03 | —")
        self.assert_fails("s", "у AC-02 нет ни одного TC")

    def test_run_fail(self):
        self.replace("SPEC.md", "| TC-02 | `run b` | PASS |", "| TC-02 | `run b` | FAIL |")
        self.assert_fails("10", "TC-02 — FAIL")

    def test_run_missing_table(self):
        self.replace("SPEC.md", "## Прогон", "## Итоги")
        self.replace("SPEC.md", "| TC | Команда | Результат | Дата |", "| TC | Команда | Итог | Дата |")
        self.assert_fails("10", "не найдена таблица «Прогон»")

    def test_run_row_missing_for_tc(self):
        self.replace("SPEC.md", "| TC-03 | `run c` | PASS | 2026-11-24 |\n", "")
        self.assert_fails("10", "нет строки для TC-03")

    def test_draft_status_is_fine_at_gate_10(self):
        self.assert_ok("10")

    def test_gate_s_rejects_m(self):
        self.replace("SPEC.md", "S — меняется", "M — меняется")
        self.assert_fails("s", "только для размера S")

    def test_gate_4_rejects_s(self):
        self.assert_fails("4", "используй --gate s")

    def test_no_mutations_required(self):
        # у S «Мутаций» нет — отсутствие таблицы не ошибка
        self.assertNotIn("Мутации", self.files["SPEC.md"])
        self.assert_ok("10")


class Headings(Base):
    def test_heading_spellings(self):
        variants = [
            ("## Критерии приёмки", "### Критерии приёмки"),
            ("## Критерии приёмки", "## 6. Критерии приёмки"),
            ("## Критерии приёмки", "## 6 Критерии приёмки"),
            ("## Критерии приёмки", "## Критерии приемки"),
            ("## Критерии приёмки", "## КРИТЕРИИ ПРИЁМКИ"),
            ("## Критерии приёмки", "## **Критерии приёмки**"),
            ("## Критерии приёмки", "## «Критерии приёмки»"),
            ("## Критерии приёмки", "## Критерии приёмки ##"),
            ("## Критерии приёмки", "## Критерии приёмки:"),
            ("## Не входит в задачу", "## 8. Не входит в задачу"),
            ("## Входы из ревью", "## Входы из ревью (от ревьюера)"),
        ]
        for old, new in variants:
            with self.subTest(heading=new):
                self.setUp()
                self.replace("SPEC.md", old, new)
                self.assert_ok("6")

    def test_heading_inside_code_block_is_not_a_section(self):
        self.replace("SPEC.md", "## Не входит в задачу\nОфлайн-режим.\n",
                     "```\n## Не входит в задачу\n```\n")
        self.assert_fails("3", "нет раздела «Не входит в задачу»")

    def test_empty_section_is_error(self):
        self.replace("SPEC.md", "## Контекст\nПросьба пользователя: ускорить загрузку.\n", "## Контекст\n")
        self.assert_fails("3", "раздел «Контекст» пуст")

    def test_design_section_with_yo_and_numbering(self):
        self.replace("DESIGN.md", "## Затронутые модули", "## 1. Затронутые модули")
        self.assert_ok("4")


class Tables(Base):
    def test_alignment_separators(self):
        self.replace("QA.md", "|----|----|-----|------------------|---------------------|",
                     "|:---|:--:|---:|:-----------------|--------------------:|")
        self.replace("PLAN.md", "|-----|--------------|-------|----|---------------------------------|------------|",
                     "|:----|:-------------|:-----:|---:|:--------------------------------|-----------:|")
        self.replace("QA.md", "|----|---------|-----------|------|", "|:---|:--------|:---------:|-----:|")
        self.assert_ok("10")

    def test_single_dash_separator(self):
        # GFM допускает «|-|-|»; такая строка не должна становиться данными
        self.replace("QA.md", "|----|----|-----|------------------|---------------------|", "|-|-|-|-|-|")
        self.assert_ok("6")

    def test_pipe_inside_code_in_run_command(self):
        self.replace("QA.md", "| TC-01 | `run a` | PASS |", r"| TC-01 | `run a \| wc -l` | PASS |")
        self.assert_ok("10")

    def test_two_ac_in_one_cell(self):
        self.replace("QA.md", "| TC-01 | AC-01 |", "| TC-01 | AC-01, AC-02 |")
        self.replace("QA.md", "| TC-02 | AC-02 | unit | `run b` | быстрее двух секунд |\n", "")
        self.replace("PLAN.md", "| TC-02 |", "| TC-01 |")
        self.assert_ok("6")

    def test_two_ac_in_one_cell_unknown_second(self):
        self.replace("QA.md", "| TC-01 | AC-01 |", "| TC-01 | AC-01, AC-09 |")
        self.assert_fails("6", "TC-01 ссылается на AC-09")

    def test_tc_without_ac(self):
        self.replace("QA.md", "| TC-03 | AC-01 |", "| TC-03 | — |")
        self.assert_fails("6", "у TC-03 не указан AC")

    def test_plan_multiple_dependencies(self):
        self.replace("PLAN.md", "| TC-01, TC-03 | — |", "| TC-01 | — |")
        self.files["PLAN.md"] += "| 3 | третий | `c.dart` | AC-01 | TC-03 | 1, 2 |\n"
        self.assert_ok("6")

    def test_plan_dependency_on_missing_step(self):
        self.files["PLAN.md"] += "| 3 | третий | `c.dart` | AC-01 | — | 1, 7 |\n"
        self.assert_fails("6", "шаг 3: зависит от шага 7, которого нет")

    def test_plan_self_dependency(self):
        self.replace("PLAN.md", "| TC-02 | 1 |", "| TC-02 | 2 |")
        self.assert_fails("6", "шаг 2: зависит от шага 2")

    def test_plan_without_dependency_column(self):
        self.replace("PLAN.md", " | Зависит от |", " |")
        self.replace("PLAN.md", "| — |\n", "\n")
        self.replace("PLAN.md", "| TC-02 | 1 |", "| TC-02 |")
        self.assert_fails("6", "нет колонки «Зависит от»")

    def test_plan_step_without_ac(self):
        self.replace("PLAN.md", "| `b.dart` | AC-02 |", "| `b.dart` | — |")
        self.assert_fails("6", "шаг 2: не указан AC")

    def test_plan_step_with_unknown_tc(self):
        self.replace("PLAN.md", "| TC-02 | 1 |", "| TC-02, TC-77 | 1 |")
        self.assert_fails("6", "TC-77 нет в таблице тестов")

    def test_transitive_dependency_silences_shared_file_warning(self):
        self.replace("PLAN.md", "| 2 | мобильный | `b.dart` | AC-02 | TC-02 | 1 |",
                     "| 2 | мобильный | `a.dart` | AC-02 | TC-02 | 1 |")
        self.files["PLAN.md"] += "| 3 | третий | `a.dart` | AC-02 | TC-02 | 2 |\n"
        code, out = self.run_gate("6")
        self.assertEqual(code, 0, out)
        self.assertNotIn("ВНИМАНИЕ", out)

    def test_siblings_sharing_file_warn(self):
        self.replace("PLAN.md", "| 2 | мобильный | `b.dart` | AC-02 | TC-02 | 1 |",
                     "| 2 | мобильный | `a.dart` | AC-02 | TC-02 | 1 |")
        self.files["PLAN.md"] += "| 3 | третий | `a.dart` | AC-02 | TC-02 | 1 |\n"
        code, out = self.run_gate("6")
        self.assertEqual(code, 0, out)
        self.assertIn("шаги 2 и 3 правят a.dart", out)

    def test_criteria_as_table_is_not_a_test_table(self):
        self.replace("SPEC.md", "- AC-01: первый кадр быстрее двух секунд.\n- AC-02: на мобильном то же.\n",
                     "| AC | Описание |\n|----|----------|\n| AC-01 | первый кадр |\n| AC-02 | мобильный |\n")
        self.assert_ok("6")

    def test_empty_inputs_table_is_fine(self):
        self.replace("SPEC.md", "| пустой кэш | страница открывается | TC-03 |\n", "")
        self.assert_ok("6")

    def test_inputs_placeholder_row_is_fine(self):
        self.replace("SPEC.md", "| пустой кэш | страница открывается | TC-03 |",
                     "| — | — | — |")
        self.assert_ok("6")

    def test_inputs_reason_instead_of_tc(self):
        self.replace("SPEC.md", "| страница открывается | TC-03 |",
                     "| страница открывается | не входит: офлайн вне задачи |")
        self.assert_ok("6")

    def test_inputs_only_two_cells(self):
        self.replace("SPEC.md", "| пустой кэш | страница открывается | TC-03 |",
                     "| пустой кэш | страница открывается |")
        self.assert_fails("6", "нет ни TC, ни причины")


class Traceability(Base):
    def test_ac_10_and_ac_1_do_not_collide(self):
        self.edit_all("AC-01", "AC-1")
        self.edit_all("AC-02", "AC-10")
        self.assert_ok("10")
        self.replace("QA.md", "| TC-02 | AC-10 |", "| TC-02 | AC-1 |")
        self.assert_fails("6", "у AC-10 нет ни одного TC")

    def test_tc_10_and_tc_1_do_not_collide(self):
        self.replace("QA.md", "| TC-03 | AC-01 |", "| TC-10 | AC-01 |")
        self.replace("PLAN.md", "TC-01, TC-03", "TC-01, TC-1")
        self.replace("QA.md", "| TC-03 | `run c` |", "| TC-10 | `run c` |")
        self.assert_fails("6", "TC-10 не проходит ни после одного шага")

    def test_ac_without_tc(self):
        self.replace("SPEC.md", "- AC-02: на мобильном то же.\n", "- AC-02: на мобильном то же.\n- AC-03: новое.\n")
        self.assert_fails("6", "у AC-03 нет ни одного TC")

    def test_tc_references_unknown_ac(self):
        self.replace("QA.md", "| TC-02 | AC-02 |", "| TC-02 | AC-05 |")
        self.assert_fails("6", "TC-02 ссылается на AC-05")

    def test_no_ac_in_spec(self):
        self.replace("SPEC.md", "- AC-01: первый кадр быстрее двух секунд.\n- AC-02: на мобильном то же.\n",
                     "Быстро.\n")
        self.assert_fails("3", "нет ни одного AC-NN")

    def test_ac_in_code_block_is_not_a_criterion(self):
        self.replace("SPEC.md", "- AC-02: на мобильном то же.\n",
                     "- AC-02: на мобильном то же.\n\n```text\nформат: AC-77 — пример\n```\n")
        self.assert_ok("6")

    def test_tc_table_in_code_block_is_not_a_test(self):
        self.replace("SPEC.md", "Просьба пользователя: ускорить загрузку.\n",
                     "Просьба пользователя: ускорить загрузку.\n\n```text\n| TC | AC |\n|----|----|\n"
                     "| TC-99 | AC-01 |\n```\n")
        self.assert_ok("6")

    def test_other_task_ac_reference_is_not_own_criterion(self):
        self.replace("SPEC.md", "- AC-02: на мобильном то же.\n",
                     "- AC-02: на мобильном то же; не ломает PERF-2/AC-05.\n")
        self.assert_ok("6")

    def test_repro_steps_table_in_context_is_not_the_plan(self):
        self.replace("SPEC.md", "Просьба пользователя: ускорить загрузку.\n",
                     "Просьба пользователя: ускорить загрузку.\n\n| Шаг | Действие |\n|-----|----------|\n"
                     "| 1 | открыть страницу |\n")
        self.assert_ok("6")

    def test_ranges_in_plan_are_understood(self):
        self.replace("PLAN.md", "| AC-01 | TC-01, TC-03 | — |", "| AC-01..AC-02 | TC-01..TC-03 | — |")
        self.replace("PLAN.md", "| AC-02 | TC-02 | 1 |", "| AC-02 | — | 1 |")
        self.assert_ok("6")

    def test_range_in_design_counts_as_mention(self):
        self.replace("SPEC.md", "- AC-02: на мобильном то же.\n", "- AC-02: на мобильном то же.\n- AC-03: третий.\n")
        self.replace("DESIGN.md", "Хеши в именах файлов — AC-01, AC-02.", "Хеши в именах файлов — AC-01..AC-03.")
        code, out = self.run_gate("4")
        self.assertEqual(code, 0, out)
        self.assertNotIn("AC-02 нигде не упомянут", out)

    def test_input_row_pointing_to_missing_tc(self):
        self.replace("SPEC.md", "| страница открывается | TC-03 |", "| страница открывается | TC-99 |")
        self.assert_fails("6", "TC-99")


class Gates(Base):
    def test_gate_3_needs_only_spec(self):
        self.files = {"SPEC.md": self.files["SPEC.md"].replace("APPROVED (ревьюер, ревизия 1)", "DRAFT")}
        self.assert_ok("3")

    def test_gate_3_size_missing(self):
        self.replace("SPEC.md", "## Размер\nM — меняется несколько файлов.\n", "## Размер\nнесколько файлов.\n")
        self.assert_fails("3", "не найдено S, M или L")

    def test_gate_3_size_xl_is_not_a_size(self):
        self.replace("SPEC.md", "M — меняется", "XL — меняется")
        self.assert_fails("3", "не найдено S, M или L")

    def test_gate_3_bad_task_id(self):
        self.replace("SPEC.md", "Задача: PERF-3", "Задача: perf")
        self.assert_fails("3", "не вида")

    def test_gate_3_missing_revision_and_status(self):
        self.replace("SPEC.md", "Ревизия: 1\n", "")
        self.replace("SPEC.md", "Статус: APPROVED (ревьюер, ревизия 1)\n", "")
        code, out = self.run_gate("3")
        self.assertEqual(code, 1, out)
        self.assertIn("«Ревизия: N»", out)
        self.assertIn("«Статус:", out)

    def test_size_not_confused_by_negations(self):
        self.replace("SPEC.md", "M — меняется несколько файлов.", "Не S и не L: размер M, меняется несколько файлов.")
        self.assert_ok("6")

    def test_gate_4_with_draft_spec(self):
        self.replace("SPEC.md", "Статус: APPROVED (ревьюер, ревизия 1)", "Статус: DRAFT")
        self.assert_fails("4", "SPEC.md: статус не APPROVED")

    def test_gate_4_draft_design_is_fine_and_qa_plan_not_needed(self):
        self.files = {
            "SPEC.md": self.files["SPEC.md"],
            "DESIGN.md": self.files["DESIGN.md"].replace("APPROVED (ревьюер, ревизия 1)", "DRAFT"),
        }
        self.assert_ok("4")

    def test_gate_4_design_missing(self):
        del self.files["DESIGN.md"]
        self.assert_fails("4", "DESIGN.md: файла нет")

    def test_gate_4_diagrams_without_mermaid_block(self):
        self.replace("DESIGN.md", "```mermaid\nsequenceDiagram\n  Браузер->>Сервер: index.html\n```",
                     "Диаграмма в формате mermaid будет позже.")
        self.assert_fails("4", "нет блока mermaid")

    def test_gate_4_diagrams_not_needed_for_s(self):
        self.use_s()
        self.files["DESIGN.md"] = DESIGN.format(status="DRAFT").replace("## Диаграммы", "## Прочее")
        code, out = self.run_gate("4")
        self.assertIn("используй --gate s", out)

    def test_gate_4_design_task_mismatch(self):
        self.replace("DESIGN.md", "Задача: PERF-3", "Задача: PERF-4")
        self.assert_fails("4", "DESIGN.md: идентификатор задачи не совпадает")

    def test_gate_4_design_missing_section(self):
        self.replace("DESIGN.md", "## Безопасность", "## Права")
        self.assert_fails("4", "нет раздела «Безопасность»")

    def test_gate_6_missing_qa(self):
        del self.files["QA.md"]
        self.assert_fails("6", "QA.md: файла нет")

    def test_gate_6_missing_plan(self):
        del self.files["PLAN.md"]
        self.assert_fails("6", "PLAN.md: файла нет")

    def test_gate_6_missing_design(self):
        del self.files["DESIGN.md"]
        self.assert_fails("6", "DESIGN.md: файла нет")

    def test_gate_6_draft_spec(self):
        self.replace("SPEC.md", "Статус: APPROVED (ревьюер, ревизия 1)", "Статус: DRAFT")
        self.assert_fails("6", "SPEC.md: статус не APPROVED")

    def test_gate_6_draft_qa_and_plan_are_the_subject_of_review(self):
        # на воротах 6 QA.md и PLAN.md сами на ревью и ещё DRAFT
        for name in ("QA.md", "PLAN.md"):
            self.replace(name, "Статус: APPROVED (ревьюер, ревизия 1)", "Статус: DRAFT")
        self.assert_ok("6")

    def test_gate_6_qa_task_mismatch(self):
        self.replace("QA.md", "Задача: PERF-3", "Задача: PERF-9")
        self.assert_fails("6", "QA.md: идентификатор задачи не совпадает")

    def test_gate_10_qa_plan_must_be_approved(self):
        self.replace("PLAN.md", "Статус: APPROVED (ревьюер, ревизия 1)", "Статус: DRAFT")
        self.assert_fails("10", "PLAN.md: статус не APPROVED")

    def test_gate_6_does_not_need_run_or_mutations(self):
        self.replace("QA.md", "## Прогон", "## Потом")
        self.assert_ok("6")

    def test_status_case_insensitive(self):
        self.replace("SPEC.md", "Статус: APPROVED", "Статус: approved")
        self.assert_ok("6")

    def test_crlf_line_endings(self):
        for name in self.files:
            self.files[name] = self.files[name].replace("\n", "\r\n")
        for gate in ("3", "4", "6", "10"):
            self.assert_ok(gate)

    def test_crlf_still_detects_gap(self):
        for name in self.files:
            self.files[name] = self.files[name].replace("\n", "\r\n")
        self.replace("QA.md", "| TC-02 | AC-02 | unit | `run b` | быстрее двух секунд |\r\n", "")
        self.replace("PLAN.md", "TC-02", "TC-01")
        self.assert_fails("6", "у AC-02 нет ни одного TC")

    def test_bom_at_file_start(self):
        for name in self.files:
            self.files[name] = "﻿" + self.files[name]
        self.assert_ok("6")

    def test_non_utf8_file_is_reported_not_crash(self):
        for name, text in self.files.items():
            (self.dir / name).write_bytes(text.encode("cp1251"))
        out = io.StringIO()
        with redirect_stdout(out):
            try:
                code = check_artifacts.main([str(self.dir), "--gate", "3"])
            except UnicodeDecodeError as exc:
                self.fail(f"необработанное исключение вместо сообщения: {exc}")
        self.assertIn(code, (1, 2))

    def test_missing_spec(self):
        self.files = {}
        self.assert_fails("3", "SPEC.md: файла нет")

    def test_bad_gate_argument(self):
        with self.assertRaises(SystemExit) as ctx, redirect_stdout(io.StringIO()), \
                __import__("contextlib").redirect_stderr(io.StringIO()):
            check_artifacts.main([str(self.dir), "--gate", "7"])
        self.assertEqual(ctx.exception.code, 2)


class RunTable(Base):
    def test_result_spellings_are_accepted(self):
        for value in ("pass", "Pass", "PASS: все 3 теста", "PASS (кэш пустой)", "**PASS**", "`PASS`"):
            with self.subTest(value=value):
                self.setUp()
                self.replace("QA.md", "| TC-02 | `run b` | PASS |", f"| TC-02 | `run b` | {value} |")
                self.assert_ok("10")

    def test_fail_spellings_are_errors(self):
        for value in ("fail", "Fail: нет файла", "FAIL (строка 5)", "**FAIL**"):
            with self.subTest(value=value):
                self.setUp()
                self.replace("QA.md", "| TC-02 | `run b` | PASS |", f"| TC-02 | `run b` | {value} |")
                self.assert_fails("10", "TC-02 — FAIL")

    def test_not_run_spellings_are_warnings(self):
        for value in ("НЕ ЗАПУЩЕН", "не запущен: нет БД", "Не запущен — нужен стенд"):
            with self.subTest(value=value):
                self.setUp()
                self.replace("QA.md", "| TC-03 | `run c` | PASS |", f"| TC-03 | `run c` | {value} |")
                code, out = self.run_gate("10")
                self.assertEqual(code, 0, out)
                self.assertIn("ВНИМАНИЕ", out)

    def test_unknown_result_is_error(self):
        self.replace("QA.md", "| TC-02 | `run b` | PASS |", "| TC-02 | `run b` | ок |")
        self.assert_fails("10", "результат «ок»")

    def test_empty_result_is_error(self):
        self.replace("QA.md", "| TC-02 | `run b` | PASS |", "| TC-02 | `run b` |  |")
        self.assert_fails("10", "TC-02")

    def test_fail_in_callers_row_is_error(self):
        self.replace("QA.md", "| — | тесты вызывающего кода | PASS |", "| — | тесты вызывающего кода | FAIL |")
        self.assert_fails("10", "FAIL")

    def test_run_table_missing(self):
        self.replace("QA.md", "| TC | Команда | Результат | Дата |", "| TC | Команда | Итог | Дата |")
        self.assert_fails("10", "не найдена таблица «Прогон»")

    def test_pass_followed_by_fail_is_error(self):
        self.replace("QA.md", "| TC-02 | `run b` | PASS |", "| TC-02 | `run b` | PASS 2 из 3, FAIL 1 |")
        self.assert_fails("10", "TC-02")


class Mutations(Base):
    def test_missing_row_for_ac(self):
        self.replace("QA.md", "| AC-02 | `b.dart:7` — убрана ветка | TC-02 |\n", "")
        self.assert_fails("10", "«Мутации»: нет строки для AC-02")

    def test_garbage_outcome(self):
        self.replace("QA.md", "— убрана ветка | TC-02 |", "— убрана ветка | позже |")
        self.assert_fails("10", "AC-02")

    def test_table_missing_for_m(self):
        self.replace("QA.md", "| Упавший TC |", "| Итог |")
        self.assert_fails("10", "не найдена таблица «Мутации»")

    def test_lowercase_none(self):
        self.replace("QA.md", "— убрана ветка | TC-02 |", "— убрана ветка | ни один |")
        self.assert_fails("10", "AC-02 — НИ ОДИН")

    def test_not_applicable_lowercase_with_reason(self):
        self.replace("QA.md", "| `b.dart:7` — убрана ветка | TC-02 |",
                     "| — | не применимо: миграция, мутацией не проверить |")
        self.assert_ok("10")

    def test_mutations_not_checked_at_gate_6(self):
        self.replace("QA.md", "— убрана ветка | TC-02 |", "— убрана ветка | НИ ОДИН |")
        self.assert_ok("6")

    def test_mutation_pointing_to_missing_tc(self):
        self.replace("QA.md", "— убрана ветка | TC-02 |", "— убрана ветка | TC-99 |")
        self.assert_fails("10", "TC-99")


class SizeL(Base):
    def setUp(self):
        super().setUp()
        self.replace("SPEC.md", "M — меняется", "L — меняется схема, а также")

    def approve_human(self):
        for name in ("SPEC.md", "DESIGN.md"):
            self.replace(name, "Статус: APPROVED (ревьюер, ревизия 1)",
                         "Статус: APPROVED (ревьюер и человек, ревизия 1)")

    def test_human_approved_passes(self):
        self.approve_human()
        self.assert_ok("10")

    def test_human_only_in_design_is_not_enough(self):
        self.replace("DESIGN.md", "Статус: APPROVED (ревьюер, ревизия 1)",
                     "Статус: APPROVED (ревьюер и человек, ревизия 1)")
        self.assert_fails("10", "SPEC.md: при размере L")

    def test_waiting_for_human_is_not_approval(self):
        for name in ("SPEC.md", "DESIGN.md"):
            self.replace(name, "Статус: APPROVED (ревьюер, ревизия 1)",
                         "Статус: APPROVED (ревьюер, ревизия 1); ждёт человека")
        self.assert_fails("10", "ревьюер и человек")

    def test_l_needs_diagrams_and_mutations(self):
        self.approve_human()
        self.replace("QA.md", "| AC-02 | `b.dart:7` — убрана ветка | TC-02 |\n", "")
        self.assert_fails("10", "нет строки для AC-02")

    def test_human_not_needed_before_gate_10(self):
        for gate in ("3", "4", "6"):
            self.assert_ok(gate)


class Cli(Base):
    def test_subprocess_exit_codes(self):
        import subprocess
        script = str(Path(__file__).parent / "check_artifacts.py")
        for name, text in self.files.items():
            (self.dir / name).write_text(text, encoding="utf-8")
        ok = subprocess.run([sys.executable, script, str(self.dir), "--gate", "10"],
                            capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.assertTrue(ok.stdout.startswith("OK"))
        (self.dir / "QA.md").unlink()
        bad = subprocess.run([sys.executable, script, str(self.dir), "--gate", "10"],
                             capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertTrue(bad.stdout.startswith("НЕ ПРОЙДЕНО"))
        usage = subprocess.run([sys.executable, script, str(self.dir)], capture_output=True, text=True)
        self.assertEqual(usage.returncode, 2)
        nodir = subprocess.run([sys.executable, script, str(self.dir / "x"), "--gate", "3"],
                               capture_output=True, text=True)
        self.assertEqual(nodir.returncode, 2)


class MutationGaps(Base):
    """Тесты, закрывающие слепые зоны, найденные мутациями самого скрипта."""

    def test_diagrams_section_without_any_diagram(self):
        self.replace("DESIGN.md", "```mermaid\nsequenceDiagram\n  Браузер->>Сервер: index.html\n```",
                     "Схем пока нет.")
        self.assert_fails("4", "нет блока mermaid")

    def test_diagrams_with_mermaid_block_pass_gate_4(self):
        self.assert_ok("4")

    def test_plan_step_with_unknown_ac(self):
        self.replace("PLAN.md", "| `b.dart` | AC-02 |", "| `b.dart` | AC-09 |")
        self.assert_fails("6", "шаг 2: AC-09 нет в критериях приёмки")

    def test_duplicate_step_numbers(self):
        self.files["PLAN.md"] += "| 2 | ещё один | `c.dart` | AC-02 | TC-02 | 1 |\n"
        self.assert_fails("6", "номера шагов плана повторяются")

    def test_ac_column_found_by_exact_name(self):
        self.replace("QA.md", "| TC | AC | Тип |", "| TC | Trace | AC | Тип |")
        self.replace("QA.md", "|----|----|-----|", "|----|-----|----|-----|")
        for tc in ("TC-01", "TC-02", "TC-03"):
            row_start = f"| {tc} | "
            i = self.files["QA.md"].index(row_start, self.files["QA.md"].index("| Команда или шаги"))
            self.files["QA.md"] = self.files["QA.md"][:i] + row_start + "x | " + self.files["QA.md"][i + len(row_start):]
        self.assert_ok("6")

    def test_design_warns_about_unmentioned_ac(self):
        self.replace("DESIGN.md", "Хеши в именах файлов — AC-01, AC-02.", "Хеши в именах файлов — AC-01.")
        code, out = self.run_gate("4")
        self.assertEqual(code, 0, out)
        self.assertIn("ВНИМАНИЕ DESIGN.md: AC-02 нигде не упомянут", out)

    def test_design_mention_of_ac_10_is_not_mention_of_ac_1(self):
        self.edit_all("AC-01", "AC-1")
        self.edit_all("AC-02", "AC-10")
        self.replace("DESIGN.md", "AC-1, AC-10", "AC-10")
        code, out = self.run_gate("4")
        self.assertIn("AC-1 нигде не упомянут", out)

    def test_run_table_not_run_warning_names_tc(self):
        self.replace("QA.md", "| TC-03 | `run c` | PASS |", "| TC-03 | `run c` | НЕ ЗАПУЩЕН |")
        code, out = self.run_gate("10")
        self.assertEqual(code, 0, out)
        self.assertIn("НЕ ЗАПУЩЕН — TC-03", out)
        self.assertIn("согласие пользователя", out)


if __name__ == "__main__":
    unittest.main()
