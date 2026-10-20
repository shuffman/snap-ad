import json
import os
import re

import anthropic


async def generate_listing(
    item_info: dict,
    image_b64_list: list[str],
    pdf_b64_list: list[str] | None = None,
    extra_info: str | None = None,
) -> str:
    async with anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"]) as client:
        content: list = []

        for b64 in (pdf_b64_list or [])[:5]:
            content.append(
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": b64,
                    },
                }
            )

        for b64 in image_b64_list[:4]:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": b64,
                    },
                }
            )

        extra_block = (
            f"\nAdditional notes from the seller:\n{extra_info}\n"
            if extra_info else ""
        )

        content.append(
            {
                "type": "text",
                "text": f"""You are a professional copywriter who specializes in online classified listings that generate real inquiries — for anything people sell: vehicles, furniture, electronics, tools, instruments, collectibles, clothing, real estate, and more.

Based on the item details and photos provided, write a compelling listing that stops a buyer mid-scroll and makes them reach out. Write like an expert in this item's category would, using the terms its buyers care about.

Item Details:
{_format_details(item_info)}{extra_block}

Write the listing using this exact structure:

# [Headline]
One punchy, specific headline. Lead with what the item is (brand/model/year where relevant) and a key hook — not generic hype.

[Opening paragraph]
2-3 sentences. Paint the picture. Who is this for, and why will they love it?

## What Makes This One Stand Out
3-4 sentences covering what's special: condition, history, provenance, rare options, or something that creates genuine trust (one owner, barely used, recently serviced, original packaging, etc.).

## Key Highlights
- Bullet 1
- Bullet 2
- (5–8 bullets covering the specs, features, condition notes, and extras that matter most for this kind of item)

## The Bottom Line
2-3 sentences on value. Be specific about why the price is right — don't just say "priced to sell." Reference what it costs new, comparable listings, remaining warranty, or included extras.

**[Call to action — one sentence urging immediate contact]**

Rules:
- Use the real data from the details; don't invent specs
- Be enthusiastic but credible — skip empty superlatives
- No clichés: "won't last", "rare find", "priced to move", "don't miss out"
- Target length: 250–450 words; shorter for simple, inexpensive items
- Output clean markdown only""",
            }
        )

        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1400,
            messages=[{"role": "user", "content": content}],
        )

        return message.content[0].text


async def analyze_item(
    image_b64_list: list[str],
    pdf_b64_list: list[str] | None = None,
) -> dict:
    """
    Use Claude vision + document understanding to identify the item and extract its details.
    Returns a dict of detected fields (only fields with confident values included);
    "specs" is a list of {"label", "value"} pairs chosen to suit the item's category.
    """
    async with anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"]) as client:
        content: list = []

        # PDFs first so Claude reads structured data (serials, specs, history) before the photos
        for b64 in (pdf_b64_list or [])[:5]:
            content.append(
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": b64,
                    },
                }
            )

        for b64 in image_b64_list[:6]:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": b64,
                    },
                }
            )

        sources = []
        if pdf_b64_list:
            sources.append("PDF documents (receipts, manuals, spec sheets, appraisals, history reports, etc.)")
        if image_b64_list:
            sources.append("photos")
        source_desc = " and ".join(sources) if sources else "the provided files"

        content.append(
            {
                "type": "text",
                "text": f"""Analyze all provided {source_desc} to identify the item being sold and extract its details.
The item could be anything: a vehicle, furniture, electronics, a tool, an instrument, a collectible, clothing, property, etc.
Read labels, model plates, serial stickers, receipts and documents where visible.
Return ONLY a valid JSON object — no explanation, no markdown fences.

Use this exact schema (set a field to null if you cannot determine it with reasonable confidence):
{{
  "item": "Herman Miller Aeron Chair",
  "category": "Furniture",
  "brand": "Herman Miller",
  "model": "Aeron Size B",
  "year": "2019",
  "condition": "Very Good",
  "price": null,
  "specs": [
    {{"label": "Size", "value": "B (medium)"}},
    {{"label": "Color", "value": "Graphite"}},
    {{"label": "Adjustments", "value": "Fully adjustable arms, PostureFit SL"}}
  ],
  "features": "Tilt limiter, forward tilt, adjustable lumbar",
  "notes": "Purchased new in 2019, smoke-free home, original receipt"
}}

Rules:
- item: short, specific name of what is being sold, as a buyer would search for it
- category: one or two words, e.g. Vehicle, Furniture, Electronics, Tools, Musical Instrument, Collectible, Clothing, Sporting Goods, Home & Garden, Real Estate
- year: 4-digit string (model year, manufacture year, or purchase year) — null if not relevant
- condition: must be exactly one of: New, Excellent, Very Good, Good, Fair
- price: only if visible in the files (a price tag or listing), digits and commas only
- specs: 3–10 of the facts buyers of this category care most about, with labels suited to it
  (vehicle: Mileage, VIN, Transmission, Drivetrain, Engine, Exterior Color;
   electronics: Storage, Screen Size, Battery Health, Serial Number;
   furniture: Dimensions, Material, Color; clothing: Size, Material; etc.)
  Copy serial numbers, VINs and odometer readings exactly as printed.
- features: list features from documents or visibly in photos
- notes: ownership history, accessories included, service or repair records, flaws
- Return ONLY the JSON object""",
            }
        )

        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": content}],
        )

        raw = message.content[0].text.strip()
        # Strip accidental markdown code fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        data = json.loads(raw)
        specs = [
            {"label": str(s["label"]).strip(), "value": str(s["value"]).strip()}
            for s in (data.pop("specs", None) or [])
            if isinstance(s, dict) and s.get("label") and s.get("value") not in (None, "", "null")
        ]
        # Return only non-null, non-empty values
        info = {k: str(v).strip() for k, v in data.items() if v not in (None, "", "null")}
        if specs:
            info["specs"] = specs
        return info


async def refine_listing(current_text: str, correction: str) -> str:
    """Revise an existing listing based on seller corrections or additions."""
    async with anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"]) as client:
        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1400,
            messages=[{
                "role": "user",
                "content": f"""You are revising a for-sale listing based on feedback from the seller.

Current listing:
---
{current_text}
---

Seller's correction or addition:
{correction}

Instructions:
- Keep the same markdown structure and overall format
- Correct any facts mentioned (price, condition, specs, features, etc.) throughout the listing
- Naturally incorporate any new information provided
- Keep the same persuasive tone — don't water it down
- Return only the revised listing, no preamble or explanation""",
            }],
        )
        return message.content[0].text


def _format_details(item_info: dict) -> str:
    label_map = {
        "item": "Item",
        "category": "Category",
        "brand": "Brand",
        "model": "Model",
        "year": "Year",
        "condition": "Condition",
        "price": "Asking Price",
    }
    lines = []
    for key, label in label_map.items():
        val = item_info.get(key, "").strip()
        if val:
            lines.append(f"- {label}: {val}")
    for spec in item_info.get("specs", []):
        lines.append(f"- {spec['label']}: {spec['value']}")
    for key, label in (("features", "Features"), ("notes", "Additional Notes")):
        val = item_info.get(key, "").strip()
        if val:
            lines.append(f"- {label}: {val}")
    return "\n".join(lines) if lines else "(No details provided)"
