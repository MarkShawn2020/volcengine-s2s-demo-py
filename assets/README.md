# Assets Directory

This directory should contain the application icons:

- `icon.icns` - macOS icon file (1024x1024 recommended)
- `icon.ico` - Windows icon file (multiple sizes: 16x16, 32x32, 48x48, 256x256)

## Creating Icons

### macOS (.icns)
```bash
# From a 1024x1024 PNG:
iconutil -c icns icon.iconset
```

### Windows (.ico)
Use a tool like ImageMagick:
```bash
convert icon.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico
```