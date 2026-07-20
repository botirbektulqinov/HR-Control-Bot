import datetime as dt
import hashlib
import secrets
from html import escape
from types import SimpleNamespace
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.config import get_settings
from app.db.base import Session
from app.db.models import Attendance, Employee

settings = get_settings()
app = FastAPI(title="HR Control Dashboard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.dashboard_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

bearer = HTTPBearer(auto_error=False)
# ponytail: process-local sessions; move to Redis/database when API uses multiple workers.
sessions: dict[str, dt.datetime] = {}
session_ttl = dt.timedelta(hours=12)


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


def _same_secret(left: str, right: str) -> bool:
    return secrets.compare_digest(
        hashlib.sha256(left.encode()).digest(), hashlib.sha256(right.encode()).digest()
    )


def require_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login required")
    expires_at = sessions.get(credentials.credentials)
    if expires_at is None or expires_at <= dt.datetime.now(dt.timezone.utc):
        sessions.pop(credentials.credentials, None)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    return credentials.credentials


def _avatar(name: str) -> str:
    initials = "".join(part[0] for part in name.split()[:2]).upper() or "HR"
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128">'
        '<rect width="100%" height="100%" fill="#2563eb"/>'
        f'<text x="50%" y="54%" text-anchor="middle" dominant-baseline="middle" '
        f'font-family="Arial" font-size="44" font-weight="700" fill="white">{escape(initials)}</text>'
        "</svg>"
    )
    return f"data:image/svg+xml,{quote(svg)}"


def _employee_dict(employee: Employee) -> dict:
    schedule = employee.schedule
    working_hours = (
        f"{schedule.start_time:%H:%M} - {schedule.end_time:%H:%M}"
        if schedule
        else ""
    )
    return {
        "id": f"EMP-{employee.id:03d}",
        "photo": _avatar(employee.full_name),
        "fullName": employee.full_name,
        "phone": employee.phone or "",
        "telegramUsername": employee.telegram_username or "",
        "telegramId": str(employee.telegram_id or ""),
        "email": "",
        "department": employee.department or "Unassigned",
        "position": employee.position or "Employee",
        "branch": employee.branch.name if employee.branch else "Unassigned",
        "manager": "",
        "status": "Active" if employee.is_active else "Inactive",
        "workingHours": working_hours,
        "hireDate": employee.created_at.date().isoformat() if employee.created_at else "",
        "salary": 0,
        "documents": [],
        "qrCode": f"HR-{employee.id}",
        "faceVerification": False,
        "gpsEnabled": employee.branch is not None,
    }


def _attendance_status(row: Attendance) -> str:
    if row.check_in_at is None:
        return "Absent"
    if row.status in {"late", "very_late"}:
        return "Late"
    if row.early_leave_minutes:
        return "Early Leave"
    return "Present"


def _local_time(value: dt.datetime | None, timezone: str) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(ZoneInfo(timezone)).strftime("%H:%M")


def _attendance_dict(row: Attendance) -> dict:
    employee = row.employee
    branch = employee.branch
    timezone = branch.timezone if branch else settings.default_timezone
    gps_verified = bool(
        branch
        and row.check_in_lat is not None
        and row.check_in_lon is not None
        and row.check_in_distance_m is not None
        and row.check_in_distance_m <= branch.radius_m
    )
    location = None
    if row.check_in_lat is not None and row.check_in_lon is not None:
        location = f"{row.check_in_lat:.5f}, {row.check_in_lon:.5f}"
        if branch:
            location += f" ({branch.name})"
    return {
        "id": f"ATT-{row.id}",
        "employeeId": f"EMP-{employee.id:03d}",
        "employeeName": employee.full_name,
        "date": row.work_date.isoformat(),
        "checkIn": _local_time(row.check_in_at, timezone),
        "checkOut": _local_time(row.check_out_at, timezone),
        "workingHours": round(row.worked_minutes / 60, 2),
        "status": _attendance_status(row),
        "gpsVerified": gps_verified,
        "gpsLocation": location,
        "faceVerified": False,
        "overtime": round(row.overtime_minutes / 60, 2),
        "lateMinutes": row.late_minutes,
    }


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/login")
async def login(body: LoginBody) -> dict:
    if not settings.dashboard_email or not settings.dashboard_password:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Dashboard credentials are not configured",
        )
    if not (
        _same_secret(body.email.strip().lower(), settings.dashboard_email.lower())
        and _same_secret(body.password, settings.dashboard_password)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    now = dt.datetime.now(dt.timezone.utc)
    for expired_token, expiry in tuple(sessions.items()):
        if expiry <= now:
            sessions.pop(expired_token, None)
    token = secrets.token_urlsafe(32)
    sessions[token] = now + session_ttl
    return {"token": token, "role": "SUPER_ADMIN", "expiresIn": int(session_ttl.total_seconds())}


@app.delete("/api/logout")
async def logout(token: str = Depends(require_session)) -> dict[str, bool]:
    sessions.pop(token, None)
    return {"ok": True}


@app.get("/api/bootstrap")
async def bootstrap(
    days: int = Query(30, ge=7, le=366), _: str = Depends(require_session)
) -> dict:
    today = dt.datetime.now(ZoneInfo(settings.default_timezone)).date()
    since = today - dt.timedelta(days=days - 1)
    async with Session() as session:
        employees = (
            await session.scalars(select(Employee).order_by(Employee.full_name))
        ).all()
        attendance = (
            await session.scalars(
                select(Attendance)
                .where(Attendance.work_date >= since)
                .order_by(Attendance.work_date.desc(), Attendance.check_in_at.desc())
            )
        ).all()
    return {
        "employees": [_employee_dict(employee) for employee in employees],
        "attendance": [_attendance_dict(row) for row in attendance],
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    branch = SimpleNamespace(name="HQ", timezone="Asia/Tashkent", radius_m=200)
    schedule = SimpleNamespace(start_time=dt.time(9), end_time=dt.time(18))
    employee = SimpleNamespace(
        id=1, full_name="Test User", phone=None, telegram_username="test",
        telegram_id=123, department="IT", position=None, branch=branch,
        schedule=schedule, is_active=True, created_at=dt.datetime(2026, 1, 1),
    )
    mapped_employee = _employee_dict(employee)
    assert mapped_employee["id"] == "EMP-001" and mapped_employee["workingHours"] == "09:00 - 18:00"
    attendance = SimpleNamespace(
        id=2, employee=employee, work_date=dt.date(2026, 1, 1),
        check_in_at=dt.datetime(2026, 1, 1, 4, tzinfo=dt.timezone.utc),
        check_out_at=None, worked_minutes=0, status="on_time",
        early_leave_minutes=0, check_in_lat=41.3, check_in_lon=69.2,
        check_in_distance_m=10, overtime_minutes=0, late_minutes=0,
    )
    mapped_attendance = _attendance_dict(attendance)
    assert mapped_attendance["checkIn"] == "09:00" and mapped_attendance["gpsVerified"] is True
    assert _attendance_status(SimpleNamespace(check_in_at=None, status="absent", early_leave_minutes=0)) == "Absent"
    assert _attendance_status(SimpleNamespace(check_in_at=object(), status="late", early_leave_minutes=0)) == "Late"
    assert _attendance_status(SimpleNamespace(check_in_at=object(), status="on_time", early_leave_minutes=5)) == "Early Leave"
    print("dashboard api mapping ok")
