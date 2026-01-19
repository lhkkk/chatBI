#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：chatbi 
@File    ：algorithm_service.py
@IDE     ：PyCharm 
@Author  ：jyy
@Date    ：2025/7/29 下午3:54 
'''
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from fuzzywuzzy import fuzz
from flask import Flask, request, jsonify
from config import CommonConfig
import hanlp

log = CommonConfig.log
# 初始化 Flask 应用
app = Flask(__name__)

# 加载 HanLP 各项模型（只加载一次，避免重复加载）
# 分词
tokenizer = hanlp.load(hanlp.pretrained.tok.PKU_NAME_MERGED_SIX_MONTHS_CONVSEG)
with open('hanlp_userdict.txt', encoding='utf-8') as f:
    user_words = {line.strip() for line in f if line.strip()}

# 或者：优先但非强制匹配（会与原词表合并，保留原有分词能力）
tokenizer.dict_combine = user_words

# 词性标注
pos_tagger = hanlp.load(hanlp.pretrained.pos.CTB5_POS_RNN)
# 命名实体识别
ner_tagger = hanlp.load(hanlp.pretrained.ner.MSRA_NER_BERT_BASE_ZH)
# 依存句法分析
dep_parser = hanlp.load(hanlp.pretrained.dep.CTB9_DEP_ELECTRA_SMALL)

@app.route('/nlp', methods=['POST'])
def nlp_pipeline():
    """
    接口说明：
    请求方法：POST
    请求示例：{ "text": "HanLP是一个优秀的NLP工具包。" }
    返回示例：
    {
        "tokens": [...],
        "pos": [...],
        "ner": [...],
        "dep": [...]
    }
    """
    data = request.get_json(force=True)
    text = data.get('text', '')
    if not text:
        return jsonify({"error": "Missing 'text' in request body"}), 400

    # 分词（返回列表嵌套一级 batch）
    tokens = tokenizer([text])[0]
    # 词性标注（输入 token 列表）
    pos_tags = pos_tagger(tokens)
    # 命名实体识别
    ner_results = ner_tagger(tokens)
    # 依存句法分析
    dep_results = dep_parser(tokens)

    # 定义一个判断函数：CTB5 中名词标签以 'N' 开头，动词标签以 'V' 开头
    def is_noun_or_verb(tag: str) -> bool:
        return tag.startswith(('N', 'V'))

    # 过滤得到的结果
    filtered = [tok for tok, tag in zip(tokens, pos_tags)
                if is_noun_or_verb(tag)]

    log.info(f"原始tokens: {tokens}")
    log.info(f"过滤后的tokens: {filtered}")

    return jsonify({
        'tokens': filtered
    })

class ChineseSimilarQuestionMatcher:
    def __init__(self, domain_keywords, qa_pairs, user_dict_path=None):
        # 加载用户词典或动态添加关键词
        if user_dict_path:
            jieba.load_userdict(user_dict_path)
        else:
            for w in domain_keywords:
                jieba.add_word(w, freq=20000)

        self.domain_keywords = set(domain_keywords)
        self.qa_pairs = qa_pairs
        self.questions = [q["question"] for q in qa_pairs]

        # TF–IDF 模型训练
        self.vectorizer = TfidfVectorizer(
            tokenizer=jieba.lcut, token_pattern=None,
            stop_words=None, min_df=1, max_features=5000
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(self.questions)

    def match(self, user_query, cos_thresh=0.4, fuzzy_thresh=60):
        # 1. 余弦相似度计算
        q_vec = self.vectorizer.transform([user_query])
        sims = cosine_similarity(q_vec, self.tfidf_matrix).flatten()

        # 2. 关键词 + 模糊匹配得分
        ratios = [fuzz.partial_ratio(user_query, q) for q in self.questions]
        kw_hits = []
        for q in self.questions:
            segs = jieba.lcut(q)
            kw_hits.append(len(set(segs) & self.domain_keywords))

        results = []
        for idx, qa in enumerate(self.qa_pairs):
            score_cos = sims[idx]
            score_fuzzy = kw_hits[idx] * 10 + ratios[idx]
            if score_cos > cos_thresh or score_fuzzy > fuzzy_thresh:
                results.append({
                    "question": qa["question"],
                    "answer": qa["answer"],
                    "cosine_similarity": round(float(score_cos), 4),
                    "fuzzy_score": score_fuzzy
                })
        return results

# 全局 matcher 实例，可以按需在每次请求中重建或缓存
matcher = None

@app.route("/similar_qa", methods=["POST"])
def similar_qa():
    global matcher
    data = request.get_json()
    domain_keywords = data.get("domain_keywords", [])
    domain_keywords = [word.strip() for word in domain_keywords.split(",")]
    # qa_pairs = data.get("qa_pairs", [])
    qa_pairs = [
        {"question": "如何统计 TCP 吞吐量？", "answer": "可以使用 iperf 或者 tshark 等工具监控。"},
        {"question": "监控网络丢包率的工具有哪些？", "answer": "常见的有 ping、mtr、Smokeping。"},
        {"question": "计算网络时延的常用方法？", "answer": "可采用 ICMP ping 或者在应用层打点计算往返时间。"},
        {"question": "如何获取上行流量峰值？", "answer": "通过 SNMP 或 NetFlow 采样并分析即可。"}
    ]
    user_query = data.get("user_query", "")
    # optional: user_dict_path = data.get("user_dict_path")

    # 重建 matcher
    matcher = ChineseSimilarQuestionMatcher(domain_keywords, qa_pairs)
    results = matcher.match(user_query, cos_thresh=0.4, fuzzy_thresh=60)
    return jsonify({"hits": results})

@app.route('/api/dialogue', methods=['POST'])
def dialogue_endpoint():
    """
    接口：/api/dialogue
    请求JSON参数:
      - current_status_code: int, 当前状态码
      - history_dialogue: list of dict, 历史对话信息，每条包含 'speaker' 和 'message'
      - current_dialogue: dict, 当前对话信息，包含 'speaker' 和 'message'

    返回JSON:
      - status_code: int, 判断后的状态码
      - responses: list of str, 自然语言响应列表
    """
    data = request.get_json()
    # 参数校验
    if not data:
        return jsonify({'error': 'Missing JSON payload'}), 400

    required_fields = ['current_status_code', 'history_dialogue', 'current_dialogue']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f"Missing field: {field}"}), 400

    current_status = data['current_status_code']
    history = data['history_dialogue']
    current = data['current_dialogue']

    # TODO: 在此处添加逻辑，根据 current_status, history 和 current 生成新的状态码和响应列表
    # 示例逻辑：如果当前对话包含关键词，则状态+1，否则不变
    new_status = current_status + 1 if '请' in current.get('message', '') else current_status

    # 示例自然语言响应列表
    responses = [
        "已收到您的请求，请稍后。",
        "正在处理历史对话信息..."
    ]

    sample_input = {
        "keywords": domain_keywords,
        "original_question": user_query,
        "qa_pairs": qa_pairs,
        "rewritten_question": result["hits"][0]["question"]
    }

    intent = intent_recognition(sample_input)
    return jsonify({
        'status_code': new_status,
        'responses': responses
    }), 200


if __name__ == '__main__':
    # Debug 环境下可开启调试模式，生产环境请关闭
    app.run(host='0.0.0.0', port=5000, debug=True)