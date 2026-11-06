import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "stories.json"

# Ordered continuation after the existing Day 1 (Egypt) story.
COUNTRIES = [
"Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan",
"Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi",
"Cabo Verde", "Cambodia", "Cameroon", "Canada", "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros", "Costa Rica", "Côte d’Ivoire", "Croatia", "Cuba", "Cyprus", "Czechia",
"Democratic Republic of the Congo", "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Honduras", "Hungary",
"Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Palestine", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Republic of the Congo", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Korea", "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Türkiye", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States", "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe",
"Åland Islands", "American Samoa", "Anguilla", "Aruba", "Bermuda", "British Virgin Islands", "Cayman Islands", "Cook Islands", "Curaçao", "Faroe Islands", "French Polynesia", "Gibraltar", "Greenland"
]


MAX_ATTEMPTS = 5
BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def request_json(url, headers, payload):
    """POST JSON with bounded retries for temporary provider/network failures."""
    data = json.dumps(payload).encode("utf-8")
    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": BROWSER_UA,
        **headers,
    }
    last_error = None
    for attempt in range(MAX_ATTEMPTS):
        req = Request(url, data=data, headers=request_headers, method="POST")
        try:
            with urlopen(req, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(
                f"AI provider returned HTTP {exc.code}: {detail[:1200]}"
            )
            # Retry only errors that are commonly temporary. Authentication,
            # permission and Cloudflare 1010 blocks need configuration changes.
            if exc.code not in (408, 425, 429, 500, 502, 503, 504) or attempt == MAX_ATTEMPTS - 1:
                raise last_error from exc
            retry_after = exc.headers.get("Retry-After")
            try:
                delay = min(60, max(1, int(retry_after))) if retry_after else 5 * 2 ** attempt
            except ValueError:
                delay = 5 * 2 ** attempt
            print(f"Temporary AI HTTP {exc.code}; retrying in {delay}s (attempt {attempt + 2}/{MAX_ATTEMPTS}).")
            time.sleep(delay)
        except (URLError, TimeoutError) as exc:
            last_error = RuntimeError(f"AI provider network error: {exc}")
            if attempt == MAX_ATTEMPTS - 1:
                raise last_error from exc
            delay = 5 * 2 ** attempt
            print(f"Temporary AI network error; retrying in {delay}s (attempt {attempt + 2}/{MAX_ATTEMPTS}).")
            time.sleep(delay)
    raise last_error or RuntimeError("AI provider request failed for an unknown reason.")


def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("AI response did not contain a JSON object")
    return json.loads(text[start:end + 1])


def prompt_for(day, country, date_str):
    return f'''Create one engaging, accurate, reader-friendly story in natural, simple Hindi for a Hindi-language website called Stories of the World.
देश: {country}
दिन संख्या: {day}
तारीख: {date_str}

इस देश से जुड़ी कोई सचमुच प्रसिद्ध ऐतिहासिक घटना, लोककथा, सांस्कृतिक परंपरा, खोज या उल्लेखनीय सच्ची घटना चुनें। कहानी रोचक और सहज हिंदी में लिखें। लोककथा और प्रमाणित इतिहास में स्पष्ट अंतर रखें। मनगढ़ंत उद्धरण, तारीखें, व्यक्ति या तथ्य न जोड़ें। अनिश्चित होने पर सावधानी से लिखें। बहुत हिंसक विवरण न दें।

केवल वैध JSON लौटाएँ, ठीक इन्हीं keys और types के साथ:
{{
  "day": {day},
  "date": "{date_str}",
  "country": "{country}",
  "flag": "एक उपयुक्त झंडे का emoji",
  "kind": "history या myth या culture या discovery",
  "title": "हिंदी में छोटा और आकर्षक शीर्षक",
  "story": ["8 से 12 अनुच्छेद, हर अनुच्छेद में 2 से 4 वाक्य, सभी हिंदी में"],
  "why": "2 से 4 हिंदी वाक्यों में बताएँ कि कहानी प्रसिद्ध क्यों है",
  "where": "2 से 4 हिंदी वाक्यों में बताएँ कि आज यह कहाँ याद की जाती है या देखी जा सकती है",
  "truth": "2 से 4 हिंदी वाक्यों में प्रमाणित तथ्यों और लोककथा/अनिश्चितता का अंतर बताएँ",
  "info": [["राजधानी", "..."], ["भाषा", "..."], ["मुद्रा", "..."], ["खास बात", "देश से जुड़ी एक उपयोगी जानकारी"]],
  "image_queries": ["Wikimedia Commons पर असली फ़ोटो खोजने के लिए अंग्रेज़ी search query (कहानी के मुख्य स्थान/वस्तु की)", "दूसरी अलग अंग्रेज़ी search query"]
}}
कहानी मौलिक हो, किसी स्रोत से कॉपी न हो। JSON strings में quotation marks सही तरह escape करें। image_queries सिर्फ़ अंग्रेज़ी में हों और कोई URL न दें। JSON keys अंग्रेज़ी में ही रखें, लेकिन कहानी और सभी दिखने वाले मान हिंदी में लिखें।'''


def call_gemini(prompt, key):
    # Try the configured model first, then stable fallbacks (a busy/missing model must not stop the day's story).
    models = [m for m in [os.getenv("GEMINI_MODEL"), "gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite"] if m]
    models = list(dict.fromkeys(models))
    last = None
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            result = request_json(url, {"x-goog-api-key": key}, {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"}
            })
            print(f"Gemini model used: {model}")
            return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:
            last = exc
            print(f"Gemini model {model} failed: {str(exc)[:200]}", file=sys.stderr)
    raise last


def call_groq(prompt, key):
    models = [m for m in [os.getenv("GROQ_MODEL"), "llama-3.3-70b-versatile", "llama-3.1-8b-instant"] if m]
    models = list(dict.fromkeys(models))
    last = None
    for model in models:
        try:
            result = request_json("https://api.groq.com/openai/v1/chat/completions", {
                "Authorization": f"Bearer {key}",
            }, {
                "model": model,
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "You write accurate, engaging educational country stories and return only valid JSON."},
                    {"role": "user", "content": prompt}
                ]
            })
            print(f"Groq model used: {model}")
            return result["choices"][0]["message"]["content"]
        except Exception as exc:
            last = exc
            print(f"Groq model {model} failed: {str(exc)[:200]}", file=sys.stderr)
    raise last


