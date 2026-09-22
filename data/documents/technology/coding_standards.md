# Engineering Coding Standards

- **Document ID:** TECH-STD-004
- **Owner:** Engineering Productivity
- **Classification:** INTERNAL
- **Access Scope:** CEO, CTO, COFOUNDER, TECHNOLOGY_DEPARTMENT
- **Effective Date:** 2026-05-20
- **Source:** Internal knowledge base

## Python

Use type hints on public functions, small focused modules, explicit error handling, and dependency injection for external services where practical.

Avoid global mutable state. Network calls should define timeouts and log request identifiers without exposing secrets.

## API Design

Endpoints should validate input through Pydantic models and return predictable error structures. Breaking API changes require a versioning or migration plan.

## Testing

Business-critical authorization rules require positive and negative tests. Retrieval components should include tests that prove unauthorized documents are excluded, not merely that authorized results are returned.

## Code Review

Reviewers should check correctness, security implications, observability, failure modes, and maintainability. Large refactors should be separated from behaviour changes where feasible.

---
Synthetic prototype corpus - not real company data.