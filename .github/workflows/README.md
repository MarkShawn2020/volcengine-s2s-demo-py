# GitHub Actions Workflows

## Overview

This directory contains automated build workflows for packaging the Volcengine Voice Chat GUI application for macOS and Windows.

## Workflows

### build-macos.yml
Builds and packages the macOS application:
- Creates a `.app` bundle using PyInstaller
- Packages into a DMG installer
- Optional code signing and notarization (requires secrets)
- Uploads artifacts and creates GitHub releases

### build-windows.yml
Builds and packages the Windows application:
- Creates a `.exe` using PyInstaller  
- Builds NSIS installer
- Creates portable ZIP package
- Optional code signing (requires secrets)
- Uploads artifacts and creates GitHub releases

## Triggering Builds

Workflows are triggered by:
1. **Version Tags**: Push a tag matching `v*` pattern (e.g., `v1.0.0`)
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **Manual Dispatch**: Run manually from GitHub Actions tab with optional test build parameter

## Required Secrets (Optional)

### macOS Code Signing
- `MACOS_CERTIFICATE`: Base64-encoded .p12 certificate
- `MACOS_CERTIFICATE_PWD`: Certificate password
- `MACOS_IDENTITY`: Developer ID Application identity

### macOS Notarization
- `APPLE_ID`: Apple Developer account email
- `APPLE_PASSWORD`: App-specific password
- `APPLE_TEAM_ID`: Apple Developer Team ID

### Windows Code Signing
- `WINDOWS_CERTIFICATE`: Base64-encoded .pfx certificate
- `WINDOWS_CERTIFICATE_PASSWORD`: Certificate password

## Adding Icons

Before running the workflows, add application icons to the `assets/` directory:
- `icon.icns` - macOS icon
- `icon.ico` - Windows icon

## Release Artifacts

Each workflow produces:
- **macOS**: DMG installer with optional notarization
- **Windows**: NSIS installer + portable ZIP
- **Checksums**: SHA256 hashes for verification

Artifacts are automatically attached to GitHub releases when triggered by version tags.