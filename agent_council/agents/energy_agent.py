from typing import List
from .base_agent import BaseAgent

class EnergyAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "energy_power"

    @property
    def display_name(self) -> str:
        return "Energy & Power Infrastructure Agent"

    @property
    def mireye_fields(self) -> List[str]:
        return [
            "nearest_power_plant_capacity_mw",
            "nearest_power_plant_distance_m",
            "nearest_transmission_line_voltage_kv",
            "nearest_transmission_line_distance_m",
            "nearest_substation_distance_m"
        ]

    @property
    def fallback_questions(self) -> List[str]:
        return [
            "Is there sufficient grid capacity and power infrastructure for a large industrial facility near here?"
        ]

    @property
    def system_prompt(self) -> str:
        return """You are the Energy & Power Infrastructure Agent for an industrial site selection council.
Your job is to evaluate if a candidate site can handle massive industrial power loads without expensive grid extensions.

You will receive JSON containing deterministic data from the Mireye Earth API about power plants, transmission lines, and substations near the site.
- High capacity power plants and high voltage lines close to the site are excellent.
- Lack of infrastructure or large distances mean expensive grid extensions.

Evaluate the data, provide a 0-100 score, a one-line verdict, and a detailed memo.
Extract citations directly from the provided data.
"""
