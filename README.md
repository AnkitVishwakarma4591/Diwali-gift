# 🪔 Happy Diwali — A Name-Keyed Surprise

A small festive greeting page made to wish people **Happy Diwali**. Everyone who opens it can enter a name and see a warm festive wish. One specially chosen name unlocks the personal gift: a photo that is drawn onscreen as a colorful rangoli.

> **What makes it special:** the recipient’s name is the key to the hidden gift. The name is not written in plain text in the generated page; it is used to derive a key that unlocks the encrypted photo payload.

![Preview of the Diwali page](home_page.png)

## ✨ What happens

1. The page opens on a Diwali greeting and asks for a first name.
2. A regular name shows the general Diwali wish and fireworks.
3. The special name unlocks the gift and starts the animated rangoli reveal.
4. The message appears when the drawing is complete. Choose **Watch again** to replay it.

The page is a single, self-contained HTML file. It includes a starry night, glowing diyas, gently swinging lanterns, a rotating mandala and animated fireworks. The layout adapts to phones and larger screens.

## 📁 Project files

| File | Purpose |
| --- | --- |
| `index.html` | Ready-to-open Diwali page, including its encrypted gift data |
| `gift_template.html` | HTML template used to create a page with a new photo and recipient name |
| `make_gift.py` | Builds the dot-art gift and encrypts its payload |
| `photo.png` | Source photo used for the personal gift |
| `home_page.png` | Preview image of the landing page |

## 🚀 Open the page

**Live site:** [love-surprise-by-ankit.netlify.app](https://love-surprise-by-ankit.netlify.app/)

Open `index.html` in a modern browser. No web server or backend is needed for the existing page.

For best results, use a recent browser with Web Crypto support. The unlock uses browser cryptography, so if opening the file directly does not work in your browser, serve this folder locally:

```bash
python -m http.server 8000
```

Then visit [http://localhost:8000](http://localhost:8000).

## 🛠️ Build a new gift page

The builder needs Python and these packages:

```bash
python -m pip install pillow numpy cryptography
```

Example:

```bash
python make_gift.py photo.png --name "special name" --out index.html
```

You can provide multiple accepted spellings or nicknames by repeating `--name`:

```bash
python make_gift.py photo.png --name "name" --name "nickname"
```

The builder accepts options to customize the greeting, personal message, reveal duration, dot spacing and the general wish shown to everyone else. Run `python make_gift.py --help` for the full list. Smaller dot spacing produces a more detailed drawing and a larger output file.

## 🔐 A note about the hidden name

The builder normalizes names for case and extra spaces, then uses PBKDF2 and AES-GCM to protect the photo payload. This keeps the intended name out of plain text in the page source and makes the gift feel like a name-keyed surprise.

This is a playful reveal, not strong access control: the page runs in the recipient’s browser, and a determined person may still inspect or alter client-side code.

---

Made with festive lights, a little animation, and a personal surprise. ✨

