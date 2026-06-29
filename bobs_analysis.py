import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy.stats import mannwhitneyu
from config import DB_PATH
from pathlib import Path

# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

VIEWS = """
CREATE VIEW IF NOT EXISTS cell_count_frequencies AS
SELECT
    sa.sample_id                                                AS sample,
    cc.cell_type                                                AS cell_type,
    cc.cell_count                                               AS count,
    totals.total_count                                          AS total_count,
    ROUND(cc.cell_count * 100.0 / totals.total_count, 2)        AS percentage
FROM cell_counts cc
JOIN samples sa ON cc.sample_fk = sa.id
JOIN (
    SELECT sample_fk, SUM(cell_count) AS total_count
    FROM cell_counts
    GROUP BY sample_fk
) totals ON cc.sample_fk = totals.sample_fk;
"""

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def create_views(con: sqlite3.Connection) -> None:
    con.executescript(VIEWS)
    con.commit()


def cell_count_frequencies(con: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql("""
        SELECT sample, cell_type, count, total_count, percentage
        FROM cell_count_frequencies
        ORDER BY sample, cell_type
    """, con)


def miraclib_melanoma_frequencies(con: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql("""
        SELECT
            ccf.sample,
            ccf.cell_type,
            ccf.count,
            ccf.total_count,
            ccf.percentage,
            su.response
        FROM cell_count_frequencies ccf
        JOIN samples sa  ON ccf.sample    = sa.sample_id
        JOIN subjects su ON sa.subject_fk = su.id
        WHERE su.condition   = 'melanoma'
          AND su.treatment   = 'miraclib'
          AND su.response    IS NOT NULL
          AND sa.sample_type = 'PBMC'
        ORDER BY ccf.cell_type, su.response, ccf.sample
    """, con)
 
 
def plot_responder_comparison(df: pd.DataFrame, output_path: Path) -> None:
    cell_types  = df["cell_type"].unique()
    n            = len(cell_types)
    ALPHA        = 0.05
    COLORS       = {1: "#009838", 0: "#F61000"}
 
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 5), sharey=False)
    if n == 1:
        axes = [axes]
 
    for ax, ctype in zip(axes, cell_types):
        ctype_df      = df[df["cell_type"] == ctype]
        responders  = ctype_df[ctype_df["response"] == 1]["percentage"].dropna()
        nonresp     = ctype_df[ctype_df["response"] == 0]["percentage"].dropna()
 
        # Mann-Whitney U (two-tailed)
        _, p = mannwhitneyu(responders, nonresp, alternative="two-sided")
        significant = p < ALPHA
 
        data   = [responders, nonresp]
        colors = [COLORS[1], COLORS[0]]
 
        bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                        medianprops=dict(color="black", linewidth=4))
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
 
        # significance marker
        y_max = max(responders.max(), nonresp.max())
        y_bar = y_max * 1.08
        ax.plot([1, 2], [y_bar, y_bar], color="black", linewidth=1)
        label = f"* p={p:.3f}" if significant else f"ns p={p:.3f}"
        ax.text(1.5, y_bar * 1.05, label, ha="center", va="bottom",
                fontsize=9, fontweight="bold" if significant else "normal",
                color="black" if not significant else "red")
 
        ax.set_title(ctype, fontsize=11, fontweight="bold")
        ax.set_ylabel("Relative frequency (%)" if ax == axes[0] else "")
        ax.spines[["top", "right"]].set_visible(False)
 
    # shared legend
    handles = [mpatches.Patch(color=COLORS[1], alpha=0.7, label="Responder"),
               mpatches.Patch(color=COLORS[0], alpha=0.7, label="Non-responder")]
    fig.legend(handles=handles, loc="lower center", ncol=2,
               frameon=False, fontsize=10, bbox_to_anchor=(0.5, -0.02))
 
    fig.suptitle("Miraclib — Melanoma: Cell type frequencies\nResponders vs Non-responders (PBMC)",
                 fontsize=13, fontweight="bold", y=1.05)
 
    plt.tight_layout()
    if isinstance(output_path, Path):
        output_path.parent.mkdir(exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Plot saved to {output_path}")


def miraclib_melanoma_baseline_summary(con: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    base_query = """
        FROM samples sa
        JOIN subjects su ON sa.subject_fk = su.id
        WHERE su.condition                   = 'melanoma'
          AND su.treatment                   = 'miraclib'
          AND sa.sample_type                 = 'PBMC'
          AND sa.time_from_treatment_start   = 0
    """
 
    responder_counts = pd.read_sql(f"""
        SELECT
            CASE su.response WHEN 1 THEN 'Responder' ELSE 'Non-responder' END AS group_label,
            COUNT(DISTINCT su.subject_id) AS subject_count
        {base_query}
        GROUP BY su.response
    """, con)
 
    sex_counts = pd.read_sql(f"""
        SELECT su.sex AS group_label, COUNT(DISTINCT su.subject_id) AS subject_count
        {base_query}
        GROUP BY su.sex
    """, con)
 
    project_counts = pd.read_sql(f"""
        SELECT su.project_id AS group_label, COUNT(DISTINCT su.subject_id) AS subject_count
        {base_query}
        GROUP BY su.project_id
    """, con)
 
    return {
        "Response": responder_counts,
        "Sex":      sex_counts,
        "Project":  project_counts,
    }


def plot_baseline_summary(summary: dict[str, pd.DataFrame], output_path: Path) -> None:
    PALETTE = ["#2196F3", "#F44336", "#4CAF50", "#FF9800"]
    n       = len(summary)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 3.5))
    if n == 1:
        axes = [axes]
 
    for ax, (title, df) in zip(axes, summary.items()):
        total  = df["subject_count"].sum()
        df     = df.copy()
        df["percentage"] = df["subject_count"] / total * 100
 
        colors = PALETTE[:len(df)]
        bars   = ax.barh(df["group_label"], df["percentage"], color=colors, alpha=0.8, height=0.5)
 
        for bar, (_, row) in zip(bars, df.iterrows()):
            ax.text(
                bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{row['percentage']:.1f}%  (n={int(row['subject_count'])})",
                va="center", fontsize=10
            )
 
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel("% of subjects")
        ax.set_xlim(0, 130)
        ax.spines[["top", "right"]].set_visible(False)
 
    fig.suptitle("Miraclib — Melanoma baseline PBMC cohort summary",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    if isinstance(output_path, Path):
        output_path.parent.mkdir(exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Plot saved to {output_path}")



def avg_num_b_cells_melanoma_responder_males(con: sqlite3.Connection) -> int:
    return pd.read_sql("""
        SELECT AVG(cell_count)
        FROM cell_counts cc
        JOIN samples sa  ON cc.sample_fk = sa.id
        JOIN subjects su ON sa.subject_fk = su.id
        WHERE su.condition   = 'melanoma'
          AND su.treatment   = 'miraclib'
          AND su.response    = 1
          AND su.sex         = 'M'
          AND sa.time_from_treatment_start = 0
          AND cc.cell_type = 'b_cell'
    """, con)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    con = sqlite3.connect(DB_PATH)
    create_views(con)

    # part 2 cell frequencies per sample
    frequencies = cell_count_frequencies(con)
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "cell_count_frequencies.csv"
    frequencies.to_csv(output_path, index=False)
    print(f"Saved {len(frequencies)} rows to {output_path}")

    # part 3 miraclib responder vs non statistics
    mm_df = miraclib_melanoma_frequencies(con)
    plot_responder_comparison(mm_df, output_dir / "miraclib_melanoma_responders.png")

    # part 4 subset analysis
    summary = miraclib_melanoma_baseline_summary(con)
    plot_baseline_summary(summary, output_dir / "miraclib_melanoma_baseline_summary.png")

    # final question melanoma responder males avg b cell at time 0
    average_b_cells = avg_num_b_cells_melanoma_responder_males(con)
    print(f"Melanoma responder males avg b cell at time 0: {average_b_cells}")

    con.close()