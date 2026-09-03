# FastAPI CRUD Demo — Project Context File

> Generated for the LLM agent. This file summarizes the source code so future
> sessions can work without re-reading every file. When the code changes,
> update this file.

## 1. What this project is

A **FastAPI + SQLAlchemy (async) + Alembic** application in the
`fastapi-crud-demo` directory. It does two things:

1. A classic **CRUD API for `products`** (create / read-all / read-one /
   update / delete).
2. An **AI billing chat endpoint** (`POST /products/chat`) that calls a
   hosted LLM (via OpenRouter) and lets the model call tools
   (`get_lookups`, `search_product`, `find_customer`, `get_bill`,
   `create_or_update_bill`) that hit the **Zedex Business API**'s
   tool-calling controller at `{ZEDEX_API_BASE_URL}/tools` (default
   `http://localhost:61815/api/tools`).

Runs with **`uv`**. Python `>=3.12`. Async driver: `asyncpg`.

**Run command** (from `app/commands for this project.txt`):

```
uv run fastapi dev app/main.py
```

**Current git branch:** `Zedex_LLM_Chat_Calling`

---

## 2. Project layout

```
fastapi-crud-demo/
├── app/
│   ├── main.py                     # FastAPI app, exception handlers, router mount
│   ├── api/
│   │   ├── products.py             # CRUD + /chat router (prefix /products)
│   │   └── __init.py               # NOTE: typo — should be __init__.py (empty)
│   ├── core/
│   │   ├── config.py               # pydantic-settings Settings from .env
│   │   └── exceptions.py           # ProductNotFoundException
│   ├── database/
│   │   ├── base.py                 # SQLAlchemy DeclarativeBase (Base)
│   │   ├── connection.py           # async engine + AsyncSessionLocal + get_db
│   │   └── __init__.py             # empty
│   ├── models/
│   │   ├── product.py              # Product ORM model (table "products")
│   │   └── __init__.py             # empty
│   ├── repositories/
│   │   └── product_repository.py   # DB access functions (get_all/get_by_id/...)
│   ├── schemas/
│   │   ├── product.py              # ProductCreate/Update/Response (Pydantic)
│   │   └── chat.py                 # ChatRole/ChatRequest/ChatResponse (Pydantic)
│   └── services/
│       ├── product_service.py      # business logic over repositories
│       ├── chat_service.py         # LLM chat loop (system prompt, tool calls)
│       └── tools_service.py        # tool schemas + implementations (HTTP)
├── alembic/
│   ├── env.py                      # async-capable Alembic env
│   └── versions/
│       └── 6a7d69d8a379_create_products_table.py
├── alembic.ini
├── pyproject.toml                  # deps (uv)
├── .env                            # DATABASE_URL, OPENROUTER_API_KEY, OPENROUTER_BASE_URL
└── .gitignore                      # NOTE: ignores alembic/env.py
```

> `app/services/__init__.py` **does not exist** — a fresh package import
> (`from app.services import ...`) still works because Python 3.3+ implicit
> namespace packages, but adding `__init__.py` would be cleaner.
> `app/schemas/__init__.py` also does **not** exist.

## 3. Dependencies (pyproject.toml)

- alembic >=1.19.1
- asyncpg >=0.31.0
- fastapi[standard] >=0.141.1
- pydantic-settings >=2.15.0
- requests >=2.32.0
- sqlalchemy >=2.0.52
- openai >=1.0.0

## 4. Environment (.env)

- `DATABASE_URL=postgresql+asyncpg://postgres:....@localhost:5432/TestForFastAPI`
- `OPENROUTER_API_KEY=sk-or-v1-...`
- `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`
- `ZEDEX_API_BASE_URL=http://localhost:61815/api` (optional — this is the
  default baked into `Settings`; only needed to point at a different Zedex.Api
  instance)

`.env` is git-ignored (as expected; `.env.example` would hold a template).

## 5. Files in detail

### app/core/config.py

`Settings(BaseSettings)` with fields `database_url`, `openrouter_api_key`,
`openrouter_base_url`, `zedex_api_base_url` (defaults to
`http://localhost:61815/api`); loads from `.env` via `SettingsConfigDict`.
Module-level singleton `settings = Settings()`. Used by DB connection, chat
service, and `tools_service`.

### app/core/exceptions.py

`ProductNotFoundException(product_id)` — message:
`"Product with id {id} was not found"`. Raised when a product lookup fails.

### app/database/base.py

`class Base(DeclarativeBase)` — the SQLAlchemy 2.0 base for all models.

### app/database/connection.py

- `engine = create_async_engine(settings.database_url)`
- `AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)`
- `async def get_db()` — FastAPI dependency yielding a session.

### app/models/product.py

```python
class Product(Base):
    __tablename__ = "products"
    id:    Mapped[int]   = mapped_column(primary_key=True, autoincrement=True)
    name:  Mapped[str]   = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
```

