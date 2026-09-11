import requests
from datetime import datetime

JSON_URL = "http://141.164.53.195/live/korea-live.json"
EPG_URL = "https://epg.lat/files/kr.xml.gz"  # South Korea EPG Guide URL

OUTPUT1 = "korea.m3u8"    # DIYP format
OUTPUT2 = "korea2.m3u8"   # Standard M3U (May EPG at Logo)

def extract_m3u8_only(uris):
    """Kukuha lang ng .m3u8 (para sa OUTPUT1)"""
    def is_m3u8(u):
        return isinstance(u, str) and ("channel=" in u.lower() or ".m3u8" in u.lower() or u.lower().endswith(".php")) and "wavve" not in u.lower() and "file-1253962976.cos" not in u.lower()

    if isinstance(uris, list):
        for u in uris:
            if is_m3u8(u):
                return u.strip()
    elif isinstance(uris, dict):
        for u in uris.values():
            if is_m3u8(u):
                return u.strip()
    elif isinstance(uris, str):
        if is_m3u8(uris):
            return uris.strip()

    return None


def extract_m3u8_or_php(uris):
    """Kukuha ng .m3u8 o .php (para sa OUTPUT2)"""
    urls = []

    def is_valid(u):
        return isinstance(u, str) and ("channel=" in u.lower() or ".m3u8" in u.lower() or u.lower().endswith(".php")) and "wavve" not in u.lower() and "file-1253962976.cos" not in u.lower()

    if isinstance(uris, list):
        urls = [u.strip() for u in uris if is_valid(u)]
    elif isinstance(uris, dict):
        urls = [u.strip() for u in uris.values() if is_valid(u)]
    elif isinstance(uris, str):
        if is_valid(uris):
            urls = [uris.strip()]

    # Unahin ang .m3u8
    for u in urls:
        if ".m3u8" in u.lower():
            return u

    # Sunod ang .php
    if urls:
        return urls[0]

    return None


def run():
    try:
        r = requests.get(JSON_URL, timeout=20)
        r.encoding = "utf-8"
        data = r.json()
    except Exception as e:
        print(f"{datetime.now()} Error sa pag-get ng JSON: {e}")
        return

    lines1 = ["#EXTM3U"]
    # Nagdagdag ng url-tvg sa header para awtomatikong i-load ng IPTV player ang EPG
    lines2 = [f'#EXTM3U url-tvg="{EPG_URL}"']

    count1 = 0
    count2 = 0

    for item in data:
        name = item.get("name", "").strip()
        uris = item.get("uris")
        logo = item.get("logo", "") or item.get("tvg-logo", "") or item.get("icon", "")
        tvg_id = item.get("tvg-id", "") or name  # Gamitin ang tvg-id kung mayroon, kung wala ay channel name

        if not name or not uris:
            continue

        # OUTPUT1: DIYP Format
        url1 = extract_m3u8_only(uris)
        if url1:
            lines1.append(f"{name},{url1}")
            count1 += 1

        # OUTPUT2: Standard M3U (may Automatic EPG tags + Logo)
        url2 = extract_m3u8_or_php(uris)
        if url2:
            logo_attr = f' tvg-logo="{logo.strip()}"' if logo else ''
            lines2.append(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{name}"{logo_attr},{name}')
            lines2.append(url2)
            count2 += 1

    with open(OUTPUT1, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines1))

    with open(OUTPUT2, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines2))

    print(f"{datetime.now()} DIYP Channels: {count1}")
    print(f"{datetime.now()} M3U Channels (with EPG): {count2}")
    print(f"{datetime.now()} File Generated: {OUTPUT1}, {OUTPUT2}")


if __name__ == "__main__":
    run()
