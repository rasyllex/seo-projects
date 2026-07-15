# Быстрый старт: Скилл webmaster

## Что исправлено

✅ Реализован реальный API Яндекс.Вебмастер с:
- Пагинацией (автоматическая выгрузка всех страниц по 200 записей)
- Retry-логикой (3 попытки при сетевых ошибках)
- Обработкой ошибок (400, 401, 403, 404)
- URL-кодированием host_id

✅ Добавлен тестовый скрипт `test_api.py` для диагностики проблем

## Быстрый тест

### 1. Установка зависимостей
```bash
pip install requests pandas openpyxl
```

### 2. Диагностика подключения
```bash
cd D:\projects\seo-agency\skills\webmaster
python test_api.py
```

Скрипт проверит:
- ✅ Валидность токена
- ✅ Получение user_id
- ✅ Список доступных хостов
- ✅ Запрос популярных запросов для bashgaz02.ru (если сайт добавлен)

### 3. Запуск реального скилла
```bash
# Для bashgaz02.ru
python run.py --host-id https:bashgaz02.ru:443 --real

# С ограничением (для быстрой проверки)
python run.py --host-id https:bashgaz02.ru:443 --real --limit 50

# Свой путь к выходному файлу
python run.py --host-id https:bashgaz02.ru:443 --real --output ../../data/webmaster/bashgaz02_full.xlsx
```

## Возможные ошибки

### Ошибка 400 Bad Request
**Причины:**
1. host_id не соответствует формату (должен быть `https:domain:443`)
2. Сайт не подтверждён в Вебмастере
3. Недостаточно данных (новый сайт или нет поисковых запросов)

**Решение:** Запустите `test_api.py` — он покажет правильный host_id из API

### Ошибка 401 Unauthorized
**Причина:** Токен невалидный или истёк

**Решение:** 
1. Перегенерируйте токен по инструкции в README.md
2. Обновите `configs/webmaster/.env`

### Ошибка 403 Forbidden
**Причина:** Недостаточно прав доступа

**Решение:** При создании приложения на oauth.yandex.ru убедитесь, что выбран доступ `webmaster:hostinfo`

## Структура выходного файла

`data/webmaster/webmaster.xlsx` содержит 3 листа:

### Лист "Запросы"
- `query_text` — текст запроса
- `impressions` — показы в поиске (TOTAL_SHOWS)
- `clicks` — клики (TOTAL_CLICKS)
- `position` — средняя позиция (AVG_SHOW_POSITION)

### Лист "Индексация"
- `url` — адрес страницы
- `title` — заголовок
- `last_access` — последний доступ робота
- `status` — статус ("В поиске")

### Лист "Ссылки"
- `source_url` — донор (откуда ссылка)
- `target_url` — акцептор (куда ведёт)
- `discovery_date` — дата обнаружения

## Что дальше?

После успешного запуска:
1. Проверьте Excel-файл в `data/webmaster/`
2. Добавьте другие сайты из Вебмастера
3. Настройте автоматическую выгрузку (cron/Task Scheduler)

## Конфигурация

Все секреты хранятся в `D:\projects\seo-agency\configs\webmaster\.env`:
```
YANDEX_WEBMASTER_TOKEN=y0_wgBEPTz4wwYkqo2IPK2wqIYMNyqirMIkucGY0WECu3eNrwJzcTTmbyR9pE
YANDEX_WEBMASTER_USER_ID=26802676
```

❗ Файл `.env` в `.gitignore` — не попадёт в Git
