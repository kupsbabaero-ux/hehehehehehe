import requests
import re
from datetime import datetime

JSON_URL = "http://141.164.53.195/live/korea-live.json"
EXTRA_M3U8_URL = "https://github.com/kupsbabaero-ux/hehehehehehe/raw/refs/heads/main/zeus.m3u8"
EPG_URL = "https://epg.pw/xmltv/epg-kr.xml"  # Automatic EPG URL

OUTPUT1 = "korea.m3u8"    # DIYP format with #genre# grouping
OUTPUT2 = "korea2.m3u8"   # Standard M3U with group-title="KR | Korea"


def extract_m3u8_or_php(uris):
    """Extract valid playback URL"""
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

    for u in urls:
        if ".m3u8" in u.lower():
            return u
    if urls:
        return urls[0]
    return None


def parse_external_m3u8(url):
    """Fetch and parse extra M3U8 channels from GitHub"""
    channels = []
    try:
        r = requests.get(url, timeout=20)
        r.encoding = "utf-8"
        lines = r.text.splitlines()
        
        current_extinf = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#EXTINF:"):
                current_extinf = line
            elif not line.startswith("#") and current_extinf:
                tvg_id = re.search(r'tvg-id="([^"]*)"', current_extinf)
                tvg_logo = re.search(r'tvg-logo="([^"]*)"', current_extinf)
                group_title = re.search(r'group-title="([^"]*)"', current_extinf)
                
                name = current_extinf.split(",")[-1].strip() if "," in current_extinf else "Unknown Channel"
                
                channels.append({
                    "name": name,
                    "url": line,
                    "logo": tvg_logo.group(1) if tvg_logo else "",
                    "tvg_id": tvg_id.group(1) if tvg_id else name,
                    "group": group_title.group(1) if group_title else "Others"
                })
                current_extinf = None
    except Exception as e:
        print(f"{datetime.now()} Error fetching external M3U8: {e}")
    return channels


def run():
    all_channels = []

    # 1. Fetch JSON channels and force group to 'KR | Korea'
    try:
        r = requests.get(JSON_URL, timeout=20)
        r.encoding = "utf-8"
        json_data = r.json()
        
        for item in json_data:
            name = item.get("name", "").strip()
            uris = item.get("uris")
            logo = item.get("logo", "") or item.get("tvg-logo", "") or item.get("icon", "")
            tvg_id = item.get("tvg-id", "") or name
            
            if not name or not uris:
                continue
            
            play_url = extract_m3u8_or_php(uris)
            if play_url:
                all_channels.append({
                    "name": name,
                    "url": play_url,
                    "logo": logo.strip() if logo else "",
                    "tvg_id": tvg_id,
                    "group": "KR | Korea"  # Hardcoded group para sa lahat ng JSON items
                })
    except Exception as e:
        print(f"{datetime.now()} Error fetching JSON: {e}")

    # 2. Fetch GitHub channels
    github_channels = parse_external_m3u8(EXTRA_M3U8_URL)
    all_channels.extend(github_channels)

    if not all_channels:
        print("Walang nakuhang channels.")
        return

    # 3. Sort channels: Group (A-Z) -> Channel Name (A-Z)
    all_channels.sort(key=lambda x: (x["group"].lower(), x["name"].lower()))

    # 4. Generate DIYP Format (OUTPUT1)
    lines1 = []
    current_diyp_group = None
    for ch in all_channels:
        if ch["group"] != current_diyp_group:
            current_diyp_group = ch["group"]
            lines1.append(f"{current_diyp_group},#genre#")
        lines1.append(f"{ch['name']},{ch['url']}")

    # 5. Generate Standard M3U Format (OUTPUT2)
    lines2 = [f'#EXTM3U url-tvg="{EPG_URL}"']
    for ch in all_channels:
        logo_attr = f' tvg-logo="{ch["logo"]}"' if ch["logo"] else ''
        lines2.append(f'#EXTINF:-1 tvg-id="{ch["tvg_id"]}" tvg-name="{ch["name"]}"{logo_attr} group-title="{ch["group"]}",{ch["name"]}')
        lines2.append(ch["url"])

    with open(OUTPUT1, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines1))

    with open(OUTPUT2, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines2))

    print(f"{datetime.now()} Total Channels: {len(all_channels)}")
    print(f"{datetime.now()} Files Generated: {OUTPUT1}, {OUTPUT2}")


if __name__ == "__main__":
    run()
