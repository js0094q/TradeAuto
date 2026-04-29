from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException

from trading_system.config import load_settings
from trading_system.health import health_payload, metrics_payload, paper_strategy_status_payload, readiness_payload
from trading_system.kill_switch import KillSwitch


settings = load_settings()
app = FastAPI(title="Trading System", docs_url=None, redoc_url=None)


def require_admin_token(x_admin_token: str | None) -> None:
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/health")
def health() -> dict:
    return health_payload()


@app.get("/ready")
def ready(x_admin_token: str | None = Header(default=None)) -> dict:
    require_admin_token(x_admin_token)
    payload = readiness_payload(settings)
    if not payload["ok"]:
        raise HTTPException(status_code=503, detail=payload)
    return payload


@app.get("/metrics")
def metrics(x_admin_token: str | None = Header(default=None)) -> dict:
    require_admin_token(x_admin_token)
    return metrics_payload(settings)


@app.get("/paper-strategy")
def paper_strategy(x_admin_token: str | None = Header(default=None)) -> dict:
    require_admin_token(x_admin_token)
    return paper_strategy_status_payload(settings)


@app.post("/admin/kill")
def enable_kill_switch(x_admin_token: str | None = Header(default=None)) -> dict:
    require_admin_token(x_admin_token)
    KillSwitch(settings.kill_switch_file).enable()
    return {"ok": True, "kill_switch": "enabled"}


@app.post("/admin/resume")
def disable_kill_switch(x_admin_token: str | None = Header(default=None)) -> dict:
    require_admin_token(x_admin_token)
    payload = readiness_payload(settings)
    if not payload["ok"]:
        raise HTTPException(status_code=503, detail=payload)
    KillSwitch(settings.kill_switch_file).disable()
    return {"ok": True, "kill_switch": "disabled"}
