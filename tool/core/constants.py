# KZTEK Image Tools — constants
CLASS_NAMES = {
    0: "car", 1: "motorcycle", 2: "bus",
    3: "truck", 4: "bicycle", 5: "license_plate",
}
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif",
    ".tiff", ".tif", ".heic", ".heif",
}

_VI = {
    '0': 'kong', '1': 'mot', '2': 'hai', '3': 'ba',
    '4': 'bon',  '5': 'nam', '6': 'sau', '7': 'bay',
    '8': 'tam',  '9': 'chin',
}
_VI_FULL = {
    'A': 'A',      'B': 'Bê',     'C': 'Xê',     'D': 'Đê',
    'E': 'E',      'F': 'Ép',     'G': 'Gờ',     'H': 'Hát',
    'I': 'I',      'J': 'Gi',     'K': 'Ca',     'L': 'Lờ',
    'M': 'Mờ',     'N': 'Nờ',     'O': 'O',      'P': 'Bê',
    'Q': 'Quy',    'R': 'Rờ',     'S': 'Ét',     'T': 'Tê',
    'U': 'U',      'V': 'Vê',     'W': 'Đáp liu','X': 'Ích',
    'Y': 'Y',      'Z': 'Rét',
    '0': 'Không',  '1': 'Một',    '2': 'Hai',    '3': 'Ba',
    '4': 'Bốn',    '5': 'Năm',    '6': 'Sáu',    '7': 'Bảy',
    '8': 'Tám',    '9': 'Chín',
}

# UI palette
BG      = "#1e1e2e"
CARD    = "#2a2a3e"
ACCENT  = "#F05922"
ACCENT2 = "#4A3F8C"
TEXT    = "#e0e0f0"
DIM     = "#9090b0"
SUCCESS = "#4caf50"
F_MAIN  = ("Segoe UI", 10)
F_BOLD  = ("Segoe UI Semibold", 11)
F_MONO  = ("Consolas", 9)

# LotteImage API defaults
_LI_API_BASE     = "http://119.17.223.230:2100"
_LI_USERNAME     = "kztek"
_LI_PASSWORD     = "123456"
_LI_MINIO_EP     = "119.17.223.230:9080"
_LI_MINIO_AK     = "kztek"
_LI_MINIO_SK     = "Kztek123456"
_LI_MINIO_BUCKET = "parking-images"

# Parkingv8Image API defaults
_P8_LOGIN_URL      = "http://localhost:5001"
_P8_API_URL        = "http://localhost:5000"
_P8_CLIENT_ID      = "kztek"
_P8_CLIENT_SECRET  = "kztek_secret"
_P8_USERNAME       = ""
_P8_PASSWORD       = ""

# Parkingv6Image API defaults (iParkingv5 ApiManagerv6, Bearer token, MinIO)
_P6_API_URL      = "http://113.162.247.111:5000"
_P6_MINIO_EP     = "113.162.247.111:9000"
_P6_MINIO_BUCKET = "parking-images"
_P6_MINIO_AK     = "admin"
_P6_MINIO_SK     = "Pass1234!"
