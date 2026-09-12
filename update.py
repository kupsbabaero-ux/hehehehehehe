import gzip
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

JSON_URL = "http://141.164.53.195/live/korea-live.json"
EXTRA_M3U8_URL = (
    "https://github.com/kupsbabaero-ux/hehehehehehe/raw/refs/heads/main/zeus.m3u8"
)
EPG_URL = "https://epg.pw/xmltv/epg.xml"

OUTPUT1 = "korea.m3u8"  # DIYP format (#genre# grouping)
OUTPUT2 = "korea2.m3u8"  # Standard M3U format

TARGET_GROUP = "KR | Korea"
PRIORITY_GROUP = "PH | Entertainment"


def fetch_epg_mapping(epg_url):
    """Downloads GZipped EPG XML and creates a mapping of cleaned channel name -> tvg-id."""
    epg_map = {}
    try:
        print(f"{datetime.now()} Downloading and parsing GZipped EPG XML...")
        r = requests.get(epg_url, timeout=30)

        decompressed_data = gzip.decompress(r.content)
        root = ET.fromstring(decompressed_data)

        for channel in root.findall("channel"):
            channel_id = channel.get("id")
            if not channel_id:
                continue

            for display_name in channel.findall("display-name"):
                if display_name.text:
                    raw_name = display_name.text.strip().lower()
                    clean_name = re.sub(
                        r"^kr:\s*", "", raw_name, flags=re.IGNORECASE
                    ).strip()

                    if clean_name and clean_name not in epg_map:
                        epg_map[clean_name] = channel_id

        print(
            f"{datetime.now()} EPG Loaded. Found {len(epg_map)} mapped channel names."
        )
    except Exception as e:
        print(f"{datetime.now()} Error loading EPG: {e}")

    return epg_map


def clean_text(text):
    """Inaalis ang prefix, resolution tags, at special characters para sa mas matinding matching."""
    text = re.sub(r"^kr:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b(hd|fhd|uhd|4k|sd|720p|1080p)\b", "", text, flags=re.IGNORECASE
    )
    text = re.sub(r"[^\w]", "", text)
    return text.lower().strip()


def match_tvg_id(channel_name, epg_map):
    """Maghahanap ng matching XMLtv channel ID sa EPG map."""
    norm_name = clean_text(channel_name)
    if not norm_name:
        return ""

    # 1. Exact cleaned match
    for epg_name, tvg_id in epg_map.items():
        if clean_text(epg_name) == norm_name:
            return tvg_id

    # 2. Substring match (basta 3 o higit pang characters)
    for epg_name, tvg_id in epg_map.items():
        clean_epg = clean_text(epg_name)
        if clean_epg and (norm_name in clean_epg or clean_epg in norm_name):
            if len(norm_name) >= 3 and len(clean_epg) >= 3:
                return tvg_id

    return ""


def format_channel_name(name, group):
    """Maglalagay LAMANG ng 'KR: ' prefix kung ang group ay 'KR | Korea'."""
    name = name.strip()
    clean_name = re.sub(r"^KR:\s*", "", name, flags=re.IGNORECASE).strip()

    if group.strip().lower() == TARGET_GROUP.lower():
        return f"KR: {clean_name}"

    return name


def extract_m3u8_or_php(uris):
    """Extract valid playback URL"""
    urls = []

    def is_valid(u):
        return (
            isinstance(u, str)
            and (
                "channel=" in u.lower()
                or ".m3u8" in u.lower()
                or u.lower().endswith(".php")
            )
            and "wavve" not in u.lower()
            and "file-1253962976.cos" not in u.lower()
        )

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


def parse_external_m3u8(url, epg_map):
    """Fetch at i-parse ang extra M3U8 channels mula sa GitHub"""
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
                tvg_logo = re.search(r'tvg-logo="([^"]*)"', current_extinf)
                group_match = re.search(
                    r'group-title="([^"]*)"', current_extinf
                )

                group = (
                    group_match.group(1) if group_match else TARGET_GROUP
                )

                raw_name = (
                    current_extinf.split(",")[-1].strip()
                    if "," in current_extinf
                    else "Unknown Channel"
                )

                formatted_name = format_channel_name(raw_name, group)
                matched_tvg_id = match_tvg_id(raw_name, epg_map)

                print(
                    f"[Match Check] '{raw_name}' --> tvg-id: '{matched_tvg_id}'"
                )

                channels.append(
                    {
                        "name": formatted_name,
                        "url": line,
                        "logo": tvg_logo.group(1) if tvg_logo else "",
                        "tvg_id": matched_tvg_id,
                        "group": group,
                    }
                )
                current_extinf = None
    except Exception as e:
        print(f"{datetime.now()} Error fetching external M3U8: {e}")
    return channels


