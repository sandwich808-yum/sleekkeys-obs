"""Generates icon.ico (multi-size) and web/icon.png for SleekKeys. Needs Pillow:  pip install pillow"""
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = 512


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make() -> Image.Image:
    # gradient rounded square (mint -> blue)
    grad = Image.new("RGBA", (S, S))
    px = grad.load()
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * S)
            px[x, y] = lerp((61, 255, 181), (31, 165, 255), t) + (255,)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((16, 16, S - 16, S - 16), radius=112, fill=255)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    # three "keys": one pressed (dark) between two glassy ones
    def key(x, y, w, h, pressed):
        r = 34
        if pressed:
            d.rounded_rectangle((x, y + 8, x + w, y + h + 8), radius=r, fill=(4, 20, 13, 255))
        else:
            d.rounded_rectangle((x, y, x + w, y + h), radius=r, fill=(255, 255, 255, 70), outline=(255, 255, 255, 140), width=4)

    key(78, 150, 100, 100, False)
    key(206, 150, 100, 100, True)
    key(334, 150, 100, 100, False)
    key(78, 290, 356, 100, False)
    # little mouse-click spark on the pressed key
    d.ellipse((236, 178, 276, 218), fill=(61, 255, 181, 255))
    return img


def main():
    img = make()
    img.save(os.path.join(ROOT, "web", "icon.png"))
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(os.path.join(ROOT, "icon.ico"), sizes=sizes)
    print("wrote icon.ico and web/icon.png")


if __name__ == "__main__":
    main()
