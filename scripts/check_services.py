import asyncio
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


async def main():
    services = [
        (
            "openai",
            "https://api.openai.com/v1/models",
            os.getenv("OPENAI_API_KEY") or os.getenv("ChatGPT_API_KEY") or os.getenv("CHATGPT_API_KEY"),
        ),
        (
            "tripo",
            "https://api.tripo3d.ai/v2/openapi/user/balance",
            os.getenv("TRIPO_API_KEY") or os.getenv("Tripo_AI_API_KEY") or os.getenv("TRIPO_AI_API_KEY"),
        ),
    ]
    async with httpx.AsyncClient(timeout=30) as client:
        for name, url, key in services:
            if not key:
                print(json.dumps({"service": name, "configured": False}))
                continue
            try:
                response = await client.get(url, headers={"Authorization": f"Bearer {key}"})
                result = {"service": name, "http_status": response.status_code}
                if response.is_success:
                    body = response.json()
                    if name == "openai":
                        result["image_models"] = [
                            m["id"] for m in body.get("data", []) if m["id"].startswith("gpt-image")
                        ]
                    else:
                        result["code"] = body.get("code")
                        result["balance"] = body.get("data", {}).get("balance")
                print(json.dumps(result))
            except (httpx.HTTPError, ValueError):
                print(json.dumps({"service": name, "connection_failed": True}))


asyncio.run(main())
