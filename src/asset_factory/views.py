"""Split light-background four-view sheets; uncertain layouts require review."""

import io

from PIL import Image, ImageChops

VIEW_ORDER = ("front", "left", "back", "right")
LAYOUT_INSTRUCTIONS = """MANDATORY LAYOUT: One 1024x1536 image with four equal cells in a 2x2 grid: top-left front, top-right left profile, bottom-left back, bottom-right right profile. Each cell is 512x768. Keep the complete subject inside its cell with at least 24 pixels of margin. Nothing may cross x=512 or y=768. Use flat white background, no grid lines, borders or labels. Use the same scale in all cells. For full-body T-poses, keep the arm span below 450 pixels by uniformly scaling all views. Left profile faces left, right profile faces right. Rotate the same pose: in profile, lateral T-pose arms are foreshortened toward/away from the camera, never stretched forward in front of the chest."""


def split_views(raw):
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = image.size
    if min(w, h) < 64:
        raise ValueError("图片过小，无法可靠拆分四视图")
    channels = image.split()
    mask = ImageChops.darker(ImageChops.darker(channels[0], channels[1]), channels[2]).point(
        lambda p: 255 if p < 225 else 0
    )

    def gutter(start, stop, count):
        runs, begin = [], None
        for pos in range(start, stop):
            if count(pos) == 0:
                if begin is None:
                    begin = pos
            elif begin is not None:
                runs.append((begin, pos))
                begin = None
        if begin is not None:
            runs.append((begin, stop))
        if not runs:
            raise ValueError("视图之间没有清楚的空白带，请修改布局后重新生成或上传")
        a, b = max(runs, key=lambda r: r[1] - r[0])
        if b - a < max(2, min(w, h) // 100):
            raise ValueError("视图间空白过窄，请增加留白")
        return (a + b) // 2

    y = gutter(int(h * 0.42), int(h * 0.58), lambda p: mask.crop((0, p, w, p + 1)).getbbox() is not None)
    xs = [
        gutter(
            int(w * 0.40),
            int(w * 0.64),
            lambda p, a=a, b=b: mask.crop((p, a, p + 1, b)).getbbox() is not None,
        )
        for a, b in ((0, y), (y, h))
    ]
    boxes = [(0, 0, xs[0], y), (xs[0], 0, w, y), (0, y, xs[1], h), (xs[1], y, w, h)]
    side = max(max(b[2] - b[0], b[3] - b[1]) for b in boxes) + 48
    result = []
    for view, box in zip(VIEW_ORDER, boxes, strict=True):
        if mask.crop(box).getbbox() is None:
            raise ValueError("至少一个视图为空，请检查四宫格布局")
        crop = image.crop(box)
        offset = ((side - crop.width) // 2, (side - crop.height) // 2)
        canvas = Image.new("RGB", (side, side), "white")
        canvas.paste(crop, offset)
        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")
        result.append(
            {
                "view": view,
                "crop_box": list(box),
                "padding_offset": list(offset),
                "output_size": [side, side],
                "image": buffer.getvalue(),
            }
        )
    return result
