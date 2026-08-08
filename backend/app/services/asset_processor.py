import re
from pathlib import Path
from PIL import Image


def natural_sort_key(filename: str):
    name = Path(filename).stem

    parts = re.split(r"(\d+)", name)

    return [
        int(part) if part.isdigit() else part.lower()
        for part in parts
    ]


def sort_filenames_naturally(filenames: list[str]) -> list[str]:
    return sorted(filenames, key=natural_sort_key)
ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


def is_valid_image_filename(filename: str) -> bool:
    extension = Path(filename).suffix.lower()

    return extension in ALLOWED_IMAGE_EXTENSIONS
def is_valid_image_file(file_path: Path) -> bool:
    try:
        with Image.open(file_path) as image:
            image.verify()

        return True

    except (OSError, SyntaxError):
        return False
ASSET_STATUS_READY = "ready"
ASSET_STATUS_PROCESSING = "processing"
ASSET_STATUS_FAILED = "failed"
ASSET_STATUS_EXCLUDED = "excluded"