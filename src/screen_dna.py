import easyocr
from PIL import ImageGrab

reader = easyocr.Reader(["en"], gpu=False)


def extract_screen_dna() -> dict:
    """Convert screen to compact JSON — no AI needed"""
    img = ImageGrab.grab()

    # OCR — find all text with positions
    results = reader.readtext(img)

    text_elements = [
        {
            "text": r[1],
            "conf": r[2],
            "x": int(r[0][0][0]),
            "y": int(r[0][0][1]),
            "w": int(r[0][2][0] - r[0][0][0]),
            "h": int(r[0][2][1] - r[0][0][1]),
        }
        for r in results
        if r[2] > 0.5
    ]

    return {"all_text": [e["text"] for e in text_elements], "raw": text_elements}


def find_element(description: str, dna: dict) -> tuple:
    """Find x,y of element by description — no AI"""
    desc_lower = description.lower()
    for elem in dna["raw"]:
        if any(word in elem["text"].lower() for word in desc_lower.split()):
            cx = elem["x"] + elem.get("w", 50) // 2
            cy = elem["y"] + elem.get("h", 20) // 2
            return (cx, cy)
    return None
