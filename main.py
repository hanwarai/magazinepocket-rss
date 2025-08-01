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
feed_file = open('feed.csv')
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
    """データをSHA256ハッシュ化"""
    return hashlib.sha256(str(data).encode()).hexdigest()


def vh(data):
    """データをSHA512ハッシュ化（JavaScriptのUP/fcに対応）"""
    return hashlib.sha512(str(data).encode()).hexdigest()


def Od(e, t):
    """キーと値をハッシュ化して結合"""
    return f"{mc(str(e))}_{vh(str(t))}"


def wh(e):
    """辞書からハッシュ値を生成"""
    t = list(e.keys())
    t.sort()
    r = []
    for i in t:
        r.append(Od(str(i), str(e[i])))
    print('r:',r, ",".join(r))
    n = mc(",".join(r))
    a = Od("", "")
    return vh(f"{n}{a}")


def Ae(e):
    return wh(e)


rendered_feeds = []
for feed in csv.reader(feed_file):
    comics_url = "https://pocket.shonenmagazine.com/title/" + feed[0]
    print(comics_url)

    comics = requests.get(comics_url, verify=SSL_VERIFY, timeout=10)
    if not comics.ok:
        print(f"{comics.status_code} for {feed[0]}")
        comics = requests.get(comics_url, verify=SSL_VERIFY, timeout=10)

    if not comics.ok:
        print(f"Failed to retrieve comics for {feed[0]}")
        continue

    soup = BeautifulSoup(comics.text, 'html.parser')

    script_tag = soup.find("script", {"id": "__NUXT_DATA__"})
    if not script_tag:
        continue

    comic_title = soup.find('h1').text.strip()
    print(feed[0], comic_title)
    rendered_feeds.append({'id': feed[0], 'title': comic_title})

    rss = feedgenerator.Atom1Feed(
        title=comic_title,
        link=comics_url,
        description=soup.find('div', class_='p-episode__comic-description').text.strip(),
        language="ja",
        image=soup.find('div', class_='p-episode__comic-img').img.get('src')
    )

    json_text = script_tag.string
    episode_ids = episode_id_list(json.loads(json_text))
    last_episode_ids = ','.join(map(str, episode_ids[-10:]))

    # 動的ハッシュ生成
    data = {'platform': 3, 'episode_id_list': last_episode_ids}
    print(data)
    manga_hash = Ae(data)

    episode_response = requests.post(api_url, data, verify=SSL_VERIFY, timeout=10, headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'Referer': 'https://pocket.shonenmagazine.com/',
        'x-manga-hash': manga_hash,
        'x-manga-is-crawler': 'false',
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

    with open('feeds/' + feed[0] + '.xml', 'w') as fp:
        rss.write(fp, 'utf-8')

# Generate index.html
jinja_env = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=True
)
jinja_template = jinja_env.get_template('index.html')
index = open('feeds/index.html', 'w')
index.write(jinja_template.render(feeds=rendered_feeds))

# 989b9f8804befc06db540f79ceeda481e7f75fe388bab52957783a6eeb32917351280418f8e5eaa292bba2b95bb7f6cbdfad54445211f5086f70eda09fb4eb6b
print(Ae({'platform': '3', 'episode_id_list': '321182,321431,321650,322158,322355,322723,323774,323988,324401,324402,324610,324611,324739,324740,325223,326291,326705,327212,327421,328467,328664,329608,329749,330013,330014,330194,330796,331010,331240,331397,332360,332790,332791,333501,333502,333976,334640,334822,336756,336757,337216,337723,338503,339048,340395,341117,341774,342479,344765,346023'}))

# e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855_cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e
print(Od("", ""))

print(mc(str([
    'fdc8b38644a75e70806d48cbf112f490c0d3e585f8c2b6af1de9cbca426617cd_1c1b30ae727283f1f70fc9691ab46b1f2e0befac5936980d2f29561e4989d9563e81055fb1f09fb5a8b064d38a276d78634145925cf77916fd4589e2933bfad8',
    'd294fcce0cc88587843099d85dd805aeef1b09a63b0db1dd3e4dc62a343c1db5_3bafbf08882a2d10133093a1b8433f50563b93c14acd05b79028eb1d12799027241450980651994501423a66c276ae26c43b739bc65c4e16b10c3af6c202aebb'])))
