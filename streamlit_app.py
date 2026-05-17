import json
import os

import requests
import streamlit as st
from openai import OpenAI

st.title("💬 Phoenix Phase Converters — AI Assistant")
st.write("Ask me to create quotes, look up calls, send texts, or check emails.")

# ── Credentials (auto-loaded from env vars) ──────────────────────────────────
with st.sidebar:
    st.header("Credentials")
    openai_api_key  = st.text_input("OpenAI API Key",                    value=os.environ.get("OPENAI_API_KEY",    ""), type="password")
    shopify_store   = st.text_input("Shopify Store Domain",              value=os.environ.get("SHOPIFY_STORE",     ""), placeholder="your-store.myshopify.com")
    shopify_token   = st.text_input("Shopify Admin API Access Token",    value=os.environ.get("SHOPIFY_TOKEN",     ""), type="password")
    openphone_key   = st.text_input("OpenPhone API Key",                 value=os.environ.get("OPENPHONE_API_KEY", ""), type="password")
    callrail_key    = st.text_input("CallRail API Key",                  value=os.environ.get("CALLRAIL_API_KEY",  ""), type="password")
    callrail_acct   = st.text_input("CallRail Account ID",               value=os.environ.get("CALLRAIL_ACCOUNT",  ""), placeholder="906309465")
    n8n_followup    = st.text_input("n8n Follow-up Webhook URL",         value=os.environ.get("N8N_FOLLOWUP_URL",  ""), placeholder="https://...")


# ── Shopify helpers ───────────────────────────────────────────────────────────
def _shopify_headers(token):
    return {"Content-Type": "application/json", "X-Shopify-Access-Token": token}

def shopify_create_customer(store, token, data):
    r = requests.post(f"https://{store}/admin/api/2025-01/customers.json",
                      headers=_shopify_headers(token), json={"customer": data}, timeout=30)
    r.raise_for_status()
    c = r.json().get("customer", {})
    return json.dumps({"id": c.get("id"), "email": c.get("email"), "name": f"{c.get('first_name','')} {c.get('last_name','')}".strip()})

def shopify_create_draft_order(store, token, data):
    r = requests.post(f"https://{store}/admin/api/2025-01/draft_orders.json",
                      headers=_shopify_headers(token), json={"draft_order": data}, timeout=30)
    r.raise_for_status()
    d = r.json().get("draft_order", {})
    return json.dumps({"id": d.get("id"), "name": d.get("name"), "invoice_url": d.get("invoice_url"), "status": d.get("status")})

def shopify_search_customers(store, token, query):
    r = requests.get(f"https://{store}/admin/api/2025-01/customers/search.json",
                     headers=_shopify_headers(token), params={"query": query, "limit": 5}, timeout=30)
    r.raise_for_status()
    customers = r.json().get("customers", [])
    return json.dumps([{"id": c["id"], "name": f"{c.get('first_name','')} {c.get('last_name','')}".strip(),
                        "email": c.get("email"), "phone": c.get("phone")} for c in customers])

def shopify_list_draft_orders(store, token, status="open"):
    r = requests.get(f"https://{store}/admin/api/2025-01/draft_orders.json",
                     headers=_shopify_headers(token), params={"status": status, "limit": 20}, timeout=30)
    r.raise_for_status()
    orders = r.json().get("draft_orders", [])
    return json.dumps([{"id": o["id"], "name": o["name"], "customer": o.get("customer", {}).get("email",""),
                        "total": o.get("total_price"), "invoice_url": o.get("invoice_url")} for o in orders])

def shopify_search_products(store, token, query):
    r = requests.get(f"https://{store}/admin/api/2025-01/products.json",
                     headers=_shopify_headers(token), params={"title": query, "limit": 10,
                     "fields": "id,title,variants"}, timeout=30)
    r.raise_for_status()
    products = r.json().get("products", [])
    out = []
    for p in products:
        for v in p.get("variants", []):
            out.append({"product_id": p["id"], "variant_id": v["id"], "title": p["title"],
                        "sku": v.get("sku"), "price": v.get("price")})
    return json.dumps(out)


