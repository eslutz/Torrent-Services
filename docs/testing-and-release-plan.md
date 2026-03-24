# Testing and Release Plan

This plan introduces JavaScript unit tests with Jest, UI smoke tests with Playwright, and a production blue/green deployment model for safe rollouts and quick rollbacks.

## 1) Unit Tests (Jest)

### Objective
Validate utility functions, API clients, and UI logic quickly on every pull request.

### Scope
- Business logic helpers and data transforms.
- API adapters and response normalization.
- Form validation and shared UI utilities.

### Suggested Conventions
- Test file pattern: `**/*.test.ts` and `**/*.test.js`.
- Co-locate tests with source or mirror under `tests/unit/`.
- Coverage gate target: 80% lines / branches (raise over time).

### Required npm scripts
Add these scripts to `package.json` when Node test assets are introduced:

```json
{
  "scripts": {
    "test:unit": "jest --ci --coverage"
  }
}
```

## 2) UI Smoke Tests (Playwright)

### Objective
Catch broken critical paths (load app, auth entry point, key navigation) before merges and before production cutover.

### Scope
- Home page loads with HTTP 200.
- Login or auth gateway is reachable.
- At least one core route renders and primary controls are visible.

### Smoke suite guidance
- Keep suite small (3-8 tests max).
- Keep run time under ~5 minutes.
- Prefer stable selectors (`data-testid`) over CSS classes.

### Required npm scripts
Add these scripts to `package.json` when UI test assets are introduced:

```json
{
  "scripts": {
    "test:ui:smoke": "playwright test --config=playwright.config.ts --grep @smoke"
  }
}
```

## 3) Workflow Integration

## CI expectations
The CI workflow now includes optional Node test jobs (auto-skipped until a `package.json` exists):

1. `tests-jest`
   - `npm ci`
   - `npm run test:unit`
2. `tests-playwright` (runs after Jest)
   - `npm ci`
   - `npx playwright install --with-deps chromium`
   - `npm run test:ui:smoke`
   - Uploads Playwright report artifact for debugging.

## Merge requirements
Recommended protected branch checks:
- Existing Python tests job (`tests`)
- `tests-jest`
- `tests-playwright`

## 4) Production Deployment: Blue/Green

### Strategy
Maintain two identical production slots:
- **Blue**: currently serving traffic.
- **Green**: next release candidate.

### Flow
1. Detect active slot and choose the idle slot as candidate.
2. Deploy candidate with the target image tag.
3. Run smoke tests against candidate URL.
4. If tests pass, switch traffic to candidate.
5. If any step fails, automatically roll back traffic to previously active slot.

### Operational requirements
- External state store for active slot marker (e.g., DNS/LB tag, config store, or deployment metadata).
- Health endpoint per slot (for smoke checks).
- Fast traffic switching primitive (load balancer weight, DNS, ingress annotation, etc.).

### Rollback
Rollback is immediate because the previously active slot remains intact and can receive traffic again without rebuild.

---

## Implementation Status in This Repository

- CI updates are in `.github/workflows/ci.yml`.
- Blue/green deployment workflow scaffold is in `.github/workflows/deploy-blue-green.yml`.
- Teams should wire environment-specific deployment commands and slot state lookup before first production run.
