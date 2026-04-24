from config import SystemConfig


class Electrolyzer:
    """Elektrolyseur: Strom -> H2 + Abwaerme"""

    def __init__(self, config: SystemConfig):
        self.p_max_kw = config.ely_kw_max
        self.eff_el = config.ely_eff_el
        self.eff_th = config.ely_eff_th
        self.lhv = config.h2_lhv_kwh_per_kg

    def run(self, P_el_kw: float, dt_h: float = 1.0) -> dict:
        """
        Berechnet H2-Produktion und Abwaerme.
        Returns: {'h2_produced_kg', 'heat_kwh', 'power_used_kw'}
        """
        if P_el_kw < 0.10 * self.p_max_kw:
            return {"h2_produced_kg": 0.0, "heat_kwh": 0.0, "power_used_kw": 0.0}

        P_el_kw = min(P_el_kw, self.p_max_kw)  # [kW]
        E_el_kwh = P_el_kw * dt_h  # [kWh]
        E_h2_kwh = E_el_kwh * self.eff_el  # [kWh] chemische Energie im H2
        m_h2_kg = E_h2_kwh / self.lhv  # [kg]
        Q_heat_kwh = E_el_kwh * self.eff_th  # [kWh_th] Abwaerme

        return {
            "h2_produced_kg": m_h2_kg,
            "heat_kwh": Q_heat_kwh,
            "power_used_kw": P_el_kw,
        }

    def __repr__(self):
        return f"Electrolyzer(P_max={self.p_max_kw}kW, eta_el={self.eff_el:.0%})"


class FuelCell:
    """Brennstoffzelle: H2 -> Strom + Abwaerme"""

    def __init__(self, config: SystemConfig):
        self.p_max_kw = config.fc_kw_max
        self.eff_el = config.fc_eff_el
        self.eff_th = config.fc_eff_th
        self.lhv = config.h2_lhv_kwh_per_kg

    def run(self, P_fc_kw: float, h2_available_kg: float, dt_h: float = 1.0) -> dict:
        """
        Berechnet Stromproduktion aus H2.
        Returns: {'power_out_kw', 'h2_used_kg', 'heat_kwh'}
        """
        if P_fc_kw < 0.10 * self.p_max_kw:
            return {"power_out_kw": 0.0, "h2_used_kg": 0.0, "heat_kwh": 0.0}

        P_fc_kw = min(P_fc_kw, self.p_max_kw)  # [kW]
        E_el_kwh = P_fc_kw * dt_h  # [kWh] gewuenschte Stromenergie
        E_h2_kwh = E_el_kwh / self.eff_el  # [kWh] benoetigte H2-Energie
        m_h2_req_kg = E_h2_kwh / self.lhv  # [kg]

        # H2-Verfuegbarkeit pruefen
        if m_h2_req_kg > h2_available_kg:
            m_h2_req_kg = h2_available_kg
            E_h2_kwh = m_h2_req_kg * self.lhv
            E_el_kwh = E_h2_kwh * self.eff_el
            P_fc_kw = E_el_kwh / dt_h

        Q_heat_kwh = m_h2_req_kg * self.lhv * self.eff_th  # [kWh_th]

        return {
            "power_out_kw": P_fc_kw,
            "h2_used_kg": m_h2_req_kg,
            "heat_kwh": Q_heat_kwh,
        }

    def __repr__(self):
        return f"FuelCell(P_max={self.p_max_kw}kW, eta_el={self.eff_el:.0%})"


class HeatPump:
    """Waermepumpe: Strom -> Waerme"""

    def __init__(self, config: SystemConfig):
        self.p_th_max_kw = config.hp_kw_th_max
        self.cop = config.hp_cop

    def run(self, P_el_kw: float, T_ambient_C: float = 10.0, dt_h: float = 1.0) -> dict:
        """
        Berechnet Waermeproduktion.
        Returns: {'heat_kwh', 'cop'}
        Hinweis: T_ambient_C ist fuer spaetere temperaturabhaengige COP-Kurve vorbereitet.
        """
        p_el_max_kw = self.p_th_max_kw / self.cop
        if P_el_kw < 0.10 * p_el_max_kw:
            return {"heat_kwh": 0.0, "cop": 0.0}

        P_el_kw = min(P_el_kw, p_el_max_kw)  # [kW]
        cop = self.cop  # konstant (Erweiterung moeglich)
        Q_heat_kwh = P_el_kw * cop * dt_h  # [kWh_th]

        return {"heat_kwh": Q_heat_kwh, "cop": cop}

    def __repr__(self):
        return f"HeatPump(COP={self.cop}, P_th_max={self.p_th_max_kw}kW)"
