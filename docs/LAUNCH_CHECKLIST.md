# Launch Checklist

> Pre-launch verification checklist. Tick each item when confirmed.

## Pre-Launch

### Security
- [ ] No API keys in code or config files
- [ ] No `C:\Users\` hardcoded paths in public files
- [ ] No `.env` files committed
- [ ] No database files
- [ ] No cookies or session files
- [ ] No browser profiles
- [ ] No private logs
- [ ] No model weights
- [ ] No large binary files
- [ ] Gitleaks scan passes on clean clone
- [ ] Git history is clean (fresh repo, no history of secrets)

### License
- [ ] LICENSE file (Apache 2.0) in root
- [ ] THIRD_PARTY_NOTICES.md with Hermes attribution
- [ ] README license section

### Repository
- [ ] GitHub account verified (chengcheng-2006)
- [ ] Repo slug confirmed (solo-windows-ai-agent)
- [ ] Repo description set
- [ ] Topics configured (10-16)
- [ ] Social preview image uploaded
- [ ] Default branch: main
- [ ] Issues enabled
- [ ] Discussions enabled
- [ ] Private vulnerability reporting enabled

### README
- [ ] English README.md complete
- [ ] Chinese README.zh-CN.md complete
- [ ] Language switch at top
- [ ] Tagline clear and specific
- [ ] Badges (4-7, meaningful)
- [ ] Quick Start (3-5 steps, verified working)
- [ ] Architecture diagram (Mermaid)
- [ ] Project status clearly stated (Alpha)
- [ ] Known limitations section
- [ ] Comparison table
- [ ] Star CTA (once, natural)

### Documentation
- [ ] docs/ARCHITECTURE.md
- [ ] docs/INSTALLATION.md
- [ ] docs/CONFIGURATION.md
- [ ] docs/SECURITY_MODEL.md
- [ ] docs/TROUBLESHOOTING.md
- [ ] docs/FAQ.md
- [ ] docs/DEVELOPMENT.md
- [ ] ROADMAP.md
- [ ] CHANGELOG.md
- [ ] SECURITY.md
- [ ] CONTRIBUTING.md
- [ ] CODE_OF_CONDUCT.md
- [ ] THIRD_PARTY_NOTICES.md

### Community
- [ ] Issue templates (bug, feature, config, security)
- [ ] PR template
- [ ] CI workflow (lint, tests, secret scan)
- [ ] Dependabot config

### Release
- [ ] Version tag created (v0.1.0-alpha or v0.1.0)
- [ ] Release notes written
- [ ] Release notes include known limitations
- [ ] Release asset: source code (via git tag)

## Launch

### Git
- [ ] `git init -b main` in release directory
- [ ] `.gitignore` excludes private files
- [ ] `git add .` — verify files
- [ ] `git diff --cached --stat` — no unwanted files
- [ ] Final secret scan on staged files
- [ ] First commit: `feat: publish Solo Windows AI agent initial open-source release`
- [ ] Remote origin set correctly

### Push
- [ ] Repo does not already exist on GitHub
- [ ] `gh repo create chengcheng-2006/solo-windows-ai-agent --public --source . --remote origin --push`
- [ ] No `--force` used
- [ ] Push succeeds

### Post-Push
- [ ] Repository description set via CLI
- [ ] Topics set via CLI
- [ ] Social preview uploaded via UI
- [ ] Discussions enabled via UI
- [ ] Issues enabled
- [ ] Release created with release notes

### Validation
- [ ] Clean clone in separate directory
- [ ] README renders correctly
- [ ] Images load
- [ ] Relative links work
- [ ] Mermaid renders
- [ ] Language switch works
- [ ] Installation commands look correct
- [ ] Example config validates
- [ ] CI passes
- [ ] License renders correctly
- [ ] No secrets in remote clone
- [ ] No user paths in remote clone

### New User Test
- [ ] 10s → Know what project does
- [ ] Know project maturity (Alpha)
- [ ] Know minimum system requirements
- [ ] Can find Quick Start
- [ ] Know what API keys are needed
- [ ] Know which data leaves the machine
- [ ] Know how to stop the system
- [ ] Can find troubleshooting guide
- [ ] Can submit an Issue
- [ ] Know how to contribute
- [ ] Know the license
- [ ] No exaggerated claims
