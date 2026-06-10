from shiny import ui

# ---------------------------------------------------------------------------
# STATUS_CONFIG
# ---------------------------------------------------------------------------
# Central configuration dictionary for the three KC status categories.
# Each key maps to a dict of visual and textual settings used by
# build_kc_modal() to render status-specific modals without duplicating code.
#
# Keys per status:
#   dot_color    : hex color for the status indicator dot in the modal title
#   row_bg       : background color for each KC row in the modal list
#   header_color : hex color for the unit section headers
#   subtitle     : lambda that formats the modal subtitle string.
#                  Args: mastery (float), attention (float), n_units (int)
# ---------------------------------------------------------------------------
STATUS_CONFIG = {
    "Mastered": {
        "dot_color":    "#60D394",
        "row_bg":       "#f0faf5",
        "header_color": "#60D394",
        # Shown when all displayed KCs are above the mastery threshold
        "subtitle": lambda mastery, attention, n_units: (
            f"≥ {mastery*100:.0f}% of the class mastered · across {n_units} unit{'s' if n_units > 1 else ''}"
        ),
    },
    "Progressing": {
        "dot_color":    "#FFD97D",
        "row_bg":       "#fffbf0",
        "header_color": "#e6b800",
        # Shown when KCs fall between the attention and mastery thresholds
        "subtitle": lambda mastery, attention, n_units: (
            f"Between {attention*100:.0f}% and {mastery*100:.0f}% of the class mastered · across {n_units} unit{'s' if n_units > 1 else ''}"
        ),
    },
    "Need Attention": {
        "dot_color":    "#FF9B85",
        "row_bg":       "#fff5f3",
        "header_color": "#e05c3a",
        # Shown when KCs are below the attention threshold
        "subtitle": lambda mastery, attention, n_units: (
            f"≤ {attention*100:.0f}% of the class mastered · across {n_units} unit{'s' if n_units > 1 else ''}"
        ),
    },
}


def build_total_kc_modal(df):
    """
    Build the modal content for the 'Total KCs' value box.

    Displays ALL knowledge components regardless of status, grouped by unit
    and sorted by unit number (ascending) then pct_mastered (descending).
    Each KC row shows a colored status badge dot and a tinted status label
    alongside the mastery percentage, making it easy to scan across statuses.

    Parameters
    ----------
    df : pd.DataFrame
        Full, unfiltered KC dataframe. Expected columns:
            - 'unit'                 : str, e.g. "Unit 1"
            - 'modeling_kc_label'  : str, the KC display name
            - 'pct_mastered'         : float in [0, 1], e.g. 0.895
            - 'status'               : str, one of "Mastered", "Progressing",
                                       "Need Attention"
    """
    # Map each status to its badge dot color; grey is the fallback for
    # any unexpected status values that might appear in the data
    badge_color = {
        "Mastered":      "#60D394",
        "Progressing":   "#FFD97D",
        "Need Attention": "#FF9B85",
    }

    # Extract unit number for correct numeric sort order (Unit 2 < Unit 10),
    # then drop the helper column after sorting
    df_sorted = df.copy()
    df_sorted["unit_num"] = df_sorted["unit"].str.extract(r"(\d+)").astype(int)
    df_sorted = (
        df_sorted
        .sort_values(["unit_num", "pct_mastered"], ascending=[True, False])
        .drop(columns="unit_num")
    )

    unit_blocks = []

    # Iterate over each unit in sorted order, building a header + KC rows
    for unit_name, group in df_sorted.groupby("unit", sort=False):
        n_skills = len(group)

        # Section header: "UNIT 1 — 3 skills"
        unit_header = ui.tags.div(
            ui.tags.span(
                unit_name.upper(),
                style="color:#8B9DBB; font-weight:700; font-size:0.85rem;",
            ),
            ui.tags.span(
                f" — {n_skills} skill{'s' if n_skills > 1 else ''}",
                style="color:#6c757d; font-size:0.85rem;",
            ),
            style="margin-top:1.2rem; margin-bottom:0.4rem;",
        )
        unit_blocks.append(unit_header)

        # One row per KC inside this unit
        for _, row in group.iterrows():
            status = row["status"]
            color  = badge_color.get(status, "#adb5bd")  # grey fallback

            kc_row = ui.tags.div(
                # Left: colored dot + KC name
                ui.tags.span(
                    ui.tags.span(
                        "●",
                        style=f"color:{color}; margin-right:0.5rem; font-size:0.8rem;",
                    ),
                    ui.tags.span(row["modeling_kc_label"]),
                    style="flex:1; display:flex; align-items:center;",
                ),
                # Right: tinted status badge + right-aligned percentage
                ui.tags.span(
                    ui.tags.span(
                        status,
                        style=(
                            f"font-size:0.75rem; color:{color}; font-weight:600;"
                            f"background:{color}22; border-radius:4px;"
                            f"padding:0.1rem 0.45rem; margin-right:0.75rem;"
                        ),
                    ),
                    ui.tags.span(
                        f"{row['pct_mastered'] * 100:.1f}%",
                        style="font-weight:600; color:#263744; min-width:3.5rem; text-align:right;",
                    ),
                    style="display:flex; align-items:center;",
                ),
                style=(
                    "display:flex; justify-content:space-between; align-items:center;"
                    "background:#f4f6f9; border-radius:6px; padding:0.55rem 0.85rem;"
                    "margin-bottom:0.35rem; font-size:0.92rem; color:#263744;"
                ),
            )
            unit_blocks.append(kc_row)

    # Summary subtitle above the list
    n_total = len(df_sorted)
    n_units = df_sorted["unit"].nunique()
    subtitle = ui.tags.p(
        f"{n_total} total skill{'s' if n_total > 1 else ''} · across {n_units} unit{'s' if n_units > 1 else ''}",
        style="color:#6c757d; font-size:0.85rem; margin-top:0.1rem; margin-bottom:0.5rem;",
    )

    return ui.tags.div(subtitle, *unit_blocks, style="padding: 0 0.25rem;")


