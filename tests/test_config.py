"""Tests fuer die zentrale Systemkonfiguration."""

from __future__ import annotations

import pytest

from config import SystemConfig


def test_h2_capacity_uses_override() -> None:
    """Prueft, dass der H2-Energieinhalt den Override-Wert verwendet."""

    config = SystemConfig(h2_capacity_override_kwh=1234.0)
    assert config.h2_capacity_kwh == pytest.approx(1234.0)


def test_h2_density_ideal_gas_without_override() -> None:
    """Prueft die Dichteberechnung ohne Override gegen ideales Gas."""

    config = SystemConfig(
        h2_density_override_kg_m3=None,
        h2_total_mass_override_kg=None,
        h2_capacity_override_kwh=None,
    )
    assert config.h2_density_kg_m3 > 0.0


def test_invalid_dispatch_limit_raises_assertion() -> None:
    """Prueft, dass eine zu grosse FC-Dispatch-Grenze abgefangen wird."""

    with pytest.raises(AssertionError):
        SystemConfig(fc_kw_max=10.0, fc_dispatch_max_kw=12.0)


def test_system_config_smoke() -> None:
    """Prueft, dass eine SystemConfig sauber erzeugt werden kann."""

    config = SystemConfig()

    assert config.price_buy_chf > 0.0
    assert config.price_sell_chf > 0.0
    assert config.h2_capacity_kwh > 0.0
