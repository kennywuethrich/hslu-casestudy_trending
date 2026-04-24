import matplotlib.pyplot as plt
import pandas as pd


def plot_h2_soc(
    df: pd.DataFrame,
    title: str = "H2-Tank Füllstand",
    save_path: str = None,
    capacity_kwh: float = None,
):
    """
    Plottet den Füllstand des H2-Tanks (State of Charge in %) über die Zeit.

    Args:
            df: DataFrame mit Spalte 'h2_soc_pct'
            title: Plot-Titel
            save_path: Optionaler Pfad zum Speichern des Plots
            capacity_kwh: Maximale Kapazität des H2-Tanks (wird nur für Info angezeigt)
    """
    if "h2_soc_pct" not in df.columns:
        raise ValueError("DataFrame muss die Spalte 'h2_soc_pct' enthalten!")

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df["h2_soc_pct"], label="H2 Füllstand [%]", color="tab:blue", linewidth=2)
    ax.set_xlabel("Zeitschritt [h]")
    ax.set_ylabel("H2 Füllstand [%]", color="tab:blue")
    ax.tick_params(axis="y", labelcolor="tab:blue")
    ax.set_ylim([0, 100])
    ax.grid(True, which="both", linestyle=":", alpha=0.5)

    if capacity_kwh is not None:
        ax.text(
            0.02,
            0.98,
            f"Kapazität: {capacity_kwh:.0f} kWh",
            transform=ax.transAxes,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

    plt.title(title)
    fig.tight_layout()

    if save_path:
        plt.savefig(save_path)
        plt.close(fig)
    else:
        plt.show()
