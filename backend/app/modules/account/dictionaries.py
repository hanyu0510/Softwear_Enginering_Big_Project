def pairs(mapping):
    return [{"value": key, "label": label} for key, label in mapping.items()]


STYLES = {"minimal":"极简", "street":"街头", "sweet":"甜美", "formal":"正式", "casual":"休闲", "vintage":"复古", "sporty":"运动"}


def dictionary_data(color_names):
    return {
        "categories": pairs({"tops":"上装", "bottoms":"下装", "outerwear":"外套", "dress":"连衣裙/套装", "shoes":"鞋", "bag":"包", "accessory":"配饰", "other":"其他"}),
        "seasons": pairs({"spring":"春", "summer":"夏", "autumn":"秋", "winter":"冬"}),
        "occasions": pairs({"commute":"通勤", "date":"约会", "travel":"旅行", "casual":"日常", "formal":"正式", "party":"聚会", "sport":"运动"}),
        "styles": pairs(STYLES),
        "colors": pairs({name:name for name in color_names}),
        "verifyStatuses": pairs({"recognizing":"识别中", "pending":"待确认", "confirmed":"已确认", "failed":"识别失败"}),
        "warmthLevels": [{"value": i, "label": str(i)} for i in range(1,6)],
        "visibilities": pairs({"private":"私密", "public":"公开"}),
        "notificationTypes": pairs({"like":"点赞", "comment":"评论", "follow":"新粉丝"}),
        "reportTargetTypes": pairs({"post":"帖子", "comment":"评论", "item":"单品"}),
        "itemSources": pairs({"owned":"自有", "wish":"心愿"}),
    }
