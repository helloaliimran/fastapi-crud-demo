
import json
import os
import requests

from app.core.config import settings


TOOLS_URL = f"{settings.zedex_api_base_url}/tools"
LOOKUPS_URL = f"{TOOLS_URL}/lookups"
SEARCH_URL = f"{TOOLS_URL}/products/search"
CUSTOMERS_URL = f"{TOOLS_URL}/customers"
BILLS_URL = f"{TOOLS_URL}/bills"
DEFAULT_CUSTOMER_ID = int(os.getenv("DEFAULT_CUSTOMER_ID", "37"))

_JSON_HEADERS = {"accept": "application/json",
                 "Content-Type": "application/json"}


def _request_json(method, url, **kwargs):
    """Call the Zedex tools API and always return JSON the LLM can read.

    HTTP 4xx/5xx responses are NOT raised — the Zedex tools endpoints return a
    JSON body describing what went wrong (e.g. "Bill not found.", validation
    errors), and the model should see that and react instead of the whole
    chat request failing with a 500. Only connection-level failures (server
    down, DNS, timeout) still raise.
    """
    response = requests.request(
        method, url, headers=_JSON_HEADERS, timeout=30, **kwargs)
    try:
        body = response.json() if response.text.strip() else None
    except ValueError:
        body = response.text

    if response.status_code >= 400:
        return {"error": True, "status": response.status_code, "detail": body}
    return body


# ---------------------------------------------------------------------------
# Tool schemas (mirror Zedex.Api's ToolCallingController)
# ---------------------------------------------------------------------------
get_lookups_function = {
    "name": "get_lookups",
    "description": "Get the lookups: colors, gauges, categories, companies",
    "additionalProperties": False,
}

search_product_function = {
    "name": "search_product",
    "description": "Search for one or more products.",
    "parameters": {
        "type": "object",
        "properties": {
            "products": {
                "type": "array",
                "description": "List of products to search for.",
                "items": {
                    "type": "object",
                    "properties": {
                        "productName": {"type": "string", "description": "Product name. Required."},
                        "company": {"type": "string", "description": "Company name. Optional."},
                        "color": {"type": "string", "description": "Product color. Optional."},
                        "gauge": {"type": "string", "description": "Product gauge. Optional."},
                        "category": {"type": "string", "description": "Product category. Optional."},
                    },
                    "required": ["productName"],
                },
            }
        },
        "required": ["products"],
    },
}

find_customer_function = {
    "name": "find_customer",
    "description": "Find customers by name or phone (contains match, max 20 results, alphabetical). Use this to resolve a customer name/phone the user gave to a customerId before creating or updating a bill.",
    "parameters": {
        "type": "object",
        "properties": {
            "search": {"type": "string", "description": "Name or phone fragment to search for. Optional — omit to browse the first 20 customers."},
        },
        "required": [],
    },
}

get_bill_function = {
    "name": "get_bill",
    "description": "Get a bill's full header and line items (with each line's billItemId) by bill id or invoice number. Always call this before editing a bill so the existing line items and their billItemIds are known.",
    "parameters": {
        "type": "object",
        "properties": {
            "idOrInvoiceNumber": {
                "type": "string",
                "description": "The bill id (e.g. 42) or invoice number (e.g. INV-20260825-0001). Required."
            }
        },
        "required": ["idOrInvoiceNumber"],
    },
}

create_or_update_bill_function = {
    "name": "create_or_update_bill",
    "description": "Create a new draft bill, or update an existing one when billId is given. Line semantics: billItemId null/0 (or omitted) adds a new line; billItemId set updates that existing line. On update, existing lines whose billItemId is left out of items are removed — always pass the FULL list of lines the bill should end up with. Standard (non-PVC) products only. Posted bills cannot be edited.",
    "parameters": {
        "type": "object",
        "properties": {
            "billId": {"type": "integer", "description": "Omit or 0 to create a new bill. Set to an existing bill id (from get_bill) to update that draft."},
            "customerId": {"type": "integer", "description": "The customer this bill is for. Required — resolve with find_customer first if not already known."},
            "remarks": {"type": "string", "description": "Optional remark/note for the bill."},
            "items": {
                "type": "array",
                "description": "The full list of line items the bill should have.",
                "items": {
                    "type": "object",
                    "properties": {
                        "billItemId": {"type": "integer", "description": "Id of an existing line to update (from get_bill). Omit or 0 for a new line."},
                        "productId": {"type": "integer", "description": "Product ID. Required."},
                        "quantity": {"type": "number", "description": "Quantity of the product. Required."},
                        "sizeFt": {"type": "number", "description": "Product size in feet. Required for per-foot products."},
                        "discountPercent": {"type": "number", "description": "Discount percentage. Optional."},
                    },
                    "required": ["productId", "quantity"],
                },
            },
        },
        "required": ["customerId", "items"],
    },
}


TOOLS = [
    {"type": "function", "function": get_lookups_function},
    {"type": "function", "function": search_product_function},
    {"type": "function", "function": find_customer_function},
    {"type": "function", "function": get_bill_function},
    {"type": "function", "function": create_or_update_bill_function},
]
# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def get_lookups():
    return _request_json("GET", LOOKUPS_URL)


def search_product(products):
    data = [
        {
            "productName": product["productName"],
            "color": product.get("color"),
            "gauge": product.get("gauge"),
            "category": product.get("category"),
            "company": product.get("company"),
        }
        for product in products
    ]
    return _request_json("POST", SEARCH_URL, json=data)


def find_customer(search=None):
    params = {"search": search} if search else None
    return _request_json("GET", CUSTOMERS_URL, params=params)


def get_bill(id_or_invoice_number):
    return _request_json("GET", f"{BILLS_URL}/{id_or_invoice_number}")


def create_or_update_bill(items, customer_id=None, bill_id=None, remarks=None):
    payload = {
        "billId": bill_id,
        "customerId": customer_id if customer_id is not None else DEFAULT_CUSTOMER_ID,
        "remarks": remarks or "AI",
        "items": items,
    }
    return _request_json("POST", BILLS_URL, json=payload)


def handle_tool_calls(message):
    responses = []
    used_tools = []

    for tool_call in message.tool_calls:
        tool_name = tool_call.function.name
        used_tools.append(tool_name)
        print(f"tool calling {tool_name}")
        arguments = json.loads(
            tool_call.function.arguments) if tool_call.function.arguments else {}

        if tool_name in ("search_product_function", "search_product"):
            result = search_product(arguments.get("products", []))

        elif tool_name in ("get_lookups_function", "get_lookups"):
            result = get_lookups()

        elif tool_name in ("find_customer_function", "find_customer"):
            result = find_customer(arguments.get("search"))

        elif tool_name in ("get_bill_function", "get_bill"):
            result = get_bill(arguments.get("idOrInvoiceNumber"))

        elif tool_name in ("create_or_update_bill_function", "create_or_update_bill"):
            result = create_or_update_bill(
                arguments.get("items", []),
                customer_id=arguments.get("customerId"),
                bill_id=arguments.get("billId"),
                remarks=arguments.get("remarks"),
            )

        else:
            result = {"error": f"Unknown tool named {tool_name}"}

        responses.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            }
        )

    return responses, used_tools
