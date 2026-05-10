EMOTIONS = {
    "joy":        {"ko": "기쁨",   "color": "#FAC775"},
    "excitement": {"ko": "설렘",   "color": "#FF9F6B"},
    "neutral":    {"ko": "평범함", "color": "#9DCFB5"},
    "surprise":   {"ko": "놀라움", "color": "#85C9EB"},
    "disgust":    {"ko": "불쾌함", "color": "#C4A882"},
    "fear":       {"ko": "두려움", "color": "#AFA9EC"},
    "sadness":    {"ko": "슬픔",   "color": "#85B7EB"},
    "anger":      {"ko": "분노",   "color": "#F09595"},
}

KOELECTRA_LABEL_MAP = {
    "기쁨": "joy", "설렘": "excitement", "평범함": "neutral", "놀라움": "surprise",
    "불쾌함": "disgust", "두려움": "fear", "슬픔": "sadness", "분노": "anger",
}
EN_TO_KO = {v: k for k, v in KOELECTRA_LABEL_MAP.items()}

NLP_SCORE_TEMPLATE = {
    "joy":        {"joy":70,"excitement":10,"neutral":5,"surprise":5,"disgust":2,"fear":2,"sadness":3,"anger":3},
    "excitement": {"joy":15,"excitement":70,"neutral":3,"surprise":8,"disgust":1,"fear":1,"sadness":1,"anger":1},
    "neutral":    {"joy":5, "excitement":5, "neutral":70,"surprise":5,"disgust":5,"fear":5,"sadness":3,"anger":2},
    "surprise":   {"joy":10,"excitement":15,"neutral":5,"surprise":55,"disgust":3,"fear":8,"sadness":2,"anger":2},
    "disgust":    {"joy":2, "excitement":1, "neutral":5,"surprise":3,"disgust":65,"fear":5,"sadness":10,"anger":9},
    "fear":       {"joy":2, "excitement":2, "neutral":5,"surprise":8,"disgust":3,"fear":65,"sadness":10,"anger":5},
    "sadness":    {"joy":3, "excitement":1, "neutral":5,"surprise":2,"disgust":4,"fear":10,"sadness":70,"anger":5},
    "anger":      {"joy":2, "excitement":2, "neutral":3,"surprise":3,"disgust":10,"fear":5,"sadness":5,"anger":70},
}

EMOTION_SEARCH_QUERIES = {
    "joy":        ["아이유 좋은날", "NewJeans Hype Boy", "BTS 봄날"],
    "excitement": ["aespa Supernova", "ILLIT Magnetic", "TWICE Fancy"],
    "neutral":    ["볼빨간사춘기 우주를 줄게", "폴킴 모든 날 모든 순간", "IU 밤편지"],
    "surprise":   ["NewJeans OMG", "aespa Next Level", "SHINee 상사병"],
    "disgust":    ["10cm 아메리카노", "이적 걱정말아요", "검정치마 Everything"],
    "fear":       ["IU 이름에게", "폴킴 비", "적재 별 보러 가자"],
    "sadness":    ["임영웅 이제 나만 믿어요", "폴킴 너였으면", "IU 잊어야 한다는 마음으로"],
    "anger":      ["BTS DOPE", "BLACKPINK Pink Venom", "aespa Girls"],
}