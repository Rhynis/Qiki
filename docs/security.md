# Security

TODO: Fill in during Phase 1 and later implementation phases.

## Baseline

- Server-side validation via Pydantic.
- Security headers on all responses.
- Rate limiting per endpoint category.
- PII masking in logs.

## Secret Leak Guard

CI runs a dependency-free secret scan before backend tests. The scan checks tracked
files for private key blocks and verifies `.env.example` files only contain empty
or placeholder values for secret-like variables.

Enable the local pre-commit hook after cloning:

```bash
git config core.hooksPath scripts/hooks
```

Run the same tracked-file scan manually:

```bash
scripts/secret-scan.sh --tracked
```
