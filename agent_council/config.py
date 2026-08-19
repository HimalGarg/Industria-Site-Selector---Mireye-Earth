import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MIREYE_API_TOKEN = os.getenv("MIREYE_API_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

MIREYE_BASE_URL = "https://api.mireye.com"
MIREYE_TIMEOUT = 120  # seconds

AGENT_MODEL = "gpt-4o-mini"
SYNTHESIZER_MODEL = "gpt-4o"

DEFAULT_WEIGHTS_5 = {
    "energy_power": 0.20,
    "water_sewer": 0.20,
    "surface_environment": 0.20,
    "transportation": 0.20,
    "risk_compliance": 0.20,
}

DEFAULT_WEIGHTS_6 = {
    "energy_power": 0.167,
    "water_sewer": 0.167,
    "surface_environment": 0.167,
    "transportation": 0.167,
    "risk_compliance": 0.167,
    "workforce_livability": 0.167,
}
