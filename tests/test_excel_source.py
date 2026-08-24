from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from win_automator.excel_source import infer_columns, normalize, unique_headers


def test_normalize_dates_and_numbers():
    assert normalize("01.08.2026") == normalize("1.8.2026")
    assert normalize("123,00") == normalize(123)


def test_infer_unique_column():
    row = {"ФИО": "Иванов И.И.", "Город": "Москва"}
    assert infer_columns(" Иванов И.И. ", row) == ["ФИО"]


def test_duplicate_headers():
    assert unique_headers(["ФИО", "ФИО", None]) == ["ФИО", "ФИО (2)", "Столбец 3"]
