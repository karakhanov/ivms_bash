## IVMS Backend API

Актуальная документация для фронтенда по основным REST‑эндпоинтам.

### Общие сведения

- **Базовый URL**: `http://<server>/api/`
- **Формат**: JSON

### Аутентификация

Все эндпоинты, кроме вебхука терминалов, требуют **Token Authentication**.

1. **Вход по логину и паролю** (рекомендуется для фронта): `POST /api/auth/login/`
   - Тело (JSON): `{"username": "<логин>", "password": "<пароль>"}`
   - Ответ 200: `{"token": "<строка-токен>", "user": {"id": 1, "username": "...", "is_staff": true}}`
   - Ответ 401: `{"error": "Неверный логин или пароль."}`
   - Пользователь создаётся в админке (Users) или через `createsuperuser`.

2. **Текущий пользователь**: `GET /api/auth/me/`
   - Заголовок: `Authorization: Token <токен>`
   - Ответ 200: `{"id": 1, "username": "...", "is_staff": true}`

3. **Получить только токен** (классический DRF): `POST /api/auth/token/`
   - Тело (JSON): `{"username": "<логин>", "password": "<пароль>"}`
   - Ответ 200: `{"token": "<строка-токен>"}`

4. **Использовать токен** в запросах к API:
   - Заголовок: `Authorization: Token <строка-токен>`
   - Пример: `Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b`

5. **Без токена** (или с неверным): ответ **401 Unauthorized**.

6. **Вебхук терминалов** (`POST /api/ivms/events/`, `POST /api/ivms/webhook/`) **не требует** авторизации — терминалы не передают заголовок; доступ при необходимости ограничивают файрволом или отдельным секретом в заголовке.

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
      "online": 0,            // количество онлайн‑устройств
      "total": 0              // всего устройств
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

#### `POST /employees/` — создать сотрудника

**Назначение**: создание нового сотрудника через API (форма для операторов или админ‑панели фронтенда).

**Тело (JSON или `multipart/form-data`)** — основные поля (без вычисляемых):

```json
{
  "external_id": "3250...",
  "first_name": "Ali",
  "last_name": "Valiyev",
  "middle_name": "Karimovich",
  "department_ref": 1,
  "position_ref": 2,
  "work_schedule_ref": 1,
  "pinfl": "3250...",
  "phone_number": "+99890...",
  "gender": "male",
  "is_active": true
}
```

- `gender`: `"male" | "female" | "other" | ""`.
- `department_ref`, `position_ref`, `work_schedule_ref` — id из соответствующих справочников.
- Фото (`photo`) отправляется как `multipart/form-data` (FormData на фронте) **в одном запросе** вместе с остальными полями.
- `external_id` (обычно ПИНФЛ) **должен быть уникальным**: при попытке создать дубликат вернётся `400 Bad Request` с сообщением `{"external_id": ["Сотрудник с таким external_id уже существует."]}`.

**Ответ 201 Created** — JSON в формате `GET /employees/<id>/` (но без `month_stats` и `attendance_history`).

#### `PUT /employees/<id>/`, `PATCH /employees/<id>/` — изменить сотрудника

**Назначение**: редактирование данных сотрудника.

- `PUT` — полная замена (как при создании).
- `PATCH` — частичное обновление (можно передать только изменённые поля).

Формат тела такой же, как у `POST /employees/`.  
Фото обновляется также через `multipart/form-data` (`photo` можно не отправлять, тогда останется прежним).

**Ответ 200 OK** — обновлённый сотрудник.

#### `DELETE /employees/<id>/` — удалить сотрудника

**Назначение**: удалить сотрудника из базы (обычно использовать осторожно, предпочтительнее делать `is_active = false`).

**Ответ 204 No Content** — без тела.

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
### 5. Роли пользователей и ограничения для операторов ввода

На уровне прав доступа к API различаются два типа пользователей:

- **Администраторы / персонал** (`is_staff = true` или `is_superuser = true`):
  - полный доступ ко всем действиям Employee API:
    - `GET /employees/`, `GET /employees/<id>/`
    - `POST /employees/`
    - `PUT/PATCH/DELETE /employees/<id>/`
    - `POST /employees/<id>/sync-to-devices/`
  - доступ ко всем остальным эндпоинтам (дашборд, посещаемость и т.д.).

