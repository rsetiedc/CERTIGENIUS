"""
Certificate generator module.
Generates certificates by overlaying text onto template images using Pillow.
Supports PNG, JPG, and PDF templates.
"""

import os
import io
from collections import Counter

import fitz  # PyMuPDF for PDF editing
from PIL import Image, ImageDraw, ImageFont
import qrcode

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


def _sample_background_color(img, cx, cy, radius=8):
    """
    Sample the most common color around a bounding box area to use as a masking background.
    Samples from multiple points (center, above, below, left, right of the area)
    to avoid picking up a decorative border or accent line.
    Falls back to white if the image can't be sampled.
    """
    width, height = img.size

    # Sample from multiple points around the area for robustness
    sample_points = [
        (cx, cy),           # center
        (cx, max(0, cy - radius * 2)),  # above
        (cx, min(height - 1, cy + radius * 2)),  # below
        (max(0, cx - radius * 2), cy),  # left
        (min(width - 1, cx + radius * 2), cy),  # right
    ]

    pixels = []
    for px, py in sample_points:
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                sx = px + dx
                sy = py + dy
                if 0 <= sx < width and 0 <= sy < height:
                    try:
                        p = img.getpixel((sx, sy))
                        if isinstance(p, tuple):
                            pixels.append(p[:3])  # Use RGB
                        else:
                            pixels.append((p, p, p))
                    except Exception:
                        pass

    if pixels:
        return Counter(pixels).most_common(1)[0][0]
    return (255, 255, 255)


def _erase_text_area(draw, img, text_x, text_y, text_width, text_height, padding=6):
    """
    Erase a rectangular area by painting over it with the sampled background color.
    This removes any placeholder text baked into the template before drawing new text.
    """
    # Sample background color from just above the text area
    bg_color = _sample_background_color(
        img, 
        text_x + text_width // 2, 
        max(0, text_y - 10)
    )
    
    # Paint a filled rectangle to erase any placeholder text or artifacts
    draw.rectangle(
        [
            (text_x - padding, text_y - padding),
            (text_x + text_width + padding, text_y + text_height + padding),
        ],
        fill=bg_color,
    )


