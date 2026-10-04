import gzip
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

JSON_URL = "http://141.164.53.195/live/korea-live.json"
EXTRA_M3U8_URL = (
    "https://github.com/kupsbabaero-ux/hehehehehehe/raw/refs/heads/main/zeus.m3u8"
)
LOCAL_EPG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "pasted-text.txt"
)

# Region EPG sources (iptv-epg.org)
EPG_SOURCES = {
    "KR": "https://iptv-epg.org/files/epg-kr.xml",
    "CA": "https://iptv-epg.org/files/epg-ca.xml",
    "UK": "https://iptv-epg.org/files/epg-gb.xml",  # GB = UK
    "US": "https://iptv-epg.org/files/epg-us.xml",
}

OUTPUT1 = "korea.m3u8"  # DIYP format (#genre# grouping)
OUTPUT2 = "korea2.m3u8"  # Standard M3U format

TARGET_GROUP = "KR | Korea"

# Map group-title → region key
REGION_RULES = [
    (r"^kr\b|korea", "KR"),
    (r"^ca\b|canada", "CA"),
    (r"^uk\b|^gb\b|united\s*kingdom|britain", "UK"),
    (r"^us\b|united\s*states|america", "US"),
]


def detect_region(group):
    """Return region key (KR/CA/UK/US) based on group-title, or None."""
    g = (group or "").strip().lower()
    for pattern, region in REGION_RULES:
        if re.search(pattern, g, flags=re.IGNORECASE):
            return region
    return None


def _strip_region_prefix(name):
    """Remove CA/UK/US/KR/GB style prefixes from display names."""
    return re.sub(
        r"^(kr|ca|uk|gb|us)\s*[-:]?\s*",
        "",
        name,
        flags=re.IGNORECASE,
    ).strip()


def _parse_epg_file(path, epg_map):
    """
    Stream-parse XML file into epg_map (cleaned_name -> tvg-id).
    Handles gzip (.gz) and plain XML. Memory-friendly for huge US EPG.
    """
    with open(path, "rb") as f:
        magic = f.read(2)

    if magic == b"\x1f\x8b":
        opener = lambda: gzip.open(path, "rb")
    else:
        opener = lambda: open(path, "rb")

    added = 0
    with opener() as f:
        for event, elem in ET.iterparse(f, events=("end",)):
            if elem.tag != "channel":
                continue
            channel_id = elem.get("id")
            if channel_id:
                for dn in elem.findall("display-name"):
                    if dn.text:
                        raw = dn.text.strip()
                        clean = _strip_region_prefix(raw).lower()
                        if clean and clean not in epg_map:
                            epg_map[clean] = channel_id
                            added += 1
            elem.clear()
    return added


def _fix_local_xml(path):
    """Ensure local XML has closing </tv> if truncated; return path to use."""
    with open(path, "rb") as f:
        data = f.read()
    text = data.decode("utf-8", errors="replace").strip()
    if "</tv>" in text.lower():
        return path
    if text.rstrip().endswith(">") or text.rstrip().endswith("/>"):
        text = text.rstrip() + "\n</tv>"
    else:
        text = text.rstrip() + "\n  </channel>\n</tv>"
    tmp = path + ".fixed.xml"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    return tmp


