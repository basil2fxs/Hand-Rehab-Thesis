# Icons

## pan_tool.png

Google Material Icons `pan_tool` (open palm, fingers up), 48dp @ 2x raster, 96x96 PNG.

Source: https://github.com/google/material-design-icons/blob/master/png/action/pan_tool/materialicons/48dp/2x/baseline_pan_tool_black_48dp.png

Licence: Apache 2.0. Full text in `LICENSE` alongside this file.

Used at runtime in two places:

- Setup screen hand-selection buttons (Right / Left / Both). The same icon is rendered as-is for "right" and horizontally flipped for "left".
- Lane strip hand badges in gameplay + diagnostics, scaled down to fit the 22 px radius badge.

Tinted at runtime to match the button or badge colour, so the raw black PNG is converted to whatever shade the theme calls for.
