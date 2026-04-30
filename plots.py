import matplotlib.dates as mdates
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

    if "timestamp" in df.columns:
        x = pd.to_datetime(df["timestamp"])
        ax.plot(
            x, df["h2_soc_pct"], label="H2 Füllstand [%]", color="tab:blue", linewidth=2
        )
        ax.set_xlabel("Monat")
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        fig.autofmt_xdate(rotation=45)
    else:
        ax.plot(
            df["h2_soc_pct"], label="H2 Füllstand [%]", color="tab:blue", linewidth=2
        )
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


def plot_h2_soc_comparison(
    df_base: pd.DataFrame,
    df_optimized: pd.DataFrame,
    title: str = "H2-Tank Füllstand Vergleich",
    save_path: str = None,
    capacity_kwh: float = None,
) -> None:
    """Plottet den H2-SoC von Base und Optimized im selben Diagramm.

    Args:
        df_base: DataFrame der BaseStrategy mit Spalte h2_soc_pct.
        df_optimized: DataFrame der OptimizedStrategy mit Spalte h2_soc_pct.
        title: Plot-Titel.
        save_path: Optionaler Pfad zum Speichern des Plots.
        capacity_kwh: Maximale H2-Tankkapazität zur Anzeige im Plot.
    """
    if "h2_soc_pct" not in df_base.columns:
        raise ValueError("df_base muss die Spalte 'h2_soc_pct' enthalten!")
    if "h2_soc_pct" not in df_optimized.columns:
        raise ValueError("df_optimized muss die Spalte 'h2_soc_pct' enthalten!")

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(
        df_base["h2_soc_pct"],
        label="BaseStrategy",
        color="tab:blue",
        linewidth=2,
    )
    ax.plot(
        df_optimized["h2_soc_pct"],
        label="OptimizedStrategy",
        color="tab:orange",
        linewidth=2,
    )
    ax.set_xlabel("Zeitschritt [h]")
    ax.set_ylabel("H2 Füllstand [%]")
    ax.set_ylim([0, 100])
    ax.grid(True, which="both", linestyle=":", alpha=0.5)
    ax.legend(loc="best")

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


def _build_grid_import_series(df: pd.DataFrame) -> pd.Series:
    """Berechnet den Netzbezug (grid_import_kw) je Zeitschritt."""
    if "grid_import_kw" not in df.columns:
        raise ValueError("DataFrame muss die Spalte 'grid_import_kw' enthalten!")
    return df["grid_import_kw"]