### app/repositories/product_repository.py

All functions take `session: AsyncSession`:

- `get_all(session)` → `select(Product)` → `.scalars().all()`
- `get_by_id(session, product_id)` → `scalar_one_or_none()`
- `create(session, product)` → add, commit, refresh, return
- `delete(session, product)` → delete, commit
- `update(session, product)` → commit, refresh, return

### app/schemas/product.py (Pydantic)

- `ProductCreate`: `name: str`, `price: float`
- `ProductUpdate`: same fields (note: identical to Create)
- `ProductResponse`: `id`, `name`, `price`, with `from_attributes=True`
  (ORM mode via `model_config`).

### app/schemas/chat.py (Pydantic)

- `ChatRole`: `role: Literal["user","assistant"]`, `content: str`
- `ChatRequest`: `message: str`, `history: list[ChatRole]`, `customer_id: int | None`
- `ChatResponse`: `reply: str`, `history: list[dict]`, `tool_calls_used: list[str]`
- Uses `typing_extensions.Literal`.

### app/api/products.py (router prefix `/products`, tags=["Products"])

Dependencies via `get_db`. Imports both `product_service` and `chat_service`.

- `POST /products/` — create (response `ProductResponse`)
- `GET /products/` — list all (response `list[ProductResponse]`)
- `GET /products/{product_id}` — one
- `PUT /products/{product_id}` — update (uses `ProductUpdate`)
- `DELETE /products/{product_id}` — delete
- `POST /products/chat` — AI chat (`ChatRequest` → `ChatResponse`)

Note: `DELETE` returns `None` (no `response_model`), unlike a 204.

### app/services/product_service.py

- `get_products(session)` → repo `get_all`
- `get_product(session, product_id)` → repo `get_by_id`; raises
  `ProductNotFoundException` if `None`
- `create_product(session, product)` → builds `Product`, repo `create`
- `update_product(session, product_id, product)` → repo lookup (raises if
  `None`), sets name/price, repo `update`
- `delete_product(session, product_id)` → lookup (raises if `None`), repo `delete`

### app/services/tools_service.py

HTTP client for the **Zedex.Api tool-calling controller** at
`TOOLS_URL = f"{settings.zedex_api_base_url}/tools"` (default
`http://localhost:61815/api/tools`) — mirrors `Zedex.Api`'s
`ToolCallingController` one-to-one.

URLs:

- `LOOKUPS_URL` → `{TOOLS_URL}/lookups`
- `SEARCH_URL` → `{TOOLS_URL}/products/search`
- `CUSTOMERS_URL` → `{TOOLS_URL}/customers`
- `BILLS_URL` → `{TOOLS_URL}/bills`
- `DEFAULT_CUSTOMER_ID` → `os.getenv("DEFAULT_CUSTOMER_ID", "37")`, cast to `int`.

Defines OpenAI tool schemas:

- **`get_lookups`** — no params; returns lookup lists (colors, gauges,
  categories, companies).
- **`search_product`** — `products: [{productName(required), company, color,
  gauge, category}]` (the `size` field was removed — the Zedex API's
  `ProductSearchRequestDto` never had one; it was previously advertised but
  silently dropped before sending).
- **`find_customer`** — `search` (optional string); resolves a name/phone to
  a `customerId` before creating/updating a bill.
- **`get_bill`** — `idOrInvoiceNumber` (required string); fetches a bill's
  header + line items (each with `billItemId`) — call before editing.
- **`create_or_update_bill`** — `customerId` (required), `items` (required,
  `[{billItemId, productId(required), quantity(required), sizeFt,
  discountPercent}]`), optional `billId` (omit/0 = create, set = update) and
  `remarks`. Replaces the old separate `create_bill`/`update_bill`/
  `get_invoice_by_number` tools, matching `Zedex.Api`'s unified
  `POST /api/tools/bills` and new `GET /api/tools/bills/{idOrInvoiceNumber}`.

`TOOLS` = the five schemas wrapped as `{"type":"function", ...}`.

Implementations all go through `_request_json(method, url, **kwargs)`, which
does **not** raise on HTTP 4xx/5xx — it returns
`{"error": True, "status": ..., "detail": ...}` so the model sees the Zedex
API's validation/not-found/conflict messages as tool output and can react,
instead of the whole chat request failing with a 500. Only connection-level
failures (server down, DNS, timeout) still raise up to `chat_service`'s
`except Exception` → `HTTPException(500)`.

- `get_lookups()` → GET `LOOKUPS_URL`.
- `search_product(products)` → POST `SEARCH_URL` with mapped list.
- `find_customer(search=None)` → GET `CUSTOMERS_URL?search=...`.
- `get_bill(id_or_invoice_number)` → GET `BILLS_URL/{id_or_invoice_number}`.
- `create_or_update_bill(items, customer_id=None, bill_id=None, remarks=None)`
  → POST `BILLS_URL`; payload
  `{billId, customerId: customer_id if not None else DEFAULT_CUSTOMER_ID,
  remarks: remarks or "AI", items}`.
