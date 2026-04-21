import matplotlib.pyplot as plt
import pandas as pd

def plot_h2_soc(df: pd.DataFrame, title: str = "H2-Tank Füllstand", save_path: str = None, capacity_kwh: float = None):
	"""
	Plottet den Füllstand des H2-Tanks (State of Charge) über die Zeit.
	Args:
		df: DataFrame mit Spalte 'h2_soc_kwh'
		title: Plot-Titel
		save_path: Optionaler Pfad zum Speichern des Plots
		capacity_kwh: Maximale Kapazität des H2-Tanks (für %-Achse)
	"""
	if 'h2_soc_kwh' not in df.columns:
		raise ValueError("DataFrame muss die Spalte 'h2_soc_kwh' enthalten!")

	fig, ax1 = plt.subplots(figsize=(12, 5))
	ax1.plot(df['h2_soc_kwh'], label="H2 Füllstand [kWh]", color="tab:blue")
	ax1.set_xlabel("Zeitschritt")
	ax1.set_ylabel("H2 Füllstand [kWh]", color="tab:blue")
	ax1.tick_params(axis='y', labelcolor="tab:blue")

	if capacity_kwh is not None:
		ax2 = ax1.twinx()
		ax2.plot(100 * df['h2_soc_kwh'] / capacity_kwh, label="Füllstand [%]", color="tab:green", alpha=0.5)
		ax2.set_ylabel("Füllstand [%]", color="tab:green")
		ax2.tick_params(axis='y', labelcolor="tab:green")

	plt.title(title)
	plt.grid(True, which="both", linestyle=":", alpha=0.5)
	fig.tight_layout()
	if save_path:
		plt.savefig(save_path)
		plt.close(fig)
	plt.show()
