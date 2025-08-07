# Contributing Guide

## Commit Message Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/) with [Angular convention](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit) for automated semantic versioning and changelog generation.

### Commit Message Format

Each commit message consists of a **header**, an optional **body**, and an optional **footer**.

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

The following types will trigger different version bumps:

#### Version Bump Types

- **feat**: A new feature (triggers **MINOR** version bump) 
  - Example: `feat: add voice activity detection`
  - Example: `feat(audio): implement noise cancellation`

- **fix**: A bug fix (triggers **PATCH** version bump)
  - Example: `fix: resolve WebSocket connection timeout`
  - Example: `fix(adapter): correct TouchDesigner UDP handling`

- **perf**: Performance improvements (triggers **PATCH** version bump)
  - Example: `perf: optimize audio buffer processing`

#### No Version Bump

These types don't trigger version changes but are important for project maintenance:

- **docs**: Documentation only changes
  - Example: `docs: update README with new adapter usage`

- **style**: Code style changes (formatting, missing semicolons, etc.)
  - Example: `style: format code with black`

- **refactor**: Code refactoring without feature changes or bug fixes
  - Example: `refactor: simplify adapter base class`

- **test**: Adding or updating tests
  - Example: `test: add unit tests for audio utils`

- **build**: Changes to build system or dependencies
  - Example: `build: update Poetry dependencies`

- **ci**: Changes to CI/CD configuration
  - Example: `ci: add macOS build workflow`

- **chore**: Other changes that don't modify src or test files
  - Example: `chore: update .gitignore`

### Breaking Changes

Breaking changes trigger a **MAJOR** version bump. There are two ways to indicate breaking changes:

1. **Footer notation** (recommended):
```
feat: remove deprecated audio format support

BREAKING CHANGE: PCM format is no longer supported. 
Use OGG format instead.
```

2. **Exclamation mark** in the header:
```
feat!: redesign adapter interface
```

### Scope

The scope is optional but recommended for clarity. Common scopes in this project:

- **audio**: Audio processing related changes
- **adapter**: Adapter implementations (local, browser, TouchDesigner, etc.)
- **volcengine**: Volcengine API client changes
- **gui**: GUI application changes
- **config**: Configuration changes
- **deps**: Dependency updates

### Examples

#### Feature with scope
```
feat(adapter): add real-time transcription support

Implement real-time speech-to-text transcription in the local adapter
using Volcengine's streaming API.

Closes #123
```

#### Bug fix
```
fix: prevent memory leak in audio buffer

Clear audio buffer after processing to prevent memory accumulation
during long sessions.
```

#### Breaking change
```
feat(api): update Volcengine client to v2

BREAKING CHANGE: The client now requires access_token instead of api_key.
Update your configuration:
- Before: VOLCENGINE_API_KEY
- After: VOLCENGINE_ACCESS_TOKEN
```

#### Multiple changes (use separate commits)
```
# Bad - don't combine different types
fix: correct WebSocket timeout and add new feature

# Good - separate commits
fix: correct WebSocket timeout
feat: add connection retry mechanism
```

## Automated Release Process

When commits are pushed to the `main` branch:

1. **Semantic Release** analyzes commit messages
2. Determines version bump type (major/minor/patch)
3. Updates version in:
   - `pyproject.toml`
   - `src/__init__.py`
4. Generates/updates `CHANGELOG.md`
5. Creates Git tag (e.g., `v1.2.0`)
6. Creates GitHub release with release notes
7. Triggers build workflows for macOS and Windows

## Pre-commit Hooks (Optional)

To ensure commit message quality, you can install commitlint locally:

```bash
# Install commitlint
npm install -g @commitlint/cli @commitlint/config-conventional

# Create configuration
echo "module.exports = {extends: ['@commitlint/config-conventional']}" > .commitlintrc.js

# Test your commit message
echo "feat: add new feature" | commitlint
```

## Pull Request Guidelines

1. **Branch naming**: Use descriptive branch names
   - `feat/voice-activity-detection`
   - `fix/websocket-timeout`
   - `docs/update-readme`

2. **PR title**: Should follow commit convention
   - The PR title will be used as the merge commit message

3. **PR description**: Include:
   - What changes were made
   - Why the changes were necessary
   - How to test the changes
   - Any breaking changes

## Version Management

- Version follows [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`
- Version is automatically managed - **never manually edit version numbers**
- Check current version: `poetry run semantic-release version --print`
- Preview next version: `poetry run semantic-release version --print-last-released`

## Questions?

If you're unsure about commit message format, use this template:

```bash
# For a new feature
git commit -m "feat: describe what the feature does"

# For a bug fix  
git commit -m "fix: describe what was broken and is now fixed"

# For documentation
git commit -m "docs: describe what documentation was added/updated"
```

Remember: Clear, descriptive commit messages help maintain a useful changelog and make it easier for others to understand the project's history!