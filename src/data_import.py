"""
This module contains helper functions to create the elements (column checklist, progress badge) in the Data Input tab in the
Teacher Portal.

Typical usage :
    from helpers.data_input_helpers import build_card

    card_html = build_card(
        title="Student Observations",
        dataset_cols=["student_id", "score", "primary_kc_id"],
        col_to_file={"student_id": "obs.xlsx", "score": "obs.xlsx"},
    )
"""
def col_status_html(dataset_cols: list[str], col_to_file: dict[str, str]) -> str:
    """Render a column checklist for one dataset card."""
    items = []
    for col in dataset_cols:
        if col in col_to_file:
            source = col_to_file[col]
            items.append(
                f'<li style="display:flex;align-items:center;gap:6px;'
                f'padding:3px 0;font-size:15px;">'
                f'<i class="ti ti-circle-check" style="color:#60D394;font-size:17px;" aria-hidden="true"></i>'
                f'<span style="color:#263744;">{col}</span>'
                f'<span style="color:#8B9DBB;font-size:13px;margin-left:auto;">{source}</span>'
                f'</li>'
            )
        else:
            items.append(
                f'<li style="display:flex;align-items:center;gap:6px;'
                f'padding:3px 0;font-size:15px;">'
                f'<i class="ti ti-circle-x" style="color:#EE6055;font-size:17px;" aria-hidden="true"></i>'
                f'<span style="color:#263744;">{col}</span>'
                f'</li>'
            )
    return f'<ul style="list-style:none;margin:0;padding:0;">{"".join(items)}</ul>'


def progress_badge(found: int, total: int) -> str:
    """Small pill showing n / total."""
    complete = found == total
    bg  = "#60D394" if complete else "#FF9B85"
    return (
        f'<span style="background:{bg};color:#263744;'
        f'font-size:13px;font-weight:500;padding:2px 8px;'
        f'border-radius:99px;white-space:nowrap;">'
        f'{found} / {total}</span>'
    )


def build_card(title: str, dataset_cols: list[str], col_to_file: dict[str, str]) -> str:
    """Create the card that holds the checklist and progress badge."""
    found = sum(1 for c in dataset_cols if c in col_to_file)
    total = len(dataset_cols)
    return (
        f'<div style="background:var(--color-background-primary);'
        f'border:0.5px solid #8B9DBB;'
        f'border-radius:var(--border-radius-lg);padding:1rem 1.25rem;">'
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:center;margin-bottom:10px;">'
        f'<span style="font-size:29px;font-weight:500;'
        f'color:#263744;">{title}</span>'
        f'{progress_badge(found, total)}'
        f'</div>'
        f'{col_status_html(dataset_cols, col_to_file)}'
        f'</div>'
    )