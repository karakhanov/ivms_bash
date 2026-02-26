# Настройка сервера для домена (IVMS Backend)

## 1. DNS

У регистратора домена создайте **A-запись**:
- Имя: `@` или `api` (для api.ваш-домен.ru)
- Значение: IP вашего сервера (например 95.46.96.135)

## 2. Django и переменные окружения

### 2.1 Настройки Django

В `core/settings.py`:
- Добавьте домен в **ALLOWED_HOSTS** (например `"api.ваш-домен.ru"`).
- Для продакшена установите `DEBUG = False` и задайте собственный `SECRET_KEY`.

Рекомендуется задавать чувствительные значения через переменные окружения:

- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` — параметры PostgreSQL.
- `DJANGO_SECRET_KEY` — секретный ключ (можно потом использовать его в `settings.py` вместо захардкоженного).
- `DJANGO_DEBUG` — `"False"` в продакшене.
- `DJANGO_ALLOWED_HOSTS` — при желании можно использовать для генерации списка `ALLOWED_HOSTS`.

### 2.2 Hikvision (несколько терминалов)

Для отправки сотрудников на терминалы (`POST /api/employees/<id>/sync-to-devices/`) используются переменные окружения:

- Один терминал:
  - `HIKVISION_DEVICE_URL` — например `http://192.168.1.10`
  - `HIKVISION_USERNAME` — логин на устройстве (обычно `admin`)
  - `HIKVISION_PASSWORD` — пароль

- Несколько терминалов:
  - `HIKVISION_DEVICES` — JSON‑массив:
    - `[{ "base_url": "http://192.168.1.10", "username": "admin", "password": "pass1" }]`

Сами терминалы должны быть настроены так, чтобы слать события на вебхук бэкенда:

- URL: `http://<SERVER_IP>/api/ivms/events/`

### 2.3 Сбор статики

```bash
python3 manage.py collectstatic --noinput
```

## 3. Сервер (Linux)

### 3.1 Зависимости
```bash
sudo apt update
sudo apt install python3-venv python3-pip nginx postgresql
```

### 3.2 Проект и venv
```bash
sudo mkdir -p /var/www/ivms_backend
sudo chown $USER:$USER /var/www/ivms_backend
# склонируйте/скопируйте проект в /var/www/ivms_backend
cd /var/www/ivms_backend
python3 -m venv venv
source venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# миграции и статика
python3 manage.py migrate
python3 manage.py collectstatic --noinput
```

### 3.3 Gunicorn (systemd)
```bash
sudo cp deploy/ivms-backend.service.example /etc/systemd/system/ivms-backend.service
# Отредактируйте User, WorkingDirectory, путь к venv
sudo systemctl daemon-reload
sudo systemctl enable ivms-backend
sudo systemctl start ivms-backend
```

### 3.4 Nginx
```bash
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/ivms
# Замените api.ваш-домен.ru на ваш домен
sudo ln -s /etc/nginx/sites-available/ivms /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3.5 HTTPS (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d api.ваш-домен.ru
```

### 3.6 Файрвол
```bash
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 22
sudo ufw enable
```

## 4. Проверка

- `curl http://api.ваш-домен.ru/` — ответ от приложения.
- После certbot: `https://api.ваш-домен.ru/`
