## Summary

<!-- One paragraph: what changed and why. Link the ticket/issue. -->

Closes #

## Type of change

- [ ] `feat` — new feature
- [ ] `fix` — bug fix
- [ ] `refactor` — no behaviour change
- [ ] `test` — tests only
- [ ] `chore` — tooling, deps, docs
- [ ] `ci` — CI/CD changes

## Changes

<!-- Bullet-point list of what changed. Be specific — reviewers read diffs but bullets give intent. -->

-
-

## Testing

<!-- How was this tested? Which test files cover it? -->

- [ ] `make test-unit` passes
- [ ] `make test-integration` passes
- [ ] `make test` ≥ 80% coverage
- [ ] Manually verified with `make smoke` (if behaviour change)

## Checklist

- [ ] Branch based on `develop`
- [ ] Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
- [ ] `make pre-commit` passes
- [ ] No `print()` / debug artifacts
- [ ] `README.md` updated if API surface changed
- [ ] Sprint doc updated if ticket closed
- [ ] No new `mypy` errors (`make pre-commit` includes mypy)

## Screenshots / curl output

<!-- For API changes: paste a curl request + response. For UI changes: screenshot. Delete if not applicable. -->

```bash
# Example
curl -X POST http://localhost:8000/songs/preview \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtu.be/dQw4w9WgXcQ"}'
```

```json

```
