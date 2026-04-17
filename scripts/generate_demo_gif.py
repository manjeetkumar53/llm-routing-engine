from __future__ import annotations

import json
from pathlib import Path
from textwrap import wrap

import httpx
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "assets" / "demo"
SCREENSHOTS_DIR = ROOT / "assets" / "screenshots"
GIF_PATH = DEMO_DIR / "routing-flow.gif"
SWAGGER_PATH = SCREENSHOTS_DIR / "swagger-ui.png"
DASHBOARD_PATH = SCREENSHOTS_DIR / "dashboard-overview.png"

WIDTH = 1280
HEIGHT = 820
BG = "#f6f4ee"
TEXT = "#202330"
MUTED = "#5e6678"
GREEN = "#0f9d58"
ORANGE = "#ff6b35"
BLUE = "#2563eb"
BORDER = "#d8dce6"
NAVY = "#0f172a"


def _get_font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    ]
    mono_candidates = [
        "/System/Library/Fonts/Supplemental/Menlo.ttc",
        "/System/Library/Fonts/SFNSMono.ttf",
    ]
    for path in (mono_candidates if mono else candidates):
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


FONT_H1 = _get_font(42)
FONT_H2 = _get_font(26)
FONT_BODY = _get_font(20)
FONT_SMALL = _get_font(16)
FONT_MONO = _get_font(18, mono=True)


def _new_canvas() -> Image.Image:
    return Image.new("RGB", (WIDTH, HEIGHT), BG)


def _draw_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    draw.text((60, 42), title, fill=TEXT, font=FONT_H1)
    draw.text((60, 98), subtitle, fill=MUTED, font=FONT_BODY)


def _badge(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, fill: str) -> int:
    bbox = draw.textbbox((0, 0), label, font=FONT_SMALL)
    width = bbox[2] - bbox[0] + 28
    draw.rounded_rectangle((x, y, x + width, y + 34), radius=12, fill=fill)
    draw.text((x + 14, y + 7), label, fill="white", font=FONT_SMALL)
    return x + width + 14


def _screenshot_frame(title: str, subtitle: str, path: Path) -> Image.Image:
    image = _new_canvas()
    draw = ImageDraw.Draw(image)
    _draw_header(draw, title, subtitle)
    screenshot = Image.open(path).convert("RGB")
    screenshot = ImageOps.contain(screenshot, (1160, 620))
    x = (WIDTH - screenshot.width) // 2
    y = 150
    draw.rounded_rectangle(
        (x - 8, y - 8, x + screenshot.width + 8, y + screenshot.height + 8),
        radius=18,
        fill="white",
        outline=BORDER,
        width=2,
    )
    image.paste(screenshot, (x, y))
    return image


def _response_frame(title: str, prompt: str, response: dict) -> Image.Image:
    image = _new_canvas()
    draw = ImageDraw.Draw(image)
    _draw_header(draw, title, "Live request sent to /v1/route/infer")

    draw.rounded_rectangle((60, 150, 1220, 270), radius=20, fill="white", outline=BORDER, width=2)
    draw.text((86, 172), "Prompt", fill=MUTED, font=FONT_SMALL)
    prompt_y = 202
    for line in wrap(prompt, width=95):
        draw.text((86, prompt_y), line, fill=TEXT, font=FONT_BODY)
        prompt_y += 28

    draw.rounded_rectangle((60, 305, 1220, 730), radius=20, fill="white", outline=BORDER, width=2)
    draw.text((86, 334), "Routing Result", fill=TEXT, font=FONT_H2)

    tier = response["route"]["selected_tier"]
    badge_x = 86
    badge_x = _badge(draw, badge_x, 378, f"tier: {tier}", GREEN if tier == "cheap" else ORANGE)
    badge_x = _badge(draw, badge_x, 378, f"complexity: {response['route']['complexity_score']}", BLUE)
    _badge(
        draw,
        badge_x,
        378,
        f"quality ok: {str(response['quality']['acceptable']).lower()}",
        "#1f7a5a",
    )

    draw.text((86, 438), f"estimated_cost_usd: {response['estimated_cost_usd']}", fill=TEXT, font=FONT_BODY)
    draw.text((430, 438), f"latency_ms: {response['latency_ms']}", fill=TEXT, font=FONT_BODY)
    draw.text((740, 438), f"quality.total: {response['quality']['total']}", fill=TEXT, font=FONT_BODY)

    draw.text((86, 492), "reason_codes", fill=MUTED, font=FONT_SMALL)
    draw.rounded_rectangle((86, 520, 1175, 700), radius=16, fill=NAVY, outline=NAVY)
    reason_lines = json.dumps(response["route"]["reason_codes"], indent=2).splitlines()
    reason_y = 545
    for line in reason_lines[:8]:
        draw.text((110, reason_y), line, fill="#dbeafe", font=FONT_MONO)
        reason_y += 26
    return image


