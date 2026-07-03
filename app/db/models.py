import datetime as dt

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import Role, Status
from app.db.base import Base


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    radius_m: Mapped[int] = mapped_column(Integer, default=150)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tashkent")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WorkSchedule(Base):
    __tablename__ = "work_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    start_time: Mapped[dt.time] = mapped_column(Time)
    end_time: Mapped[dt.time] = mapped_column(Time)
    grace_minutes: Mapped[int] = mapped_column(Integer, default=5)
    # ISO weekday: 1=Mon ... 7=Sun
    workdays: Mapped[str] = mapped_column(String(20), default="1,2,3,4,5")

    def workday_set(self) -> set[int]:
        return {int(x) for x in self.workdays.split(",") if x.strip()}


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    jshshir: Mapped[str] = mapped_column(String(14), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(32))
    department: Mapped[str | None] = mapped_column(String(120))
    position: Mapped[str | None] = mapped_column(String(120))
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"))
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("work_schedules.id"))
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(2), default="uz")
    role: Mapped[str] = mapped_column(String(20), default=Role.EMPLOYEE.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    branch: Mapped["Branch | None"] = relationship(lazy="joined")
    schedule: Mapped["WorkSchedule | None"] = relationship(lazy="joined")

    @property
    def is_admin(self) -> bool:
        return self.role in (Role.HR.value, Role.SUPER_ADMIN.value)


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("employee_id", "work_date", name="uq_att_emp_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"))
    work_date: Mapped[dt.date] = mapped_column(Date, index=True)

    check_in_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    check_in_lat: Mapped[float | None] = mapped_column(Float)
    check_in_lon: Mapped[float | None] = mapped_column(Float)
    check_in_accuracy: Mapped[float | None] = mapped_column(Float)
    check_in_distance_m: Mapped[float | None] = mapped_column(Float)

    check_out_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    check_out_lat: Mapped[float | None] = mapped_column(Float)
    check_out_lon: Mapped[float | None] = mapped_column(Float)
    check_out_accuracy: Mapped[float | None] = mapped_column(Float)
    check_out_distance_m: Mapped[float | None] = mapped_column(Float)

    status: Mapped[str] = mapped_column(String(30), default=Status.ON_TIME.value)
    late_minutes: Mapped[int] = mapped_column(Integer, default=0)
    early_leave_minutes: Mapped[int] = mapped_column(Integer, default=0)
    worked_minutes: Mapped[int] = mapped_column(Integer, default=0)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0)
    # anti-spoof ogohlantirishlari (JSON matn sifatida)
    flags: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    employee: Mapped["Employee"] = relationship(lazy="joined")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    action: Mapped[str] = mapped_column(String(60))
    target: Mapped[str | None] = mapped_column(String(120))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
