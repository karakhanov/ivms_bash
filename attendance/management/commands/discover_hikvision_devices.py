from __future__ import annotations

import ipaddress
import logging
from typing import Optional

import requests
import urllib3
from django.conf import settings
from django.core.management.base import BaseCommand

from attendance.models import Device

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Scan a subnet for Hikvision devices by MAC prefix and create/update "
        "Device records."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--network",
            type=str,
            default=getattr(settings, "HIKVISION_SCAN_NETWORK", "192.168.68.0/24"),
            help=(
                "IPv4 network in CIDR notation to scan, e.g. 192.168.68.0/24. "
                "Default comes from settings.HIKVISION_SCAN_NETWORK or "
                "192.168.68.0/24."
            ),
        )
        parser.add_argument(
            "--mac-prefix",
            type=str,
            default=getattr(settings, "HIKVISION_MAC_PREFIX", "88:de:39"),
            help=(
                "MAC address prefix to match (case-insensitive), e.g. 88:de:39 "
                "for Hikvision devices."
            ),
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=2.0,
            help="HTTP request timeout in seconds for each device probe.",
        )

    def handle(self, *args, **options) -> None:
        network_str: str = options["network"]
        mac_prefix: str = options["mac_prefix"].lower()
        timeout: float = options["timeout"]

        username: str = getattr(settings, "HIKVISION_USERNAME", "") or ""
        password: str = getattr(settings, "HIKVISION_PASSWORD", "") or ""

        if not username or not password:
            self.stderr.write(
                self.style.ERROR(
                    "HIKVISION_USERNAME and HIKVISION_PASSWORD must be set in settings "
                    "or environment to scan devices."
                )
            )
            return

        try:
            network = ipaddress.ip_network(network_str, strict=False)
        except ValueError as exc:
            self.stderr.write(self.style.ERROR(f"Invalid network '{network_str}': {exc}"))
            return

        self.stdout.write(
            self.style.NOTICE(
                f"Scanning network {network} for Hikvision devices "
                f"(MAC prefix {mac_prefix})..."
            )
        )

        found = 0
        updated = 0

        for ip in network.hosts():
            ip_str = str(ip)
            mac, name = self._probe_device(ip_str, username, password, timeout)
            if not mac:
                continue

            norm_mac = mac.replace("-", ":").lower()
            if not norm_mac.startswith(mac_prefix):
                continue

            found += 1
            device_name = name or f"Hikvision {ip_str}"

            obj, created = Device.objects.update_or_create(
                device_id=ip_str,
                defaults={
                    "name": device_name,
                    "address": ip_str,
                    "mac_address": norm_mac,
                    "is_active": True,
                },
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Discovered device {obj.name} at {obj.address} (MAC {obj.mac_address})"
                    )
                )
            else:
                updated += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated device {obj.name} at {obj.address} (MAC {obj.mac_address})"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Scan finished. Matching devices: {found}, updated existing: {updated}."
            )
        )

    @staticmethod
    def _probe_device(
        ip: str, username: str, password: str, timeout: float
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Try to query /ISAPI/System/deviceInfo on the given IP.
        Returns (mac_address, device_name) if this looks like a Hikvision device,
        otherwise (None, None).
        """
        from requests.auth import HTTPDigestAuth

        base_url = f"http://{ip}"
        url = f"{base_url}/ISAPI/System/deviceInfo?format=json"

        try:
            resp = requests.get(
                url,
                auth=HTTPDigestAuth(username, password),
                timeout=timeout,
                verify=False,
            )
        except requests.RequestException:
            logger.debug("Failed to connect to %s", ip, exc_info=True)
            return None, None

        if resp.status_code != 200:
            return None, None

        try:
            data = resp.json()
        except ValueError:
            logger.debug("Non-JSON response from %s: %r", ip, resp.text[:200])
            return None, None

        info = data.get("DeviceInfo") or data
        mac = info.get("macAddress") or info.get("mac") or ""
        name = info.get("deviceName") or info.get("name") or None

        mac = str(mac).strip()
        if not mac:
            return None, None

        return mac, name

