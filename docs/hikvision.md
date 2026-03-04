## Hikvision терминалы и интеграция с IVMS

Этот файл описывает, как настроить и сопровождать терминалы Hikvision, которые отправляют события в IVMS и обнаруживаются через локальную сеть.

---

## 1. Терминалы и их IP / MAC

Терминалы Hikvision в сети определяются по их MAC-адресам, которые начинаются с префикса:

- `88:de:39:...`

Пример вывода `arp-scan -l`:

```text
192.168.68.113  88:de:39:42:ed:dd
192.168.68.116  88:de:39:42:ed:e3
```

Оба этих устройства должны попадать в таблицу `attendance_device`.

---

## 2. Обнаружение терминалов (discover_devices / refresh_devices)

### 2.1. Команда `discover_devices`

Базовая команда (на сервере в том же сегменте сети, что и терминалы):

```bash
cd /srv/ivms_bash
python manage.py discover_devices --subnet 192.168.68.0/24 --interface enp2s0
```

Что она делает:

- запускает `arp-scan` по указанной подсети и интерфейсу;
- парсит пары `(IP, MAC)`;
- фильтрует только устройства, чьи MAC начинаются на префиксы из настройки `DISCOVER_DEVICE_MAC_PREFIXES` (по умолчанию — только Hikvision `88:de:39`);
- по каждому `(IP, MAC)`:
  - если в БД есть устройство с таким `mac_address` — обновляет `address` и `device_id` этим IP;
  - иначе, если есть запись по этому IP (`address` или `device_id`) — дописывает `mac_address`;
  - иначе создаёт новое устройство с `device_id = IP`, `address = IP`, `mac_address = MAC`, `is_active = True`.

### 2.2. Команда `refresh_devices` (укороченный алиас)

Чтобы не писать каждый раз длинную команду, есть специальная management-команда:

```bash
python manage.py refresh_devices
```

Она жёстко использует параметры:

- `subnet="192.168.68.0/24"`
- `interface="enp2s0"`
- `arp_only=False`

То есть фактически это:

```bash
python manage.py discover_devices --subnet 192.168.68.0/24 --interface enp2s0
```

Рекомендуется для ручного обновления устройств на боевом сервере вызывать именно:

```bash
python manage.py refresh_devices
```

---

## 3. Настройка MAC-префиксов в settings

Чтобы ограничить список устройств только терминалами Hikvision (и при необходимости добавить ещё типы устройств), используется настройка `DISCOVER_DEVICE_MAC_PREFIXES` в `core/settings.py`:

```python
DISCOVER_DEVICE_MAC_PREFIXES = [
    "88:de:39",  # все терминалы Hikvision
]
```

Особенности:

- фильтрация делается по `mac.lower().startswith(<префикс>)`;
- если список ПУСТОЙ (`[]` или `()`), фильтрация по префиксу отключается, и будут обрабатываться все устройства из `arp-scan` / ARP-таблицы;
- если указано несколько префиксов, то подойдут любые из них.

---

## 4. Проверка, что оба терминала попали в БД

На сервере:

```bash
cd /srv/ivms_bash
python manage.py shell
```

Внутри Django shell:

```python
from attendance.models import Device

list(
    Device.objects.filter(
        mac_address__istartswith="88:de:39"
    ).values("id", "device_id", "address", "mac_address")
)
```

Ожидается, что в списке будут все терминалы Hikvision, включая оба IP, найденных через `arp-scan` (например `192.168.68.113` и `192.168.68.116`).

---

## 5. Настройка push сотрудников на терминалы

Для интеграции с Hikvision API используются настройки в `core/settings.py`:

- `HIKVISION_DEVICE_URL` — URL одного терминала (если используется одиночное устройство);
- `HIKVISION_USERNAME` / `HIKVISION_PASSWORD` — логин и пароль администратора на терминале;
- `HIKVISION_DEVICES` (опционально) — JSON-массив с несколькими терминалами:

```bash
export HIKVISION_DEVICES='[
  {"base_url": "http://192.168.68.113", "username": "admin", "password": "pass"},
  {"base_url": "http://192.168.68.116", "username": "admin", "password": "pass"}
]'
```

При настройке следите, чтобы:

- IP терминалов совпадали с теми, что получены через `refresh_devices`;
- логины/пароли были актуальными и одинаковыми с теми, что заданы на самих устройствах.