# ── OpenPhone helpers ─────────────────────────────────────────────────────────
def _op_headers(key):
    return {"Authorization": key, "Content-Type": "application/json"}

def openphone_list_calls(key, limit=10):
    r = requests.get("https://api.openphone.com/v1/calls",
                     headers=_op_headers(key), params={"maxResults": limit}, timeout=30)
    r.raise_for_status()
    calls = r.json().get("data", [])
    return json.dumps([{"id": c.get("id"), "from": c.get("from"), "to": c.get("to"),
                        "duration": c.get("duration"), "createdAt": c.get("createdAt"),
                        "direction": c.get("direction")} for c in calls])

def openphone_get_transcript(key, call_id):
    r = requests.get(f"https://api.openphone.com/v1/call-transcripts/{call_id}",
                     headers=_op_headers(key), timeout=30)
    r.raise_for_status()
    return json.dumps(r.json().get("data", {}))

def openphone_send_sms(key, from_number, to_number, text):
    # Route via n8n to avoid rate limits when n8n webhook is set; fall back to direct API
    n8n_url = os.environ.get("N8N_FOLLOWUP_URL", "")
    if n8n_url:
        r = requests.post(n8n_url.replace("phoenix-followup-email", "retell-send-tracking-sms"),
                          json={"to": to_number, "message": text}, timeout=30)
        r.raise_for_status()
        return json.dumps({"ok": True, "via": "n8n"})
    r = requests.post("https://api.openphone.com/v1/messages",
                      headers=_op_headers(key),
                      json={"from": from_number, "to": [to_number], "content": text}, timeout=30)
    r.raise_for_status()
    return json.dumps(r.json().get("data", {}))

def openphone_list_messages(key, phone_number, limit=20):
    r = requests.get("https://api.openphone.com/v1/messages",
                     headers=_op_headers(key),
                     params={"phoneNumberId": phone_number, "maxResults": limit}, timeout=30)
    r.raise_for_status()
    msgs = r.json().get("data", [])
    return json.dumps([{"id": m.get("id"), "from": m.get("from"), "to": m.get("to"),
                        "body": m.get("body"), "createdAt": m.get("createdAt")} for m in msgs])


# ── CallRail helpers ──────────────────────────────────────────────────────────
def callrail_list_calls(key, account, limit=20, search=None):
    params = {"per_page": limit, "fields": "id,customer_name,customer_phone_number,duration,start_time,recording,tracking_source,note"}
    if search:
        params["search"] = search
    r = requests.get(f"https://api.callrail.com/v3/a/{account}/calls.json",
                     headers={"Authorization": f"Token token={key}"}, params=params, timeout=30)
    r.raise_for_status()
    calls = r.json().get("calls", [])
    return json.dumps([{"id": c.get("id"), "name": c.get("customer_name"),
                        "phone": c.get("customer_phone_number"), "duration": c.get("duration"),
                        "time": c.get("start_time"), "source": c.get("tracking_source"),
                        "note": c.get("note")} for c in calls])

def callrail_get_transcript(key, account, call_id):
    r = requests.get(f"https://api.callrail.com/v3/a/{account}/calls/{call_id}.json",
                     headers={"Authorization": f"Token token={key}"},
                     params={"fields": "transcription,recording,customer_name,customer_phone_number,start_time"}, timeout=30)
    r.raise_for_status()
    return json.dumps(r.json())


# ── Email (n8n follow-up) ─────────────────────────────────────────────────────
def send_followup_email(webhook_url, to_email, subject, first_name, call_date, need, model, sizing, product_url):
    r = requests.post(webhook_url, json={
        "toEmail": to_email, "subject": subject, "firstName": first_name,
        "callDate": call_date, "need": need, "model": model,
        "sizing": sizing, "productUrl": product_url
    }, timeout=30)
    r.raise_for_status()
    return json.dumps({"ok": True, "to": to_email, "subject": subject})


