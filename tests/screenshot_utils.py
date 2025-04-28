from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import os

def overlay_timestamp(image_path, dt=None):
    """
    Overlays the given datetime (or now, if None) on the PNG at image_path.
    Text is bottom center, 10% up from the bottom, in red font.
    """
    if dt is None:
        dt = datetime.utcnow()
    timestamp = dt.strftime('%Y-%m-%d %H:%M:%S UTC')

    with Image.open(image_path) as im:
        draw = ImageDraw.Draw(im)
        width, height = im.size
        # Try to use a truetype font, fallback to default
        try:
            font_path = os.path.join(os.path.dirname(__file__), 'DejaVuSans-Bold.ttf')
            font = ImageFont.truetype(font_path, size=int(height * 0.04))
        except Exception:
            font = ImageFont.load_default()
        # Use textbbox to get text size in Pillow >=8.0
        bbox = draw.textbbox((0, 0), timestamp, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) // 2
        y = int(height * 0.9 - text_height // 2)  # 10% up from bottom
        # Draw with a slight black shadow for visibility
        shadow_offset = 2
        draw.text((x+shadow_offset, y+shadow_offset), timestamp, font=font, fill=(0,0,0,180))
        draw.text((x, y), timestamp, font=font, fill=(255,0,0,255))
        im.save(image_path)

def save_screenshot_with_timestamp(page, path):
    """
    Takes a screenshot with Playwright's page, overlays current timestamp, saves to path.
    """
    page.screenshot(path=path)
    overlay_timestamp(path)
