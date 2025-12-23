# Development Schedule - CHA-71

## Issue List

| ID | Title | Dependencies | Label | Priority |
|----|-------|--------------|-------|----------|
| CHA-71 | Fix bug where local DB deletion happens even when Gemini deletion fails | None | Bug | Urgent |

## Dependency Graph

```
CHA-71 (Standalone)
```

> No dependencies - single issue

## File Conflict Analysis

| Issue | Expected File Changes | Conflict Group |
|-------|----------------------|----------------|
| CHA-71 | scheduler_jobs.py, trash_repository.py, test_scheduler_jobs.py | A |

> Single issue, no file conflicts

## Execution Plan

| Step | Issue | Execution Mode |
|------|-------|----------------|
| 1 | CHA-71 | Solo |

## Expected Duration
- Step 1 (CHA-71): ~5-8 minutes
- Total Expected: ~5-8 minutes

## Context for Developer

**Original Request**: "Fix orphan resource bug"

**Bug Description**:
Currently, in `scheduler_jobs.py:206-218`, the cleanup job:
1. Attempts to delete channels from Gemini
2. Logs warnings for failures
3. **Always** deletes from local DB regardless of Gemini success

**Problem**: If Gemini deletion fails, resources remain in Gemini cloud → ongoing costs

**Required Fix**:
1. Track which channels were successfully deleted from Gemini
2. Only delete those channels from local DB
3. Treat "not found" errors as success (already deleted)
4. Keep notes deletion separate (notes don't have Gemini resources)

**Side Effects Analysis** (already completed by Issue Team):
| Side Effect | Mitigation |
|-------------|------------|
| Zombie channels (never deleted) | Treat "not found" errors as success |
| Infinite retry | Distinguish error types (not found vs others) |
| cleanup_expired_trash function | Modify to accept specific IDs for deletion |
| Notes separation | Notes have no Gemini resources, delete separately |

## Key Files

- `src/services/scheduler_jobs.py:206-218` - Bug location
- `src/services/trash_repository.py` - cleanup_expired_trash function
- `src/services/gemini.py:79-97` - delete_store method (returns bool)

## Recommendations

Proceed with development according to this plan.

**Status**: ✅ Ready for execution
