"""One visual review per generated component; advisory, never auto-regenerates."""

import base64
import hashlib
import json
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    view: Literal["front", "left", "back", "right", "all"]
    severity: Literal["warning", "error", "uncertain"]
    description: str
    suggested_change: str


class ReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Literal["pass", "needs_review"]
    summary: str
    findings: list[Finding] = Field(max_length=20)


class VisualReviewer:
    def __init__(self, key, model="gpt-5-mini", transport=None):
        self.key, self.model, self.transport = key, model, transport

    async def review(self, stage, image, authority):
        rules = (Path(__file__).resolve().parents[2] / "prompts" / "component_review.txt").read_text()
        prompt = (
            rules
            + f"\nComponent: {stage}. Image 1 is the component sheet; image 2 is the approved whole-character authority."
        )
        content = [{"type": "input_text", "text": prompt}]
        for raw in (image, authority):
            content.append(
                {
                    "type": "input_image",
                    "image_url": "data:image/png;base64," + base64.b64encode(raw).decode(),
                    "detail": "high",
                }
            )
        async with httpx.AsyncClient(timeout=120, transport=self.transport) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self.key}"},
                json={
                    "model": self.model,
                    "store": False,
                    "input": [{"role": "user", "content": content}],
                    "reasoning": {"effort": "low"},
                    "max_output_tokens": 2500,
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "component_review",
                            "strict": True,
                            "schema": ReviewResult.model_json_schema(),
                        }
                    },
                },
            )
        if response.status_code >= 400:
            raise ValueError("Visual review unavailable; check provider configuration or billing records.")
        data = response.json()
        if data.get("status") != "completed":
            raise ValueError("Visual review incomplete; no automatic retry.")
        text = "".join(
            c.get("text", "")
            for item in data.get("output", [])
            for c in item.get("content", [])
            if c.get("type") == "output_text"
        )
        result = ReviewResult.model_validate(json.loads(text)).model_dump()
        if result["findings"]:
            result["verdict"] = "needs_review"
        return {
            "status": "completed",
            **result,
            "model": self.model,
            "usage": data.get("usage"),
            "provider_request_id": response.headers.get("x-request-id"),
            "prompt": prompt,
            "prompt_version": hashlib.sha256(rules.encode()).hexdigest()[:16],
            "human_review_required": True,
        }
