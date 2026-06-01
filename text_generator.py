import os

import anthropic


async def generate_listing(car_info: dict, image_b64_list: list[str]) -> str:
    async with anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"]) as client:
        content: list = []

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

        content.append(
            {
                "type": "text",
                "text": f"""You are a professional automotive copywriter who specializes in online car listings that generate real inquiries.

Based on the vehicle details and photos provided, write a compelling listing that stops a buyer mid-scroll and makes them pick up the phone.

Car Details:
{_format_details(car_info)}

Write the listing using this exact structure:

# [Headline]
One punchy, specific headline. Lead with the year/make/model and a key emotional hook — not generic hype.

[Opening paragraph]
2-3 sentences. Paint the picture. Who is this car for, and why will they love it?

## What Makes This One Stand Out
3-4 sentences covering what's special: condition, history, trim level, rare options, or something that creates genuine trust (one owner, garage kept, recent work, etc.).

## Key Highlights
- Bullet 1
- Bullet 2
- (5–8 bullets covering drivetrain, mileage, features, condition notes, and any extras worth calling out)

## The Bottom Line
2-3 sentences on value. Be specific about why the price is right — don't just say "priced to sell." Reference market comps, remaining warranty, or cost to replicate.

**[Call to action — one sentence urging immediate contact]**

Rules:
- Use the real data from the details; don't invent specs
- Be enthusiastic but credible — skip empty superlatives
- No clichés: "won't last", "rare find", "priced to move", "don't miss out"
- Target length: 350–450 words
- Output clean markdown only""",
            }
        )

        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1400,
            messages=[{"role": "user", "content": content}],
        )

        return message.content[0].text


def _format_details(car_info: dict) -> str:
    label_map = {
        "year": "Year",
        "make": "Make",
        "model": "Model",
        "trim": "Trim / Package",
        "vin": "VIN",
        "mileage": "Mileage",
        "price": "Asking Price",
        "exterior_color": "Exterior Color",
        "interior_color": "Interior Color",
        "condition": "Condition",
        "transmission": "Transmission",
        "drivetrain": "Drivetrain",
        "engine": "Engine",
        "features": "Features & Options",
        "notes": "Additional Notes",
    }
    lines = []
    for key, label in label_map.items():
        val = car_info.get(key, "").strip()
        if val:
            lines.append(f"- {label}: {val}")
    return "\n".join(lines) if lines else "(No details provided)"
