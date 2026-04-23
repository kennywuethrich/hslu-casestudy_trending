"""Test der SystemConfig mit API-Integration"""
from config import SystemConfig

print("Initialisiere SystemConfig...")
config = SystemConfig()

print(f"\nErgebnisse:")
print(f"  price_buy_chf: {config.price_buy_chf}")
print(f"  price_sell_chf: {config.price_sell_chf}")

print(f"\nKonfig: {config}")
