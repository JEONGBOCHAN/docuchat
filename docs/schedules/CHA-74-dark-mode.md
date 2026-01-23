# CHA-74 Dark Mode Implementation Schedule

## Issue Summary

| Field | Value |
|-------|-------|
| ID | CHA-74 |
| Title | Implement Dark Mode with Settings Toggle |
| Type | Feature |
| Priority | Medium |

## Current State Analysis

### Existing Implementation
- **Tailwind `dark:` classes**: 346 occurrences across 31 files (already prepared)
- **CSS Variables**: `globals.css` has dark mode colors via `prefers-color-scheme: dark`
- **Settings Page**: Dark Mode toggle UI exists but is disabled (`opacity-50 pointer-events-none`)

### Missing Components
1. **next-themes** library not installed
2. **ThemeProvider** not configured in Providers.tsx
3. **html `class` attribute** control for manual theme switching
4. **Working toggle** in Settings page

## Implementation Plan

### Step 1: Install and Configure next-themes

**Files to Modify:**
| File | Change Type |
|------|-------------|
| `frontend/package.json` | Add next-themes dependency |
| `frontend/src/app/layout.tsx` | Add `suppressHydrationWarning` to html tag |
| `frontend/src/components/Providers.tsx` | Add ThemeProvider wrapper |
| `frontend/src/app/globals.css` | Update CSS for class-based dark mode |

**Description:**
- Install `next-themes` package
- Configure ThemeProvider with `attribute="class"` and `defaultTheme="system"`
- Enable system preference detection with manual override

### Step 2: Enable Dark Mode Toggle in Settings

**Files to Modify:**
| File | Change Type |
|------|-------------|
| `frontend/src/app/settings/page.tsx` | Major refactor |

**Description:**
- Remove `opacity-50 pointer-events-none` from Appearance section
- Implement working toggle switch with `useTheme()` hook
- Add system/light/dark mode options
- Keep API Configuration and Data Management as Coming Soon

### Dependency Analysis

```
Step 1 (next-themes setup)
    │
    └──▶ Step 2 (Settings toggle)
```

**Explanation**: Settings toggle requires ThemeProvider to be configured first.

## File Conflict Analysis

| Step | Files Modified | Conflict Group |
|------|---------------|----------------|
| Step 1 | package.json, layout.tsx, Providers.tsx, globals.css | A |
| Step 2 | settings/page.tsx | B |

→ No file conflicts between steps, but **logical dependency** requires sequential execution.

## Execution Plan

| Step | Task | Execution Mode | Estimated Time |
|------|------|---------------|----------------|
| 1 | Install next-themes, configure ThemeProvider | Sequential | ~3 min |
| 2 | Implement Settings dark mode toggle | Sequential | ~3 min |
| 3 | Local Docker test | Sequential | ~2 min |
| 4 | Playwright verification | Sequential | ~2 min |
| 5 | Azure deployment | Sequential | ~3 min |

**Total Estimated Time**: ~13 minutes

## Testing Requirements

### Unit Tests
- ThemeProvider renders correctly
- Toggle switches theme state
- System preference detection works

### E2E Tests (Playwright)
- Navigate to Settings page
- Toggle dark mode switch
- Verify UI changes to dark theme
- Refresh page, verify preference persists (localStorage)
- Test system preference detection

### Local Docker Test
- Build and run in Docker container
- Verify dark mode works in containerized environment

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Hydration mismatch | Medium | Low | Use `suppressHydrationWarning` on html tag |
| Flash of incorrect theme | Medium | Low | Use blocking script or CSS to prevent |
| CSS variable conflicts | Low | Medium | Test thoroughly in both modes |

## Recommendations

1. **Sequential execution** is required due to logical dependency
2. **Test in local Docker** before Azure deployment
3. **Playwright E2E** should verify persistence and system detection
4. Keep the implementation simple - only enable Dark Mode toggle, leave other settings as Coming Soon

## Approval Status

**Status**: Pending orchestrator approval

---

*Document created by Dev Team Lead*
*Date: 2025-12-24*
