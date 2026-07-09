"""
Валидация входных данных перед обработкой.
"""

import pandas as pd
from pathlib import Path


def validate_excel(filepath):
    """
    Проверяет входной Excel файл.

    Returns:
        (is_valid: bool, error_msg: str)
    """
    path = Path(filepath)

    # Проверка существования файла
    if not path.exists():
        return False, f"Файл не найден: {filepath}"

    # Проверка расширения
    if path.suffix.lower() not in (".xlsx", ".xls", ".csv"):
        return False, f"Неподдерживаемый формат: {path.suffix}. Используй .xlsx или .csv"

    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
    except Exception as e:
        return False, f"Не удалось прочитать файл: {e}"

    # Проверка наличия колонки keyword
    if "keyword" not in df.columns:
        return False, f"В файле нет колонки 'keyword'. Найдены колонки: {list(df.columns)}"

    # Проверка на пустоту
    keywords = df["keyword"].dropna().astype(str).tolist()
    if len(keywords) == 0:
        return False, "Колонка 'keyword' пуста"

    # Проверка на дубликаты
    duplicates = df["keyword"].duplicated().sum()
    if duplicates > 0:
        print(f"⚠️  Найдено дубликатов ключей: {duplicates}")

    return True, f"OK: {len(keywords)} ключей"
