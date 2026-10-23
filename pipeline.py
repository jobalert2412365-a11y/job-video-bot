import asyncio, json, os, re, subprocess, sys
import edge_tts, feedparser, requests

LANG = os.getenv("VIDEO_LANGUAGE", "English")
VOICE = os.getenv("VOICE", "en-IN-NeerjaNeural")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")   # check the current free model name
FONT = os.getenv("FONT_FILE", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
MAX_TRIES = 5


def load_seen():
    return set(json.load(open("seen.json"))["seen"])


def save_seen(seen):
    json.dump({"seen": sorted(seen)[-500:]}, open("seen.json", "w"), indent=1)


def candidates(seen):
    feeds = [l.strip() for l in open("feeds.txt") if l.strip() and not l.startswith("#")]
    items = []
    for url in feeds:
        for e in feedparser.parse(url).entries:
            if e.get("link") and e["link"] not in seen:
                items.append({"title": e.get("title", ""), "link": e["link"],
                              "summary": e.get("summary", ""),
                              "date": e.get("published_parsed") or (0,)})
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


def page_text(item):
    try:
        html = requests.get(item["link"], timeout=30, headers={"User-Agent": "Mozilla/5.0"}).text
        html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        if len(text) > 300:
            return text[:4000]
    except Exception as ex:
        print("page fetch failed:", ex)
    return re.sub(r"<[^>]+>", " ", item["summary"])[:4000]


def ask_gemini(item):
    prompt = f"""You turn job notifications into a short vertical-video script.
Use ONLY facts present in the text. If a field is missing, use null. Never invent dates, vacancies or links.
Return JSON with keys: organization, post_name, vacancies, qualification, last_date, apply_link,
headline (max 8 words), script (about 90 spoken words in {LANG}, ending with a reminder to check the
official notification), youtube_title (max 80 chars), youtube_description, tags (array of strings).

Title: {item['title']}
Link: {item['link']}
Text: {page_text(item)}"""
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}},
        timeout=90)
    r.raise_for_status()
    return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])


def wrap(s, n):
    lines, cur = [], ""
    for w in str(s or "").split():
        if len((cur + " " + w).strip()) > n:
            lines.append(cur.strip()); cur = w
        else:
            cur += " " + w
    if cur.strip():
        lines.append(cur.strip())
    return "\n".join(lines)


def build_video(d):
    asyncio.run(edge_tts.Communicate(d["script"], VOICE).save("audio.mp3"))
    open("head.txt", "w", encoding="utf-8").write(wrap(d.get("headline") or d.get("post_name") or "Job Alert", 18))
    rows = [("Org", d.get("organization")), ("Vacancies", d.get("vacancies")),
            ("Qualification", d.get("qualification")), ("Last date", d.get("last_date"))]
    open("body.txt", "w", encoding="utf-8").write(
        "\n\n".join(wrap(f"{k}: {v}", 28) for k, v in rows if v))
    vf = (f"drawtext=fontfile={FONT}:textfile=head.txt:fontcolor=white:fontsize=84:"
          f"x=(w-text_w)/2:y=260:line_spacing=24,"
          f"drawtext=fontfile={FONT}:textfile=body.txt:fontcolor=0xffd166:fontsize=48:"
          f"x=80:y=800:line_spacing=18")
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x0b1f3a:s=1080x1920:r=30",
                    "-i", "audio.mp3", "-vf", vf, "-shortest", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "video.mp4"], check=True)


def send_telegram(d, apply_link):
    tok, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    title = (d.get("youtube_title") or d.get("headline") or "Job Alert")[:85] + " #Shorts"
    desc = (f"{d.get('youtube_description') or ''}\n\nOfficial notification: {apply_link}\n\n"
            "Disclaimer: Always verify details on the official website before applying. "
            "AI-assisted video.\n#Shorts #JobAlert #Jobs")
    tags = ", ".join(d.get("tags") or [])
    base = f"https://api.telegram.org/bot{tok}"
    with open("video.mp4", "rb") as f:
        r = requests.post(f"{base}/sendVideo",
                          data={"chat_id": chat, "caption": title[:1000], "supports_streaming": "true",
                                "width": 1080, "height": 1920},
                          files={"video": f}, timeout=300)
    r.raise_for_status()
    text = f"TITLE:\n{title}\n\nDESCRIPTION:\n{desc}\n\nTAGS:\n{tags}"
    requests.post(f"{base}/sendMessage", json={"chat_id": chat, "text": text[:4000]},
                  timeout=60).raise_for_status()


def main():
    seen = load_seen()
    items = candidates(seen)
    if not items:
        print("No new openings today."); return
    for item in items[:MAX_TRIES]:
        seen.add(item["link"]); save_seen(seen)        # never retry the same link
        try:
            d = ask_gemini(item)
        except Exception as ex:
            print("Gemini failed:", ex); continue
        if not d.get("last_date") or not d.get("script"):
            print("Skipping (missing key facts):", item["title"]); continue
        build_video(d)
        send_telegram(d, d.get("apply_link") or item["link"])
        print("Sent to Telegram:", item["title"])
        return
    print("No usable opening found today.")


if __name__ == "__main__":
    main()
