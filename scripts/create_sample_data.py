from pathlib import Path
from openpyxl import Workbook

out = Path(__file__).resolve().parents[1] / "sample-data.xlsx"
wb = Workbook()
ws = wb.active
ws.title = "Сотрудники"
ws.append(["ФИО", "Дата рождения", "Отдел", "Должность"])
ws.append(["Иванов Иван Иванович", "12.04.1980", "ОП", "Инженер"])
ws.append(["Петров Пётр Петрович", "23.09.1985", "ОМН", "Синоптик"])
ws.append(["Сидоров Андрей Сергеевич", "04.02.1990", "АЭРО", "Техник"])
wb.save(str(out))
print(out)
