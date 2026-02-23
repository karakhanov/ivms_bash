from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from django.utils import timezone

from .models import AttendanceLog


@dataclass
class AttendanceDaySummary:
    employee_id: int
    date: date
    first_in: Optional[datetime]
    last_out: Optional[datetime]
    worked_hours: float
    lateness_minutes: int
    overtime_minutes: int

    def to_dict(self) -> Dict:
        return asdict(self)


class AttendanceCalculationService:
    """
    Pure calculation service for attendance statistics.

    Expects logs to be fetched by selectors; does not perform DB queries.
    """

    WORK_START = time(hour=9, minute=0)
    WORK_END = time(hour=18, minute=0)

    @classmethod
    def calculate_daily_attendance(
        cls, logs: Iterable[AttendanceLog]
    ) -> Dict[int, Dict[date, Dict]]:
        """
        Group logs by employee and date, calculate first IN, last OUT,
        worked hours, lateness, and overtime.

        Returns:
            {
              employee_id: {
                date: {
                  "employee_id": int,
                  "date": date,
                  "first_in": datetime | None,
                  "last_out": datetime | None,
                  "worked_hours": float,   # hours
                  "lateness_minutes": int,
                  "overtime_minutes": int,
                },
                ...
              },
              ...
            }
        """
        # Normalize to aware datetimes in current timezone
        def normalize_dt(dt: datetime) -> datetime:
            if timezone.is_naive(dt):
                return timezone.make_aware(dt, timezone.get_current_timezone())
            return dt.astimezone(timezone.get_current_timezone())

        grouped: Dict[Tuple[int, date], List[AttendanceLog]] = defaultdict(list)

        for log in logs:
            event_dt = normalize_dt(log.event_time)
            key = (log.employee_id, event_dt.date())
            grouped[key].append(log)

        result: Dict[int, Dict[date, Dict]] = defaultdict(dict)

        for (employee_id, day), day_logs in grouped.items():
            # Separate IN and OUT logs and sort by time
            in_logs: List[AttendanceLog] = []
            out_logs: List[AttendanceLog] = []

            for log in day_logs:
                if log.event_type == AttendanceLog.EventType.IN:
                    in_logs.append(log)
                elif log.event_type == AttendanceLog.EventType.OUT:
                    out_logs.append(log)

            if in_logs:
                first_in_dt = normalize_dt(min(in_logs, key=lambda l: l.event_time).event_time)
            else:
                first_in_dt = None

            if out_logs:
                last_out_dt = normalize_dt(max(out_logs, key=lambda l: l.event_time).event_time)
            else:
                last_out_dt = None

            # Worked hours
            if first_in_dt and last_out_dt and last_out_dt > first_in_dt:
                worked_delta: timedelta = last_out_dt - first_in_dt
                worked_hours = worked_delta.total_seconds() / 3600.0
            else:
                worked_hours = 0.0

            # Lateness (minutes after 09:00)
            if first_in_dt:
                scheduled_start = datetime.combine(day, cls.WORK_START, tzinfo=first_in_dt.tzinfo)
                if first_in_dt > scheduled_start:
                    lateness_minutes = int(
                        (first_in_dt - scheduled_start).total_seconds() // 60
                    )
                else:
                    lateness_minutes = 0
            else:
                lateness_minutes = 0

            # Overtime (minutes after 18:00)
            if last_out_dt:
                scheduled_end = datetime.combine(day, cls.WORK_END, tzinfo=last_out_dt.tzinfo)
                if last_out_dt > scheduled_end:
                    overtime_minutes = int(
                        (last_out_dt - scheduled_end).total_seconds() // 60
                    )
                else:
                    overtime_minutes = 0
            else:
                overtime_minutes = 0

            summary = AttendanceDaySummary(
                employee_id=employee_id,
                date=day,
                first_in=first_in_dt,
                last_out=last_out_dt,
                worked_hours=worked_hours,
                lateness_minutes=lateness_minutes,
                overtime_minutes=overtime_minutes,
            )

            result[employee_id][day] = summary.to_dict()

        return result

