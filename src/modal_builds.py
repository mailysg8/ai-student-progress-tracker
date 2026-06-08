from shiny import ui

STATUS_CONFIG = {
    "Mastered": {
        "dot_color":   "#60D394",
        "row_bg":      "#f0faf5",
        "header_color":"#60D394",
        "subtitle":    lambda mastery, attention, n_units: (
            f"≥ {mastery*100:.0f}% of the class mastered · across {n_units} unit{'s' if n_units > 1 else ''}"
        ),
    },
    "Progressing": {
        "dot_color":   "#FFD97D",
        "row_bg":      "#fffbf0",
        "header_color":"#e6b800",
        "subtitle":    lambda mastery, attention, n_units: (
            f"Between {attention*100:.0f}% and {mastery*100:.0f}% of the class mastered· across {n_units} unit{'s' if n_units > 1 else ''}"
        ),
    },
    "Need Attention": {
        "dot_color":   "#FF9B85",
        "row_bg":      "#fff5f3",
        "header_color":"#e05c3a",
        "subtitle":    lambda mastery, attention, n_units: (
            f"≤ {attention*100:.0f}% of the class mastered · across {n_units} unit{'s' if n_units > 1 else ''}"
        ),
    },
}

def build_total_kc_modal(df):
    badge_color = {
        "Mastered":        "#60D394",
        "Progressing":     "#FFD97D",
        "Need Attention": "#FF9B85",
    }

    # Sort by unit number, then by pct_mastered descending within each unit
    df_sorted = df.copy()
    df_sorted["unit_num"] = df_sorted["unit"].str.extract(r"(\d+)").astype(int)
    df_sorted = (
        df_sorted
        .sort_values(["unit_num", "pct_mastered"], ascending=[True, False])
        .drop(columns="unit_num")
    )

    unit_blocks = []

    for unit_name, group in df_sorted.groupby("unit", sort=False):
        n_skills = len(group)

        # Unit header
        unit_header = ui.tags.div(
            ui.tags.span(unit_name.upper(), style="color:#8B9DBB; font-weight:700; font-size:0.85rem;"),
            ui.tags.span(
                f" — {n_skills} skill{'s' if n_skills > 1 else ''}",
                style="color:#6c757d; font-size:0.85rem;",
            ),
            style="margin-top:1.2rem; margin-bottom:0.4rem;",
        )
        unit_blocks.append(unit_header)

        # KC rows with status badge
        for _, row in group.iterrows():
            status = row["status"]
            color  = badge_color.get(status, "#adb5bd")  # fallback grey

            kc_row = ui.tags.div(
                # Left side: colored dot + KC name
                ui.tags.span(
                    ui.tags.span("●", style=f"color:{color}; margin-right:0.5rem; font-size:0.8rem;"),
                    ui.tags.span(row["modeling_kc_label_x"]),
                    style="flex:1; display:flex; align-items:center;",
                ),
                # Right side: score + status label
                ui.tags.span(
                    ui.tags.span(
                        status,
                        style=(
                            f"font-size:0.75rem; color:{color}; font-weight:600;"
                            f"background:{color}22; border-radius:4px;"  # 22 = ~13% opacity
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

    n_total = len(df_sorted)
    n_units = df_sorted["unit"].nunique()
    subtitle = ui.tags.p(
        f"{n_total} total skill{'s' if n_total > 1 else ''} · across {n_units} unit{'s' if n_units > 1 else ''}",
        style="color:#6c757d; font-size:0.85rem; margin-top:0.1rem; margin-bottom:0.5rem;",
    )

    return ui.tags.div(subtitle, *unit_blocks, style="padding: 0 0.25rem;")



def build_kc_modal(df, status, mastery, attention):
    """
    df:        full dataframe (unfiltered)
    status:    one of "Mastered", "Progressing", "Need Attention"
    threshold: mastery threshold float (e.g. 0.7)
    """
    config = STATUS_CONFIG[status]

    # Filter + sort
    df_filtered = df[df["status"] == status].copy()
    df_filtered["unit_num"] = df_filtered["unit"].str.extract(r"(\d+)").astype(int)
    df_filtered = (
        df_filtered
        .sort_values(["unit_num", "pct_mastered"], ascending=[True, False])
        .drop(columns="unit_num")
    )

    grouped = df_filtered.groupby("unit", sort=False)
    unit_blocks = []

    for unit_name, group in grouped:
        n_skills = len(group)

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
            kc_row = ui.tags.div(
                ui.tags.span(row["modeling_kc_label_x"], style="flex:1;"),
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

    n_units = df_filtered["unit"].nunique()
    subtitle = ui.tags.p(
        config["subtitle"](mastery, attention, n_units),
        style="color:#6c757d; font-size:0.85rem; margin-top:0.1rem; margin-bottom:0.5rem;",
    )

    return ui.tags.div(subtitle, *unit_blocks, style="padding: 0 0.25rem;")