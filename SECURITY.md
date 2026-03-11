# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | Yes       |

## Reporting a Vulnerability

To report a security vulnerability, open a GitHub issue with the label `security` or contact the maintainer directly via the repository's GitHub profile.

Please include a description of the issue, steps to reproduce it, and any relevant environment details. You can expect an initial response within 5 business days.

Accepted vulnerabilities will be patched in a follow-up release. Declined reports will include an explanation.

## Security Considerations

- The `SECRET_KEY` environment variable must be set to a strong random value before deployment. The application will refuse to start if this variable is empty.
- Wildcard CORS origins (`*`) are rejected at startup. Set `ALLOWED_ORIGINS` to explicit origins.
- Swagger and ReDoc are disabled when `APP_ENV=production`. Set `ENABLE_DOCS=false` if needed.
- All routes under `/api/v1` require a valid JWT bearer token.
- Twilio webhook requests are validated using the Twilio auth token signature.
- Rate limiting is enforced on all endpoints via SlowAPI.
