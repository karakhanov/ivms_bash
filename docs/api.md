## IVMS Backend API

Актуальная документация для фронтенда по основным REST‑эндпоинтам.

### Общие сведения

- **Базовый URL**: `http://<server>/api/`
- **Формат**: JSON
- **Аутентификация**: сейчас отсутствует (по необходимости можно добавить позже).

---

### 1. Дашборд

#### `GET /dashboard/summary/`

**Назначение**: агрегированные данные для главного дашборда (карточки «Присутствуют», «Отсутствуют», «Опоздали» и блок «Последняя активность»).

**Параметры**: отсутствуют.

**Ответ 200 OK**:

```json
{
  "summary": {
    "total": 248,             // всего активных сотрудников
    "present": 186,           // сегодня присутствуют (есть DailyAttendanceSummary)
    "absent": 50,             // сегодня отсутствуют
    "late": 12,               // опоздали
    "on_leave": 0,            // в отпуске / на больничном (пока всегда 0)
    "devices_online": {
      "online": 0,            // количество онлайн‑устройств (пока заглушка)
      "total": 0              // всего устройств (пока заглушка)
    }
  },
  "recent_activity": [
    {
      "employee_id": 123,
      "employee_external_id": "3060...",       // ПИНФЛ / внешний ID
      "employee_full_name": "Иванов Иван Иванович",
      "employee_photo_url": "/media/employees/photos/123.jpg", // аватар (может быть null)
      "device_id": "door-1",                   // ID терминала
      "event_type": "IN",                      // сырое значение: IN / OUT
      "event_type_display": "Вход",            // локализовано: "Вход" / "Выход"
      "event_time": "2025-02-25T09:14:32+05:00", // ISO‑строка с таймзоной
      "time_display": "09:14",                 // только время, для таблицы
      "status": "Вовремя"                      // "Вовремя" / "Опоздал" / "Завершено"
    }
  ]
}
```

---

### 2. Посещаемость по дням

#### `GET /daily-attendance-summaries/`

**Назначение**: список сотрудников и их статуса за день (или период) для страницы «Посещаемость».

**Параметры (query)**:

- **Фильтрация по дате**:
  - `date=YYYY-MM-DD` — конкретный день (основной сценарий фронта).
  - либо (если нужен диапазон):
    - `date_from=YYYY-MM-DD`
    - `date_to=YYYY-MM-DD`
- **Фильтрация по сотруднику**:
  - `employee_id=<int>`
- **Фильтрация по отделу**:
  - `department_ref_id=<int>` — по справочнику отделов (`Department.id`) — рекомендуется использовать именно это.
  - `department=<string>` — по старому строковому названию; для нового фронта лучше не использовать.
- **Пагинация**:
  - `page=<int>` — номер страницы (с 1).
  - `page_size=<int>` — размер страницы (по умолчанию 50, максимум 200).
- **Сортировка** (опционально):
  - `ordering=<поле>[,<поле>...]`
  - допустимые поля: `date`, `worked_hours`, `lateness_minutes`, `overtime_minutes`
  - для убывания: `-date`, `-worked_hours` и т.п.

**Ответ 200 OK** (DRF‑пагинация):

```json
{
  "count": 123,
  "next": "http://<server>/api/daily-attendance-summaries/?page=2&date=2025-02-25",
  "previous": null,
  "results": [
    {
      "id": 1,
      "employee": 123,                     // id сотрудника
      "employee_external_id": "3060...",   // ПИНФЛ / внешний ID
      "employee_full_name": "Иванов Иван Иванович",
      "employee_department": "IT отдел",   // Department.name, если есть ref
      "employee_position": "Инженер",      // Position.name, если есть ref
      "employee_photo_url": "/media/employees/photos/123.jpg", // аватар (может быть null)
      "date": "2025-02-25",
      "first_entry": "2025-02-25T09:14:32+05:00",
      "last_exit": "2025-02-25T18:02:11+05:00",
      "worked_hours": 8.1,                 // часы (float)
      "lateness_minutes": 14,              // минуты опоздания
      "overtime_minutes": 10,              // переработка (минуты)
      "status": "Присутствует"             // "Отсутствует" / "Присутствует" / "Опоздал" / "Присутствовал"
    }
  ]
}
```

---

### 3. Список сотрудников

#### `GET /employees/`

**Назначение**: таблица сотрудников для страницы «Сотрудники».

**Параметры (query)**:

