import base64
import io
import sqlite3
import matplotlib.pyplot as plt
from config import DB_PATH, PORT

from dash import Dash, html
from bobs_analysis import (
    create_views,
    miraclib_melanoma_frequencies,
    miraclib_melanoma_baseline_summary,
    plot_responder_comparison,
    plot_baseline_summary,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fig_to_img(plot_fn, *args) -> str:
    """Call a plot function, capture the matplotlib figure as a PNG."""
    plot_fn(*args, output_path=io.BytesIO())
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close()
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode()


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def build_layout(con: sqlite3.Connection) -> html.Div:
    mm_df   = miraclib_melanoma_frequencies(con)
    summary = miraclib_melanoma_baseline_summary(con)

    responder_img = fig_to_img(plot_responder_comparison, mm_df)
    summary_img   = fig_to_img(plot_baseline_summary, summary)

    return html.Div([
        html.H1("Miraclib — Melanoma Study Dashboard",
                style={"fontFamily": "sans-serif", "padding": "24px 32px 0"}),

        html.Hr(),

        html.Div([
            html.H2("Baseline PBMC Cohort Summary",
                    style={"fontFamily": "sans-serif"}),
            html.Img(src=summary_img, style={"maxWidth": "100%"}),
        ], style={"padding": "16px 32px"}),

        html.Hr(),

        html.Div([
            html.H2("Cell Population Frequencies: Responders vs Non-responders",
                    style={"fontFamily": "sans-serif"}),
            html.Img(src=responder_img, style={"maxWidth": "100%"}),
        ], style={"padding": "16px 32px"}),
    ])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    con = sqlite3.connect(DB_PATH)
    create_views(con)

    app = Dash(__name__)
    app.layout = build_layout(con)

    print(f"\nDashboard running at http://localhost:{PORT}\n")
    app.run(debug=False, port=PORT)