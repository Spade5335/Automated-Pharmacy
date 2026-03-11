import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Paths
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DRUG_NAMES_PATH = os.path.join(BASE_DIR, "data", "drug_names.json")
INVENTORY_PATH = os.path.join(BASE_DIR, "data", "inventory.json")

# Upload settings
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

# Fuzzy matching
MATCH_SCORE_THRESHOLD = 65  # Minimum similarity score (0-100)
MATCH_LIMIT = 3  # Top N candidates per extracted name

# OCR
USE_GPU = False
