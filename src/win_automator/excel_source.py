from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from openpyxl import load_workbook


def normalize(value: Any) -> Tuple[str, Any]:
    if value is None:
        return ("empty", "")
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, dt.datetime):
        return ("datetime", value.replace(microsecond=0))
    if isinstance(value, dt.date):
        return ("date", value)
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        try:
            return ("number", Decimal(str(value)).normalize())
        except InvalidOperation:
            pass

    text = re.sub(r"\s+", " ", str(value).strip())
    lowered = text.casefold()

    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%y", "%d-%m-%Y"):
        try:
            return ("date", dt.datetime.strptime(text, fmt).date())
        except ValueError:
            continue

    numeric = text.replace(" ", "").replace(",", ".")
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", numeric):
        try:
            return ("number", Decimal(numeric).normalize())
        except InvalidOperation:
            pass
    return ("text", lowered)


def infer_columns(value: Any, row: Dict[str, Any]) -> List[str]:
    needle = normalize(value)
    return [column for column, candidate in row.items() if normalize(candidate) == needle]


def _tokens(value: object) -> List[str]:
    return [token for token in re.findall(r"[0-9a-zа-яё]+", str(value or "").casefold()) if token]


def infer_column(value: Any, row: Dict[str, Any], hints: Iterable[object] = ()) -> Optional[str]:
    """Resolve one Excel column for a recorded value.

    Exact value matching is primary. If several columns contain the same value,
    semantic hints from the target control (AccessibleName/name/automation id)
    are used only when they produce a unique best match. Ambiguous data stays
    ambiguous instead of being silently bound to a random column.
    """

    matches = infer_columns(value, row)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return None

    hint_texts = [str(h).strip().casefold() for h in hints if str(h or "").strip()]
    hint_tokens = set(token for hint in hint_texts for token in _tokens(hint))
    ranked: List[Tuple[int, str]] = []
    for column in matches:
        column_text = str(column).strip().casefold()
        column_tokens = set(_tokens(column))
        score = 0
        for hint in hint_texts:
            if column_text == hint:
                score = max(score, 100)
            elif column_text and hint and (column_text in hint or hint in column_text):
                score = max(score, 60)
        score += 10 * len(column_tokens & hint_tokens)
        ranked.append((score, column))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    if ranked and ranked[0][0] > 0 and (len(ranked) == 1 or ranked[0][0] > ranked[1][0]):
        return ranked[0][1]
    return None


def unique_headers(values: Sequence[Any]) -> List[str]:
    result: List[str] = []
    counts: Dict[str, int] = {}
    for index, value in enumerate(values, start=1):
        base = str(value).strip() if value not in (None, "") else "Столбец {}".format(index)
        counts[base] = counts.get(base, 0) + 1
        result.append(base if counts[base] == 1 else "{} ({})".format(base, counts[base]))
    return result


def _numeric_pattern(sample: str):
    compact = sample.strip().replace(" ", "")
    match = re.fullmatch(r"([+-]?)(\d+)(?:([,.])(\d+))?", compact)
    if not match:
        return None
    sign, integer, separator, fraction = match.groups()
    return sign, integer, separator or "", fraction or ""


def format_like_sample(value: Any, sample: Any) -> str:
    """Format an Excel value like the value entered during training.

    This preserves operator-visible formats that are otherwise lost when
    openpyxl returns typed values, notably dates (dd.mm.yyyy), decimal comma,
    fixed decimals and leading zeroes.
    """

    if value is None:
        return ""
    sample_text = "" if sample is None else str(sample)

    if isinstance(value, dt.datetime):
        value = value.replace(microsecond=0)
    if isinstance(value, (dt.date, dt.datetime)):
        for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%y", "%d-%m-%Y"):
            try:
                dt.datetime.strptime(sample_text.strip(), fmt)
                return value.strftime(fmt)
            except ValueError:
                continue
        if isinstance(value, dt.datetime) and (":" in sample_text):
            return value.strftime("%d.%m.%Y %H:%M:%S")
        return str(value)

    pattern = _numeric_pattern(sample_text)
    if pattern and isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        sign, integer_sample, separator, fraction_sample = pattern
        try:
            number = Decimal(str(value))
            decimals = len(fraction_sample)
            if decimals:
                quantizer = Decimal(1).scaleb(-decimals)
                rendered = format(number.quantize(quantizer), ".{}f".format(decimals))
            else:
                rendered = format(number.quantize(Decimal("1")), "f")
            number_sign = ""
            if rendered.startswith("-"):
                number_sign = "-"
                rendered = rendered[1:]
            integer_part, dot, fraction_part = rendered.partition(".")
            if len(integer_sample) > 1 and integer_sample.startswith("0"):
                integer_part = integer_part.zfill(len(integer_sample))
            if decimals:
                rendered = integer_part + (separator or ".") + fraction_part
            else:
                rendered = integer_part
            if number_sign:
                rendered = "-" + rendered
            elif sign == "+":
                rendered = "+" + rendered
            return rendered
        except (InvalidOperation, ValueError):
            pass

    return str(value)


class ExcelSource:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._book = load_workbook(str(self.path), data_only=True, read_only=True)

    @property
    def sheets(self) -> List[str]:
        return list(self._book.sheetnames)

    def detect_header_row(self, sheet: str, scan_rows: int = 20) -> int:
        """Detect a practical header row while keeping row order deterministic.

        Title rows with one merged/filled cell are skipped. The first row with
        at least two non-empty mostly textual cells and a populated following
        row is preferred. If no confident candidate exists, the first non-empty
        row is used, falling back to row 1 for an empty sheet.
        """

        ws = self._book[sheet]
        rows = list(ws.iter_rows(min_row=1, max_row=max(1, scan_rows + 1), values_only=True))
        first_nonempty = 1
        found_nonempty = False
        for index, values in enumerate(rows[:scan_rows], start=1):
            nonempty = [value for value in values if value not in (None, "")]
            if nonempty and not found_nonempty:
                first_nonempty = index
                found_nonempty = True
            if len(nonempty) < 2:
                continue
            textual = sum(
                1
                for value in nonempty
                if isinstance(value, str) and value.strip()
            )
            if textual < max(2, int(len(nonempty) * 0.6)):
                continue
            next_values = rows[index] if index < len(rows) else ()
            next_nonempty = sum(1 for value in next_values if value not in (None, ""))
            if next_nonempty >= max(1, len(nonempty) // 2):
                return index
        return first_nonempty if found_nonempty else 1

    def read(self, sheet: str, header_row: int = 1) -> Tuple[List[str], List[Dict[str, Any]]]:
        ws = self._book[sheet]
        iterator = ws.iter_rows(values_only=True)
        for _ in range(max(0, header_row - 1)):
            next(iterator, None)
        header_values = next(iterator, None)
        if header_values is None:
            return [], []
        headers = unique_headers(header_values)
        rows: List[Dict[str, Any]] = []
        for values in iterator:
            padded = list(values) + [None] * max(0, len(headers) - len(values))
            row = {headers[i]: padded[i] for i in range(len(headers))}
            if any(value not in (None, "") for value in row.values()):
                rows.append(row)
        return headers, rows

    def close(self) -> None:
        self._book.close()
