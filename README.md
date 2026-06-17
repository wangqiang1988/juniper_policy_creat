# Juniper Policy Generator

A small web app that turns a structured form (policy name, zones, IPs, ports) into a complete block of Juniper `set` commands you paste into your SRX. The app auto-creates the matching address and application objects, in the right order, with deterministic names.

It does **not** connect to your SRX. It only generates text.

## Features

- **CIDR normalization**: `10.20.0.5` → `10.20.0.5/32`; `10.20.0.5/24` → `10.20.0.0/24`. Real-time preview under each textarea.
- **Self-naming objects**: address object name = the CIDR itself (`10.20.0.0/24`). Application name = `tcp-443`, `tcp-8000-to-8100`, `udp-53`.
- **Multi-value inputs**: source/dest IPs and TCP/UDP ports accept one value per line.
- **Port ranges**: `8000-8100` is rendered as a single application with a destination-port range.
- **Deterministic**: no randomness, no LLM. Same input → identical output, byte-for-byte.
- **Pure Python**: FastAPI + Jinja2 + Pydantic. Runs offline.

## Quick start

### Option A — Local Python (with `uv`)

```bash
# 1. Install dependencies
uv sync --dev

# 2. Run the test suite (should be 66 passed)
uv run pytest

# 3. Start the web app
uv run uvicorn app:app --reload --host 0.0.0.0 --port 8000

# 4. Open in browser
#    http://localhost:8000
```

### Option B — Docker

```bash
# Build and run with docker compose (recommended)
docker compose up --build

# Or plain docker
docker build -t juniper-policy-generator .
docker run --rm -p 8000:8000 juniper-policy-generator

# Open in browser
#    http://localhost:8000
```

The image is multi-stage: builder compiles deps into a venv, runtime stage copies the venv + source into a minimal `python:3.12-slim` image and runs as a non-root user. It includes a `/health` endpoint and a `HEALTHCHECK` directive so `docker ps` shows healthy status.

To expose on a different port:
```bash
docker run --rm -p 9000:8000 juniper-policy-generator   # host 9000 -> container 8000
```

That's it. Fill the form, click **Generate set commands**, copy the output, paste into your SRX.

## How to use

1. Fill the form on the home page:
   - **Policy name**: lowercase, digits, `-` or `_` (e.g. `sales-chi-to-sfdc`)
   - **From zone / To zone**: SRX zone names
   - **Source IPs / Destination IPs**: one per line. Each line is auto-normalized:
     - `10.20.0.5` → `10.20.0.5/32`
     - `10.20.0.5/24` → `10.20.0.0/24`
   - **TCP ports / UDP ports**: one per line. `443` or `8000-8100`.
   - **Action**: `permit` (default) or `deny`
   - **Description**: optional
2. As you type, each textarea shows a green/yellow preview line with the normalized form. Yellow = normalization happened.
3. Click **Generate set commands**. The right panel shows:
   - summary pills (number of addresses, applications, policy name, action)
   - the full `set` command block
   - **Copy to clipboard** and **Download .set** buttons
   - an expandable object summary
4. On the SRX:
   ```bash
   # Option A: paste into configure mode
   configure
   <paste the set commands>
   commit and-quit

   # Option B: load from file
   configure
   load set /var/tmp/policy.set
   show | compare
   commit and-quit
   ```

## Naming convention

| Input | Object name on the SRX |
|---|---|
| src `10.20.0.0/24` | `10.20.0.0/24` |
| src `10.20.0.5` (no /) | `10.20.0.5/32` |
| dst `203.0.113.0/24` | `203.0.113.0/24` |
| TCP port `443` | `tcp-443` |
| TCP range `8000-8100` | `tcp-8000-to-8100` |
| UDP port `53` | `udp-53` |

Address object names are the CIDR itself (the name on the SRX equals the value). Application names are `{protocol}-{port}`. If you regenerate a policy with the same inputs, the new command block will collide on existing objects — rename or delete the old ones first.

> Note: Juniper address object names typically must match `[a-zA-Z0-9_-]{1,63}`. The forward slash `/` in `10.20.0.0/24` is not legal in Junos object names. If the device rejects the name, change `ip_to_object_name` in `juniper_policy_generator/naming.py` to return a sanitized form (e.g. `addr-10-20-0-0-24`).

## Architecture

```
juniper-policy-generator/
├── pyproject.toml
├── app.py                       # FastAPI: /, /preview, /generate
├── juniper_policy_generator/
│   ├── models.py                # Pydantic models
│   ├── naming.py                # CIDR/port normalization, naming rules
│   ├── validator.py             # Input validation
│   ├── renderer.py              # Jinja2 rendering of set commands
│   └── templates/
│       ├── index.html           # The form + JS for live preview
│       └── policy.set.j2        # set-command template
├── tests/
│   ├── test_naming.py
│   ├── test_validator.py
│   └── test_renderer.py
└── examples/
    ├── chi-sales-sfdc.yaml      # Example YAML input
    ├── chi-sales-sfdc.set       # Example rendered output
    └── dns-egress.yaml          # Another example
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Form UI |
| `POST` | `/preview` | Live CIDR/port normalization (used by JS) |
| `POST` | `/generate` | Render the full `set` command block |

`/preview` body: `{"field": "src_ips", "value": "10.20.0.5/24\n..."}`

`/generate` body: standard form fields (see `app.py`).

## Adding new fields (e.g., owner, ticket, expire)

1. Add the field to `PolicyInput` in `juniper_policy_generator/models.py`.
2. Add the field to the form in `juniper_policy_generator/templates/index.html`.
3. Pass it through in `app.py` `generate()`.
4. Reference it in `juniper_policy_generator/templates/policy.set.j2` if you want it in the output.
5. Add a test in `tests/test_renderer.py`.

## Out of scope (intentional)

- ❌ Connecting to the SRX (NETCONF/SSH). The app generates text only.
- ❌ Reading existing config. The app does not know what's already on the device.
- ❌ Multi-vendor support. Juniper SRX only.
- ❌ Authentication, multi-tenant, billing. Single-user local tool.
- ❌ LLM / AI. Pure deterministic generation.

## License

Personal project; do whatever you want.
