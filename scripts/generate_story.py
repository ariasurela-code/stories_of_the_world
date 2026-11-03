import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
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


def request_json(url, headers, payload):
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={**headers, "Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("AI response did not contain a JSON object")
    return json.loads(text[start:end + 1])


def prompt_for(day, country, date_str):
    return f'''Create one engaging, accurate, reader-friendly English story for a website called Stories of the World.
Country: {country}
Day number: {day}
Date: {date_str}

Choose a genuinely famous historical event, legend, discovery, cultural tradition, or remarkable true incident connected to this country. Clearly distinguish folklore from verified history in the truth field. Do not invent quotations, dates, people, or facts. If uncertain, phrase cautiously. Avoid graphic violence.

Return ONLY valid JSON with exactly these keys and types:
{{
  "day": {day},
  "date": "{date_str}",
  "country": "{country}",
  "flag": "one suitable flag emoji",
  "kind": "history or myth or culture or discovery",
  "title": "short engaging title",
  "story": ["8 to 12 paragraphs, each 2 to 4 sentences"],
  "why": "2 to 4 sentences explaining why the story is famous",
  "where": "2 to 4 sentences explaining where it is remembered or seen today",
  "truth": "2 to 4 sentences separating established facts from legend or uncertainty",
  "info": [["Capital", "..."], ["Language", "..."], ["Currency", "..."], ["Special", "one useful country fact"]]
}}
The story must be original prose, not copied from a source. Keep all JSON strings valid and escape quotation marks correctly.'''


def call_gemini(prompt, key):
    # Gemini REST generateContent endpoint; model can be overridden in repository Variables.
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    result = request_json(url, {"x-goog-api-key": key}, {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"}
    })
    return result["candidates"][0]["content"]["parts"][0]["text"]


def call_groq(prompt, key):
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    result = request_json("https://api.groq.com/openai/v1/chat/completions", {
        "Authorization": f"Bearer {key}"
    }, {
        "model": model,
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You write accurate, engaging educational country stories and return only valid JSON."},
            {"role": "user", "content": prompt}
        ]
    })
    return result["choices"][0]["message"]["content"]


def main():
    existing = json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else []
    if not isinstance(existing, list):
        raise ValueError("stories.json must contain a JSON array")
    base = json.loads((ROOT / "index.html").read_text(encoding="utf-8")) if False else []
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
    prompt = prompt_for(next_day, country, date_str)
    raw = None
    errors = []
    gemini_key, groq_key = os.getenv("GEMINI_API_KEY"), os.getenv("GROQ_API_KEY")
    if gemini_key:
        try:
            raw = call_gemini(prompt, gemini_key)
            print("Story generated with Gemini.")
        except Exception as exc:
            errors.append(f"Gemini failed: {exc}")
            print(errors[-1], file=sys.stderr)
    if raw is None and groq_key:
        try:
            raw = call_groq(prompt, groq_key)
            print("Story generated with Groq fallback.")
        except Exception as exc:
            errors.append(f"Groq failed: {exc}")
            print(errors[-1], file=sys.stderr)
    if raw is None:
        raise RuntimeError("No AI provider succeeded. " + " | ".join(errors or ["Add GEMINI_API_KEY or GROQ_API_KEY repository secret."]))

    story = extract_json(raw)
    required = {"day", "date", "country", "flag", "kind", "title", "story", "why", "where", "truth", "info"}
    if not required.issubset(story):
        raise ValueError("AI story is missing required fields: " + ", ".join(sorted(required - set(story))))
    story["day"], story["date"], story["country"] = next_day, date_str, country
    if not isinstance(story["story"], list) or len(story["story"]) < 5:
        raise ValueError("AI story has too few paragraphs")
    existing.append(story)
    ARCHIVE.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Published Day {next_day}: {country}")

if __name__ == "__main__":
    main()