- `handle_tool_calls(message)` → iterates `message.tool_calls`, dispatches by
  name (also accepts names with a `_function` suffix), returns
  `(tool_responses, used_tools)`.

### app/services/chat_service.py

- `_client()` → builds `OpenAI(api_key, base_url)` from settings.
- `_Model = "gpt-4o-mini"` via OpenRouter.
- `_sanitize_messages(messages)` → drops messages with roles not in
  `{"system","user","assistant","tool"}`; replaces `None` content with `""`.
- `run_chat(messages, customer_id=None)` — tool-call loop: calls
  `client.chat.completions.create(model=_Model, messages, tools=TOOLS)`;
  while `finish_reason == "tool_calls"`, calls `handle_tool_calls`, appends
  assistant tool-call message + tool responses, repeats; returns
  `(final_content, used_tools)`.
- `SYSTEM_MESSAGE` — a long **Billing Agent** system prompt describing how to
  parse product requirements, apply shared values, validate against lookups,
  ask only when ambiguous, and produce a table before creating a bill. Also
  instructs the model to resolve a named customer via `find_customer` before
  creating/updating a bill, and to call `get_bill` first when editing an
  existing bill (to learn current line items and their `billItemId`s).
- `async chat(request: ChatRequest)` — builds `messages`, calls `run_chat`,
  returns a `ChatResponse` echoing updated history; wraps any exception in
  `HTTPException(500)`. **Must NOT `await` the `ChatResponse`** (Pydantic
  models aren't awaitable — doing so previously caused an HTTP 500). The
  `except Exception` handler now logs the full traceback (via
  `logging`/`traceback`) server-side so failures are diagnosable instead of
  being reduced to a bare `detail` string.

### app/main.py

Creates `app = FastAPI()` (no title/version set). Registers exception handler
for `ProductNotFoundException` → `JSONResponse(status_code=404, {"detail": str(exc)})`.
Mounts `product_router`. Root `GET /` → `{"message": "API is running"}`.

## 6. Database / Alembic

- **alembic.ini**: `script_location` = `%(here)s/alembic`, `prepend_sys_path = .`,
  `path_separator = os`. `sqlalchemy.url` in the ini is a placeholder — real URL
  comes from `settings.database_url` in `alembic/env.py`.
- **alembic/env.py**: async migrations. Imports `app.database.base.Base`,
  `app.models.product.Product`, `app.core.config.settings`. Uses `asyncio.run`
  around `run_async_migrations`, `create_async_engine(settings.database_url)`,
  `compare_type=True`.
- **Migration `6a7d69d8a379`** ("create_products_table"):
  - up: `create_table("products", id Integer PK autoincrement, name String(255)
not null, price Numeric(10,2) not null)`
  - down: `drop_table("products")`
  - `down_revision = None` (first migration)

## 7. Known quirks / notes (agent-relevant)

1. `app/api/__init.py` is misnamed — should be `__init__.py`.
   `app/services/__init__.py` and `app/schemas/__init__.py` are absent.
   Imports still work via namespace packages.
2. `.gitignore` ignores `alembic/env.py` (unusual — env.py is typically
   committed; the line is `alembic/env.py` at the very end).
3. ~~`tools_service.create_bill` ignored `customer_id` and its signature only
   accepted `items` while `handle_tool_calls` passed `customer_id=...` (would
   raise `TypeError` when the LLM called the tool)~~ — **FIXED**:
   `create_bill(items, customer_id=None)` uses `customer_id or
   DEFAULT_CUSTOMER_ID`.
4. **FIXED (chat 500):** `chat_service.chat` used `await ChatResponse(...)`,
   but Pydantic models aren't awaitable → `TypeError` → HTTP 500. The `await`
   was removed.
5. `ProductUpdate` and `ProductCreate` are identical — the update route
   therefore cannot tell "field omitted" from "set to default". All fields are
   required on update.
6. `DELETE /products/{id}` has no explicit status/response model.
7. The LLM tool-call loop lives only in `chat_service`; conversation state is
   echoed back to the caller via `ChatResponse.history` (the server is
   stateless).
8. `alembic.ini` `sqlalchemy.url` is a placeholder; the actual URL is injected
   in `env.py` from `.env`.
9. **Chat runtime error (environmental):** `OpenRouter` calls fail on this
   machine with `APIConnectionError: Connection error.` because DNS cannot
   resolve `api.openrouter.ai` (`Errno 11001 getaddrinfo failed`), while
   general DNS works (`google.com` resolves). The `.env` base URL is correct
   (`https://api.openrouter.ai/v1`). Fix the DNS/firewall/ISP block to reach
   OpenRouter — this is not a code bug.