def ask_ai(prompt):
    """Gemini first (with model fallbacks), then Groq. Returns raw text."""
    errors = []
    gemini_key, groq_key = os.getenv("GEMINI_API_KEY"), os.getenv("GROQ_API_KEY")
    if gemini_key:
        try:
            return call_gemini(prompt, gemini_key)
        except Exception as exc:
            errors.append(f"Gemini failed: {exc}")
            print(errors[-1], file=sys.stderr)
    if groq_key:
        try:
            return call_groq(prompt, groq_key)
        except Exception as exc:
            errors.append(f"Groq failed: {exc}")
            print(errors[-1], file=sys.stderr)
    raise RuntimeError("No AI provider succeeded. " + " | ".join(errors or ["Add GEMINI_API_KEY or GROQ_API_KEY repository secret."]))


def translate_prompt(story):
    src = {k: story[k] for k in ("title", "story", "why", "where", "truth", "info")}
    return ("Translate this Hindi story content into clear, natural English. Keep facts exactly the same, keep the "
            "same number of paragraphs and the same structure. Return ONLY valid JSON with exactly these keys: "
            "title (string), story (array of strings), why (string), where (string), truth (string), "
            "info (array of [label, value] pairs, labels and values in English).\n\n"
            + json.dumps(src, ensure_ascii=False))


def add_english(story):
    en = extract_json(ask_ai(translate_prompt(story)))
    if not isinstance(en.get("story"), list) or not en.get("title"):
        raise ValueError("English translation is incomplete")
    story["en"] = {k: en[k] for k in ("title", "story", "why", "where", "truth", "info") if k in en}


def http_get_json(url):
    req = Request(url, headers={"User-Agent": BROWSER_UA, "Accept": "application/json"})
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def strip_html(t):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t or "")).strip()


