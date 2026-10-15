# Stylesheet guide

There is a single dark neon theme, defined once in `src/figma_to_pyside6/theme.py` (`COLORS`,
`tokens_qss`, `main_qss`, `components_qss`). The workbench applies it directly; generated projects
receive it as three files:

- `tokens.qss` - base colors and typography.
- `main.qss` - window, labels, cards, scrollbars.
- `components.qss` - inputs, lists and buttons with cyan/magenta hover and focus states.

Qt style sheets do not support `@import`, so the generated `main_window.py` concatenates the three
files at start-up. The glow around key widgets is a `QGraphicsDropShadowEffect` (QSS has no box-shadow).

The QSS files in a generated project are yours: regeneration never overwrites them.
