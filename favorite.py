#!/usr/env/bin python
# -*- encoding:utf-8 -*-

import json
import time
import sqlite3
from operator import itemgetter
from collections import OrderedDict

from  pytumblr import TumblrRestClient
from encoding_ja import pp

import logging
from logging import getLogger, FileHandler, Formatter, DEBUG

#: ログを記録する
#: ログのフォーマットを指定する
log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOGFILE_NAME = 'tmp/log.txt'

logger = getLogger(__name__)
formatter = Formatter(log_fmt)
handler = FileHandler(LOGFILE_NAME)

logger.setLevel(DEBUG)
handler.setLevel(DEBUG)

handler.setFormatter(formatter)
logger.addHandler(handler)

class FavaritePost(object):
    #: Tumblr API Clientを生成する
    def setup(self):
        with open('credentials_dummy.json') as f:
            credentials= json.loads(f.read())
        self.client = TumblrRestClient(credentials['consumer_key'], credentials['consumer_secret'], credentials['oauth_token'], credentials['oauth_token_secret'])

    #: ポストのタグを取得する
    #: リスト型のposts_likedを引数にとる
    def get_tags_reblogkey(self, posts_liked):
        #: ポストのタグとidを格納する
        id_tags_dict = {}

        for post in posts_liked:
            tags = []
            for tag in post["tags"]:
                tags.append(tag)

            id = post["id"]
            reblog_key = post["reblog_key"]

            rbkey_tags = (reblog_key, tags)
            id_tags_dict[id] = rbkey_tags

        return id_tags_dict

    #: ライクしているポストを取得する
    def get_likes(self):
        posts_liked = self.client.likes(limit=50)

        return posts_liked

    #: ライクしているポストの数を取得する
    def get_loops_of_like(self):
        num_of_likes = self.client.info()['user']['likes']
        loop_likes = (num_of_likes / 20) + 1

        return loop_likes

    #: ライクしているポストからtagとreblog_keyを抽出する
    def extract_tags(self):
        reblogkey_tags = []
        #: ライクしているポストを取得する
        post_like = self.get_likes()
        #: ポストからタグとreblog_keyを抽出する
        reblogkey_tags = self.get_tags_reblogkey(post_like['liked_posts'])

        return reblogkey_tags

def sort_tags(tags):
    #: タグをキーにソートしたidとタグリストを格納する
    tags = OrderedDict(sorted(tags.items(), key=lambda x:x[1][1]))

    return tags

#: アスキーコードを判定する
def is_ascii(string):
    if string:
        return max([ord(char) for char in string]) < 128

#: 日本語のタグのみを抽出する
#: 日本語タグだけをディクショナリのvalueに設定する
def extract_ja_tags(tags):
    tags_ja = {}
    #: reblog_keyとtagリストのタプルから要素を取り出す
    for k, vs in tags.items():
        for v in vs[1][:]:
            if is_ascii(v):
                tags[k][1].remove(v)
    return tags

def create_db():
    query = "CREATE TABLE IF NOT EXISTS posts (id int, reblogkey text, tags text)"
    conn = sqlite3.connect('post.db')
    cur = conn.cursor()
    cur.execute(query)
    conn.commit()

def clear_db():
    query = "DROP TABLE IF EXISTS posts"
    conn = sqlite3.connect('post.db')
    cur = conn.cursor()
    cur.execute(query)
    conn.commit()

def init_db():
    clear_db()
    create_db()

def insert_post(id, reblog_key, tags):
    conn = sqlite3.connect('post.db')
    cur = conn.cursor()
    cur.execute("INSERT INTO posts VALUES (?, ?, ?)", (id, reblog_key, tags))
    conn.commit()
    conn.close()

def select_post():
    query = "SELECT * FROM posts ORDER BY tags ASC"
    conn = sqlite3.connect('post.db')
    cur = conn.cursor()
    cur.execute(query)

    return cur.fetchall()

def main():
    #: Tumblr API Clientを生成する
    fav = FavaritePost()
    fav.setup()

    #: likeを呼び出す回数を取得する
    #: loop_of_likes = fav.get_loops_of_like()
    loop_of_likes = 2

    #: データベースを初期化する
    init_db()
    logger.debug("Start sorting posts!")

    #: ポストを取得し、データベースに登録後にunlikeする
    for i in range(loop_of_likes):
        reblogkey_tags = fav.extract_tags()

        #: 日本語名のタグだけを抽出する
        reblogkey_tags = extract_ja_tags(reblogkey_tags)
        #: ライクしているポストからアンライクするものをループさせる
        for k, v in reblogkey_tags.items():
            #: ポストをデータベースに格納する
            id = k
            reblog_key = v[0]
            tags  = v[1]
            tags = ' '.join(tags)
            #: データベースに登録
            insert_post(id, reblog_key, tags)
            #: ポストをアンライクする
            fav.client.unlike(id, reblog_key)

    #: タグでソートされたポストのリストを取得する
    tags_sorted = select_post()
    #: 保存していたポストをライクする
    for post in tags_sorted:
        id = post[0]
        reblogkey = post[1]
        logger.debug(pp(post))
        fav.client.like(id, reblogkey)
        time.sleep(0.1)

    logger.debug("Like completed!*")

if __name__ == '__main__':
    main()
