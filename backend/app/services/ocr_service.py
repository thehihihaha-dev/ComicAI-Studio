import easyocr
from app.services.performance import timed_stage

_reader = None


def get_ocr():
    global _reader

    if _reader is None:
        print("Loading EasyOCR model...")

        _reader = easyocr.Reader(
            ["vi", "en"],
            gpu=False,
        )

        print("EasyOCR model loaded.")

    return _reader


@timed_stage("ocr")
def extract_ocr_blocks(image_path: str) -> list[dict]:
    reader = get_ocr()

    results = reader.readtext(
        image_path,
        detail=1,
    )

    blocks = []

    for box, text, confidence in results:
        blocks.append(
            {
                "text": text,
                "confidence": float(confidence),
                "box": [
                    [int(point[0]), int(point[1])]
                    for point in box
                ],
            }
        )

    return blocks


def extract_text_from_image(image_path: str) -> str:
    blocks = extract_ocr_blocks(image_path)

    return "\n".join(
        block["text"]
        for block in blocks
        if block["text"].strip()
    )
