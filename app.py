"""FastAPI application entrypoint."""
from __future__ import annotations

import os

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from juniper_policy_generator.models import PolicyInput
from juniper_policy_generator.naming import cidr_was_normalized, normalize_cidr, parse_port_spec
from juniper_policy_generator.renderer import render_set
from juniper_policy_generator.validator import ValidationError

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "juniper_policy_generator", "templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

app = FastAPI(title="Juniper Policy Generator", description="Juniper SRX set-command generator")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> object:
    return templates.TemplateResponse(request, "index.html")


@app.get("/health")
async def health() -> dict:
    """Lightweight liveness probe used by Docker HEALTHCHECK."""
    return {"status": "ok"}


@app.post("/preview")
async def preview(request: Request) -> JSONResponse:
    """Live normalization preview for a single textarea field.

    Body: {"field": "src_ips"|"dst_ips"|"tcp_ports"|"udp_ports", "value": "..."}
    """
    payload = await request.json()
    field = payload.get("field", "")
    value = payload.get("value", "")
    lines = [s.strip() for s in value.splitlines() if s.strip()]
    if not lines:
        return JSONResponse({"normalized": [], "was_changed": False})

    try:
        if field in ("src_ips", "dst_ips"):
            normalized = [normalize_cidr(s) for s in lines]
            was_changed = any(cidr_was_normalized(s) for s in lines)
        elif field in ("tcp_ports", "udp_ports"):
            normalized = []
            for s in lines:
                spec, _kind = parse_port_spec(s)
                normalized.append(spec)
            was_changed = any(spec != s.strip() for spec, s in zip(normalized, lines))
        else:
            return JSONResponse({"error": f"unknown field: {field}"}, status_code=400)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    return JSONResponse({"normalized": normalized, "was_changed": was_changed})


@app.post("/generate")
async def generate(
    name: str = Form(...),
    from_zone: str = Form(...),
    to_zone: str = Form(...),
    src_ips: str = Form(""),
    dst_ips: str = Form(""),
    tcp_ports: str = Form(""),
    udp_ports: str = Form(""),
    action: str = Form("permit"),
    description: str = Form(""),
) -> JSONResponse:
    try:
        policy_input = PolicyInput(
            name=name.strip(),
            from_zone=from_zone.strip(),
            to_zone=to_zone.strip(),
            src_ips=[s for s in src_ips.splitlines() if s.strip()],
            dst_ips=[s for s in dst_ips.splitlines() if s.strip()],
            tcp_ports=[s for s in tcp_ports.splitlines() if s.strip()],
            udp_ports=[s for s in udp_ports.splitlines() if s.strip()],
            action=action,
            description=description,
        )
        set_cmds, addresses, applications, policy = render_set(policy_input)
        return JSONResponse(
            {
                "ok": True,
                "set_commands": set_cmds,
                "addresses": [a.model_dump() for a in addresses],
                "applications": [a.model_dump() for a in applications],
                "policy": policy.model_dump(),
            }
        )
    except ValidationError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
