# Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| "Could not access the Figma file" | Wrong link, expired token, or no access to the file. The token needs file read access. |
| "Figma did not respond in time" | 30 s timeout; check the connection or proxy and retry. |
| "No FRAME nodes were found" | The link/JSON has no top-level frames (only groups or components). Link a section or page that contains frames. |
| Generated pages look plain or miss artwork | Vector, icon and image layers are exported from Figma during Generate, so use the GUI with a token (the offline CLI skips them and warns). Check the warnings in the result line. |
| Text looks slightly different from Figma | The design font is not installed. Copy its `.ttf`/`.otf` files into `src/ui/assets/fonts/` of the generated project. |
| "kept your version" warning | A generated file lost its marker line and is treated as hand-written. Restore the first line to let the generator manage it again. |
| GUI does not start | Run from an environment with PySide6 and a display. Headless tests use `QT_QPA_PLATFORM=offscreen`. |
| `validate` exits with 2 | A required page or manifest entry is missing, or a `.py` file does not parse. The failing check id is printed. |
