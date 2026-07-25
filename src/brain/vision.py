import io
import mss
from PIL import Image


def capture_screen(max_width: int = 1280) -> bytes:
    """Скриншот основного экрана -> сжатый JPEG в байтах."""
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[1])    # [1] = основной монитор

    img = Image.frombytes("RGB", shot.size, shot.rgb)

    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)))

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=80)
    return buffer.getvalue()