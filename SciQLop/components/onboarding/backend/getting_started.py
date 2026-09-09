from SciQLop.components.onboarding.backend.tour import Tour, TourStep
from SciQLop.components.onboarding.backend import targets, completions
from SciQLop.core.ui.shortcuts import native_shortcut_text, modifier_key_name

GETTING_STARTED = Tour(
    id="getting_started",
    title="Getting Started",
    description=(
        "A two-minute walk through SciQLop: plot real data, navigate it, "
        "label events, and find the tools around them."
    ),
    steps=[
        TourStep(
            step_id="welcome",
            title="Welcome to SciQLop",
            body=(
                "This short tour shows how to plot real data, navigate it, "
                "label time intervals and find the tools around them. Use "
                "Next to move on, Escape to leave, and Tools → Take a tour "
                "to replay it later."
            ),
        ),
        TourStep(
            step_id="create_panel",
            title="Create a plot panel",
            body=(
                "Plots live in panels, and every plot in a panel shares the "
                "same time axis. Click + to create your first panel."
            ),
            resolver=targets.resolve_add_panel_button,
            completion=completions.panel_created,
        ),
        TourStep(
            step_id="search_products",
            title="Search for data",
            body=(
                "An empty panel offers a search box: type a mission, "
                "instrument or parameter (ACE MFI, MMS FGM…) and pick a "
                "result to plot it, or move on to browse the full catalog. "
                "A Speasy proxy plot link pasted here rebuilds its panel."
            ),
            resolver=targets.resolve_search_box,
            completion=completions.plot_settled_in("create_panel"),
        ),
        TourStep(
            step_id="open_products",
            title="Browse every product",
            body=(
                "The Products browser lists every data provider — AMDA, "
                "CDAWeb, CSA, SSCWeb and more — organized by mission and "
                "instrument. Hover or click the icon to open it."
            ),
            resolver=targets.unless_dock_visible(
                "Products", targets.side_tab_resolver("Products")),
            completion=completions.dock_visible("Products"),
        ),
        TourStep(
            step_id="plot_product",
            title="Plot a product",
            body=(
                "Drag a product onto your empty panel to plot it — ACE's "
                "magnetic field, highlighted here, is a good first pick. The "
                "search box above the tree filters the whole catalog."
            ),
            resolver=targets.skip_when_plotted(
                targets.in_dock("Products", targets.resolve_example_product)),
            completion=completions.plot_settled_in("create_panel"),
        ),
        TourStep(
            step_id="add_more_data",
            title="Add more data",
            body=(
                "Drop another product in the middle of a plot to overlay it, "
                "or near the top or bottom edge (a blue highlight appears) to "
                "stack it as a new plot. Right-clicking a product offers the "
                "same choices without dragging."
            ),
            resolver=targets.resolve_panel_widget,
        ),
        TourStep(
            step_id="navigate",
            title="Navigate in time",
            body=(
                "Scroll or drag on a plot to move through time and "
                f"{modifier_key_name()}+scroll to zoom; every plot in the panel "
                "follows. Down here you can set an exact start time and "
                "duration, step with the arrows, and toggle the crosshair "
                f"read-out ({native_shortcut_text('Ctrl+Shift+H')})."
            ),
            resolver=targets.resolve_panel_chrome,
        ),
        TourStep(
            step_id="properties",
            title="Tweak a plot",
            body=(
                "Click a plot or a curve, then hover the Properties icon to "
                "open the inspector and change its color, line style, "
                "markers and more. There, Delete removes the selected curve "
                "or plot, and dragging a plot up or down reorders the panel."
            ),
            resolver=targets.side_tab_resolver("Properties"),
        ),
        TourStep(
            step_id="open_catalogs",
            title="Label time intervals",
            body=(
                "Catalogs are lists of time intervals — events — with their "
                "own attributes. Click to open Catalogs."
            ),
            resolver=targets.unless_dock_visible(
                "Catalogs", targets.side_tab_resolver("Catalogs")),
            completion=completions.dock_visible("Catalogs"),
        ),
        TourStep(
            step_id="catalog_sources",
            title="Where catalogs come from",
            body=(
                "'My Catalogs' is your own library: right-click it to create "
                "one. 'Remote' mirrors read-only catalogs from AMDA and other "
                "services, and 'Shared' catalogs are edited live with "
                "collaborators."
            ),
            resolver=targets.in_dock("Catalogs", targets.resolve_catalog_tree),
        ),
        TourStep(
            step_id="overlay_catalog",
            title="Show events on a plot",
            body=(
                "Drag a catalog onto a plot to overlay its events, or "
                "right-click the panel → Catalogs. Select a catalog here to "
                "see its events in the table below and edit them in place."
            ),
            resolver=targets.in_dock("Catalogs", targets.resolve_catalog_tree),
        ),
        TourStep(
            step_id="edit_events",
            title="Create and jump to events",
            body=(
                "Switch this panel to Edit mode "
                f"({native_shortcut_text('Ctrl+Shift+M')} cycles modes), "
                "then Shift+click on a plot to start a new event and click "
                "again to finish it. Jump mode moves the panel to whichever "
                "event you pick in the table."
            ),
            resolver=targets.resolve_catalog_chrome,
        ),
        TourStep(
            step_id="settings",
            title="Make it yours",
            body=(
                "Themes, plot defaults, plugins and workspaces all live in "
                "Settings: hover the icon to open it. Appearance changes "
                "apply instantly."
            ),
            resolver=targets.side_tab_resolver("Settings"),
        ),
        TourStep(
            step_id="finish",
            title="You're all set",
            body=(
                f"{native_shortcut_text('Ctrl+K')} opens the command palette: "
                "every action, searchable. Tools → Open JupyterLab lets you "
                "drive this very session from Python, and the Plugin Store "
                "adds data sources and tools. Replay this tour anytime from "
                "Tools → Take a tour."
            ),
        ),
    ],
)
