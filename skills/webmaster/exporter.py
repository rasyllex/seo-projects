"""
Сохранение результатов в многостраничный Excel.
"""

import pandas as pd


def to_excel(data_sheets, output_path):
    """
    Сохраняет данные в многостраничный Excel.

    Args:
        data_sheets: dict {"Лист1": [ {...}, ... ], "Лист2": [ ... ]}
        output_path: путь к файлу
    """
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for sheet_name, rows in data_sheets.items():
            df = pd.DataFrame(rows)
            df.to_excel(writer, sheet_name=sheet_name, index=False)