# ── Tool definitions ──────────────────────────────────────────────────────────
TOOLS = [
    # Shopify
    {"type": "function", "function": {"name": "shopify_create_customer", "description": "Create a new Shopify customer.",
        "parameters": {"type": "object", "properties": {"data": {"type": "object", "description": "Customer fields: first_name, last_name, email, phone, company, addresses, tags, note"}}, "required": ["data"]}}},
    {"type": "function", "function": {"name": "shopify_create_draft_order", "description": "Create a Shopify draft order (quote). Always create the customer first and include customer.id.",
        "parameters": {"type": "object", "properties": {"data": {"type": "object", "description": "Draft order object with line_items, customer, shipping_line, tax_exempt, note, tags"}}, "required": ["data"]}}},
    {"type": "function", "function": {"name": "shopify_search_customers", "description": "Search Shopify customers by name, email, or phone.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "shopify_list_draft_orders", "description": "List Shopify draft orders by status (open, invoice_sent, completed).",
        "parameters": {"type": "object", "properties": {"status": {"type": "string", "enum": ["open", "invoice_sent", "completed"], "default": "open"}}, "required": []}}},
    {"type": "function", "function": {"name": "shopify_search_products", "description": "Search Shopify products/variants by name or SKU to get variant IDs and prices.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    # OpenPhone
    {"type": "function", "function": {"name": "openphone_list_calls", "description": "List recent OpenPhone calls.",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "default": 10}}, "required": []}}},
    {"type": "function", "function": {"name": "openphone_get_transcript", "description": "Get the transcript for a specific OpenPhone call by call ID.",
        "parameters": {"type": "object", "properties": {"call_id": {"type": "string"}}, "required": ["call_id"]}}},
    {"type": "function", "function": {"name": "openphone_send_sms", "description": "Send an SMS via OpenPhone.",
        "parameters": {"type": "object", "properties": {
            "from_number": {"type": "string", "description": "OpenPhone number to send from (e.g. +16029628859)"},
            "to_number": {"type": "string", "description": "Recipient phone number in E.164 format"},
            "text": {"type": "string"}}, "required": ["from_number", "to_number", "text"]}}},
    {"type": "function", "function": {"name": "openphone_list_messages", "description": "List recent SMS messages for an OpenPhone number.",
        "parameters": {"type": "object", "properties": {
            "phone_number": {"type": "string", "description": "OpenPhone phone number ID"},
            "limit": {"type": "integer", "default": 20}}, "required": ["phone_number"]}}},
    # CallRail
    {"type": "function", "function": {"name": "callrail_list_calls", "description": "List recent CallRail calls, optionally searching by name or phone.",
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer", "default": 20},
            "search": {"type": "string", "description": "Optional search term (name or phone)"}}, "required": []}}},
    {"type": "function", "function": {"name": "callrail_get_transcript", "description": "Get the full transcript and recording info for a CallRail call.",
        "parameters": {"type": "object", "properties": {"call_id": {"type": "string"}}, "required": ["call_id"]}}},
    # Email
    {"type": "function", "function": {"name": "send_followup_email", "description": "Send the Phoenix Phase Converters branded HTML follow-up quote email via n8n.",
        "parameters": {"type": "object", "properties": {
            "to_email": {"type": "string"},
            "subject": {"type": "string", "description": "e.g. 'Phase Converter Quote — Company | Model'"},
            "first_name": {"type": "string"},
            "call_date": {"type": "string", "description": "e.g. 'Sunday, May 17, 2026'"},
            "need": {"type": "string", "description": "Description of customer's equipment/application"},
            "model": {"type": "string", "description": "Recommended model name"},
            "sizing": {"type": "string", "description": "Explanation of why this model was recommended"},
            "product_url": {"type": "string", "description": "Shopify invoice URL from draft order"}},
        "required": ["to_email", "subject", "first_name", "call_date", "need", "model", "sizing", "product_url"]}}},
]


