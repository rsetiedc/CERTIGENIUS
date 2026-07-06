import fitz

doc = fitz.open("uploads/certificate_template/test_1st_prize.pdf")
page = doc[0]
print(f"Page width: {page.rect.width}, Page center: {page.rect.width / 2}")

text_blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
for block in text_blocks:
    if block["type"] != 0: continue
    for line in block["lines"]:
        for span in line["spans"]:
            text = span["text"].strip()
            if not text: continue
            if span["size"] > 50 and all(c == "_" for c in text):
                nb = span["bbox"]
                print(f"Name span center: {(nb[0] + nb[2]) / 2}, bbox: {nb}")
