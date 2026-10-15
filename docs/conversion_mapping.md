# Conversion mapping

Positions are emitted as `setGeometry(x, y, w, h)` relative to the parent node (offsets may be
negative; sizes are rounded to whole pixels, minimum 1).

| Figma node | Generated widget |
| --- | --- |
| FRAME (top level) | One page module (`<frame>_page.py`) with a fixed-size canvas |
| TEXT | `QLabel` with the text `characters` (falls back to the node name) |
| INSTANCE / COMPONENT without children | `QPushButton` labelled with the node name |
| FRAME, GROUP, other nodes with children | `QFrame` (object name `card`), children nested inside |
| VECTOR and every other node | Empty `QFrame` placeholder |

Every widget gets a tooltip `"<name> (<TYPE>)"`.

Frame names become module names: lower-case, non-alphanumerics replaced by `_`, prefixed with
`screen_` if they start with a digit or are a Python keyword, and numbered (`_2`, `_3`) on collision.

Not converted: fills and colors, fonts, auto-layout, constraints, images, effects. Unsupported node
types produce warnings (`ConversionResult.warnings`), shown in the GUI status line.
