# Архитектура проекта

## Структура
- `scripts/` — атомарные скрипты
- `skills/` — пайплайны
- `data/` — результаты
- `configs/` — API-ключи

## Принципы
- AI точечно, правила широко
- Паспорт проектов — единая точка правды
- HTML-кэш в `data/page-registry/`

## Запуск скиллов
```bash
python skills/<skill-name>/run.py --domain example.com
```

## Data pipeline
semantics → positions → weak_pages