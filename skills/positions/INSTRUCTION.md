# Инструкция: Съём позиций

Скилл уже настроен для работы с реальным XMLRiver API. Нужно только добавить ключи и запустить.

## Шаг 0. Подготовка

1. Зарегистрируйся на https://xmlriver.com/ и получи `user_id` + `api_key`
2. Скопируй `config.env.example` в `config.env`:
   ```bash
   cp config.env.example config.env
   ```
3. Запиши реальные ключи в `config.env`:
   ```env
   XMLRIVER_USER_ID=your_user_id
   XMLRIVER_API_KEY=your_api_key
   ```

## Шаг 1. Мок-режим

Убедись, что скилл запускается без реальных запросов:

```bash
python run.py --input data/keywords_example.xlsx --domain example.com
```

Ты должен увидеть:
- ✅ Входные данные корректны
- → Ключей для проверки: N
- Прогресс-бар
- ✅ Результат сохранён
- Статистику

## Шаг 2. Реальный API — Яндекс

```bash
python run.py --input data/keywords_example.xlsx --domain твой-домен.com --engine yandex --real
```

## Шаг 3. Реальный API — Google

Google отдаёт ~10 URL за запрос, поэтому скилл ходит постранично до ТОП-30:

```bash
python run.py --input data/keywords_example.xlsx --domain твой-домен.com --engine google --real
```

## Шаг 4. Многопоточность

По умолчанию используется 8 потоков. Можно изменить:

```bash
python run.py --input data/keywords_example.xlsx --domain твой-домен.com --engine yandex --real --threads 4
```

## Шаг 5. Проверка

- [ ] Результат сохранился в `data/output.xlsx` (колонки: keyword, position, url, date)
- [ ] Кэш создался в `data/cache.json`
- [ ] Повторный запуск быстрее (берёт из кэша)
- [ ] Нет критических ошибок в консоли

## Шаг 6. Сохранение

```bash
git add .
git commit -m "feat: скилл съёма позиций через XMLRiver"
git push
```

Проверь, что `config.env` не попал в репозиторий (должен быть в `.gitignore`).

## Если что-то пошло не так

1. **API не отвечает** — проверь `config.env`, запусти без `--real` для теста
2. **Excel не читается** — проверь `validate_input.py`, убедись, что есть колонка `keyword`
3. **Ошибка 111 / 101** — XMLRiver перегружен, попробуй позже или уменьши `--threads`
4. **Хочешь доработать скилл** — открой `SKILL.md` и попроси AI помочь
