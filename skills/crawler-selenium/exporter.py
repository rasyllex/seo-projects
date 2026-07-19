"""
Сохранение реестра краулера в Excel.
Порядок колонок — из seo.COLUMNS; кастомные XPath-колонки идут в конец.
"""

import pandas as pd

from seo import COLUMNS


def to_excel(results, output_path):
    """Сохраняет реестр в Excel с фиксированным порядком известных колонок."""
    df = pd.DataFrame(results)
    ordered = [c for c in COLUMNS if c in df.columns] + \
              [c for c in df.columns if c not in COLUMNS]
    df[ordered].to_excel(output_path, index=False)
