# MCP-Dock Assets Directory

This directory contains the logo and favicon files for the MCP-Dock application.

## Required Files

### Favicon Files
- `favicon.ico` - Main favicon file (16x16, 32x32, 48x48 pixels)
- `favicon-16x16.png` - 16x16 pixel PNG favicon
- `favicon-32x32.png` - 32x32 pixel PNG favicon
- `apple-touch-icon.png` - 180x180 pixel Apple touch icon

### Logo Files
- `logo.png` - Main logo file in PNG format
- Recommended size: 256x256 pixels or higher for crisp display
- Should work well on both light and dark backgrounds

## File Placement Instructions

1. **Favicon Files**: Place all favicon files directly in this `/static/assets/` directory
2. **Logo File**: Place `logo.png` in this `/static/assets/` directory

## Fallback Behavior

The application has a fallback system:
1. First tries to load `logo.png` from `/static/assets/`
2. If that fails, falls back to `logo.svg` from `/static/images/`
3. If both fail, displays a Font Awesome cogs icon

## Creating Favicon Files

You can create favicon files from your logo using online tools like:
- https://favicon.io/
- https://realfavicongenerator.net/
- https://www.favicon-generator.org/

## Logo Requirements

- Format: PNG (preferred) or SVG
- Transparent background recommended
- Should be readable at small sizes (24px height in sidebar)
- Works well with the application's blue color scheme