def fetch_all_epg_maps():
    """
    Download each region EPG to a temp file, parse with iterparse.
    Returns: { "KR": {name: id}, "CA": {...}, "UK": {...}, "US": {...} }
    """
    maps = {k: {} for k in EPG_SOURCES}

    for region, url in EPG_SOURCES.items():
        tmp_path = None
        try:
            print(f"{datetime.now()} Downloading {region} EPG: {url}")
            r = requests.get(url, timeout=300, allow_redirects=True, stream=True)
            r.raise_for_status()

            # Stream to temp file (avoid holding 500MB+ in RAM)
            fd, tmp_path = tempfile.mkstemp(suffix=f".{region}.xml")
            os.close(fd)
            with open(tmp_path, "wb") as out:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        out.write(chunk)

            n = _parse_epg_file(tmp_path, maps[region])
            print(f"{datetime.now()} {region} EPG loaded: {n} channel names")
        except Exception as e:
            print(f"{datetime.now()} Error loading {region} EPG: {e}")
        finally:
            if tmp_path and os.path.isfile(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # Local KR fallback
    if not maps["KR"] and os.path.isfile(LOCAL_EPG_FILE):
        try:
            print(f"{datetime.now()} Loading local KR EPG fallback: {LOCAL_EPG_FILE}")
            path = _fix_local_xml(LOCAL_EPG_FILE)
            n = _parse_epg_file(path, maps["KR"])
            print(f"{datetime.now()} Local KR EPG loaded: {n} channel names")
            if path != LOCAL_EPG_FILE and os.path.isfile(path):
                os.remove(path)
        except Exception as e:
            print(f"{datetime.now()} Error loading local EPG: {e}")

    total = sum(len(m) for m in maps.values())
    if total == 0:
        print(f"{datetime.now()} WARNING: No EPG mapping loaded.")
    else:
        print(f"{datetime.now()} Total EPG names across regions: {total}")

    return maps


def clean_text(text):
    """Normalize for matching: strip region prefix, quality tags, non-alnum."""
    text = _strip_region_prefix(text)
    text = re.sub(
        r"\b(hd|fhd|uhd|4k|sd|720p|1080p)\b", "", text, flags=re.IGNORECASE
    )
    text = re.sub(r"[^\w]", "", text)
    return text.lower().strip()


def match_tvg_id(channel_name, epg_map):
    """Find real tvg-id from a single region map."""
    if not epg_map:
        return ""
    norm = clean_text(channel_name)
    if not norm:
        return ""

    # 1. Exact
    for epg_name, tvg_id in epg_map.items():
        if clean_text(epg_name) == norm:
            return tvg_id

    # 2. Substring (min 3 chars)
    for epg_name, tvg_id in epg_map.items():
        clean_epg = clean_text(epg_name)
        if clean_epg and (norm in clean_epg or clean_epg in norm):
            if len(norm) >= 3 and len(clean_epg) >= 3:
                return tvg_id

    return ""


def match_tvg_id_for_group(channel_name, group, all_maps):
    """Pick the right region map from group-title, then match."""
    region = detect_region(group)
    if not region:
        return ""
    return match_tvg_id(channel_name, all_maps.get(region, {}))


def format_channel_name(name, group):
    """Add region prefix for known regions (KR: / CA: / UK: / US:)."""
    name = name.strip()
    clean_name = re.sub(
        r"^(KR|CA|UK|GB|US):\s*", "", name, flags=re.IGNORECASE
    ).strip()

    region = detect_region(group)
    if region == "KR":
        return f"KR: {clean_name}"
    if region == "CA":
        return f"CA: {clean_name}"
    if region == "UK":
        return f"UK: {clean_name}"
    if region == "US":
        return f"US: {clean_name}"
    return name


def extract_m3u8_or_php(uris):
    """Extract valid playback URL."""
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


def parse_external_m3u8(url, all_maps):
    """Parse GitHub M3U8; apply tvg-id for KR/CA/UK/US groups only."""
    channels = []
    try:
        r = requests.get(url, timeout=30)
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
                group = group_match.group(1) if group_match else TARGET_GROUP

                raw_name = (
                    current_extinf.split(",")[-1].strip()
                    if "," in current_extinf
                    else "Unknown Channel"
                )

                formatted_name = format_channel_name(raw_name, group)
                matched_tvg_id = match_tvg_id_for_group(
                    raw_name, group, all_maps
                )

                region = detect_region(group) or "-"
                print(
                    f"[Match] [{region}] '{raw_name}' --> tvg-id: '{matched_tvg_id}'"
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

    # 0. Load all region EPGs (stream to disk, low memory)
    all_maps = fetch_all_epg_maps()

    # 1. JSON Korea channels (always KR | Korea)
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
                matched_tvg_id = match_tvg_id_for_group(
                    raw_name, group, all_maps
                )

                print(f"[Match] [KR] '{raw_name}' --> tvg-id: '{matched_tvg_id}'")

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

    # 2. GitHub M3U8 (KR/CA/UK/US groups get real tvg-id)
    github_channels = parse_external_m3u8(EXTRA_M3U8_URL, all_maps)
    raw_channels.extend(github_channels)

    if not raw_channels:
        print("Walang nakuhang channels.")
        return

    # 3. Dedup only within KR | Korea
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

    # 4. Sort
    all_channels.sort(key=lambda x: (x["group"].lower(), x["name"].lower()))

    # 5. DIYP output
    lines1 = []
    current_diyp_group = None
    for ch in all_channels:
        if ch["group"] != current_diyp_group:
            current_diyp_group = ch["group"]
            lines1.append(f"{current_diyp_group},#genre#")
        lines1.append(f"{ch['name']},{ch['url']}")

    # 6. Standard M3U — all region EPGs in url-tvg
    url_tvg = " ".join(EPG_SOURCES.values())
    lines2 = [f'#EXTM3U url-tvg="{url_tvg}"']
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

    with_id = sum(1 for c in all_channels if c["tvg_id"])
    by_region = {}
    for c in all_channels:
        reg = detect_region(c["group"]) or "OTHER"
        by_region[reg] = by_region.get(reg, 0) + 1

    print(f"\n{datetime.now()} Total Channels: {len(all_channels)}")
    print(f"{datetime.now()} With real tvg-id: {with_id}")
    print(f"{datetime.now()} By region: {by_region}")
    print(f"{datetime.now()} Files: {OUTPUT1}, {OUTPUT2}")


if __name__ == "__main__":
    run()
