from __future__ import annotations

import os

APP_NAME = "helixgate"
APP_ENV = os.getenv("APP_ENV", "demo")
JWT_SECRET = os.getenv("HELIXGATE_JWT_SECRET", "helixgate-demo-secret-key-32b!!!")
JWT_ISSUER = os.getenv("HELIXGATE_JWT_ISSUER", "https://id.helixgate.dev")
DEMO_RATE_RPS = float(os.getenv("HELIXGATE_DEMO_RPS", "6"))
DEMO_RATE_BURST = float(os.getenv("HELIXGATE_DEMO_BURST", "10"))
