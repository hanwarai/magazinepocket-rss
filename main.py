import csv
import hashlib
import json
import os

import feedgenerator
import requests
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader
from datetime import datetime

SSL_VERIFY = os.getenv('SSL_VERIFY', 'True') == 'True'
api_url = "https://api.pocket.shonenmagazine.com/episode/list"


def episode_id_list(values):
    for value in values:
        if isinstance(value, dict):
            if 'episode_id_list' in value:
                episode_ids = []
                for episode_idx in values[value['episode_id_list']]:
                    episode_ids.append(values[episode_idx])
                return episode_ids
    return None


def mc(data):
    return hashlib.sha256(str(data).encode()).hexdigest()


def vh(data):
    return hashlib.sha512(str(data).encode()).hexdigest()


def Od(e, t):
    return f"{mc(str(e))}_{vh(str(t))}"


def wh(e):
    t = list(e.keys())
    t.sort()
    r = []
    for i in t:
        r.append(Od(str(i), str(e[i])))
    n = mc(",".join(r))
    a = Od("", "")
    return vh(f"{n}{a}")


def Ae(e):
    return wh(e)


rendered_feeds = []
with open('feed.csv') as feed_file:
    for feed in csv.reader(feed_file):
        feed_id = feed[0].strip()

        # パストラバーサル防止: IDは数字のみ許可
        if not feed_id.isdigit():
            print(f"Invalid feed ID: {feed_id!r}, skipping")
            continue

        comics_url = "https://pocket.shonenmagazine.com/title/" + feed_id
        print(feed_id, comics_url)

        comics = requests.get(comics_url, verify=SSL_VERIFY, timeout=10)
        if not comics.ok:
            print(f"{comics.status_code} for {feed_id}, retrying...")
            comics = requests.get(comics_url, verify=SSL_VERIFY, timeout=10)

        if not comics.ok:
            print(f"Failed to retrieve comics for {feed_id}")
            continue

        soup = BeautifulSoup(comics.text, 'html.parser')

        script_tag = soup.find("script", {"id": "__NUXT_DATA__"})
        if not script_tag:
            print(f"No NUXT data for {feed_id}")
            continue

        h1 = soup.find('h1')
        if not h1:
            print(f"No h1 for {feed_id}")
            continue
        comic_title = h1.text.strip()
        print(feed_id, comic_title)
        rendered_feeds.append({'id': feed_id, 'title': comic_title})

        description_div = soup.find('div', class_='p-episode__comic-description')
        comic_img_div = soup.find('div', class_='p-episode__comic-img')
        description = description_div.text.strip() if description_div else ""
        image = comic_img_div.img.get('src') if comic_img_div and comic_img_div.img else None

        rss = feedgenerator.Atom1Feed(
            title=comic_title,
            link=comics_url,
            description=description,
            language="ja",
            image=image
        )

        json_text = script_tag.string
        episode_ids = episode_id_list(json.loads(json_text))
        last_episode_ids = ','.join(map(str, episode_ids[-10:]))

        data = {'episode_id_list': last_episode_ids}
        manga_hash = Ae(data)

        episode_response = requests.post(api_url, data, verify=SSL_VERIFY, timeout=10, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'Referer': 'https://pocket.shonenmagazine.com/',
            'x-manga-hash': manga_hash,
            'x-manga-is-crawler': 'false',
            'x-manga-platform': '3',
        })
        episode_json = episode_response.json()

        for episode in episode_json['episode_list']:
            if episode['point'] != 0:
                continue

            rss.add_item(
                unique_id=episode['episode_id'],
                title=episode['episode_name'],
                link=comics_url + "/episode/" + str(episode['episode_id']),
                description="",
                pubdate=datetime.strptime(episode['start_time'], '%Y-%m-%d %H:%M:%S'),
                content=""
            )

        with open('feeds/' + feed_id + '.xml', 'w') as fp:
            rss.write(fp, 'utf-8')

# Generate index.html
jinja_env = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=True
)
jinja_template = jinja_env.get_template('index.html')
with open('feeds/index.html', 'w') as index:
    index.write(jinja_template.render(feeds=rendered_feeds))
