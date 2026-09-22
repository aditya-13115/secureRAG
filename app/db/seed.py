from __future__ import annotations

from app.db.database import SessionLocal, init_db
from app.db.models import Department, Role, User


ROLES = [
    {
        "code": "CEO",
        "name": "Chief Executive Officer",
        "description": "Full organization access",
        "is_global_access": True,
    },
    {
        "code": "CTO",
        "name": "Chief Technology Officer",
        "description": "Full organization access",
        "is_global_access": True,
    },
    {
        "code": "COFOUNDER",
        "name": "Co-Founder",
        "description": "Full organization access",
        "is_global_access": True,
    },
    {
        "code": "FINANCE_HEAD",
        "name": "Finance Head",
        "description": "Finance and HR access",
        "is_global_access": False,
    },
    {
        "code": "HR_HEAD",
        "name": "HR Head",
        "description": "HR and Finance access",
        "is_global_access": False,
    },
    {
        "code": "ENGINEER",
        "name": "Engineer",
        "description": "Technology access",
        "is_global_access": False,
    },
    {
        "code": "MANAGER",
        "name": "Manager",
        "description": "Management access",
        "is_global_access": False,
    },
    {
        "code": "MARKETING",
        "name": "Marketing",
        "description": "Marketing access",
        "is_global_access": False,
    },
    {
        "code": "EMPLOYEE",
        "name": "Employee",
        "description": "Public/company-wide access",
        "is_global_access": False,
    },
]


DEPARTMENTS = [
    ("FIN", "Finance"),
    ("HR", "Human Resources"),
    ("TECH", "Technology"),
    ("MGT", "Management"),
    ("MKT", "Marketing"),
    ("GENERAL", "General"),
]


ROLE_DEPARTMENT_MAPPING = {
    "FINANCE_HEAD": ["FIN", "HR"],
    "HR_HEAD": ["HR", "FIN"],
    "ENGINEER": ["TECH"],
    "MANAGER": ["MGT"],
    "MARKETING": ["MKT"],
}


USERS = [
    {
        "employee_code": "ME-0001",
        "email": "ceo@monke.ai",
        "full_name": "Arjun Malhotra",
        "role": "CEO",
        "department": "GENERAL",
    },
    {
        "employee_code": "ME-0002",
        "email": "cto@monke.ai",
        "full_name": "Vikram Rao",
        "role": "CTO",
        "department": "TECH",
    },
    {
        "employee_code": "ME-0003",
        "email": "cofounder@monke.ai",
        "full_name": "Riya Shah",
        "role": "COFOUNDER",
        "department": "GENERAL",
    },
    {
        "employee_code": "ME-0004",
        "email": "finance.head@monke.ai",
        "full_name": "Nisha Iyer",
        "role": "FINANCE_HEAD",
        "department": "FIN",
    },
    {
        "employee_code": "ME-0005",
        "email": "hr.head@monke.ai",
        "full_name": "Meera Rao",
        "role": "HR_HEAD",
        "department": "HR",
    },
    {
        "employee_code": "ME-0006",
        "email": "engineer@monke.ai",
        "full_name": "Aarav Menon",
        "role": "ENGINEER",
        "department": "TECH",
    },
    {
        "employee_code": "ME-0007",
        "email": "manager@monke.ai",
        "full_name": "Kabir Shah",
        "role": "MANAGER",
        "department": "MGT",
    },
    {
        "employee_code": "ME-0008",
        "email": "marketing@monke.ai",
        "full_name": "Ananya Kapoor",
        "role": "MARKETING",
        "department": "MKT",
    },
    {
        "employee_code": "ME-0009",
        "email": "employee@monke.ai",
        "full_name": "Rohan Das",
        "role": "EMPLOYEE",
        "department": "GENERAL",
    },
]


def seed_roles(session):
    role_map = {}

    for data in ROLES:
        role = (
            session.query(Role)
            .filter(Role.code == data["code"])
            .one_or_none()
        )

        if role is None:
            role = Role(**data)
            session.add(role)
            session.flush()

        role_map[role.code] = role

    return role_map


def seed_departments(session):
    department_map = {}

    for code, name in DEPARTMENTS:
        department = (
            session.query(Department)
            .filter(Department.code == code)
            .one_or_none()
        )

        if department is None:
            department = Department(
                code=code,
                name=name,
            )
            session.add(department)
            session.flush()

        department_map[department.code] = department

    return department_map


def seed_role_department_access(
    role_map,
    department_map,
):
    for role_code, department_codes in ROLE_DEPARTMENT_MAPPING.items():
        role = role_map[role_code]

        for department_code in department_codes:
            department = department_map[department_code]

            if department not in role.accessible_departments:
                role.accessible_departments.append(department)


def seed_users(
    session,
    role_map,
    department_map,
):
    for data in USERS:
        existing = (
            session.query(User)
            .filter(User.email == data["email"])
            .one_or_none()
        )

        if existing:
            continue

        user = User(
            employee_code=data["employee_code"],
            email=data["email"],
            full_name=data["full_name"],
            role=role_map[data["role"]],
            department=department_map[data["department"]],
        )

        session.add(user)


def main():
    init_db()

    with SessionLocal() as session:
        role_map = seed_roles(session)
        department_map = seed_departments(session)

        seed_role_department_access(
            role_map,
            department_map,
        )

        seed_users(
            session,
            role_map,
            department_map,
        )

        session.commit()

    print("Database seeded successfully.")


if __name__ == "__main__":
    main()