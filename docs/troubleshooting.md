# Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| "Could not access the Figma file" | Wrong link, expired token, or no access to the file. The token needs file read access. |
| "Figma did not respond in time" | 30 s timeout; check the connection or proxy and retry. |
| "No FRAME nodes were found" | The link/JSON has no top-level frames (only groups or components). Link a section or page that contains frames. |
| Generated pages are empty | Children nested deeper than frame, child, grandchild are not fetched. Also check the warnings in the status line. |
| "kept your version" warning | A generated file lost its marker line and is treated as hand-written. Restore the first line to let the generator manage it again. |
| GUI does not start | Run from an environment with PySide6 and a display. Headless tests use `QT_QPA_PLATFORM=offscreen`. |
| `validate` exits with 2 | A required page or manifest entry is missing, or a `.py` file does not parse. The failing check id is printed. |
