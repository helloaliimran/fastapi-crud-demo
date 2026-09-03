# FastAPI CRUD Demo — AI Billing Agent

An async **FastAPI** backend that pairs a textbook CRUD API with something more interesting: a **multi-turn LLM tool-calling agent** that turns a plain-English message ("10 door panels in black, 1.2mm gauge for John") into a validated, priced invoice — by calling real backend tools, not by hallucinating numbers.

Built to demonstrate practical skill with **Python, FastAPI, async SQLAlchemy, and LLM function-calling/agent design**, integrated end-to-end against a real external REST API.

---

## What this project demonstrates

- **LLM tool-calling / function-calling agent design** — an OpenAI-compatible tool schema (via OpenRouter), a multi-turn `while finish_reason == "tool_calls"` loop, argument parsing, and a dispatcher that routes each tool call to a typed Python function.
- **Designing an API contract for an AI agent, not a human** — the tool set (`get_lookups`, `search_product`, `find_customer`, `get_bill`, `create_or_update_bill`) was scoped specifically so an LLM can reliably look things up, resolve ambiguity, and safely edit existing records without re-sending unrelated data.
- **Clean layered architecture** — `api/` (routers) → `services/` (business logic) → `repositories/` (data access) → `schemas/`/`models/` (contracts), with async SQLAlchemy 2.0 and Alembic migrations.
- **Resilient integration with a real external system** — the agent's tools call a separate **.NET (ASP.NET Core) backend**, the Zedex Business API, over HTTP. Errors from that API (validation failures, "bill not found", posted-bill conflicts) are surfaced back to the LLM as structured tool output instead of crashing the request, so the agent can recover mid-conversation.
- **Configuration & environment management** — typed settings via `pydantic-settings`, `.env`-driven, no hardcoded secrets.

---

## The AI Billing Agent

A single endpoint, `POST /products/chat`, exposes a stateless conversational agent. The caller sends a message (+ optional prior history) and gets back a reply, updated history, and the list of tools the model actually invoked.

```
POST /products/chat
{
  "message": "Create a bill for Ali: 10x Door Panel 159x20, black, 1.2mm, size 19",
  "history": []
}
```

The agent doesn't write invoice numbers, prices, or product IDs itself — it looks everything up through tools backed by the real database, then asks the API to create the bill. That separation (LLM decides *what* to do, the backend decides *if it's valid and what it costs*) is the core design idea.

### Tools exposed to the model

| Tool | Purpose | Backing endpoint |
|---|---|---|
| `get_lookups` | Fetch valid colors, gauges, categories, companies | `GET /api/tools/lookups` |
| `search_product` | Fuzzy/contains search for products by name + optional refinements | `POST /api/tools/products/search` |
| `find_customer` | Resolve a spoken/typed customer name or phone to a `customerId` | `GET /api/tools/customers` |
| `get_bill` | Fetch a bill's header + line items (with `billItemId`s) before an edit | `GET /api/tools/bills/{idOrInvoiceNumber}` |
| `create_or_update_bill` | Create a new draft bill, or merge-edit an existing one | `POST /api/tools/bills` |

`create_or_update_bill` is a single unified tool rather than separate create/update tools: on edit, existing line items are matched by `billItemId` (kept/updated), new lines omit it, and lines left out of the request are removed — a merge model the LLM can reason about without needing to track a diff itself.

### Example flow

1. User: *"I need door panels, black, 1.2mm, qty 10, for Ali Khan"*
2. Agent calls `get_lookups` + `search_product` to validate the color/gauge/product exist and resolve a `productId`.
3. Agent calls `find_customer("Ali Khan")` to resolve a `customerId` — asks the user to disambiguate if more than one match comes back.
4. Agent presents a summary table and, once confirmed, calls `create_or_update_bill` — returns the new invoice number.
5. Later, *"add 5 more window panels to that bill"* → agent calls `get_bill` first to load current lines, then `create_or_update_bill` with the full merged item list.

---

## Tech stack

- **FastAPI** (async) + **Uvicorn**
- **SQLAlchemy 2.0** (async) + **asyncpg** + **Alembic** migrations
- **Pydantic v2** / **pydantic-settings**
- **OpenAI SDK** pointed at **OpenRouter** for the LLM
- **requests** for synchronous calls into the external Zedex Business API
- **PostgreSQL**

---

## Project structure

```
app/
├── api/
│   └── products.py         # routes: CRUD + POST /products/chat
├── core/
│   ├── config.py           # typed Settings (.env-driven)
│   └── exceptions.py
├── database/                # async engine/session setup
├── models/                  # SQLAlchemy ORM models
├── repositories/             # data access layer
├── schemas/                  # Pydantic request/response contracts
└── services/
    ├── product_service.py    # CRUD business logic
    ├── chat_service.py       # agent loop + system prompt
    └── tools_service.py      # tool schemas + HTTP calls to the external API
alembic/                      # async database migrations
```

---

## Getting started

```bash
uv sync
```

Create a `.env`:

```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/your_db
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
ZEDEX_API_BASE_URL=http://localhost:61815/api   # optional, this is the default
```

Run migrations and start the server:

```bash
uv run alembic upgrade head
uv run fastapi dev app/main.py
```

Interactive API docs: `http://127.0.0.1:8000/docs`

---

## API reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/products/` | Create a product |
| `GET` | `/products/` | List products |
| `GET` | `/products/{id}` | Get one product |
| `PUT` | `/products/{id}` | Update a product |
| `DELETE` | `/products/{id}` | Delete a product |
| `POST` | `/products/chat` | Talk to the AI billing agent |

---

## Notable engineering decisions

- **Tool errors return, they don't raise.** HTTP 4xx/5xx responses from the external API are converted into a `{"error": true, ...}` payload handed back to the model as tool output, so a validation failure becomes something the agent can explain to the user and recover from — not a 500 that ends the conversation.
- **Stateless by design.** The server holds no session state; the client echoes conversation history back on each turn (`ChatResponse.history`), keeping the API simple to scale and test.
- **Contract designed for an LLM caller, not a UI.** Tool parameter names, required/optional fields, and descriptions were written to be self-explanatory to a model reading them cold, minimizing prompt engineering needed to get reliable tool use.

## Known limitations

- No authentication yet on the external API's tool endpoints (tracked, deliberate for now).
- The billing agent covers Standard (non-PVC) products only.
- No automated test suite yet.
