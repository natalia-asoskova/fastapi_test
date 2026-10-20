# Kvitto Payments API

Небольшой сервис приёма платежей за курс: тарифы, платежи (карта / СБП / рассрочка),
промокод, идемпотентность и вебхук банка. FastAPI + SQLAlchemy 2.0 + SQLite.

## Запуск

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Сервис на http://localhost:8000, документация — http://localhost:8000/docs.
Таблицы и тарифы создаются при старте автоматически (файл `kvitto.db`).

Переменные окружения (необязательные):

| Переменная       | Назначение                                                              |
|------------------|-------------------------------------------------------------------------|
| `DATABASE_URL`   | по умолчанию `sqlite:///./kvitto.db`; для PostgreSQL — `postgresql+psycopg://...` |
| `WEBHOOK_SECRET` | если задан, `/webhooks/bank` требует заголовок `X-Signature` (HMAC-SHA256) |

> Без `WEBHOOK_SECRET` подпись **не проверяется** — это удобно для разработки, но в проде
> переменную нужно задавать обязательно.

## Тесты и линтер

```bash
pytest -q
ruff check .
```

Тесты идут на SQLite in-memory и не трогают `kvitto.db`.

## Примеры запросов

```bash
# тарифы
curl localhost:8000/tariffs

# рассрочка на 3 месяца с промокодом (регистр не важен)
curl -X POST localhost:8000/payments \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: order-42' \
  -d '{"tariff_id":"standard","email":"student@example.com","method":"installment","installment_months":3,"promo_code":"kvitto10"}'

# платёж по id
curl localhost:8000/payments/<id>

# список с фильтрами
curl 'localhost:8000/payments?email=student@example.com&status=pending'

# вебхук банка
curl -X POST localhost:8000/webhooks/bank \
  -H 'Content-Type: application/json' \
  -d '{"payment_id":"<id>","status":"succeeded"}'
```

Вебхук с подписью:

```bash
BODY='{"payment_id":"<id>","status":"succeeded"}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | awk '{print $NF}')
curl -X POST localhost:8000/webhooks/bank -H "X-Signature: $SIG" -d "$BODY"
```

## Принятые решения

- **Деньги** — только `int` в копейках, `float` и `round()` нигде не используются.
  Скидка: `price * 10 // 100` (целочисленное деление; для текущих цен делится нацело).
- **Рассрочка**: `divmod(amount, months)`, остаток по одной копейке раздаётся первым платежам.
  Для `card` и `sbp` `schedule = null`.
- **`installment_months`**: обязателен и ∈ {3, 6, 12} для `installment`; для `card`/`sbp`
  передавать его нельзя (422).
- **Неизвестный `tariff_id`** — 422.
- **Идемпотентность**: `Idempotency-Key` хранится в колонке с `UNIQUE`. При гонке двух
  одинаковых запросов проигравший ловит `IntegrityError`, откатывается и возвращает уже
  созданный платёж (200). Ключ сопоставляется только по значению: тело повторного запроса
  не сравнивается.
- **Статусы**: таблица переходов в `app/statuses.py`. Повтор того же статуса (например,
  `succeeded → succeeded`) считается запрещённым переходом (409). Смена статуса — условный
  `UPDATE ... WHERE status = <прочитанный>`, чтобы параллельные вебхуки не перезаписали друг друга.
- **Время** `created_at` хранится и отдаётся в UTC.

## Структура

```
app/
  main.py        приложение, lifespan, seed тарифов
  db.py          engine, сессия
  models.py      Tariff, Payment
  schemas.py     Pydantic-схемы и валидация
  price.py     промокод и график рассрочки (чистые функции)
  statuses.py    enum и таблица переходов
  routers/       tariffs, payments, webhooks
tests/           pytest (SQLite in-memory)
```
