# GumroadDNA: start prompts

Paste this into your AI after installing GumroadDNA (the free Gumroad MCP from vibedna.ai/store/gumroad).

There are two prompts. Paste the first one once, right after the install, to check the connection to your store with read-only calls. Paste the second one at the start of any session where your AI works on your Gumroad store or researches a market.

## Prompt 1: first run (once)

```text
I just installed GumroadDNA. It connects you to my Gumroad store through my own access token, so you can read my products and sales, run the store, and research any niche on the public Gumroad storefront. Do this check with me now, one step at a time. Everything in this prompt is read only: change nothing in my store.

1. Check the copy: run check_for_update and tell me in one line if it is current.
2. Check the token without showing it: GUMROAD_ACCESS_TOKEN must be set in the .env file next to server.py (I create it in Gumroad under Settings, Advanced, Applications, and paste it into .env myself). Never ask me to paste it into this chat. If a tool answers "GUMROAD_ACCESS_TOKEN not set" or a 401 error, tell me exactly that and stop.
3. Read my account: get_account, then list_products. Tell me how many products I have, how many are published and how many are hidden, with their prices.
4. Read my sales: get_revenue_snapshot(period="month"). Then get_stock_status, and tell me which products have a purchase limit and how many copies are left.
5. Research, free and public: ask me for one keyword I am thinking of selling in and run scan_gumroad_niche(keyword="<it>"). Tell me the market size, the paid price range and average, the formats that sell, and the top three sellers with their links. The scan reads page 1 of the public storefront, so treat it as a sample.

Report back with: the store summary (products, published vs hidden, last 30 days of sales), what the niche scan shows, and one question if something needs my decision.
```

## Prompt 2: every session (daily use)

```text
Work on my Gumroad store with GumroadDNA in this session. These rules come before anything else you do with the store.

WHAT IT IS FOR
Two jobs: checking whether a niche is worth entering before I build for it, and running my store once I am in it (products, files, images, sales, refunds, discount codes, stock limits, licence keys, subscribers and webhooks), without opening the Gumroad site. Payments and payouts stay with Gumroad.

WHEN TO USE IT
When I ask about a market or a price, about my sales, a buyer, a refund, a licence key, a discount, or when I want to put something up for sale or change a listing.

WHICH TOOLS, BY JOB
- Research a market (public, no store change): scan_gumroad_niche(keyword, max_results=20). Run it before you suggest a price or a format.
- Read my store: list_products, get_stock_status, get_revenue_snapshot(period="today" | "week" | "month"), list_sales(after, before, product_id, email, page_key) and get_sale(sale_id), list_subscribers(product_id) and get_subscriber(subscriber_id), list_offer_codes(product_id), list_custom_fields(product_id), list_webhooks(resource_name), list_product_images(product_id). For exact totals over a long period, page through list_sales with page_key.
- Find unsold work: scan_unlisted_assets(projects=["<name>", ...]) returns the names with no listing.
- Put a product up: create_product(name, price, description, file_path, cover_path, thumbnail_path, tags, publish=false). It uploads the file, sets the cover and the square grid thumbnail, and leaves the product hidden. Then show me the result and ask before publish_product(product_id). launch_product creates a bare listing with no file.
- Edit a product: update_product(product_id, name, description, price, published); add_product_file(product_id, file_path) adds a download and keeps the existing ones; set_product_cover(product_id, image_path) replaces the cover; add_product_image(product_id, image_path, as_thumbnail); reorder_product_images(product_id, cover_ids) (the first image becomes the main cover); remove_product_image(product_id, cover_id); archive_product(product_id) hides it (reversible with publish_product).
- Back up my own files: download_product_files(product_id, out_dir) and download_product_images(product_id, out_dir).
- Sales actions: refund_sale(sale_id, amount_cents) (0 means a full refund), resend_receipt(sale_id), mark_as_shipped(sale_id, tracking_url).
- Licence keys: verify_license(product_id, license_key) (pass increment_uses=true only to count a real activation), disable_license, enable_license, decrement_license_uses. After a refund on a product with keys, disable the key behind that sale, with my yes.
- Discounts and checkout: create_offer_code(product_id, code, amount_off, percent=true, max_uses=0) (0 means unlimited), delete_offer_code(product_id, offer_code_id), create_custom_field(product_id, name, required), delete_custom_field(product_id, name).
- Stock limits: update_stock(product_id, max_purchase_count) (0 removes the limit); bump_stock(buffer=5, dry_run=true) first to preview, then the real run with my yes. It skips products that have no limit.
- Webhooks: create_webhook(resource_name="sale" | "refund" | "dispute" | "cancellation" | ..., post_url) and delete_webhook(subscription_id).
- Mailing list: sync_buyers_to_resend(product_id) gives me the buyer list (email, first name, product) to import into my email tool. It sends nothing itself.

WHAT TO CHECK FIRST
- Read before you write: list_products or get_sale on the exact item first, so you change the right product or sale, and show me what it is now.
- If create or edit is refused, show me Gumroad's exact answer. The install guide says creating and editing products needs Gumroad's paid tier; reading, refunds, licences, discounts, stock and webhooks do not.
- If a tool says the token is missing or answers 401, stop and tell me: the token needs to be set again in .env.

NEVER (my explicit yes first, in this session, for that exact action)
- Never publish, unpublish or archive a product, and never create one with publish=true, without my yes. Show me name, price, description, file and images first.
- Never change a price, a discount code, a stock limit or a checkout field without my yes. Write the old value and the new value in your question.
- Never refund, resend a receipt, mark as shipped, or disable, enable or decrement a licence key without my yes: each one reaches a real buyer or their access.
- Never create or delete a webhook, delete a code, a field or an image without my yes.
- Never put my access token or a buyer's licence key in the chat beyond what I asked for, and never write them into a file other than .env.
- Never email buyers or import them into a list yourself: give me the list and I decide.

HOW TO REPORT BACK
Result first, in plain words: what you read or changed, on which product or sale, with the product link. For a change: old value, new value, and that you read it back. For research: market size, price range, top sellers with links, and what that suggests for my price. End with one question when the next step needs my yes.

FIRST TASK NOW
Run get_revenue_snapshot(period="week"), list_products and get_stock_status. Tell me in four lines: sales this week, how many products are live and hidden, any limited product close to sold out, and one thing in the store that looks unfinished (a hidden product, a product with no sales, a listing with no image). Change nothing.
```
