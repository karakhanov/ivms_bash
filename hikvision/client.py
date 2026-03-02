"""
Hikvision ISAPI client: create/update user (UserInfo) and upload face photo (FDLib).
Config from Django settings: HIKVISION_DEVICE_URL, HIKVISION_USERNAME, HIKVISION_PASSWORD.
Optional: HIKVISION_DEVICES as JSON list of {base_url, username, password} for multiple devices.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from requests.auth import HTTPDigestAuth

logger = logging.getLogger(__name__)


def _get_devices_config() -> list[dict[str, str]]:
    """
    Список конфигов устройств Hikvision.

    Приоритет:
    1) settings.HIKVISION_DEVICES (JSON/список)
    2) settings.HIKVISION_DEVICE_URL + USERNAME/PASSWORD (один девайс)
    3) Модель Device (is_active=True, есть address), при наличии
       HIKVISION_USERNAME / HIKVISION_PASSWORD — используем один логин/пароль
       для всех найденных терминалов.
    """
    from django.conf import settings

    devices = getattr(settings, "HIKVISION_DEVICES", None)
    if devices is not None:
        if isinstance(devices, str):
            devices = json.loads(devices)
        if devices:
            return devices
    base_url = getattr(settings, "HIKVISION_DEVICE_URL", "") or ""
    username = getattr(settings, "HIKVISION_USERNAME", "") or ""
    password = getattr(settings, "HIKVISION_PASSWORD", "") or ""
    if base_url and username:
        return [{"base_url": base_url.rstrip("/"), "username": username, "password": password}]

    # Если в настройках явных устройств нет, пробуем взять активные терминалы из БД.
    if username and password:
        try:
            from attendance.models import Device

            qs = Device.objects.filter(is_active=True).exclude(address__isnull=True).exclude(address="")
            configs: list[dict[str, str]] = []
            for dev in qs:
                addr = str(dev.address).strip()
                if not addr:
                    continue
                # Допускаем, что в address может быть уже URL; если нет схемы — добавляем http://
                if addr.startswith("http://") or addr.startswith("https://"):
                    base = addr.rstrip("/")
                else:
                    base = f"http://{addr}".rstrip("/")
                configs.append({"base_url": base, "username": username, "password": password})
            if configs:
                return configs
        except Exception:
            # Не ломаемся, если миграций ещё нет или нет таблицы Device.
            logger.exception("Failed to load Device-based Hikvision configs")

    return []


def _full_name(employee: Any) -> str:
    parts = [
        getattr(employee, "last_name", ""),
        getattr(employee, "first_name", ""),
        getattr(employee, "middle_name", ""),
    ]
    return " ".join(p for p in parts if p).strip() or str(employee)


def _session(base_url: str, username: str, password: str, timeout: int = 15) -> requests.Session:
    s = requests.Session()
    s.auth = HTTPDigestAuth(username, password)
    s.headers["Content-Type"] = "application/json"
    s.timeout = timeout
    s.verify = False  # many devices use self-signed certs
    return s


def create_or_update_user(
    base_url: str, username: str, password: str, employee: Any
) -> tuple[bool, str]:
    """
    POST UserInfo to Hikvision device. Returns (success, message).
    employee must have: external_id, first_name, last_name, middle_name (optional).
    """
    url = f"{base_url}/ISAPI/AccessControl/UserInfo/Record?format=json"
    payload = {
        "UserInfo": {
            "employeeNo": str(employee.external_id),
            "name": _full_name(employee),
            "userType": "normal",
            "doorRight": "1",
            "RightPlan": [{"doorNo": 1, "planTemplateNo": "1"}],
            "Valid": {
                "enable": True,
                "beginTime": "2020-01-01T00:00:00",
                "endTime": "2035-12-31T23:59:59",
                "timeType": "local",
            },
        }
    }
    try:
        s = _session(base_url, username, password)
        r = s.post(url, json=payload)
        if r.status_code in (200, 201):
            return True, "ok"
        # Если пользователь с таким employeeNo уже существует,
        # устройство возвращает employeeNoAlreadyExist. В этом случае
        # считаем, что пользователь есть, и продолжаем (например, для обновления фото).
        try:
            data = r.json()
        except ValueError:
            data = {}
        if (
            r.status_code == 400
            and isinstance(data, dict)
            and data.get("subStatusCode") == "employeeNoAlreadyExist"
        ):
            return True, "employeeNoAlreadyExist"
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except requests.RequestException as e:
        logger.exception("Hikvision UserInfo request failed")
        return False, str(e)


def upload_employee_photo(
    base_url: str, username: str, password: str, employee: Any
) -> tuple[bool, str]:
    """
    Upload face image to device FDLib. employee must have photo (ImageField) and external_id.
    Returns (success, message).
    """
    photo = getattr(employee, "photo", None)
    if not photo or not photo.name:
        return False, "no_photo"
    try:
        with photo.open("rb") as f:
            image_data = f.read()
    except OSError as e:
        return False, str(e)
    if not image_data:
        return False, "empty_photo"

    url = f"{base_url}/ISAPI/Intelligent/FDLib/FaceDataRecord?format=json"
    # FPID must match employeeNo on device (user must exist)
    fpid = str(employee.external_id)
    fdid = "1"  # default face DB id on device
    meta = {
        "faceLibType": "blackFD",
        "FDID": fdid,
        "FPID": fpid,
    }
    files = [
        ("FaceDataRecord", ("", json.dumps(meta), "application/json")),
        ("FaceImage", ("face.jpg", image_data, "image/jpeg")),
    ]
    try:
        s = _session(base_url, username, password)
        # multipart: do not set Content-Type, let requests set boundary
        s.headers.pop("Content-Type", None)
        r = s.post(url, files=files)
        if r.status_code in (200, 201):
            return True, "ok"
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except requests.RequestException as e:
        logger.exception("Hikvision FaceDataRecord request failed")
        return False, str(e)


def sync_employee_to_devices(employee: Any) -> list[dict[str, Any]]:
    """
    For each configured device: create/update user, then upload photo if present.
    Returns list of { "base_url", "user_ok", "user_message", "photo_ok", "photo_message" }.
    """
    results = []
    for cfg in _get_devices_config():
        base_url = cfg.get("base_url", "")
        username = cfg.get("username", "")
        password = cfg.get("password", "")
        if not base_url or not username:
            results.append({
                "base_url": base_url or "(empty)",
                "user_ok": False,
                "user_message": "missing base_url or username",
                "photo_ok": False,
                "photo_message": "skipped",
            })
            continue
        user_ok, user_msg = create_or_update_user(base_url, username, password, employee)
        photo_ok, photo_msg = False, "no_photo"
        if user_ok and getattr(employee, "photo", None) and employee.photo.name:
            photo_ok, photo_msg = upload_employee_photo(base_url, username, password, employee)
        results.append({
            "base_url": base_url,
            "user_ok": user_ok,
            "user_message": user_msg,
            "photo_ok": photo_ok,
            "photo_message": photo_msg,
        })
    return results
