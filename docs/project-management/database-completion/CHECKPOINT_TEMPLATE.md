# The Brights Analytics — Validation Checkpoint Template

**Checkpoint ID:** CP-DB-XX
**Date:**
**Chunk:**
**Branch:**
**Commit:**
**Database environment:**
**Reviewer:**

## 1. Chunk objectives
Describe the approved objectives and acceptance criteria.

## 2. Completed work
Record the actual implementation completed during this chunk.

## 3. Files changed
List all created, modified, or deleted files.

## 4. Validation evidence

| Validation | Evidence | Result |
|---|---|---|
| Correct Git branch | git branch --show-current | NOT RUN |
| Expected repository changes | git status --short | NOT RUN |
| Django system check | python manage.py check | NOT RUN |
| Migration consistency | python manage.py makemigrations --check --dry-run | NOT RUN |
| Migration status | python manage.py showmigrations retail | NOT RUN |
| PostgreSQL integration tests | Actual test command and output | NOT RUN |
| Tenant isolation | Relevant security tests | NOT RUN |
| No production changes | Environment verification | NOT VERIFIED |

## 5. Decisions
Record decisions made and their reasons.

## 6. Risks and unresolved issues
Record blockers, missing protections, and deferred requirements.

## 7. Checkpoint outcome

**Status:** AWAITING REVIEW

Possible statuses:
- PASS
- FAIL
- BLOCKED
- AWAITING REVIEW

## 8. User approval

**Decision:** PENDING

Possible decisions:
- APPROVE NEXT CHUNK
- REQUEST CHANGES
- HOLD

**Approval date:**

## 9. Next authorized action
Specify one concrete action for the next session.

## Rules
- Do not mark tests as passed without actual evidence.
- Do not proceed to the next chunk without user approval.
- Update PROJECT_STATE.md after each completed step.
- Preserve database and security constraints.
- Never activate automatic authentication audit-record deletion without separate approval.