def plot_consumption_averages(
    df: pd.DataFrame,
    title: str = "Durchschnittlicher Netzbezug",
    save_path: str = None,
) -> None:
    """Plottet 3 aggregierte Netzbezug-Kurven in einem 3x1-Fenster.

    Args:
        df: DataFrame mit Simulationsoutput (stündliche Werte).
        title: Übergeordneter Fenstertitel.
        save_path: Optionaler Pfad zum Speichern des Plots.
    """
    grid_import_kw = _build_grid_import_series(df)

    avg_by_hour = grid_import_kw.groupby(grid_import_kw.index % 24).mean()

    weekday_order = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    avg_by_weekday = grid_import_kw.groupby((grid_import_kw.index // 24) % 7).mean()
    avg_by_weekday.index = [weekday_order[int(i)] for i in avg_by_weekday.index]

    avg_by_week = grid_import_kw.groupby(grid_import_kw.index // 168).mean()
    avg_by_week.index = avg_by_week.index + 1

    fig, axes = plt.subplots(3, 1, figsize=(12, 12), sharex=False)

    axes[0].plot(avg_by_hour.index, avg_by_hour.values, color="tab:blue", linewidth=2)
    axes[0].set_title("Ø Netzbezug pro Stunde (24h)")
    axes[0].set_xlabel("Stunde des Tages")
    axes[0].set_ylabel("Leistung [kW]")
    axes[0].set_xticks(range(0, 24, 2))
    axes[0].grid(True, linestyle=":", alpha=0.5)

    axes[1].plot(
        avg_by_weekday.index,
        avg_by_weekday.values,
        color="tab:orange",
        linewidth=2,
        marker="o",
    )
    axes[1].set_title("Ø Netzbezug pro Wochentag (Mo-So)")
    axes[1].set_xlabel("Wochentag")
    axes[1].set_ylabel("Leistung [kW]")
    axes[1].grid(True, linestyle=":", alpha=0.5)

    axes[2].plot(avg_by_week.index, avg_by_week.values, color="tab:green", linewidth=2)
    axes[2].set_title("Ø Netzbezug pro Woche (Jahr)")
    axes[2].set_xlabel("Kalenderwoche")
    axes[2].set_ylabel("Leistung [kW]")
    axes[2].grid(True, linestyle=":", alpha=0.5)

    fig.suptitle(title)
    fig.tight_layout(rect=[0, 0.02, 1, 0.97])

    if save_path:
        plt.savefig(save_path)
        plt.close(fig)
    else:
        plt.show()


def plot_consumption_averages_comparison(
    df_base: pd.DataFrame,
    df_optimized: pd.DataFrame,
    title: str = "Durchschnittlicher Netzbezug Vergleich",
    save_path: str = None,
) -> None:
    """Plottet 3 Vergleichskurven für Base und Optimized Netzbezug in einem 3x1-Fenster.

    Args:
        df_base: DataFrame der BaseStrategy mit Simulationsoutput.
        df_optimized: DataFrame der OptimizedStrategy mit Simulationsoutput.
        title: Übergeordneter Fenstertitel.
        save_path: Optionaler Pfad zum Speichern des Plots.
    """
    base_grid_import = _build_grid_import_series(df_base)
    opt_grid_import = _build_grid_import_series(df_optimized)

    base_avg_by_hour = base_grid_import.groupby(base_grid_import.index % 24).mean()
    opt_avg_by_hour = opt_grid_import.groupby(opt_grid_import.index % 24).mean()

    weekday_order = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    base_avg_by_weekday = base_grid_import.groupby(
        (base_grid_import.index // 24) % 7
    ).mean()
    opt_avg_by_weekday = opt_grid_import.groupby(
        (opt_grid_import.index // 24) % 7
    ).mean()
    base_avg_by_weekday.index = [
        weekday_order[int(i)] for i in base_avg_by_weekday.index
    ]
    opt_avg_by_weekday.index = [weekday_order[int(i)] for i in opt_avg_by_weekday.index]

    base_avg_by_week = base_grid_import.groupby(base_grid_import.index // 168).mean()
    opt_avg_by_week = opt_grid_import.groupby(opt_grid_import.index // 168).mean()
    base_avg_by_week.index = base_avg_by_week.index + 1
    opt_avg_by_week.index = opt_avg_by_week.index + 1

    fig, axes = plt.subplots(3, 1, figsize=(12, 12), sharex=False)

    axes[0].plot(
        base_avg_by_hour.index,
        base_avg_by_hour.values,
        color="tab:blue",
        linewidth=2,
        label="BaseStrategy",
    )
    axes[0].plot(
        opt_avg_by_hour.index,
        opt_avg_by_hour.values,
        color="tab:orange",
        linewidth=2,
        label="OptimizedStrategy",
    )
    axes[0].set_title("Ø Netzbezug pro Stunde (24h)")
    axes[0].set_xlabel("Stunde des Tages")
    axes[0].set_ylabel("Leistung [kW]")
    axes[0].set_xticks(range(0, 24, 2))
    axes[0].grid(True, linestyle=":", alpha=0.5)
    axes[0].legend(loc="best")

    axes[1].plot(
        base_avg_by_weekday.index,
        base_avg_by_weekday.values,
        color="tab:blue",
        linewidth=2,
        marker="o",
        label="BaseStrategy",
    )
    axes[1].plot(
        opt_avg_by_weekday.index,
        opt_avg_by_weekday.values,
        color="tab:orange",
        linewidth=2,
        marker="o",
        label="OptimizedStrategy",
    )
    axes[1].set_title("Ø Netzbezug pro Wochentag (Mo-So)")
    axes[1].set_xlabel("Wochentag")
    axes[1].set_ylabel("Leistung [kW]")
    axes[1].grid(True, linestyle=":", alpha=0.5)
    axes[1].legend(loc="best")

    axes[2].plot(
        base_avg_by_week.index,
        base_avg_by_week.values,
        color="tab:blue",
        linewidth=2,
        label="BaseStrategy",
    )
    axes[2].plot(
        opt_avg_by_week.index,
        opt_avg_by_week.values,
        color="tab:orange",
        linewidth=2,
        label="OptimizedStrategy",
    )
    axes[2].set_title("Ø Netzbezug pro Woche (Jahr)")
    axes[2].set_xlabel("Kalenderwoche")
    axes[2].set_ylabel("Leistung [kW]")
    axes[2].grid(True, linestyle=":", alpha=0.5)
    axes[2].legend(loc="best")

    fig.suptitle(title)
    fig.tight_layout(rect=[0, 0.02, 1, 0.97])

    if save_path:
        plt.savefig(save_path)
        plt.close(fig)
    else:
        plt.show()
