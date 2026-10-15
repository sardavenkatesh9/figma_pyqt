# Conversion mapping

| Figma feature | Current conversion behaviour |
| --- | --- |
| FRAME | Converted into a simple screen container |
| TEXT | Mapped to QLabel-based content |
| INSTANCE | Preserved as a named component reference |
| Color styles | Exported to QSS token definitions |

Unsupported features are reported in diagnostics instead of being silently dropped.
