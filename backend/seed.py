# -*- coding: utf-8 -*-
"""灌入本地联调用的种子数据：14 条小红书式笔记 + 7 个用户 + 评论。

    python seed.py          # 重建 data/app.db
    python seed.py --keep   # 已有数据就不动

笔记风格刻意贴近用户给的例子：
  「去掉滤镜不摆拍‼️115斤梨形小个子春装试穿 衬衫那套…」
两种类型混排：outfit（穿搭推荐）/ help（个人求助，详情显示「求建议」）。
图片用 preview/assets 下的占位图，宽高从文件实际读取，保证瀑布流比例真实。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

from PIL import Image

from app.core.db import connect, db_path, init_db

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "preview", "assets")
TZ = timezone(timedelta(hours=8))

USERS = [
    ("u_1", "阿岚的衣橱", "avatar_01.png", "每天一套通勤穿搭，衣柜只有 30 件"),
    ("u_2", "MOMO酱", "avatar_02.png", "158 / 小个子显高研究员"),
    ("u_3", "老周的穿搭日记", "avatar_03.png", "男生基础款叠穿，少买但买对"),
    ("u_4", "十一在路上", "avatar_04.png", "一个登机箱走 4 天"),
    ("u_5", "甜盐 Nana", "avatar_05.png", "约会穿搭 / 甜酷之间来回横跳"),
    ("u_6", "小满", "avatar_06.png", "街头、皮衣、球鞋"),
    ("u_me", "我", "avatar_07.png", "这学期开始整理自己的衣橱"),
]

# (id, user_id, type, title, body, tags, image_no, hours_ago, like_count)
POSTS = [
    ("post_1", "u_1", "outfit",
     "去掉滤镜不摆拍‼️115斤梨形小个子春装试穿 衬衫那套真的显瘦",
     "先说身材：158cm / 115斤，胯宽大腿粗，典型梨形。全部自然光手机直出，没滤镜没摆拍，站着拍完就发。\n\n"
     "第一套衬衫是我今年最满意的一件：落肩但不塌，下摆塞一半，腰线立刻出来；配奶白阔腿裤，胯和大腿全藏住。\n\n"
     "第二套针织开衫+半裙，裙长卡在小腿最细的地方，配短靴视觉腿长直接+8cm。\n\n"
     "梨形姐妹真的别硬穿紧身裤，把「松但不垮」这四个字记住就够了。",
     ["梨形穿搭", "春装试穿", "不摆拍"], 1, 3, 128),

    ("post_2", "u_5", "help",
     "求助😭 158/105斤梨形胯宽，通勤到底怎么穿不显胯？",
     "下周开始实习，公司要求不能太休闲。我胯宽+大腿粗，穿西裤像偷穿妈妈的裤子，穿裙子又怕坐电梯尴尬。\n\n"
     "预算有限，最好能和我衣柜里已有的白衬衫、卡其风衣搭。姐妹们有无具体版型/长度推荐？球鞋能穿吗？\n\n"
     "真的求建议，不是钓鱼！评论区我把试穿图补上。",
     ["求助", "梨形穿搭", "通勤"], 2, 8, 342),

    ("post_3", "u_3", "outfit",
     "男生秋冬叠穿公式｜三层就够，别再往上堆第四层了",
     "衬衫 + 圆领针织 + 长大衣，这是我今年重复率最高的一套。\n\n"
     "关键是每层长度要错开：衬衫下摆露出 3cm，针织袖口露出 1cm，大衣不要扣。\n\n"
     "颜色控制在三个以内：藏青、米白、炭灰。预算不高也能穿得干净。",
     ["男生穿搭", "叠穿", "通勤"], 3, 20, 96),

    ("post_4", "u_4", "outfit",
     "大理4天3套｜一个20寸箱子真的够了，不摆拍实拍",
     "行程：古城拍照 + 洱海骑行 + 苍山徒步。我没有带很多衣服，就是薄针织、长裙、一件防风外套来回换。\n\n"
     "早晚温差大，靠叠穿解决；鞋子只带一双好走路的乐福鞋。\n\n"
     "旅行穿搭最重要的是别为了拍照穿难受的衣服，走两公里就知道差别了。",
     ["旅行穿搭", "大理", "行李"], 4, 2, 76),

    ("post_5", "u_6", "outfit",
     "不摆拍实测｜皮衣配白T，重点全在鞋上",
     "皮衣买回来闲置了半年，这次终于找到舒服的穿法：里面只穿一件宽松白T，不扣扣子。\n\n"
     "下半身直筒牛仔裤，鞋子换成厚底球鞋，整体就不会太攻击者。\n\n"
     "身高 163，梨形，这套亲测显高。",
     ["街头", "皮衣", "梨形穿搭"], 5, 30, 210),

    ("post_6", "u_1", "outfit",
     "极简灰白公式：三个颜色过一整周，打工人早八友好",
     "灰、白、燕麦，三色闭环，闭着眼拿都不会出错。\n\n"
     "我的方法是：周末把下周 5 套搭好拍照存在备忘录，早上直接照着穿，省掉的决策时间够多睡十分钟。",
     ["极简", "通勤", "胶囊衣橱"], 6, 52, 405),

    ("post_7", "u_2", "outfit",
     "160小个子｜高腰线这样找，视觉腿长+8cm（无滤镜对比）",
     "上衣塞一半比全塞更自然；腰带和裙腰同色，视觉上是一条连续的线。\n\n"
     "外套长度要么到腰、要么到大腿中，最忌卡在胯最宽的位置。\n\n"
     "图二是我穿错的长度，对比一下就知道差别有多大。",
     ["小个子", "显高", "不摆拍"], 7, 5, 88),

    ("post_8", "u_3", "outfit",
     "降温了！羽绒服也能穿得不臃肿的3个穿法",
     "短款羽绒服 + 直筒裤，把腰线露出来；内搭尽量薄但保暖，羊毛衫比卫衣利落。\n\n"
     "长款羽绒服敞开穿，里面用同色系，视觉上是一条竖线。\n\n"
     "不建议上下都宽松，会整个人变成一个球。",
     ["冬季穿搭", "羽绒服", "男生穿搭"], 8, 15, 63),

    ("post_9", "u_5", "help",
     "求建议！第一次约会穿针织开衫+缎面裙会不会太用力？",
     "晚上七点吃饭，商场里灯光比较暗。我打算穿米色开衫+香槟色缎面裙，但怕显得太正式。\n\n"
     "开衫是扣满还是留两颗？鞋子穿芭蕾鞋还是短靴？在线等，挺急的😭",
     ["求助", "约会穿搭", "搭配建议"], 9, 40, 268),

    ("post_10", "u_6", "outfit",
     "球鞋配西装，通勤也能松弛｜梨形亲测不显腿粗",
     "把西裤换成直筒牛仔，正式感降一半，舒服度翻倍。\n\n"
     "西装选微oversize，肩线刚好落在肩膀外侧一点；球鞋干净就行，不用非得新。\n\n"
     "这套我穿着挤了一小时地铁，没勒也没皱。",
     ["通勤", "西装", "球鞋"], 10, 70, 152),

    ("post_11", "u_4", "outfit",
     "换季衣橱断舍离｜最后只留了这12件，附我的筛选标准",
     "标准很简单：一年没穿就出局；穿上要在镜子前停留超过 3 秒还觉得舒服。\n\n"
     "最后留下 12 件，通勤、约会、旅行都能互相搭。数量少了以后，早上反而更快。\n\n"
     "不是极简主义，是真的懒得选了。",
     ["胶囊衣橱", "整理", "极简"], 11, 96, 520),

    ("post_12", "u_2", "outfit",
     "秋日野餐｜卡其色系一套，包和鞋同色照片真的更统一",
     "卡其风衣 + 白T + 棕色半裙，包和鞋都选深棕，整体就收住了。\n\n"
     "野餐坐草地，所以裙子选了不容易皱的面料，垫子颜色也跟着衣服选。\n\n"
     "到底是穿搭还是摆拍？反正我坐下去第一件事是先吃东西。",
     ["秋装", "卡其色", "野餐"], 12, 26, 118),

    ("post_13", "u_5", "help",
     "应届生面试穿什么？预算300，梨形求一套不踩雷的搭配",
     "下周校招面试，岗位偏互联网运营，不用正装但要得体。身高 160 / 112斤，胯宽。\n\n"
     "预算 300 以内（学生党），最好能买到大衣+内搭+鞋。有没有姐妹能提供具体店铺或版型关键词？\n\n"
     "附一张我现在的衣柜照片，真的没什么能穿的。",
     ["求助", "面试穿搭", "预算"], 4, 12, 231),

    ("post_14", "u_1", "outfit",
     "梨形春天怎么穿｜这5条半裙亲测显瘦，不修图实拍",
     "168/118斤，胯宽。半裙我试了十几条，留下这 5 条：\n\n"
     "1) A字中长裙，裙长到小腿最细处；2) 百褶不过膝；3) 直筒牛仔裙开衩；\n"
     "4) 高腰伞裙配短上衣；5) 一片式裹裙。\n\n"
     "统一原则：腰线要高、胯部要松、下摆要稳。图中都是原相机直出。",
     ["梨形穿搭", "半裙", "春装试穿"], 2, 18, 187),
]

# (id, post_id, user_id, text, parent_comment_id, hours_ago)
COMMENTS = [
    ("c_1", "post_1", "u_2", "姐妹这个衬衫什么版型？我也115斤梨形想抄作业😭", None, 2.5),
    ("c_2", "post_1", "u_1", "私信你啦～落肩的，别买正肩会显壮", "c_1", 2.2),
    ("c_3", "post_1", "u_5", "奶白阔腿裤真的显瘦！我买了同款不同色", None, 1.8),
    ("c_4", "post_1", "u_me", "不摆拍这点太加分了，终于看到真实身材的试穿", None, 1.1),

    ("c_5", "post_2", "u_1", "西裤选高腰直筒、裤线压褶的，胯那里别有口袋，亲测！", None, 6.5),
    ("c_6", "post_2", "u_3", "男生路过：直筒九分西裤+乐福鞋，通勤够用了", None, 5.8),
    ("c_7", "post_2", "u_2", "风衣敞开穿，内搭同色系，视觉上一条竖线", None, 4.2),
    ("c_8", "post_2", "u_5", "姐妹们太感谢了！我今晚就试，明天补上身图", None, 2.1),

    ("c_9", "post_3", "u_6", "第四层真的多余哈哈哈，收藏了", None, 18),
    ("c_10", "post_3", "u_me", "长度错开这个点我之前一直没注意", None, 12),

    ("c_11", "post_4", "u_2", "乐福鞋走两公里真的不累吗？", None, 1.5),
    ("c_12", "post_4", "u_4", "不累，但建议先穿几次磨合，新鞋别直接上旅途", "c_11", 1.2),

    ("c_13", "post_5", "u_1", "厚底球鞋显高又不笨重，同意", None, 26),
    ("c_14", "post_6", "u_me", "照着做了一周，真的没早起纠结过衣服", None, 40),

    ("c_15", "post_9", "u_6", "留两颗！扣满像上班，缎面裙配芭蕾鞋更轻", None, 35),
    ("c_16", "post_9", "u_1", "香槟色很好看，别再加亮闪闪的配饰就够了", None, 30),
    ("c_17", "post_9", "u_5", "听你们的，决定留两颗配芭蕾鞋，谢谢！", None, 24),

    ("c_18", "post_13", "u_1", "预算优先买内搭和鞋，大衣可以先借/二手", None, 9),
    ("c_19", "post_13", "u_3", "关键词搜「垂感 直筒 九分 西裤」，别买紧身", None, 7),
    ("c_20", "post_13", "u_2", "160梨形+1，面试用裙子记得坐下来试一下长度", None, 5),

    ("c_21", "post_14", "u_2", "一片式裹裙求具体店铺！", None, 14),
    ("c_22", "post_14", "u_1", "评论区置顶了，是去年买的，现在应该有同款", "c_21", 13),
]

# 当前登录用户（演示态）
VIEWER = "u_me"
FOLLOWS = ["u_1", "u_3"]
LIKES = ["post_2", "post_6"]
FAVORITES = ["post_4"]


def image_size(filename: str) -> tuple[int, int]:
    with Image.open(os.path.join(ASSETS, filename)) as im:
        return im.size


def main(keep: bool = False) -> None:
    path = db_path()
    if keep and os.path.exists(path):
        print("db exists, skip:", path)
        return
    if os.path.exists(path):
        os.remove(path)
        for suffix in ("-wal", "-shm"):
            if os.path.exists(path + suffix):
                os.remove(path + suffix)

    conn = connect(path)
    init_db(conn)

    now = datetime.now(TZ)
    conn.execute("BEGIN")
    for uid, nickname, avatar, bio in USERS:
        conn.execute(
            "INSERT INTO users (id, nickname, avatar_url, bio, created_at) VALUES (?,?,?,?,?)",
            (uid, nickname, f"/assets/{avatar}", bio, (now - timedelta(days=90)).isoformat(timespec="seconds")),
        )

    authors = {p[0]: p[1] for p in POSTS}
    for pid, uid, ptype, title, body, tags, no, hours, likes in POSTS:
        created = (now - timedelta(hours=hours)).isoformat(timespec="seconds")
        n_comments = sum(1 for c in COMMENTS if c[1] == pid)  # 冗余计数以真实评论行为准
        conn.execute(
            "INSERT INTO posts (id, user_id, title, text, post_type, outfit_id,"
            " like_count, comment_count, status, created_at) VALUES (?,?,?,?,?,?,?,?,'normal',?)",
            (pid, uid, title, body, ptype, f"outfit_{pid}", likes, n_comments, created),
        )
        fn = f"look_{no:02d}.jpg"
        w, h = image_size(fn)
        conn.execute(
            "INSERT INTO post_images (post_id, url, thumb_url, width, height, sort_order)"
            " VALUES (?,?,?,?,?,?)",
            (pid, f"/assets/{fn}", f"/assets/{fn}", w, h, 0),
        )
        for i, t in enumerate(tags):  # 顺序即展示顺序，tags[0] 是卡片主标签
            conn.execute("INSERT INTO post_tags (post_id, tag, sort_order) VALUES (?,?,?)", (pid, t, i))

    for cid, pid, uid, text, parent_id, hours in COMMENTS:
        conn.execute(
            "INSERT INTO comments (id, post_id, user_id, text, parent_id, created_at) VALUES (?,?,?,?,?,?)",
            (cid, pid, uid, text, parent_id, (now - timedelta(hours=hours)).isoformat(timespec="seconds")),
        )
        # 评论 -> 给作者写通知（自己评论自己不写）
        author = authors[pid]
        if uid != author:
            conn.execute(
                "INSERT INTO notifications (id, user_id, type, from_user_id, target_type, target_id, is_read, created_at)"
                " VALUES (?,?, 'comment', ?, 'post', ?, 0, ?)",
                (f"n_{cid}", author, uid, pid, (now - timedelta(hours=hours)).isoformat(timespec="seconds")),
            )

    stamp = now.isoformat(timespec="seconds")
    for uid in FOLLOWS:
        conn.execute("INSERT INTO follows VALUES (?,?,?)", (VIEWER, uid, stamp))
    for pid in LIKES:
        conn.execute("INSERT INTO likes VALUES (?,?,?)", (VIEWER, pid, stamp))
    for pid in FAVORITES:
        conn.execute("INSERT INTO favorites VALUES (?, 'post', ?, ?)", (VIEWER, pid, stamp))

    conn.execute("COMMIT")
    n = conn.execute("SELECT COUNT(*) n FROM posts").fetchone()["n"]
    c = conn.execute("SELECT COUNT(*) n FROM comments").fetchone()["n"]
    print(f"seeded {n} posts / {c} comments -> {path}")
    conn.close()


if __name__ == "__main__":
    main(keep="--keep" in sys.argv)