# ── Credential check ──────────────────────────────────────────────────────────
missing = []
if not openai_api_key: missing.append("OpenAI API Key")
if not shopify_store or not shopify_token: missing.append("Shopify credentials")

if missing:
    st.info(f"Missing: {', '.join(missing)}. Add them in the sidebar.", icon="🔑")
else:
    client = OpenAI(api_key=openai_api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask me anything — quotes, calls, transcripts, texts, emails…"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        messages = [
            {"role": "system", "content": (
                "You are the AI assistant for Phoenix Phase Converters. You can:\n"
                "- Create Shopify customers and draft orders (quotes)\n"
                "- Search Shopify customers, products, and draft orders\n"
                "- Look up recent OpenPhone calls and transcripts\n"
                "- Send SMS via OpenPhone\n"
                "- Look up recent CallRail calls and transcripts\n"
                "- Send branded HTML follow-up quote emails via n8n\n\n"
                "RULES:\n"
                "- Always create Shopify customer FIRST, then draft order linked to that customer\n"
                "- Standard freight: $360 (most units), $500-650 (50HP+)\n"
                "- Always tax_exempt: true for phone quotes\n"
                "- Phone number to send FROM: +16029628859\n"
                "- Do not send emails without confirming with the user first\n"
                "- For quotes, ask for: customer name, email, phone, equipment/application, and model if not provided"
            )},
            *st.session_state.messages,
        ]

        # Agentic loop
        while True:
            completion = client.chat.completions.create(
                model="gpt-4.1-mini", messages=messages, tools=TOOLS)
            msg = completion.choices[0].message

            if msg.tool_calls:
                messages.append(msg)
                for call in msg.tool_calls:
                    args = json.loads(call.function.arguments)
                    fn   = call.function.name
                    try:
                        if fn == "shopify_create_customer":
                            result = shopify_create_customer(shopify_store, shopify_token, args["data"])
                        elif fn == "shopify_create_draft_order":
                            result = shopify_create_draft_order(shopify_store, shopify_token, args["data"])
                        elif fn == "shopify_search_customers":
                            result = shopify_search_customers(shopify_store, shopify_token, args["query"])
                        elif fn == "shopify_list_draft_orders":
                            result = shopify_list_draft_orders(shopify_store, shopify_token, args.get("status","open"))
                        elif fn == "shopify_search_products":
                            result = shopify_search_products(shopify_store, shopify_token, args["query"])
                        elif fn == "openphone_list_calls":
                            result = openphone_list_calls(openphone_key, args.get("limit", 10))
                        elif fn == "openphone_get_transcript":
                            result = openphone_get_transcript(openphone_key, args["call_id"])
                        elif fn == "openphone_send_sms":
                            result = openphone_send_sms(openphone_key, args["from_number"], args["to_number"], args["text"])
                        elif fn == "openphone_list_messages":
                            result = openphone_list_messages(openphone_key, args["phone_number"], args.get("limit", 20))
                        elif fn == "callrail_list_calls":
                            result = callrail_list_calls(callrail_key, callrail_acct, args.get("limit", 20), args.get("search"))
                        elif fn == "callrail_get_transcript":
                            result = callrail_get_transcript(callrail_key, callrail_acct, args["call_id"])
                        elif fn == "send_followup_email":
                            if not n8n_followup:
                                result = json.dumps({"error": "n8n Follow-up Webhook URL not configured"})
                            else:
                                result = send_followup_email(
                                    n8n_followup, args["to_email"], args["subject"],
                                    args["first_name"], args["call_date"], args["need"],
                                    args["model"], args["sizing"], args["product_url"])
                        else:
                            result = json.dumps({"error": f"Unknown tool: {fn}"})
                    except requests.HTTPError as e:
                        result = json.dumps({"error": str(e), "body": e.response.text[:500]})
                    except Exception as e:
                        result = json.dumps({"error": str(e)})

                    messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
                continue

            reply = msg.content or "Done."
            with st.chat_message("assistant"):
                st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            break
