"""
Diwali Rangoli Gift - page builder
-----------------------------------
Ek single HTML file (index.html) banata hai:
  * link kholne par pehle naam puchta hai
  * naam sahi -> photo dot dot se rangoli ki tarah ban jaati hai
  * naam galat -> "This gift is for a special person"

Photo us naam se ENCRYPT hoti hai (AES-256 + PBKDF2), isliye naam HTML mein kahin
likha nahi hota aur View Source se bhi photo/naam nahi nikal sakta. Backend ki zaroorat nahi.

Use:
    pip install pillow numpy cryptography
    python make_gift.py photo.png --name "priya"
    python make_gift.py photo.png --name "priya" --name "priya sharma" --name "pri"

Options:
    --name        wo naam jo wo type karegi (kai baar de sakte ho: nickname, full name...)
                  (capital/small, extra space ka farak nahi padta)
    --greeting    {name} ki jagah wohi naam aayega jo usne type kiya
    --message     neeche ka chhota sa message
    --duration    drawing kitne seconds mein poori ho (default 12)
    --spacing     dots ka gap, chhota = zyada clear (default 5)
    --no-detail   edges wale extra chhote dots band (aapki purani .py jaisa simple look)
    --wish-title / --wish-message / --from   dusre logon ko dikhne wala Happy Diwali wish
    --out         output file (default index.html)
"""
import argparse
import base64
import json
import os
import struct
import sys
import unicodedata

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

PBKDF2_ITER = 200_000
MAX_W, MAX_H = 1000, 800
DETAIL_THRESHOLD = 28
SHARPEN = 1.0


# ----------------------------- image -> dots -----------------------------
def load_image(path):
    img = Image.open(path).convert("RGB")
    scale = min(MAX_W / img.width, MAX_H / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    blur = img.filter(ImageFilter.GaussianBlur(25))
    a = np.asarray(img, dtype=np.float32)
    b = np.asarray(blur, dtype=np.float32)
    a = np.clip(a + 0.5 * (a - b), 0, 255)
    img = Image.fromarray(a.astype(np.uint8))
    img = ImageOps.autocontrast(img, cutoff=0.5)
    img = ImageEnhance.Color(img).enhance(1.25)
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=int(160 * SHARPEN), threshold=2))
    return img


def grid(W, H, spacing, offset=0.0):
    row_h = spacing * np.sqrt(3) / 2
    ys = np.arange(spacing / 2 + offset, H, row_h)
    xs_base = np.arange(spacing / 2 + offset, W, spacing)
    X, Y = [], []
    for row, y in enumerate(ys):
        xs = xs_base + (spacing / 2 if row % 2 else 0)
        xs = xs[xs < W]
        X.append(xs)
        Y.append(np.full(xs.shape, y))
    return np.concatenate(X), np.concatenate(Y)


def sample_colors(img, X, Y, r_sample):
    W, H = img.size
    src = img.filter(ImageFilter.BoxBlur(r_sample)) if r_sample > 0 else img
    arr = np.asarray(src, dtype=np.float32)
    c = arr[np.clip(Y.astype(int), 0, H - 1), np.clip(X.astype(int), 0, W - 1)]
    return c.astype(np.uint8)


def spiral_order(X, Y, W, H):
    cx, cy = X - W / 2, H / 2 - Y
    key = np.hypot(cx, cy) + 0.15 * np.degrees(np.arctan2(cy, cx))
    return np.argsort(key, kind="stable")


