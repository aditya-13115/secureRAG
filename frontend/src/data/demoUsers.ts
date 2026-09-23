import type {
  DemoUser,
  RoleGroup,
} from "../types";

export const demoUsers: DemoUser[] = [
  {
    id: 1,
    name: "Arjun Malhotra",
    email: "ceo@monke.ai",
    role: "CEO",
    department: "General",
    accent: "AM",
    description: "Global access",
  },
  {
    id: 2,
    name: "Vikram Rao",
    email: "cto@monke.ai",
    role: "CTO",
    department: "Technology",
    accent: "VR",
    description: "Global access",
  },
  {
    id: 3,
    name: "Riya Shah",
    email: "cofounder@monke.ai",
    role: "COFOUNDER",
    department: "General",
    accent: "RS",
    description: "Global access",
  },
  {
    id: 4,
    name: "Nisha Iyer",
    email: "finance.head@monke.ai",
    role: "FINANCE_HEAD",
    department: "Finance",
    accent: "NI",
    description: "Finance + HR + public",
  },
  {
    id: 5,
    name: "Meera Rao",
    email: "hr.head@monke.ai",
    role: "HR_HEAD",
    department: "HR",
    accent: "MR",
    description: "HR + Finance + public",
  },
  {
    id: 6,
    name: "Aarav Menon",
    email: "engineer@monke.ai",
    role: "ENGINEER",
    department: "Technology",
    accent: "AM",
    description: "Technology + public",
  },
  {
    id: 7,
    name: "Kabir Shah",
    email: "manager@monke.ai",
    role: "MANAGER",
    department: "Management",
    accent: "KS",
    description: "Management + public",
  },
  {
    id: 8,
    name: "Ananya Kapoor",
    email: "marketing@monke.ai",
    role: "MARKETING",
    department: "Marketing",
    accent: "AK",
    description: "Marketing + public",
  },
  {
    id: 9,
    name: "Rohan Das",
    email: "employee@monke.ai",
    role: "EMPLOYEE",
    department: "General",
    accent: "RD",
    description: "Public documents",
  },
];

export const roleGroups: RoleGroup[] = [
  {
    role: "CEO",
    department: "General",
    users: demoUsers.filter(
      (user) => user.role === "CEO"
    ),
  },
  {
    role: "CTO",
    department: "Technology",
    users: demoUsers.filter(
      (user) => user.role === "CTO"
    ),
  },
  {
    role: "COFOUNDER",
    department: "General",
    users: demoUsers.filter(
      (user) => user.role === "COFOUNDER"
    ),
  },
  {
    role: "FINANCE_HEAD",
    department: "Finance",
    users: demoUsers.filter(
      (user) => user.role === "FINANCE_HEAD"
    ),
  },
  {
    role: "HR_HEAD",
    department: "HR",
    users: demoUsers.filter(
      (user) => user.role === "HR_HEAD"
    ),
  },
  {
    role: "ENGINEER",
    department: "Technology",
    users: demoUsers.filter(
      (user) => user.role === "ENGINEER"
    ),
  },
  {
    role: "MANAGER",
    department: "Management",
    users: demoUsers.filter(
      (user) => user.role === "MANAGER"
    ),
  },
  {
    role: "MARKETING",
    department: "Marketing",
    users: demoUsers.filter(
      (user) => user.role === "MARKETING"
    ),
  },
  {
    role: "EMPLOYEE",
    department: "General",
    users: demoUsers.filter(
      (user) => user.role === "EMPLOYEE"
    ),
  },
];

export const roleDescriptions: Record<
  string,
  string
> = {
  CEO: "Global access across the entire knowledge corpus.",
  CTO: "Global access across the entire knowledge corpus.",
  COFOUNDER:
    "Global access across the entire knowledge corpus.",
  FINANCE_HEAD:
    "Finance, HR and public/company-wide information.",
  HR_HEAD:
    "HR, Finance and public/company-wide information.",
  ENGINEER:
    "Technology documentation and public information.",
  MANAGER:
    "Management documentation and public information.",
  MARKETING:
    "Marketing documentation and public information.",
  EMPLOYEE:
    "Public and company-wide information only.",
};