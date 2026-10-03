"""Versioned application instructions, assembled into the Images API prompt."""

import hashlib
from pathlib import Path

from .models import Stage
from .views import LAYOUT_INSTRUCTIONS

DIRECTORY = Path(__file__).resolve().parents[2] / "prompts"


def prompt_templates():
    common = (DIRECTORY / "common.txt").read_text().strip()
    result = {}
    for stage in Stage:
        instructions = (DIRECTORY / f"{stage.value}.txt").read_text().strip()
        if stage != Stage.design:
            instructions += "\n\n" + LAYOUT_INSTRUCTIONS
        version = hashlib.sha256((common + "\n" + instructions).encode()).hexdigest()[:16]
        result[stage.value] = {"common": common, "instructions": instructions, "version": version}
    return result
