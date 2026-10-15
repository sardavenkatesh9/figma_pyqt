# Conversion mapping

Each Figma frame becomes one page. Layers are placed at their exact Figma position (relative to
their parent, whole pixels, negative offsets kept) and painted back to front in layer order. The
page canvas is the frame's size and is scaled to fit the window, keeping its aspect ratio.

## Built from widgets

| Figma | Generated |
| --- | --- |
| FRAME, GROUP, INSTANCE, COMPONENT, RECTANGLE, ELLIPSE | `box(...)`: a `QFrame` styled with a Qt style sheet, children nested inside |
| TEXT | `text(...)`: a `QLabel` with the layer's font family, size, weight, italic, underline, letter spacing, case, alignment and color |
| Solid fill | `background: rgba(...)` |
| Linear / radial gradient | `qlineargradient` / `qradialgradient` with the gradient's stops (angular and diamond fall back to the first stop) |
| Several fills | The first fill is the box itself; each further fill is an overlay box on top |
| Stroke | `border: Npx solid rgba(...)` (drawn above all fills; gradient strokes use their first stop) |
| Corner radius / per-corner radii | `border-radius` (rounded down when larger than half the box, which Qt would otherwise ignore) |
| Opacity | Multiplied through the tree into fills, strokes, text and images (Qt effects are not used) |
| Drop shadow | A pre-blurred picture created just behind the box (`shadow(...)`) |
| Hidden layers, layers fully outside their parent | Not generated |

## Exported as images

Qt cannot draw these, so the generator asks Figma to render them (images API, PNG at 2x) and ships
the files under `src/ui/assets/`. Files are named by content (`fig_<hash>.png`), so an icon or logo that
appears many times, or on several frames, is stored once and every page reuses it.

Exported layers:

* VECTOR, BOOLEAN_OPERATION, STAR, LINE, REGULAR_POLYGON
* any layer with a bitmap (IMAGE) fill
* rotated layers
* groups that contain a mask
* icon-like containers whose visible content is only vector art

Layers larger than 8000 px are skipped. Without a Figma connection (offline JSON through the CLI) these
layers are left out and reported in the warnings.

## Not converted

Auto-layout and constraints (positions are fixed at design size), inner shadows, layer and background
blur, blend modes, dashed strokes, per-side stroke weights, text styled per character range, and
nesting deeper than what the REST API returns for the selected frames' subtrees (they are fetched in full).

## Fonts

Text uses the font family from Figma, then falls back to Segoe UI / Helvetica Neue / Arial. To match the
design exactly, put the font files (for example Inter) into `src/ui/assets/fonts/`; the generated app
registers every `.ttf`/`.otf` found there at start-up.

Frame names become module names: lower-case, non-alphanumerics replaced by `_`, prefixed with `screen_`
if they start with a digit or are a Python keyword, and numbered (`_2`, `_3`) on collision. Repeated frame
names are numbered in the sidebar: `Name (1)`, `Name (2)`.