def generate_from_image_template(
    template_path, output_path, data, placeholders=None, dpi=300, qr_data=None
):
    """
    Generate a certificate from an image template by drawing text on it.
    Automatically masks/erases placeholder text areas before drawing values.

    Args:
        template_path: Path to the template image
        output_path: Path where the certificate will be saved
        data: Dict of field_name -> value mappings
        placeholders: Optional list of placeholder definitions with position info.
                      If None, fields are auto-positioned.
    """
    img = Image.open(template_path).convert("RGBA")
    
    # Work directly on the image (not a transparent overlay) so we can
    # erase placeholder text before drawing new values.
    img_rgb = img.convert("RGB")
    draw = ImageDraw.Draw(img_rgb)

    width, height = img_rgb.size

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
                color = tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))

            if len(color) == 4:
                color = color[:3]  # Strip alpha for RGB mode

            # If it's prize_position, event_name, or date, render it bold
            if field_name.lower() in ("prize_position", "event_name", "date"):
                font_path = _get_bold_font(font_path)

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

            # Erase any placeholder text at this position before drawing
            _erase_text_area(draw, img_rgb, text_x, text_y, text_width, text_height)
            draw.text((text_x, text_y), str(value), fill=color, font=font)
    else:
        # Auto-position placeholders with smart layout
        font_size = min(width // 20, 60)
        font = _get_font(primary_font, font_size) if primary_font else ImageFont.load_default()

        # Draw each field with automatic positioning
        center_x = width // 2
        start_y = height // 3

        special_fields = {
            "participant_name": {"size": font_size + 20, "y_offset": 0, "bold": False},
            "prize_position": {"size": font_size, "y_offset": font_size + 40, "bold": True},
            "event_name": {"size": font_size, "y_offset": 2 * (font_size + 40), "bold": True},
            "date": {"size": font_size, "y_offset": 3 * (font_size + 40), "bold": True},
        }

        for i, (field_name, value) in enumerate(data.items()):
            if not value:
                continue

            field_config = special_fields.get(field_name.lower(), {"size": font_size, "y_offset": 0, "bold": False})
            use_size = field_config.get("size", font_size)
            use_bold = field_config.get("bold", False)

            # Clean time if it is the date field
            if field_name.lower() == "date":
                val_str = str(value).strip()
                for time_pattern in [" 00:00:00", "T00:00:00", " 00:00", "T00:00"]:
                    if time_pattern in val_str:
                        val_str = val_str.replace(time_pattern, "")
                value = val_str.strip()

            # Compute actual y offset based on configured ones
            if field_name.lower() in special_fields:
                y_offset = special_fields[field_name.lower()]["y_offset"]
            else:
                y_offset = start_y + (font_size + 20) * i

            font_to_use = _get_bold_font(primary_font) if (use_bold and primary_font) else primary_font
            use_font = _get_font(font_to_use, use_size) if font_to_use else ImageFont.load_default()

            bbox = draw.textbbox((0, 0), str(value), font=use_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = center_x - text_width // 2
            text_y = height // 3 + y_offset

            # Erase any placeholder text at this position before drawing
            _erase_text_area(draw, img_rgb, text_x, text_y, text_width, text_height)
            draw.text(
                (text_x, text_y),
                str(value),
                fill=(0, 0, 0, 255),
                font=use_font,
            )

    if qr_data:
        qr = qrcode.QRCode(version=1, box_size=10, border=1)
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        
        # Calculate QR code size and position (bottom right corner)
        # Using roughly 15% of width for the QR code size
        qr_size = int(width * 0.15)
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
        
        # Position at ~82% width, ~74% height to match the PDF coordinates roughly
        qr_x = int(width * 0.816)
        qr_y = int(height * 0.737)
        img_rgb.paste(qr_img, (qr_x, qr_y))

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    img_rgb.save(output_path, "PDF", resolution=dpi)
    return output_path


def generate_from_pdf_template(
    template_path, output_path, data, placeholders=None, qr_data=None
):
    """
    Generate a certificate from a PDF template using PyMuPDF (fitz).
    Dynamically detects underscore placeholder positions by scanning text
    spans, erases complete lines, and redraws them with filled values.

    Handles templates with these placeholder patterns:
      - Name: large underscore text (script font, size > 50)
      - Event: "for having [won Nth prize / participated] in ______"
               followed by a continuation line of underscores
      - Date: "held on ______ ."
    """
    doc = fitz.open(template_path)
    page = doc[0]

    # Get absolute base directory of the project
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # --- Register the official Niconne-Regular font for participant name ---
    script_font_name = "helv"
    niconne_font = None
    # Check both current directory and absolute path paths
    for font_path in [
        os.path.join(base_dir, "fonts", "Niconne-Regular.ttf"),
        "fonts/Niconne-Regular.ttf"
    ]:
        if os.path.exists(font_path):
            try:
                page.insert_font(fontname="Niconne", fontfile=font_path)
                script_font_name = "Niconne"
                niconne_font = fitz.Font(fontfile=font_path)
                break
            except Exception:
                pass

    # --- Register the official Montserrat-Regular font for body text ---
    body_render_font = "helv"
    montserrat_font = None
    for font_path in [
        os.path.join(base_dir, "fonts", "Montserrat-Regular.ttf"),
        "fonts/Montserrat-Regular.ttf"
    ]:
        if os.path.exists(font_path):
            try:
                page.insert_font(fontname="Montserrat", fontfile=font_path)
                body_render_font = "Montserrat"
                montserrat_font = fitz.Font(fontfile=font_path)
                break
            except Exception:
                pass

    # --- Register the official Montserrat-Bold font for bold body text ---
    body_render_font_bold = "hebo"  # 'hebo' is the valid built-in Helvetica Bold name in PyMuPDF
    for font_path in [
        os.path.join(base_dir, "fonts", "Montserrat-Bold.ttf"),
        "fonts/Montserrat-Bold.ttf"
    ]:
        if os.path.exists(font_path):
            try:
                page.insert_font(fontname="MontserratBold", fontfile=font_path)
                body_render_font_bold = "MontserratBold"
                break
            except Exception:
                pass

    def get_text_width(text, is_script=False, size=12):
        """Measure text width using loaded TTF files, falling back to base-14 Helvetica."""
        if is_script and niconne_font:
            try:
                return niconne_font.text_length(text, fontsize=size)
            except Exception:
                pass
        elif not is_script and montserrat_font:
            try:
                return montserrat_font.text_length(text, fontsize=size)
            except Exception:
                pass
        return fitz.get_text_length(text, fontname="helv", fontsize=size)

    # --- Scan all text spans to locate placeholder fields dynamically ---
    text_blocks = page.get_text(
        "dict", flags=fitz.TEXT_PRESERVE_WHITESPACE
    )["blocks"]

    name_span = None          # Large underscore placeholder for participant name
    event_line1_span = None   # "for having won Xth prize in ______..."
    event_line2_span = None   # "______________________" continuation line
    date_span = None          # "held on ______ ."

    for block in text_blocks:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue
                size = span["size"]
                bbox_y0 = span["bbox"][1]

                # Name placeholder: large font (>50pt), all underscores
                if size > 50 and all(c == "_" for c in text):
                    name_span = span

                # Event line 1: starts with "for having"
                elif text.lower().startswith("for having"):
                    event_line1_span = span

                # Event line 2: all underscores, body font size, below y=340
                elif (
                    all(c == "_" for c in text)
                    and 12 <= size <= 15
                    and bbox_y0 > 340
                ):
                    event_line2_span = span

                # Date line: contains "held" and underscores
                elif "held" in text.lower() and "_" in text:
                    date_span = span

    # --- Extract field values with flexible key matching ---
    participant_name = (
        data.get("participant_name")
        or data.get("Participant Name")
        or data.get("Name")
        or data.get("name")
        or ""
    )

    event_name = (
        data.get("Event")
        or data.get("event")
        or data.get("event_name")
        or data.get("Event Name")
        or ""
    )

    date_val = data.get("Date") or data.get("date") or ""

    body_fontsize = 13.1

    # ---------- 1. Participant Name ----------
    if participant_name and name_span:
        name_str = str(participant_name).strip()
        nb = name_span["bbox"]  # (x0, y0, x1, y1)

        # Auto-size to fit within the placeholder width (with margin)
        available_width = (nb[2] - nb[0]) - 40
        name_font_size = 24  # fallback minimum
        for test_size in [60, 56, 52, 48, 44, 40, 36, 32, 28, 24, 20, 18, 16]:
            tw = get_text_width(name_str, is_script=True, size=test_size)
            if tw <= available_width:
                name_font_size = test_size
                break

        # Erase the full underscore area
        page.draw_rect(
            fitz.Rect(nb[0] - 5, nb[1] - 2, nb[2] + 5, nb[3] + 2),
            color=(1, 1, 1),
            fill=(1, 1, 1),
            width=0,
            overlay=True,
        )

        # Center the name horizontally within the placeholder's bounding box using insert_textbox
        rect = fitz.Rect(nb[0], nb[1] - 15, nb[2], nb[3] + 15)
        page.insert_textbox(
            rect,
            name_str,
            fontname=script_font_name,
            fontsize=name_font_size,
            align=1,  # fitz.TEXT_ALIGN_CENTER
            color=(0, 0, 0),
        )

    # ---------- 2. Event Name ----------
    if event_name and event_line1_span:
        event_str = str(event_name).strip()
        eb1 = event_line1_span["bbox"]
        full_text_line1 = event_line1_span["text"]

        # Extract the prefix (everything before underscores)
        underscore_idx = full_text_line1.find("_")
        if underscore_idx > 0:
            prefix = full_text_line1[:underscore_idx]
            # Ensure it ends with a space
            if not prefix.endswith(" "):
                prefix = prefix.rstrip() + " "
        else:
            prefix = ""

        # Erase event line 1 completely (prefix + underscores)
        page.draw_rect(
            fitz.Rect(eb1[0] - 5, eb1[1] - 2, eb1[2] + 5, eb1[3] + 2),
            color=(1, 1, 1),
            fill=(1, 1, 1),
            width=0,
            overlay=True,
        )

        # Erase event line 2 completely
        eb2 = None
        if event_line2_span:
            eb2 = event_line2_span["bbox"]
            page.draw_rect(
                fitz.Rect(eb2[0] - 5, eb2[1] - 2, eb2[2] + 5, eb2[3] + 2),
                color=(1, 1, 1),
                fill=(1, 1, 1),
                width=0,
                overlay=True,
            )

        # Determine text area boundaries from the widest span
        line_left = min(eb1[0], eb2[0]) if eb2 else eb1[0]
        line_right = max(eb1[2], eb2[2]) if eb2 else eb1[2]
        max_line_width = line_right - line_left
        text_area_center = (line_left + line_right) / 2

        # Build the combined text: prefix + event name
        combined_text = prefix + event_str
        
        # Determine a bounding box spanning from line 1 to line 2 (if present)
        top_y = eb1[1] - 5
        bottom_y = eb2[3] + 5 if eb2 else eb1[3] + 15
        rect = fitz.Rect(line_left, top_y, line_right, bottom_y)
        
        page.insert_textbox(
            rect,
            combined_text,
            fontname=body_render_font_bold,
            fontsize=body_fontsize,
            align=1,  # fitz.TEXT_ALIGN_CENTER
            color=(0, 0, 0),
        )

    # ---------- 3. Date ----------
    if date_val and date_span:
        date_str = str(date_val).strip()

        # Clean 00:00:00 from date
        for time_pattern in [" 00:00:00", "T00:00:00", " 00:00", "T00:00"]:
            if time_pattern in date_str:
                date_str = date_str.replace(time_pattern, "")
        date_str = date_str.strip()

        db = date_span["bbox"]
        full_text = date_span["text"]

        # Extract prefix (everything before underscores, e.g. "held on ")
        underscore_idx = full_text.find("_")
        if underscore_idx > 0:
            prefix = full_text[:underscore_idx]
        else:
            prefix = "held on "

        # Erase the entire date line and redraw with filled value
        page.draw_rect(
            fitz.Rect(db[0] - 5, db[1] - 2, db[2] + 5, db[3] + 2),
            color=(1, 1, 1),
            fill=(1, 1, 1),
            width=0,
            overlay=True,
        )

        # Rebuild the full date text: "held on [date] ."
        full_date_text = f"{prefix}{date_str} ."
        rect = fitz.Rect(db[0], db[1] - 5, db[2], db[3] + 15)
        page.insert_textbox(
            rect,
            full_date_text,
            fontname=body_render_font_bold,
            fontsize=body_fontsize,
            align=1,  # fitz.TEXT_ALIGN_CENTER
            color=(0, 0, 0),
        )

    # ---------- 4. QR Code ----------
    if qr_data:
        qr = qrcode.QRCode(version=1, box_size=10, border=1)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        img_bytes = io.BytesIO()
        img_qr.save(img_bytes, format="PNG")
        
        # Insert QR code over the exact gold placeholder bounding box
        qr_rect = fitz.Rect(687.36, 438.78, 809.52, 566.16)
        page.insert_image(qr_rect, stream=img_bytes.getvalue())

    # ---------- Save ----------
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()

    return output_path


def generate_certificate(
    template_path, template_type, output_path, data, placeholders=None, qr_data=None
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
            template_path, output_path, data, placeholders, qr_data=qr_data
        )
    elif template_type.lower() == "pdf":
        return generate_from_pdf_template(
            template_path, output_path, data, placeholders, qr_data=qr_data
        )
    else:
        raise ValueError(f"Unsupported template type: {template_type}")
