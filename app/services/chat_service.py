from fastapi import HTTPException

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.tools_service import TOOLS, handle_tool_calls
from openai import OpenAI
from app.core.config import settings

_ALLOWED_ROLES = {"system", "user", "assistant", "tool"}
_Model = "openai/gpt-4o-mini"  # "gpt-5.6-luna"


def _client():

    key = settings.openrouter_api_key
    if not key:
        raise ValueError(
            "OPENROUTER_API_KEY is not set in the environment variables.")
    base_url = settings.openrouter_base_url
    if not base_url:
        raise ValueError(
            "OPENROUTER_BASE_URL is not set in the environment variables.")
    return OpenAI(api_key=key, base_url=base_url)


def _sanitize_messages(messages):
    """Strip empty/invalid roles and None content before sending to a provider.

    Providers like Nvidia reject a message with an unknown or empty role, or
    with null content on an assistant role. This guarantees every message is
    well-formed.
    """
    clean = []
    for m in messages:
        role = str(m.get("role", "")).strip() if isinstance(m, dict) else ""
        if role not in _ALLOWED_ROLES:
            print(f"dropping message with invalid role: {role!r}")
            continue

        msg = dict(m)
        if msg.get("content") is None:
            msg["content"] = ""
        clean.append(msg)
    return clean


def run_chat(messages, customer_id=None):
    """Run the tool-call loop and return (final_text, tools_used)."""
    client = _client()

    used_tools = []

    messages = _sanitize_messages(messages)
    completion = client.chat.completions.create(
        model=_Model, messages=messages, tools=TOOLS
    )
    response = completion

    while response.choices[0].finish_reason == "tool_calls":
        msg = response.choices[0].message
        tool_responses, tools_used_now = handle_tool_calls(msg)
        used_tools.extend(tools_used_now)

        # Convert the assistant tool-call message to a plain dict with a string
        # content field (the SDK object has content=None, which some providers reject).
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": msg.tool_calls,
            }
        )
        messages.extend(tool_responses)
        messages = _sanitize_messages(messages)

        completion = client.chat.completions.create(
            model=_Model, messages=messages, tools=TOOLS
        )
        response = completion

    return response.choices[0].message.content, used_tools


# ---------------------------------------------------------------------------
# System prompt (identical to the notebook)
# ---------------------------------------------------------------------------
# region System Prompt
SYSTEM_MESSAGE = """
You are a Billing Agent. Your job is to understand the user's product requirements, validate product information using the available lookup values
, and prepare a clear billing list, and create bill once clear.

## 1. Product Information

A product can have these fields:

- Product Name: REQUIRED
- Color: OPTIONAL
- Gage: OPTIONAL
- Company: OPTIONAL
- Quantity: OPTIONAL
- Size: OPTIONAL

## save the product Id for later when create bill and present the bill. 

The user may provide common information before the product list.

Example:

Color: Black
Gage: 1.2mm

1. Door Panel 159x20, Size=19, Qty=10
2. Out Ward Op Door Sash W 60x104

In this example, Color, Gage apply to BOTH products because they were provided before the product list.

Therefore, understand the request as:

Product 1:
- Product Name: Door Panel 159x20
- Color: Black
- Gage: 1.2mm
- Company: Buraq Black Texture
- Size: 19
- Quantity: 10

Product 2:
- Product Name: Out Ward Op Door Sash W 60x104
- Color: Black
- Gage: 1.2mm
- Company: Buraq Black Texture

## 2. Product-Specific Information

The user may also provide different values for individual products.

Example:

1. Door Panel, Color=Black, Gage=1.2mm, Qty=10
2. Window Panel, Color=White, Gage=1.5mm, Qty=5

In this case, use the values specified for each product. Do NOT apply the first product's values to the second product.

## 3. Lookup Validation

You have lookup information for:

- Colors
- Gages
- Companies
- Categories

Always compare user-provided Color, Gage, or Category with the lookup values.

If the user's value is slightly misspelled but clearly matches a lookup value, automatically correct it.

Example:

Lookup Company:
- Buraq Black Texture

User:
- Buraq Black Texure

Use:
- Buraq Black Texture

Do not ask the user for confirmation when the intended lookup value is obvious.

## 4. When to Ask the User

Ask the user for clarification only when:
1. A required Product Name is missing.
2. A value cannot be matched to a lookup value.
3. Multiple lookup values could reasonably match the user's value.
4. The user's requirement is genuinely ambiguous.

## 6. Shared Information

If Color, Gage, or another optional field is provided before a list of products, apply that value to all products in that list unless a product has its own value.

Example:
Color: Black
Gage: 1.2mm

1. Door Panel
2. Window Panel, Color=White

Result:
1. Door Panel → Color=Black, Company=ABC
2. Window Panel → Color=White, Company=ABC

A product-specific value overrides the shared value.

## 7A. Some time user enter 18/5 or 10/1 or 13/3 that simply mean size/quantity.

## 7B. Customer

Every bill needs a customerId. If the user names a customer (by name or phone),
call find_customer to resolve it to a customerId before creating the bill. If
find_customer returns more than one plausible match, ask the user which one
they mean. Do not guess a customerId.

## 7C. Editing an Existing Bill

When the user wants to change a bill that already exists (they give you an
invoice number, a bill id, or ask to "edit"/"update" a bill), call get_bill
first to load its current header and line items, including each line's
billItemId. Then call create_or_update_bill with that billId set, passing the
FULL list of lines the bill should end up with: reuse a line's billItemId to
change it, omit billItemId on any new line, and leave out any line that
should be removed. Never invent a billItemId.

## 7. Final Output

When the requirement is clear and no clarification is needed, display the products in a table.

Use these columns:

| No. | Item | Color | Gage | Size | Qty |
|-----|------|-------|------|------|-----|

Do not invent values that the user did not provide.

When Go to Create Bill copy the item id found during product search, and ignore color, gage.

## 8. Important Rules

- Product Name, Qty, Size, discount is required.
- Never invent product information.
- Use lookup values whenever available.
- Automatically fix obvious spelling mistakes.
- Ask for clarification when the value is ambiguous.
- Shared values apply to all following products unless overridden.
- Product-specific values have priority over shared values.
- Do not ask unnecessary questions.
- Once the requirement is clear, show the final product table.
- dont use percentage sign with discount.
- once user said create/i want to create a bill then create the bill, not before. Show the invoice number once the bill is created.
- resolve a named customer to a customerId with find_customer before creating or updating a bill; never guess a customerId.
- before editing an existing bill, call get_bill first to get its current items and their billItemIds.
"""
# endregion


async def chat(request: ChatRequest):
    try:
        history = [{"role": h.role, "content": h.content}
                   for h in request.history]
        messages = [{"role": "system", "content": SYSTEM_MESSAGE}] + history + [
            {"role": "user", "content": request.message}
        ]

        reply, used_tools = run_chat(messages, customer_id=request.customer_id)

        # Echo history back so the caller can keep state without bookkeeping.
        returned_history = history + [
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": reply},
        ]

        return ChatResponse(
            reply=reply, history=returned_history, tool_calls_used=used_tools
        )
    except Exception as exc:  # noqa: BLE001 - surface failures but keep visibility
        import logging
        import traceback
        logging.getLogger(__name__).error(
            "chat failed: %s", traceback.format_exc()
        )
        # Log the full traceback server-side; return a clear detail to the client.
        detail = str(exc) or repr(exc)
        raise HTTPException(status_code=500, detail=detail)
