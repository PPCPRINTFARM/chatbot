# 💬 ChatGPT + Shopify Assistant

A Streamlit app that connects ChatGPT to Shopify so you can create:

- **Quotes** as Shopify **draft orders**
- **Orders** as Shopify **orders**

## What you need

- OpenAI API key
- Shopify store domain (for example: `your-store.myshopify.com`)
- Shopify Admin API access token with permission to write draft orders and orders

## How to run locally

1. Install dependencies

```bash
pip install -r requirements.txt
```

2. (Optional) Set credentials as environment variables

```bash
export OPENAI_API_KEY="sk-..."
export SHOPIFY_SHOP="your-store.myshopify.com"
export SHOPIFY_ACCESS_TOKEN="shpat_..."
```

3. Start the app

```bash
streamlit run streamlit_app.py
```

4. In the sidebar, enter (or let them auto-fill from env vars):
   - OpenAI API key
   - Shopify store domain
   - Shopify Admin API token

5. In chat, ask for actions such as:
   - "Create a quote for 2 blue t-shirts for chris@example.com"
   - "Create an order for 1 black hoodie for sam@example.com"
