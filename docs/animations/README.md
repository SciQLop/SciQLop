# Gesture guides

Short looping animations that each teach one SciQLop manipulation, drawn as a simplified window.

| File | Shows |
| --- | --- |
| `plot-a-product.svg` | Open the Products pane, drag a product onto a panel. |
| `drop-on-a-panel.svg` | Where to drop on a panel that has plots: on a plot, on its top edge, on its bottom edge. |
| `show-a-catalog.svg` | Open the Catalogs pane, drag a catalog onto a panel: its events show as spans. |
| `create-an-event.svg` | Catalog mode Edit, then Shift+click, move, click again. |

Each file is a standalone SVG animated with CSS: no script, no image. It follows the light or dark
theme of whatever displays it, and shows a still picture where animation is off. It plays in a web
page (the welcome page, the website) and in a README; Qt's own SVG renderer shows it still.

The files are generated; the generators are not in this repository yet.
