# Security Policy

## Supported versions

Only the latest release on the `main` branch receives security fixes.

## Reporting a vulnerability

Please do not open a public issue for security problems.

Report privately through GitHub: open the repository's **Security** tab and choose **Report a vulnerability** (private vulnerability reporting). Include:

- a description of the issue and its impact
- steps or a proof of concept to reproduce it
- the affected version or commit

You can expect an acknowledgement within a few days and a fix or mitigation plan as soon as it is confirmed. Please allow time for a fix before any public disclosure.

## Scope and deployment notes

JobTrace is designed to run on your own machine for a single user.

- The API has no authentication and binds to `127.0.0.1` by default. Do not expose it to untrusted networks or the internet.
- API keys and the Telegram bot token are stored in `.env` and `config.yaml` on disk. Both are git-ignored. Keep their file permissions restricted.
- The settings API returns masked secrets only.
- Uploaded resumes are stored in the project root as `resume.<ext>` and are git-ignored.

If you find that any of these assumptions can be broken, that is worth reporting.