def _metrics_frame(title: str, subtitle: str, path: Path, metrics: dict) -> Image.Image:
    image = _new_canvas()
    draw = ImageDraw.Draw(image)
    _draw_header(draw, title, subtitle)

    request_count = metrics.get("total_requests", metrics.get("request_count", "n/a"))
    avg_cost = metrics.get("avg_cost_usd", "n/a")
    avg_latency = metrics.get("avg_latency_ms", "n/a")
    tier_mix = metrics.get("by_tier", {})

    cards = [
        ("Requests", str(request_count)),
        ("Avg Cost", str(avg_cost)),
        ("Avg Latency", str(avg_latency)),
        ("Tier Mix", json.dumps(tier_mix)),
    ]
    x = 60
    for label, value in cards:
        draw.rounded_rectangle((x, 150, x + 270, 242), radius=18, fill="white", outline=BORDER, width=2)
        draw.text((x + 20, 168), label, fill=MUTED, font=FONT_SMALL)
        for idx, line in enumerate(wrap(value, width=22)[:2]):
            draw.text((x + 20, 192 + idx * 22), line, fill=TEXT, font=FONT_BODY)
        x += 290

    dashboard = Image.open(path).convert("RGB")
    dashboard = ImageOps.contain(dashboard, (1160, 500))
    sx = (WIDTH - dashboard.width) // 2
    sy = 280
    draw.rounded_rectangle(
        (sx - 8, sy - 8, sx + dashboard.width + 8, sy + dashboard.height + 8),
        radius=18,
        fill="white",
        outline=BORDER,
        width=2,
    )
    image.paste(dashboard, (sx, sy))
    return image


def main() -> None:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    if not SWAGGER_PATH.exists() or not DASHBOARD_PATH.exists():
        raise FileNotFoundError("Expected screenshots in assets/screenshots before generating the GIF")

    base_url = "http://127.0.0.1:8000"
    simple_prompt = "What is machine learning?"
    complex_prompt = (
        "Design a scalable event-driven microservice architecture for a fintech platform "
        "and compare the trade-offs of CQRS and event sourcing."
    )

    with httpx.Client(timeout=120.0) as client:
        simple = client.post(f"{base_url}/v1/route/infer", json={"prompt": simple_prompt}).json()
        complex_response = client.post(
            f"{base_url}/v1/route/infer", json={"prompt": complex_prompt}
        ).json()
        metrics = client.get(f"{base_url}/v1/metrics/summary").json()

    frames = [
        _screenshot_frame(
            "1. Explore the API surface",
            "Swagger UI exposes routing, metrics, and event endpoints.",
            SWAGGER_PATH,
        ),
        _response_frame("2. Route a simple prompt", simple_prompt, simple),
        _response_frame("3. Route a complex prompt", complex_prompt, complex_response),
        _metrics_frame(
            "4. See telemetry update",
            "Metrics and dashboard reflect request mix, latency, and spend.",
            DASHBOARD_PATH,
            metrics,
        ),
    ]

    frames[0].save(
        GIF_PATH,
        save_all=True,
        append_images=frames[1:],
        duration=[1600, 1800, 1800, 2200],
        loop=0,
    )
    print(GIF_PATH)


if __name__ == "__main__":
    main()