- `department_ref_id=<int>` — фильтр по отделу (справочник `Department.id`).
- `is_active=true|false|1|0` — только активные / только неактивные.
- `search=<строка>` — поиск по:
  - фамилии, имени, отчеству (`last_name`, `first_name`, `middle_name`, `icontains`);
  - `external_id`.
- Пагинация:
  - `page=<int>`
  - `page_size=<int>` (по умолчанию 50, максимум 200).

**Ответ 200 OK**:

```json
{
  "count": 45,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 123,
      "external_id": "3060...",          // ПИНФЛ / внешний ID
      "first_name": "Иван",
      "last_name": "Иванов",
      "middle_name": "Иванович",
      "full_name": "Иванов Иван Иванович",
      "department": "IT отдел",          // Department.name, если есть ref, иначе строковое поле
      "position": "Инженер",             // Position.name, если есть ref
      "phone_number": "+99890...",       // если заполнено
      "photo_url": "/media/employees/photos/123.jpg", // аватар (может быть null)
      "last_entry": "2025-02-25T09:14:32+05:00", // последняя отметка Вход (IN) или null
      "is_active": true,
      "status": "Активен"                // "Активен" / "Неактивен"
    }
  ]
}
```

#### `GET /employees/<id>/`

**Назначение**: детальная карточка сотрудника + его посещаемость за месяц (для страницы, как на скрине).

**Параметры**:

- `<id>` в пути.
- `month=YYYY-MM` (опционально) — за какой месяц отдавать статистику и историю; по умолчанию — текущий месяц.

**Ответ 200 OK**:

```json
{
  "id": 123,
  "external_id": "3060...",
  "first_name": "Иван",
  "last_name": "Иванов",
  "middle_name": "Иванович",
  "full_name": "Иванов Иван Иванович",
  "department": "IT отдел",
  "position": "Инженер",
  "phone_number": "+99890...",
  "photo_url": "/media/employees/photos/123.jpg",
  "last_entry": "2025-02-25T09:14:32+05:00",
  "is_active": true,
  "status": "Активен",
  "month_stats": {
    "month": "2025-02",
    "total_days_with_records": 18,   // сколько дней есть записи в DailyAttendanceSummary
    "present_days": 18,              // из них с первым входом
    "late_days": 3,                  // дней с опозданием
    "overtime_days": 1,              // дней с переработкой
    "total_worked_hours": 144.5,     // суммарно отработанные часы за месяц
    "attendance_percent": 100.0      // present_days / total_days_with_records * 100
  },
  "attendance_history": [
    {
      "id": 1,
      "employee": 123,
      "employee_external_id": "3060...",
      "employee_full_name": "Иванов Иван Иванович",
      "employee_department": "IT отдел",
      "employee_position": "Инженер",
      "employee_photo_url": "/media/employees/photos/123.jpg",
      "date": "2025-02-25",
      "first_entry": "2025-02-25T09:14:32+05:00",
      "last_exit": "2025-02-25T18:02:11+05:00",
      "worked_hours": 8.1,
      "lateness_minutes": 14,
      "overtime_minutes": 10,
      "status": "Присутствует"
    }
    // ... остальные дни месяца
  ]
}
```

#### `POST /employees/<id>/sync-to-devices/`

**Назначение**: отправить данные сотрудника на настроенные терминалы Hikvision (создать/обновить пользователя и загрузить фото).

**Параметры**: только `<id>` в пути.

**Конфигурация** (переменные окружения):

- Один терминал: `HIKVISION_DEVICE_URL`, `HIKVISION_USERNAME`, `HIKVISION_PASSWORD`
  - пример: `HIKVISION_DEVICE_URL=http://192.168.1.10` (без слэша в конце)
- Несколько терминалов: `HIKVISION_DEVICES` — JSON-массив:
  - `[{"base_url": "http://192.168.1.10", "username": "admin", "password": "..."}]`

**Ответ 200 OK**:

```json
{
  "results": [
    {
      "base_url": "http://192.168.1.10",
      "user_ok": true,
      "user_message": "ok",
      "photo_ok": true,
      "photo_message": "ok"
    }
  ]
}
```

Если устройств не задано: **400** с `"detail": "No Hikvision devices configured."`. В каждом элементе `results`: `user_ok` / `photo_ok` — успех запроса пользователя и загрузки фото; при отсутствии фото у сотрудника `photo_ok: false`, `photo_message: "no_photo"`.

---
