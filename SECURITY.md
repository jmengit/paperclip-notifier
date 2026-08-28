# Security policy

## Reporting a vulnerability

Please do not open a public issue for a security vulnerability. Contact the repository owner through the private GitHub security advisory workflow.

## Deployment requirements

- Keep Paperclip API keys, Discord URLs, Telegram tokens, webhook URLs, headers, and HMAC secrets outside Git.
- Use Docker secrets or protected environment files.
- Do not mount the Paperclip database or Docker socket.
- Keep HTTPS certificate verification enabled.
- Review generic webhook destinations for SSRF and data-disclosure risk.
- Treat GET webhook query strings as potentially logged by intermediaries.
