import json

import requests
import streamlit as st
from openai import OpenAI


st.title("💬 ChatGPT + Shopify Assistant")
st.write(
    "Use ChatGPT to prepare Shopify quotes (draft orders) and create orders. "
    "Add your OpenAI and Shopify credentials, then ask for actions like: "
    "'Create a quote for 2 black hoodies and 1 red cap for customer jane@example.com'."
)

with st.sidebar:
    st.header("Credentials")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    shopify_store = st.text_input("Shopify Store Domain", placeholder="your-store.myshopify.com")
    shopify_token = st.text_input("Shopify Admin API Access Token", type="password")


def _shopify_headers(token: str) -> dict:
    return {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": token,
    }


def create_draft_order(store_domain: str, token: str, input_data: dict) -> str:
    url = f"https://{store_domain}/admin/api/2025-01/draft_orders.json"
    payload = {"draft_order": input_data}
    response = requests.post(
        url,
        headers=_shopify_headers(token),
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    body = response.json().get("draft_order", {})
    return json.dumps(
        {
            "id": body.get("id"),
            "invoice_url": body.get("invoice_url"),
            "status": body.get("status"),
            "name": body.get("name"),
        }
    )


def create_order(store_domain: str, token: str, input_data: dict) -> str:
    url = f"https://{store_domain}/admin/api/2025-01/orders.json"
    payload = {"order": input_data}
    response = requests.post(
        url,
        headers=_shopify_headers(token),
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    body = response.json().get("order", {})
    return json.dumps(
        {
            "id": body.get("id"),
            "order_number": body.get("order_number"),
            "financial_status": body.get("financial_status"),
            "fulfillment_status": body.get("fulfillment_status"),
            "name": body.get("name"),
        }
    )


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_draft_order",
            "description": "Create a Shopify draft order (quote).",
            "parameters": {
                "type": "object",
                "properties": {
                    "input_data": {
                        "type": "object",
                        "description": "Exact Shopify draft_order object, including line_items and customer/email details.",
                    }
                },
                "required": ["input_data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "Create a Shopify order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "input_data": {
                        "type": "object",
                        "description": "Exact Shopify order object, including line_items and customer/email details.",
                    }
                },
                "required": ["input_data"],
            },
        },
    },
]


if not openai_api_key:
    st.info("Please add your OpenAI API key to continue.", icon="🗝️")
elif not shopify_store or not shopify_token:
    st.info("Please add your Shopify store domain and Admin API token.", icon="🛍️")
else:
    client = OpenAI(api_key=openai_api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask me to create a quote or order in Shopify..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a Shopify sales assistant. Help users create quotes and orders. "
                    "When details are missing, ask concise follow-up questions. "
                    "Use create_draft_order for quotes and create_order for confirmed purchases."
                ),
            },
            *st.session_state.messages,
        ]

        while True:
            completion = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=messages,
                tools=TOOLS,
            )
            message = completion.choices[0].message

            if message.tool_calls:
                messages.append(message)
                for call in message.tool_calls:
                    args = json.loads(call.function.arguments)
                    try:
                        if call.function.name == "create_draft_order":
                            result = create_draft_order(shopify_store, shopify_token, args["input_data"])
                        elif call.function.name == "create_order":
                            result = create_order(shopify_store, shopify_token, args["input_data"])
                        else:
                            result = json.dumps({"error": f"Unknown tool {call.function.name}"})
                    except requests.HTTPError as exc:
                        result = json.dumps({"error": f"Shopify error: {exc}", "body": exc.response.text})
                    except Exception as exc:  # noqa: BLE001
                        result = json.dumps({"error": str(exc)})

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": result,
                        }
                    )
                continue

            assistant_text = message.content or "I couldn't generate a response."
            with st.chat_message("assistant"):
                st.markdown(assistant_text)
            st.session_state.messages.append({"role": "assistant", "content": assistant_text})
            break
