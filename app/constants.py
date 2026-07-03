from enum import StrEnum


class Role(StrEnum):
    EMPLOYEE = "employee"
    HR = "hr"
    SUPER_ADMIN = "super_admin"


class Status(StrEnum):
    ON_TIME = "on_time"
    LATE = "late"
    VERY_LATE = "very_late"
    ABSENT = "absent"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    OUTSIDE_RADIUS = "outside_radius"
    INVALID_LOCATION = "invalid_location"


# Check-in kechikish darajasi (daqiqa). grace dan keyingi chegaralar.
VERY_LATE_THRESHOLD_MIN = 60