def run():
    raw_channels = []

    # 0. Load EPG Mapping
    epg_map = fetch_epg_mapping(EPG_URL)

    # 1. Fetch JSON channels
    try:
        r = requests.get(JSON_URL, timeout=20)
        r.encoding = "utf-8"
        json_data = r.json()

        for item in json_data:
            raw_name = item.get("name", "").strip()
            uris = item.get("uris")
            logo = (
                item.get("logo", "")
                or item.get("tvg-logo", "")
                or item.get("icon", "")
            )

            if not raw_name or not uris:
                continue

            play_url = extract_m3u8_or_php(uris)
            if play_url:
                group = TARGET_GROUP
                formatted_name = format_channel_name(raw_name, group)
                matched_tvg_id = match_tvg_id(raw_name, epg_map)

                print(
                    f"[Match Check] '{raw_name}' --> tvg-id: '{matched_tvg_id}'"
                )

                raw_channels.append(
                    {
                        "name": formatted_name,
                        "url": play_url,
                        "logo": logo.strip() if logo else "",
                        "tvg_id": matched_tvg_id,
                        "group": group,
                    }
                )
    except Exception as e:
        print(f"{datetime.now()} Error fetching JSON: {e}")

    # 2. Fetch GitHub channels
    github_channels = parse_external_m3u8(EXTRA_M3U8_URL, epg_map)
    raw_channels.extend(github_channels)

    if not raw_channels:
        print("Walang nakuhang channels.")
        return

    # 3. Deduplication Logic
    all_channels = []
    seen_kr_keys = set()

    for ch in raw_channels:
        if ch["group"].strip().lower() == TARGET_GROUP.lower():
            unique_key = (clean_text(ch["name"]), ch["url"].strip())

            if unique_key in seen_kr_keys:
                print(
                    f"[Duplicate Skipped in {TARGET_GROUP}] {ch['name']} -> {ch['url']}"
                )
                continue

            seen_kr_keys.add(unique_key)

        all_channels.append(ch)

    # 4. Custom Sorting (Inuuna ang 'PH | Entertainment')
    def custom_sort_key(x):
        is_priority = 0 if x["group"].strip().lower() == PRIORITY_GROUP.lower() else 1
        return (is_priority, x["group"].lower(), x["name"].lower())

    all_channels.sort(key=custom_sort_key)

    # 5. DIYP Format Generation (OUTPUT1)
    lines1 = []
    current_diyp_group = None
    for ch in all_channels:
        if ch["group"] != current_diyp_group:
            current_diyp_group = ch["group"]
            lines1.append(f"{current_diyp_group},#genre#")
        lines1.append(f"{ch['name']},{ch['url']}")

    # 6. Standard M3U Format Generation (OUTPUT2)
    lines2 = [f'#EXTM3U url-tvg="{EPG_URL}"']
    for ch in all_channels:
        logo_attr = f' tvg-logo="{ch["logo"]}"' if ch["logo"] else ""
        tvg_id_attr = (
            f' tvg-id="{ch["tvg_id"]}"' if ch["tvg_id"] else ' tvg-id=""'
        )

        lines2.append(
            f'#EXTINF:-1{tvg_id_attr} tvg-name="{ch["name"]}"{logo_attr}'
            f' group-title="{ch["group"]}",{ch["name"]}'
        )
        lines2.append(ch["url"])

    with open(OUTPUT1, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines1))

    with open(OUTPUT2, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines2))

    print(f"\n{datetime.now()} Total Channels Processed: {len(all_channels)}")
    print(f"{datetime.now()} Files Generated: {OUTPUT1}, {OUTPUT2}")


if __name__ == "__main__":
    run()
