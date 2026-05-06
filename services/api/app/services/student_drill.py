from __future__ import annotations

from ..db.models import Student

ADMIN_DRILL_STUDENT_NOS = frozenset({"bujiuhong6"})


def is_admin_drill_student(student: Student) -> bool:
    return (student.student_no or "").strip().lower() in ADMIN_DRILL_STUDENT_NOS