def build_kc_modal(df, status, mastery, attention):
    """
    Build the modal content for a single status-filtered KC value box.

    Filters the dataframe to the given status, then renders KCs grouped
    by unit with a subtitle describing the threshold range for that status.
    Visual styling (colors, row background) is driven by STATUS_CONFIG.

    Parameters
    ----------
    df : pd.DataFrame
        Full, unfiltered KC dataframe. Expected columns:
            - 'unit'                 : str, e.g. "Unit 1"
            - 'modeling_kc_label'  : str, the KC display name
            - 'pct_mastered'         : float in [0, 1], e.g. 0.895
            - 'status'               : str, one of "Mastered", "Progressing",
                                       "Need Attention"
    status : str
        The status category to display. Must be a key in STATUS_CONFIG:
        "Mastered", "Progressing", or "Need Attention".
    mastery : float
        The mastery threshold (e.g. 0.7 for 70%). Used in the subtitle.
    attention : float
        The attention threshold (e.g. 0.4 for 40%). Used in the subtitle
        for "Progressing" and "Need Attention" categories.

    """
    # Look up colors and subtitle template for the requested status
    config = STATUS_CONFIG[status]

    # Filter to only the relevant status, then sort by unit number
    # and descending mastery within each unit
    df_filtered = df[df["status"] == status].copy()
    df_filtered["unit_num"] = df_filtered["unit"].str.extract(r"(\d+)").astype(int)
    df_filtered = (
        df_filtered
        .sort_values(["unit_num", "pct_mastered"], ascending=[True, False])
        .drop(columns="unit_num")
    )

    grouped = df_filtered.groupby("unit", sort=False)
    unit_blocks = []

    # Build one section per unit: a header followed by a row for each KC
    for unit_name, group in grouped:
        n_skills = len(group)

        # Section header: "UNIT 1 — 2 skills" in the status-specific color
        unit_header = ui.tags.div(
            ui.tags.span(
                unit_name.upper(),
                style=f"color:{config['header_color']}; font-weight:700; font-size:0.85rem;",
            ),
            ui.tags.span(
                f" — {n_skills} skill{'s' if n_skills > 1 else ''}",
                style="color:#6c757d; font-size:0.85rem;",
            ),
            style="margin-top:1.2rem; margin-bottom:0.4rem;",
        )

        rows = []
        for _, row in group.iterrows():
            # Each row: KC name on the left, mastery percentage on the right
            kc_row = ui.tags.div(
                ui.tags.span(row["modeling_kc_label"], style="flex:1;"),
                ui.tags.span(
                    f"{row['pct_mastered'] * 100:.1f}%",
                    style="font-weight:600; color:#263744;",
                ),
                style=(
                    f"display:flex; justify-content:space-between; align-items:center;"
                    f"background:{config['row_bg']}; border-radius:6px; padding:0.55rem 0.85rem;"
                    f"margin-bottom:0.35rem; font-size:0.92rem; color:#263744;"
                ),
            )
            rows.append(kc_row)

        unit_blocks.append(unit_header)
        unit_blocks.extend(rows)

    # Subtitle uses the status-specific lambda from STATUS_CONFIG,
    # passing both thresholds so each status can format its own message
    n_units = df_filtered["unit"].nunique()
    subtitle = ui.tags.p(
        config["subtitle"](mastery, attention, n_units),
        style="color:#6c757d; font-size:0.85rem; margin-top:0.1rem; margin-bottom:0.5rem;",
    )

    return ui.tags.div(subtitle, *unit_blocks, style="padding: 0 0.25rem;")