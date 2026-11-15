from datetime import date, datetime, timedelta, timezone

from app.core.errors import AppError


def parse_date(value: str, field: str = "date") -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise AppError(f"{field} : format attendu AAAA-MM-JJ.", code="invalid_date", details={"value": value}) from exc


def day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)
