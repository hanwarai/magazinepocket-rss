"""週刊少年マガジンポケットの無料エピソードを取得するAtom RSSジェネレータ。"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import feedgenerator
import requests
import urllib3
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("magazinepocket-rss")

TITLE_BASE_URL = "https://pocket.shonenmagazine.com/title/"
API_URL = "https://api.pocket.shonenmagazine.com/episode/list"
REQUEST_TIMEOUT = 10
EPISODE_HASH_WINDOW = 10

FEEDS_DIR = Path("feeds")
FEED_LIST_PATH = Path("feed.csv")
TEMPLATE_DIR = Path("templates")


def _parse_bool(value: str) -> bool:
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


SSL_VERIFY = _parse_bool(os.getenv("SSL_VERIFY", "True"))


# API 検証ハッシュ生成(サイト側で難読化された識別子をそのまま使用)
def mc(data: object) -> str:
    return hashlib.sha256(str(data).encode()).hexdigest()


def vh(data: object) -> str:
    return hashlib.sha512(str(data).encode()).hexdigest()


def Od(e: object, t: object) -> str:
    return f"{mc(str(e))}_{vh(str(t))}"


def wh(e: dict[str, Any]) -> str:
    parts = [Od(str(k), str(e[k])) for k in sorted(e.keys())]
    return vh(f"{mc(','.join(parts))}{Od('', '')}")


def Ae(e: dict[str, Any]) -> str:
    return wh(e)


def episode_id_list(values: list[Any]) -> list[Any] | None:
    for value in values:
        if isinstance(value, dict) and "episode_id_list" in value:
            return [values[i] for i in values[value["episode_id_list"]]]
    return None


def create_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.verify = SSL_VERIFY
    return session


def fetch_episode_list(session: requests.Session, episode_ids: list[Any]) -> list[dict[str, Any]]:
    last_ids = ",".join(map(str, episode_ids[-EPISODE_HASH_WINDOW:]))
    payload = {"episode_id_list": last_ids}
    response = session.post(
        API_URL,
        data=payload,
        timeout=REQUEST_TIMEOUT,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Referer": "https://pocket.shonenmagazine.com/",
            "x-manga-hash": Ae(payload),
            "x-manga-is-crawler": "false",
            "x-manga-platform": "3",
        },
    )
    response.raise_for_status()
    episodes = response.json().get("episode_list", [])
    return list(episodes)


def build_feed_for_title(session: requests.Session, feed_id: str) -> dict[str, str] | None:
    url = f"{TITLE_BASE_URL}{feed_id}"
    logger.info("%s %s", feed_id, url)

    response = session.get(url, timeout=REQUEST_TIMEOUT)
    if not response.ok:
        logger.warning("failed to retrieve %s (status=%s)", feed_id, response.status_code)
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    script_tag = soup.find("script", {"id": "__NUXT_DATA__"})
    if not script_tag:
        logger.warning("no NUXT data for %s", feed_id)
        return None

    h1 = soup.find("h1")
    if not h1:
        logger.warning("no h1 for %s", feed_id)
        return None

    title = h1.text.strip()
    logger.info("%s %s", feed_id, title)

    description_div = soup.find("div", class_="p-episode__comic-description")
    comic_img_div = soup.find("div", class_="p-episode__comic-img")
    description = description_div.text.strip() if description_div else ""
    image = comic_img_div.img.get("src") if comic_img_div and comic_img_div.img else None

    rss = feedgenerator.Atom1Feed(
        title=title,
        link=url,
        description=description,
        language="ja",
        image=image,
    )

    nuxt_json = script_tag.string
    if not nuxt_json:
        logger.warning("empty NUXT data for %s", feed_id)
        return None

    try:
        episode_ids = episode_id_list(json.loads(nuxt_json))
        for episode in fetch_episode_list(session, episode_ids or []):
            if episode["point"] != 0:
                continue
            rss.add_item(
                unique_id=episode["episode_id"],
                title=episode["episode_name"],
                link=f"{url}/episode/{episode['episode_id']}",
                description="",
                pubdate=datetime.strptime(episode["start_time"], "%Y-%m-%d %H:%M:%S"),
                content="",
            )
    except Exception:
        logger.exception("failed to fetch episodes for %s", feed_id)

    with (FEEDS_DIR / f"{feed_id}.xml").open("w") as fp:
        rss.write(fp, "utf-8")

    return {"id": feed_id, "title": title}


def read_feed_ids(path: Path) -> Iterator[str]:
    seen: set[str] = set()
    with path.open() as fp:
        for row in csv.reader(fp):
            if not row:
                continue
            feed_id = row[0].strip()
            if not feed_id:
                continue
            # パストラバーサル防止: IDは数字のみ許可
            if not feed_id.isdigit():
                logger.warning("invalid feed ID %r, skipping", feed_id)
                continue
            if feed_id in seen:
                logger.warning("duplicate feed ID %r, skipping", feed_id)
                continue
            seen.add(feed_id)
            yield feed_id


def render_index(feeds: list[dict[str, str]]) -> None:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("index.html")
    (FEEDS_DIR / "index.html").write_text(template.render(feeds=feeds))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not SSL_VERIFY:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    session = create_session()
    rendered: list[dict[str, str]] = []
    for feed_id in read_feed_ids(FEED_LIST_PATH):
        try:
            result = build_feed_for_title(session, feed_id)
        except Exception:
            logger.exception("failed to build feed for %s", feed_id)
            continue
        if result:
            rendered.append(result)
    render_index(rendered)


if __name__ == "__main__":
    main()