def commons_images(queries, country, flag, limit=2):
    """Find real, existing photos on Wikimedia Commons (never trust AI-invented URLs)."""
    found, seen = [], set()
    for q in queries:
        if len(found) >= limit:
            break
        params = {
            "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
            "gsrsearch": q + " filetype:bitmap", "gsrlimit": 12, "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata", "iiurlwidth": 900,
        }
        try:
            data = http_get_json("https://commons.wikimedia.org/w/api.php?" + urlencode(params))
        except Exception as exc:
            print(f"Commons search failed for '{q}': {exc}", file=sys.stderr)
            continue
        pages = sorted((data.get("query", {}).get("pages", {})).values(), key=lambda p: p.get("index", 99))
        for pg in pages:
            info = (pg.get("imageinfo") or [None])[0]
            if not info or info.get("mime") not in ("image/jpeg", "image/png"):
                continue
            if info.get("width", 0) < 700 or info.get("width", 0) < info.get("height", 0) * 0.7:
                continue
            thumb = info.get("thumburl") or info.get("url")
            if not thumb or thumb in seen:
                continue
            seen.add(thumb)
            meta = info.get("extmetadata", {})
            title = re.sub(r"^File:|\.[A-Za-z]+$", "", pg.get("title", "")).replace("_", " ")
            desc = strip_html(meta.get("ImageDescription", {}).get("value", ""))
            en_cap = (desc if 8 < len(desc) <= 140 else title)
            artist = strip_html(meta.get("Artist", {}).get("value", "")) or "Wikimedia Commons"
            lic = strip_html(meta.get("LicenseShortName", {}).get("value", ""))
            found.append({
                "url": thumb, "source": info.get("descriptionurl", ""),
                "en": en_cap, "hi": f"{flag} {country}: {title}",
                "credit": f"{artist[:80]}, {lic}".strip(", "), "commons": True,
            })
            break
    return found


def repair_archive(existing):
    """Backfill English text and real Commons photos for any story missing them."""
    changed = False
    for st in existing:
        if not isinstance(st, dict):
            continue
        if "en" not in st and isinstance(st.get("story"), list):
            try:
                add_english(st); changed = True
                print(f"Added English version for Day {st.get('day')}.")
            except Exception as exc:
                print(f"English backfill failed for Day {st.get('day')}: {exc}", file=sys.stderr)
        if not any(im.get("commons") for im in (st.get("images") or []) if isinstance(im, dict)):
            title_en = (st.get("en") or {}).get("title", "")
            queries = list(st.get("image_queries") or []) + [f"{st.get('country')} {title_en}".strip(), f"{st.get('country')} landmark"]
            imgs = commons_images(queries, st.get("country", ""), st.get("flag", ""))
            if imgs:
                st["images"] = imgs; changed = True
                print(f"Added {len(imgs)} Commons image(s) for Day {st.get('day')}.")
    return changed


def save(existing):
    ARCHIVE.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    existing = json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else []
    if not isinstance(existing, list):
        raise ValueError("stories.json must contain a JSON array")
    # Fix older stories first (English text + working photos). Saved immediately so it is never lost.
    try:
        if repair_archive(existing):
            save(existing)
    except Exception as exc:
        print(f"Archive repair skipped: {exc}", file=sys.stderr)

    used_days = [int(s.get("day", 0)) for s in existing if isinstance(s, dict)]
    # The original Egypt story (Day 1) lives inside index.html, so the archive starts at Day 2.
    next_day = max([1] + used_days) + 1
    if any(int(s.get("day", -1)) == next_day for s in existing if isinstance(s, dict)):
        raise RuntimeError("This day already exists; refusing to duplicate it")

    used_countries = {str(s.get("country", "")).casefold() for s in existing if isinstance(s, dict)}
    country = next((c for c in COUNTRIES if c.casefold() not in used_countries and c.casefold() != "egypt"), None)
    if not country:
        print("Country list completed; no new country generated.")
        return

    date_str = datetime.now(timezone.utc).date().isoformat()
    story = extract_json(ask_ai(prompt_for(next_day, country, date_str)))
    required = {"day", "date", "country", "flag", "kind", "title", "story", "why", "where", "truth", "info"}
    if not required.issubset(story):
        raise ValueError("AI story is missing required fields: " + ", ".join(sorted(required - set(story))))
    story["day"], story["date"], story["country"] = next_day, date_str, country
    if not isinstance(story["story"], list) or len(story["story"]) < 5:
        raise ValueError("AI story has too few paragraphs")
    story.pop("images", None)  # never keep AI-invented image URLs
    try:
        add_english(story)
    except Exception as exc:
        print(f"English translation failed (will be backfilled next run): {exc}", file=sys.stderr)
    queries = list(story.get("image_queries") or []) + [f"{country} {(story.get('en') or {}).get('title', '')}".strip(), f"{country} landmark"]
    imgs = commons_images(queries, country, story.get("flag", ""))
    if imgs:
        story["images"] = imgs
    existing.append(story)
    save(existing)
    print(f"Published Day {next_day}: {country}")

if __name__ == "__main__":
    main()
