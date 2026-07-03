"""
Certificate generator module.
Generates certificates by overlaying text onto template images using Pillow.
Supports PNG, JPG, and PDF templates.
"""

import os
import tempfile
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from config import Config

# Cache for fonts
_font_cache = {}


def _get_font(font_path, size):
    """Get or load a font with caching."""
    cache_key = (font_path, size)
    if cache_key not in _font_cache:
        try:
            _font_cache[cache_key] = ImageFont.truetype(font_path, size)
        except (IOError, OSError):
            # Fallback to default font
            _font_cache[cache_key] = ImageFont.load_default()
    return _font_cache[cache_key]


def _get_available_fonts():
    """Return a list of available font paths, preferring common system fonts."""
    font_candidates = [
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Helvetica.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Times.ttc",
        "/System/Library/Fonts/Georgia.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        # Windows
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\calibri.ttf",
        "C:\\Windows\\Fonts\\times.ttf",
    ]

    available = []
    for font_path in font_candidates:
        if os.path.exists(font_path):
            available.append(font_path)

    return available


def _get_bold_font(font_path):
    """Get a bold variant of a font."""
    bold_variants = {
        "/System/Library/Fonts/Helvetica.ttc": "/System/Library/Fonts/Helvetica-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttf": "/System/Library/Fonts/Helvetica-Bold.ttf",
        "/Library/Fonts/Arial.ttf": "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf": "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    }
    bold_path = bold_variants.get(font_path)
    if bold_path and os.path.exists(bold_path):
        return bold_path
    return font_path


def generate_from_image_template(
    template_path, output_path, data, placeholders=None, dpi=300
):
    """
    Generate a certificate from an image template by drawing text on it.

    Args:
        template_path: Path to the template image
        output_path: Path where the certificate will be saved
        data: Dict of field_name -> value mappings
        placeholders: Optional list of placeholder definitions with position info.
                      If None, fields are auto-positioned.
    """
    img = Image.open(template_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    width, height = img.size

    # Get available fonts
    fonts = _get_available_fonts()
    primary_font = fonts[0] if fonts else None

    if placeholders:
        # Use predefined placeholder positions
        for ph in placeholders:
            field_name = ph.get("field", "")
            value = data.get(field_name, "")

            if not value:
                continue

            # Position and styling from placeholder definition
            x = ph.get("x", width // 2)
            y = ph.get("y", height // 2)
            font_size = ph.get("font_size", 36)
            color = ph.get("color", (0, 0, 0, 255))
            alignment = ph.get("alignment", "center")
            font_path = ph.get("font_path", primary_font)

            if isinstance(color, str):
                # Parse hex color
                color = color.lstrip("#")
                color = tuple(int(color[i : i + 2], 16) for i in (0, 2, 4)) + (255,)

            font = _get_font(font_path, font_size)

            # Handle text drawing with alignment
            bbox = draw.textbbox((0, 0), str(value), font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            if alignment == "center":
                text_x = x - text_width // 2
            elif alignment == "right":
                text_x = x - text_width
            else:
                text_x = x

            text_y = y - text_height // 2

            draw.text((text_x, text_y), str(value), fill=color, font=font)
    else:
        # Auto-position placeholders with smart layout
        font_size = min(width // 20, 60)
        font = _get_font(primary_font, font_size) if primary_font else ImageFont.load_default()

        # Draw each field with automatic positioning
        center_x = width // 2
        start_y = height // 3
        line_height = font_size + 20

        special_fields = {
            "participant_name": {"size": font_size + 20, "y_offset": 0},
            "prize_position": {"size": font_size, "y_offset": font_size + 40},
            "event_name": {"size": font_size, "y_offset": 2 * (font_size + 40)},
        }

        for i, (field_name, value) in enumerate(data.items()):
            if not value:
                continue

            field_config = special_fields.get(field_name.lower(), {"size": font_size, "y_offset": 0})
            use_size = field_config.get("size", font_size)

            # Compute actual y offset based on configured ones
            if field_name.lower() in special_fields:
                y_offset = special_fields[field_name.lower()]["y_offset"]
            else:
                y_offset = start_y + (font_size + 20) * i

            use_font = _get_font(primary_font, use_size) if primary_font else ImageFont.load_default()

            bbox = draw.textbbox((0, 0), str(value), font=use_font)
            text_width = bbox[2] - bbox[0]
            text_x = center_x - text_width // 2

            draw.text(
                (text_x, height // 3 + y_offset),
                str(value),
                fill=(0, 0, 0, 255),
                font=use_font,
            )

    # Composite and save
    result = Image.alpha_composite(img, overlay)
    result = result.convert("RGB")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    result.save(output_path, "PDF", resolution=dpi)
    return output_path


def generate_from_pdf_template(
    template_path, output_path, data, placeholders=None
):
    """
    Generate a certificate from a PDF template.
    Since editing existing PDFs is complex, we create a new PDF
    that matches the template layout with filled fields.

    For production use, consider using a library like pdfrw or
    PyMuPDF for direct PDF template editing.
    """
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.pdfgen import canvas

    width, height = landscape(letter)

    c = canvas.Canvas(output_path, pagesize=landscape(letter))

    # Try to embed the template as a background image
    # For simple PDF templates, we draw text on a new page
    fonts = _get_available_fonts()

    c.setFont("Helvetica", 16)

    # Draw each field
    center_x = width / 2

    special_fields = {
        "participant_name": {"y": height * 0.45, "size": 36},
        "prize_position": {"y": height * 0.38, "size": 24},
        "event_name": {"y": height * 0.31, "size": 20},
    }

    for field_name, value in data.items():
        if not value:
            continue

        field_config = special_fields.get(
            field_name.lower(), {"y": height * 0.25, "size": 16}
        )

        c.setFont("Helvetica-Bold" if field_name.lower() == "participant_name" else "Helvetica", field_config.get("size", 16))
        c.setFillColorRGB(0, 0, 0)

        text_width = c.stringWidth(str(value), "Helvetica-Bold" if field_name.lower() == "participant_name" else "Helvetica", field_config.get("size", 16))
        c.drawString(center_x - text_width / 2, field_config.get("y", height * 0.25), str(value))

    c.save()
    return output_path


def generate_certificate(
    template_path, template_type, output_path, data, placeholders=None
):
    """
    Generate a certificate using the appropriate method based on template type.

    Args:
        template_path: Path to the template file
        template_type: 'png', 'jpg', 'jpeg', or 'pdf'
        output_path: Path where the certificate PDF will be saved
        data: Dict of field values to populate
        placeholders: Optional list of placeholder definitions

    Returns:
        Path to the generated certificate
    """
    if template_type.lower() in ("png", "jpg", "jpeg"):
        return generate_from_image_template(
            template_path, output_path, data, placeholders
        )
    elif template_type.lower() == "pdf":
        return generate_from_pdf_template(
            template_path, output_path, data, placeholders
        )
    else:
        raise ValueError(f"Unsupported template type: {template_type}")