def build_dots(img, spacing, detail=True):
    W, H = img.size
    X, Y = grid(W, H, spacing)
    C = sample_colors(img, X, Y, max(1, spacing // 3))
    i = spiral_order(X, Y, W, H)
    X, Y, C = X[i], Y[i], C[i]
    n_main = len(X)
    if not detail:
        return W, H, X, Y, C, n_main

    gray = img.convert("L").filter(ImageFilter.GaussianBlur(1))
    edges = np.asarray(gray.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    fs = max(2.5, spacing / 2)
    fX, fY = grid(W, H, fs, offset=spacing / 4)
    keep = edges[np.clip(fY.astype(int), 0, H - 1), np.clip(fX.astype(int), 0, W - 1)] > DETAIL_THRESHOLD
    fX, fY = fX[keep], fY[keep]
    fC = sample_colors(img, fX, fY, 0)
    j = spiral_order(fX, fY, W, H)

    X = np.concatenate([X, fX[j]])
    Y = np.concatenate([Y, fY[j]])
    C = np.concatenate([C, fC[j]])
    return W, H, X, Y, C, n_main


def pack_dots(X, Y, C):
    """Har dot = 7 bytes: x*4 (u16), y*4 (u16), r, g, b."""
    n = len(X)
    buf = np.empty((n, 7), dtype=np.uint8)
    xq = np.round(X * 4).astype("<u2").view(np.uint8).reshape(n, 2)
    yq = np.round(Y * 4).astype("<u2").view(np.uint8).reshape(n, 2)
    buf[:, 0:2], buf[:, 2:4], buf[:, 4:7] = xq, yq, C
    return buf.tobytes()


# ------------------------------- encryption -------------------------------
def norm_name(s):
    return " ".join(unicodedata.normalize("NFC", s).lower().split())


def derive_key(name, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITER)
    return kdf.derive(norm_name(name).encode("utf-8"))


def b64(b):
    return base64.b64encode(b).decode("ascii")


def encrypt_payload(payload, names):
    salt = os.urandom(16)
    data_key = AESGCM.generate_key(bit_length=256)
    iv = os.urandom(12)
    ct = AESGCM(data_key).encrypt(iv, payload, None)
    wraps = []
    for nm in names:
        wiv = os.urandom(12)
        wraps.append({"iv": b64(wiv), "ct": b64(AESGCM(derive_key(nm, salt)).encrypt(wiv, data_key, None))})
    return {"salt": b64(salt), "iter": PBKDF2_ITER, "wraps": wraps, "iv": b64(iv), "ct": b64(ct)}


# --------------------------------- main ---------------------------------
def main():
    ap = argparse.ArgumentParser(description="Diwali rangoli gift page builder")
    ap.add_argument("photo")
    ap.add_argument("--name", action="append", help="naam jo wo type karegi (kai baar de sakte ho)")
    ap.add_argument("--greeting", default="Happy Diwali, {name} \u2728")
    ap.add_argument("--message", default="Made with love, just for you \U0001FA94")
    ap.add_argument("--duration", type=float, default=12)
    ap.add_argument("--spacing", type=int, default=5)
    ap.add_argument("--no-detail", action="store_true")
    ap.add_argument("--wish-title", default="Happy Diwali, {name}!")
    ap.add_argument("--wish-message", default=(
        "May the festival of lights fill your life with happiness, prosperity and peace. "
        "May every diya you light brighten your home and your heart. "
        "Wishing you and your family a very Shubh Deepawali! \u2728"))
    ap.add_argument("--from", dest="sender", default="")
    ap.add_argument("--out", default="index.html")
    args = ap.parse_args()

    names = [n for n in (args.name or []) if n.strip()]
    if not names:
        names = [input("Wo kaunsa naam type karegi? (ek naam): ").strip()]
        if not names[0]:
            sys.exit("Naam zaroori hai.")

    img = load_image(args.photo)
    W, H, X, Y, C, n_main = build_dots(img, args.spacing, detail=not args.no_detail)
    meta = {
        "w": W, "h": H, "n": int(len(X)), "nMain": int(n_main),
        "rMain": round(args.spacing * 0.6, 2),
        "rDetail": round(max(1.0, args.spacing * 0.22), 2),
        "greeting": args.greeting, "message": args.message, "duration": args.duration,
    }
    meta_b = json.dumps(meta, ensure_ascii=False).encode("utf-8")
    payload = struct.pack("<I", len(meta_b)) + meta_b + pack_dots(X, Y, C)
    box = encrypt_payload(payload, names)

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "gift_template.html"), encoding="utf-8") as f:
        html = f.read().replace("__GIFT_JSON__", json.dumps(box))
        wish = {"title": args.wish_title, "message": args.wish_message, "from": args.sender}
        html = html.replace("__WISH_JSON__", json.dumps(wish, ensure_ascii=False))
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Done! {args.out} ban gayi  ({len(X)} dots, {os.path.getsize(args.out) // 1024} KB)")
    print("Accepted naam:", ", ".join(names))


if __name__ == "__main__":
    main()