- **Обычные пользователи (операторы ввода)** (`is_staff = false`, `is_superuser = false`):
  - могут **только создавать** новых сотрудников:
    - `POST /employees/`
  - не могут:
    - просматривать список сотрудников (`GET /employees/` → `403 Forbidden`),
    - открывать карточки сотрудников (`GET /employees/<id>/` → `403 Forbidden`),
    - изменять или удалять сотрудников,
    - вызывать `sync-to-devices` и другие служебные операции.

Типичный сценарий для оператора:

1. Получить токен через `POST /api/auth/login/` с логином/паролем, выданными администратором.
2. Использовать этот токен для единственного разрешённого действия: отправки формы создания сотрудника (`POST /api/employees/`) с полями ПИНФЛ, Ф.И.О., отдел, должность, телефон и фото (как `multipart/form-data`).
3. При попытке сделать что‑то ещё (список, деталка, изменение, удаление) API вернёт `403 Forbidden`.

---

### 4. Вебхук терминалов iVMS (Hikvision)

#### URL

- `POST /api/ivms/events/`
- `POST /api/ivms/webhook/`

Оба URL обрабатываются одинаково (`IvmsEventAPIView`), различие только в названии роутов.

#### Аутентификация

- **Без авторизации** (`AllowAny`): терминалы не умеют передавать токен.
- Защита рекомендуется на уровне сети (Firewall, IP‑фильтрация, отдельный секрет в заголовке).

#### Формат запроса (основной кейс AccessControllerEvent)

Тело запроса — JSON, похожий на стандартный Hikvision `AccessControllerEvent`:

```json
{
  "eventType": "AccessControllerEvent",
  "ipAddress": "192.168.68.10",
  "dateTime": "2026-02-23T09:00:00+00:00",
  "AccessControllerEvent": {
    "employeeNoString": "EXT-1",
    "name": "Webhook User",
    "attendanceStatus": "checkIn"
  }
}
```

- **`eventType`**:
  - `"AccessControllerEvent"` — создаётся событие посещаемости.
  - `"heartBeat"` — просто проверка связи, без создания событий.
  - любые другие значения — игнорируются.
- **`employeeNoString`** → используется как `external_id` сотрудника.
- **`ipAddress`** → используется как `device_id` и IP‑адрес устройства.
- **`dateTime`** → время события (конвертируется в локальную таймзону).

#### Логика обработки

- Если `eventType = "heartBeat"`:
  - ответ: `200 OK`, тело: `{"status": "ok"}`.
- Если `eventType` не `"AccessControllerEvent"` и не `"heartBeat"`:
  - ответ: `200 OK`, тело: `{"status": "ignored"}`.
- Если `eventType = "AccessControllerEvent"`:
  - по `employeeNoString` ищется сотрудник `Employee.external_id`.
  - **Если сотрудник найден**:
    - создаётся запись `AttendanceLog` (если такого же события ещё не было),
    - пересчитывается и обновляется `DailyAttendanceSummary` за соответствующий день,
    - создаётся/обновляется `Device` по IP‑адресу (если нужно),
    - ответ: `201 Created`, тело:

      ```json
      {
        "id": 1,
        "employee_id": 123,
        "event_type": "IN",
        "event_time": "2026-02-23T14:00:00+05:00"
      }
      ```

  - **Если сотрудник с таким `external_id` не найден**:
    - **сотрудник не создаётся автоматически**,
    - событие игнорируется (лог и сводка не создаются),
    - ответ: `200 OK`, тело: `{"status": "ignored"}`.
  - **Если такое же событие уже было записано** (дубликат по сотруднику, устройству, типу и точному времени):
    - лог повторно не создаётся,
    - ответ: `200 OK`, тело: `{"status": "ignored", "reason": "duplicate"}`.

> **Важно**: сотрудники должны быть заведены заранее (импортом или через админку/CRUD API).  
> Вебхук не создаёт сотрудников автоматически, он только фиксирует события для уже существующих `Employee`.

---
