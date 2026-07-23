# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| latest (main branch) | ✅ Active development |
| older releases | ❌ |

## Reporting a Vulnerability

Solo is a personal AI productivity tool, not enterprise infrastructure. However, we take security seriously.

**To report a vulnerability:**

1. **Do NOT** open a public GitHub Issue
2. Use **GitHub Private Vulnerability Reporting** at:
   `https://github.com/chengcheng-2006/solo-windows-ai-agent/security/advisories`
3. If you cannot use the private reporting system, contact us through the project's Discussion page

### What to include:
- Description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Potential impact
- Suggested fix (if any)

### What to expect:
- Acknowledgment within 48 hours
- Status updates every 7 days
- Credit in release notes if the finding is accepted

## Security Best Practices

### For Users
- Keep Solo updated to the latest version
- Use strong, unique API keys
- Review audit logs periodically
- Don't share your `.env` file or config directory
- Use the approval gate for all high-risk operations

### For Contributors
- Never commit secrets, tokens, or credentials
- Use environment variables for sensitive configuration
- Follow the least-privilege principle when adding new tools
- All Computer Use capabilities must include safety tests
- New high-risk actions must have approval gates

## Scope

Solo is a self-hosted system designed for single-user operation. The security model assumes:
- The host machine is trusted
- The user is the sole operator
- API keys are managed by the user
- Network services are loopback-only

Solo is **not** designed for:
- Multi-tenant deployment
- Enterprise compliance
- External network exposure
- Handling classified or highly sensitive data

## Security Features

- Loopback-only network binding
- Multi-agent approval gates
- DPAPI-encrypted secret storage
- Full audit trail
- Tool-level permission whitelists
- No secrets in Git history
