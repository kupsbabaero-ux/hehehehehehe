import requests
from datetime import datetime

JSON_URL = "http://141.164.53.195/live/korea-live.json"
M3U_URL = "https://raw.githubusercontent.com/kupsbabaero-ux/ZeusChannels/refs/heads/main/Zeus%20Channels%20(ONPROGRESS).m3u"

OUTPUT1 = "korea.m3u8"   # DIYP 影音
OUTPUT2 = "korea2.m3u8"  # 标准 M3U（支持 php）


def is_valid_uri(u):
    """Check if the URI matches valid streaming patterns and excludes blacklisted items."""
    if not isinstance(u, str):
        return False
    u_lower = u.lower()
    has_valid_extension = (
        "channel=" in u_lower or ".m3u8" in u_lower or u_lower.endswith(".php")
    )
    is_not_blacklisted = (
        "wavve" not in u_lower and "file-1253962976.cos" not in u_lower
    )
    return has_valid_extension and is_not_blacklisted


def extract_m3u8_only(uris):
    """仅提取 .m3u8（用于 OUTPUT1）"""
    if isinstance(uris, list):
        items = uris
    elif isinstance(uris, dict):
        items = uris.values()
    elif isinstance(uris, str):
        items = [uris]
    else:
        return None

    for u in items:
        if is_valid_uri(u):
            return u.strip()

    return None


def extract_m3u8_or_php(uris):
    """
    提取 .m3u8 或 .php
    优先 m3u8，其次 php（用于 OUTPUT2）
    """
    if isinstance(uris, list):
        items = uris
    elif isinstance(uris, dict):
        items = uris.values()
    elif isinstance(uris, str):
        items = [uris]
    else:
        return None

    urls = [u.strip() for u in items if is_valid_uri(u)]

    # 优先 m3u8
    for u in urls:
        if ".m3u8" in u.lower():
            return u

    # 其次 php
    if urls:
        return urls[0]

    return None


def run():
    try:
        r = requests.get(JSON_URL, timeout=20)
        r.encoding = "utf-8"
        data = r.json()
    except Exception as e:
        print(f"{datetime.now()} 获取 JSON 失败: {e}")
        return

    lines1 = ["#EXTM3U"]
    lines2 = ["#EXTM3U"]

    count1 = 0
    count2 = 0

    for item in data:
        name = item.get("name", "").strip()
        uris = item.get("uris")

        if not name or not uris:
            continue

        # OUTPUT1：只要 m3u8
        url1 = extract_m3u8_only(uris)
        if url1:
            lines1.append(f"{name},{url1}")
            count1 += 1

        # OUTPUT2：m3u8 或 php
        url2 = extract_m3u8_or_php(uris)
        if url2:
            lines2.append(f"#EXTINF:-1,{name}")
            lines2.append(url2)
            count2 += 1

    with open(OUTPUT1, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines1))

    with open(OUTPUT2, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines2))

    print(f"{datetime.now()} DIYP 频道数量: {count1}")
    print(f"{datetime.now()} 标准 M3U 频道数量: {count2}")
    print(f"{datetime.now()} 已生成文件: {OUTPUT1}, {OUTPUT2}")


if __name__ == "__main__":
    run()
