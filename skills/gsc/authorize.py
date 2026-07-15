"""
Одноразовая OAuth-авторизация Google-аккаунта для скилла gsc.

Что нужно заранее: configs/gsc/client_secret.json (OAuth-клиент типа Desktop
из Google Cloud Console проекта, где включён Search Console API).

Запуск:  python authorize.py
Откроется браузер — войди в нужный Google-аккаунт и разреши доступ.
Результат: configs/gsc/token.json (с refresh_token, обновляется сам).
"""

from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from gsc_client import SCOPES

BASE = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE / "configs" / "gsc"
CLIENT_SECRET = CONFIG_DIR / "client_secret.json"
TOKEN = CONFIG_DIR / "token.json"


def main():
    if not CLIENT_SECRET.exists():
        raise SystemExit(
            f"Нет {CLIENT_SECRET}.\n"
            "Скачай OAuth-клиент (Desktop) из Google Cloud Console:\n"
            "APIs & Services -> Credentials -> Create Credentials -> OAuth client ID")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    TOKEN.write_text(creds.to_json(), encoding="utf-8")
    print(f"[OK] Токен сохранён: {TOKEN}")
    print("Проверка: python run.py --list-sites")


if __name__ == "__main__":
    main()
