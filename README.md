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

2. Start the app

```bash
streamlit run streamlit_app.py
```

3. In the sidebar, enter:
   - OpenAI API key
   - Shopify store domain
   - Shopify Admin API token

4. In chat, ask for actions such as:
   - "Create a quote for 2 blue t-shirts for chris@example.com"
   - "Create an order for 1 black hoodie for sam@example.com"
