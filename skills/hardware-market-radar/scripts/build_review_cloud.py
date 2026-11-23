# -*- coding: utf-8 -*-
"""
竞品官方客户评价 -> 词云 + 关注点矩阵 + 细节摘录
用法:
    python build_review_cloud.py <评价表.csv>
输出:
    out/词云_竞品对比.html
    out/词频汇总.csv
    out/关注点矩阵.csv
    out/明细摘录.csv
"""
import csv, os, re, sys, math, html
from collections import Counter, defaultdict

try:
    import jieba
    jieba.setLogLevel(60)
except Exception:
    jieba = None

BRANDS_ORDER = ["梅特勒-托利多", "奥豪斯", "巨天"]

# ---------- 停用词 ----------
STOP = set("""
的 了 是 我 也 就 都 和 与 及 而 但 在 有 没 很 太 还 又 再 才 只 被 把 给 让 从 到 对 为 以 于 这 那 这个 那个 这样 那样 这些 那些
我们 你们 他们 自己 一个 一下 一些 什么 怎么 怎样 如何 因为 所以 如果 虽然 但是 而且 然后 现在 已经 可以 可能 应该 需要 觉得 感觉
东西 商品 产品 宝贝 卖家 商家 客服 店家 这家 一次 一点 一直 非常 比较 有点 稍微 特别 真的 确实 还是 就是 只是 不过 还有 没有 不会 不能
买 用 说 看 想 要 会 能 好 差 大 小 多 少 高 低 快 慢 新 旧 很 挺 蛮 超 贼 太 更 最 一 二 三 四 五 六 七 八 九 十
质量 问题 情况 方面 时候 时间 地方 有点 整体 总体 总之 反正 基本 主要 直接 明显 实际 差不多 一般般 还行 不错 可以了 到位 满意 好评 推荐 值得 喜欢 认可
斤 公斤 kg 克 g 台 个 件 次 天 元 块 米 毫米 mm cm 型号 规格 参数 重量 称重 秤 电子秤 电子称 台秤 地磅 秤体 称 买 购买 收到 到手 使用 用了
机器人 协作机器人 工业机器人 移动机器人 机械臂 设备 厂家 公司 品牌 代理 经销商 杠杠 真的 超级 十分 相当 算是 算是 东西 物美价廉 物超所值 值得购买 值得推荐 满分 五星 客观 真实 中肯 评价 点评 晒单 追评 下单 付款 快递 物流 包裹 顺丰
""".split())

# ---------- 关注点规则 ----------
TOPICS = {
    "精度与稳定性": ["精度", "准", "误差", "重复定位", "定位", "漂移", "稳定", "抖动", "轨迹", "偏差", "校准", "标定", "一致性"],
    "负载与节拍": ["负载", "臂展", "速度", "节拍", "效率", "产能", "抓取", "工作范围", "行程", "加速度", "拍张", "取放"],
    "易用与编程": ["示教", "编程", "上手", "拖拽", "图形化", "简单", "难学", "代码", "脚本", "调试", "配置", "二次开发", "SDK"],
    "做工与耐用": ["做工", "结实", "厚实", "扎实", "用料", "材质", "外壳", "毛刺", "生锈", "变形", "耐用", "扛造", "防护", "IP", "散热"],
    "价格与性价比": ["价格", "便宜", "贵", "性价比", "划算", "实惠", "报价", "优惠", "预算", "一分钱", "贵了", "回本", "投资回收"],
    "发货与物流": ["发货", "物流", "快递", "到货", "运输", "包装", "木箱", "破损", "磕碰", "运费", "送货", "交期"],
    "客服与响应": ["客服", "回复", "态度", "讲解", "耐心", "专业", "咨询", "沟通", "秒回", "不回复", "答非所问", "技术支持"],
    "部署与集成": ["安装", "部署", "调试", "上门", "集成", "产线", "对接", "接线", "IO", "PLC", "通信", "协议", "EtherCAT", "Modbus", "视觉", "力控", "夹具"],
    "售后与保修": ["售后", "保修", "质保", "维修", "换货", "退货", "返修", "备件", "配件", "维修点", "上门服务", "响应时间"],
    "培训与交付": ["培训", "指导", "文档", "手册", "说明书", "视频", "课程", "周期", "工期", "多久", "延期", "拖"],
    "合规与认证": ["认证", "CE", "CR", "ISO", "安全", "合规", "检测", "报告", "资质", "标准", "过检"],
}

NEG = ["差", "坑", "失望", "退货", "退款", "不行", "问题", "坏", "不准", "误差大", "虚标", "假", "骗", "慢", "拖", "破损", "磕碰", "生锈", "变形", "毛刺",
       "生硬", "恶劣", "不回复", "敷衍", "后悔", "不值", "贵", "劣质", "凑合", "没法用", "麻烦", "返修", "漏水", "卡", "死机", "崩"]
POS = ["好", "稳", "准", "快", "满意", "推荐", "实惠", "划算", "专业", "耐心", "结实", "扎实", "耐用", "漂亮", "省心", "靠谱", "方便", "清晰", "划算"]

COL_ALIAS = {
    "brand": ["品牌", "竞品", "品牌名", "brand"],
    "body": ["评价正文", "评价内容", "正文", "内容", "评价", "评论", "content", "body", "review"],
    "model": ["商品型号", "型号", "规格", "product", "model", "sku"],
    "star": ["评分星级", "星级", "评分", "star", "score"],
    "time": ["评价时间", "时间", "日期", "date", "time"],
    "channel": ["渠道", "平台", "channel"],
    "link": ["商品链接", "链接", "url", "link"],
    "shop": ["店铺/账号", "店铺", "shop", "seller"],
}


def read_csv(path):
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise SystemExit("无法识别文件编码，请另存为 UTF-8 CSV")


def pick(row, key):
    for k in row.keys():
        if k is None:
            continue
        if k.strip().lower() in [a.lower() for a in COL_ALIAS[key]]:
            return row[k]
    return ""


def norm_brand(s):
    s = (s or "").strip()
    if not s:
        return ""
    low = s.lower()
    if "梅特勒" in s or "mettler" in low or "mt" == low:
        return "梅特勒-托利多"
    if "奥豪斯" in s or "ohaus" in low:
        return "奥豪斯"
    if "巨天" in s or "j-sky" in low or "jsky" in low or "秤哥" in s:
        return "巨天"
    return s


def tokenize(text):
    text = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9\.%]+", " ", text)
    words = []
    if jieba:
        for w in jieba.cut(text):
            w = w.strip()
            if len(w) < 2:
                continue
            if w in STOP:
                continue
            if re.fullmatch(r"[\d\.%]+", w):
                continue
            words.append(w)
    else:
        for seg in text.split():
            if len(seg) >= 2:
                words.append(seg)
    return words


def star_of(row):
    s = pick(row, "star")
    m = re.search(r"(\d)", str(s))
    return int(m.group(1)) if m else None


def topics_of(body):
    hit = []
    for name, kws in TOPICS.items():
        if any(k in body for k in kws):
            hit.append(name)
    return hit


NEG_CLEAN = ["没问题", "没有问题", "无问题", "没问题了", "差不多", "不错", "不差", "不贵", "不慢",
             "误差小", "误差很小", "没误差", "无误差", "不卡", "没坏", "没有坏", "不太", "没毛病"]


def polarity(body, star=None):
    """星级优先，无星级时用词面计数（先剔除否定式，避免把「没问题」判成负面）"""
    if star in (1, 2, 3):
        return "偏负"
    if star in (4, 5):
        return "偏正"
    t = body
    for w in NEG_CLEAN:
        t = t.replace(w, "")
    n = sum(t.count(k) for k in NEG)
    p = sum(t.count(k) for k in POS)
    if n > p and n >= 1:
        return "偏负"
    if p > n:
        return "偏正"
    return "中性"


# ---------- 词云 SVG ----------
PALETTE = ["#1B4A8B", "#2E6DB4", "#4E8FCB", "#7FA9D4", "#E8743B", "#F0A24B", "#8C7F6D", "#5B5F66"]


def text_width(w, fs):
    wsum = 0.0
    for ch in w:
        wsum += 1.0 if ord(ch) > 0x2E80 else 0.56
    return wsum * fs


def layout(words, size, seed=7, k=1.0):
    """阿基米德螺旋 + 矩形碰撞检测（按字符宽度精确估宽）"""
    W, H = size
    cx, cy = W / 2, H / 2
    placed = []
    out = []
    if not words:
        return out
    maxf = max(f for _, f in words) or 1
    minf = min(f for _, f in words) or 1
    for idx, (w, f) in enumerate(words):
        t = (f - minf) / (maxf - minf) if maxf > minf else 1
        fs = (14 + (44 - 14) * (t ** 0.62)) * k
        wbox = text_width(w, fs) + fs * 0.22
        hbox = fs * 1.28
        ok_place = False
        for attempt in range(2600):
            ang = attempt * 0.30 + seed
            r = 3.6 * (ang ** 1.03)
            x = cx + r * math.cos(ang) * 1.35
            y = cy + r * math.sin(ang) * 0.86
            bx, by = x - wbox / 2, y - hbox / 2
            if bx < 6 or by < 4 or bx + wbox > W - 6 or by + hbox > H - 4:
                continue
            box = (bx, by, bx + wbox, by + hbox)
            if any(not (box[2] < pb[0] or box[0] > pb[2] or box[3] < pb[1] or box[1] > pb[3])
                   for pb in placed):
                continue
            placed.append(box)
            out.append((w, fs, x, y, PALETTE[idx % len(PALETTE)]))
            ok_place = True
            break
        if not ok_place:
            continue
    return out


def cloud_svg(words, W=520, H=330, title=""):
    best = []
    for k in (1.0, 1.12, 1.24, 1.36, 1.48, 1.60, 1.72):
        items = layout(words[:55], (W, H), k=k)
        if len(items) > len(best):
            best = items
        xs = [x for _, _, x, _, _ in items]
        ys = [y for _, _, _, y, _ in items]
        if xs and (max(xs) - min(xs)) > W * 0.66 and (max(ys) - min(ys)) > H * 0.58:
            best = items
            break
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" preserveAspectRatio="xMidYMid meet" '
             'xmlns="http://www.w3.org/2000/svg" style="display:block;background:#FBFBF9;border-radius:10px">'
             % (W, H, H)]
    for w, fs, x, y, c in best:
        parts.append('<text x="%.1f" y="%.1f" font-size="%.1f" fill="%s" text-anchor="middle" '
                     'font-family="PingFang SC,Microsoft YaHei,sans-serif" font-weight="%s">%s</text>'
                     % (x, y, fs, c, "600" if fs > 26 else "400", html.escape(w)))
    if not best:
        parts.append('<text x="%d" y="%d" font-size="16" fill="#999" text-anchor="middle">'
                     '样本不足，无法成图</text>' % (W // 2, H // 2))
    parts.append("</svg>")
    return "".join(parts)


def bar(v, maxv, color="#2E6DB4"):
    pct = 0 if not maxv else v / maxv * 100
    return ('<div class="bar"><span style="width:%.1f%%;background:%s"></span></div>' % (pct, color))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    rows = read_csv(src)
    recs = []
    for r in rows:
        body = (pick(r, "body") or "").strip()
        if not body or body.startswith("（示例行"):
            continue
        b = norm_brand(pick(r, "brand"))
        if not b:
            continue
        recs.append({
            "brand": b, "body": body, "model": (pick(r, "model") or "").strip(),
            "star": star_of(r), "time": (pick(r, "time") or "").strip(),
            "channel": (pick(r, "channel") or "").strip(), "shop": (pick(r, "shop") or "").strip(),
            "link": (pick(r, "link") or "").strip(),
        })
    if not recs:
        raise SystemExit("没有读到有效评价，检查品牌列与正文列是否填写")

    brands = [b for b in BRANDS_ORDER if any(r["brand"] == b for r in recs)]
    for b in recs:
        if b["brand"] not in brands:
            brands.append(b["brand"])

    os.makedirs("out", exist_ok=True)
    freq_all = {}
    stat = {}
    for b in brands:
        rs = [r for r in recs if r["brand"] == b]
        cnt = Counter()
        for r in rs:
            cnt.update(tokenize(r["body"]))
        cnt = Counter({w: c for w, c in cnt.items() if c >= 2}) or cnt
        freq_all[b] = cnt.most_common(80)
        stars = [r["star"] for r in rs if r["star"]]
        stat[b] = {
            "n": len(rs),
            "avg": round(sum(stars) / len(stars), 2) if stars else None,
            "low": sum(1 for s in stars if s <= 3),
            "chars": sum(len(r["body"]) for r in rs),
        }

    # 词频 CSV
    with open("out/词频汇总.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(["品牌", "排名", "词", "出现次数"])
        for b in brands:
            for i, (word, c) in enumerate(freq_all[b], 1):
                w.writerow([b, i, word, c])

    # 关注点矩阵
    with open("out/关注点矩阵.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["关注点"] + ["%s提及数" % b for b in brands] + ["%s提及率" % b for b in brands])
        for t in TOPICS:
            counts = []
            for b in brands:
                rs = [r for r in recs if r["brand"] == b]
                c = sum(1 for r in rs if t in topics_of(r["body"]))
                counts.append(c)
            w.writerow([t] + counts + ["%.0f%%" % (c / max(1, stat[b]["n"]) * 100) for c, b in zip(counts, brands)])

    # 明细摘录
    with open("out/明细摘录.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["品牌", "渠道", "型号", "星级", "倾向", "关注点", "评价正文", "时间", "链接"])
        for r in recs:
            w.writerow([r["brand"], r["channel"], r["model"], r["star"] or "", polarity(r["body"], r["star"]),
                        "/".join(topics_of(r["body"])), r["body"], r["time"], r["link"]])

    # HTML
    max_n = max(stat[b]["n"] for b in brands)
    h = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width,initial-scale=1">',
         '<title>竞品客户评价词云与细节</title><style>',
         ':root{--ink:#14161A;--sub:#5B5F66;--line:#E3E1DA;--blue:#1B4A8B;--orange:#E8743B}',
         '*{box-sizing:border-box}body{margin:0;background:#F5F4F0;color:var(--ink);',
         "font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;line-height:1.6}",
         '.wrap{max-width:1180px;margin:0 auto;padding:40px 28px 64px}',
         'h1{font-size:30px;margin:0 0 6px;letter-spacing:-.02em}',
         '.meta{color:var(--sub);font-size:13px;margin-bottom:28px}',
         '.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:32px;align-items:stretch}',
         '.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px;display:flex;flex-direction:column}',
         '.card h3{margin:0 0 4px;font-size:16px}',
         '.kpi{display:flex;gap:14px;font-size:12px;color:var(--sub);margin:8px 0 12px;flex-wrap:wrap}',
         '.kpi b{color:var(--ink);font-size:15px;display:block}',
         'h2{font-size:19px;margin:34px 0 12px;padding-top:22px;border-top:1px solid var(--line)}',
         'table{width:100%;border-collapse:collapse;font-size:13px;background:#fff}',
         'th,td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}',
         'th{background:#FAFAF8;font-weight:600;color:var(--sub);font-size:12px}',
         '.bar{background:#EDEDE8;height:8px;border-radius:4px;overflow:hidden;min-width:60px}',
         '.bar span{display:block;height:100%}',
         '.q{font-size:12.5px;color:#33363C;border-left:2px solid var(--line);padding-left:9px;margin:6px 0}',
         '.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:999px;background:#EEF2F8;color:var(--blue);margin-right:5px}',
         '.neg{color:#C0392B}.pos{color:#1E7A4C}',
         'footer{color:var(--sub);font-size:12px;margin-top:36px;border-top:1px solid var(--line);padding-top:14px}',
         '@media(max-width:860px){.grid{grid-template-columns:1fr}}',
         '</style></head><body><div class="wrap">',
         '<h1>竞品官方客户评价：词云与细节</h1>',
         '<div class="meta">样本 %d 条 · 品牌 %d 家 · 分词 jieba · 词云仅统计评价正文，已剔除品牌名与功能词</div>'
         % (len(recs), len(brands)),
         '<div class="grid">']
    for b in brands:
        s = stat[b]
        h.append('<div class="card"><h3>%s</h3>' % html.escape(b))
        h.append('<div class="kpi"><div><b>%d</b>条评价</div><div><b>%s</b>均分</div><div><b>%d</b>条≤3星</div>'
                 '<div><b>%d</b>字样本</div></div>' % (s["n"], s["avg"] if s["avg"] is not None else "—", s["low"], s["chars"]))
        h.append(cloud_svg(freq_all[b], 520, 330))
        h.append("</div>")
    h.append("</div>")

    h.append("<h2>关注点结构：谁在被夸、谁在被骂</h2><table><tr><th>关注点</th>")
    for b in brands:
        h.append("<th>%s</th>" % html.escape(b))
    h.append("</tr>")
    for t in TOPICS:
        h.append("<tr><td>%s</td>" % t)
        mx = 0
        vals = []
        for b in brands:
            c = sum(1 for r in recs if r["brand"] == b and t in topics_of(r["body"]))
            vals.append(c)
            mx = max(mx, c)
        for c, b in zip(vals, brands):
            h.append('<td>%d %s</td>' % (c, bar(c, mx)))
        h.append("</tr>")
    h.append("</table>")

    h.append("<h2>细节：原话摘录</h2>")
    for b in brands:
        rs = [r for r in recs if r["brand"] == b]
        seen = set()

        def uniq(items):
            res = []
            for it in items:
                k = it["body"][:40]
                if k in seen:
                    continue
                seen.add(k)
                res.append(it)
            return res

        neg = uniq([r for r in rs if polarity(r["body"], r["star"]) == "偏负"])[:6]
        pos = uniq([r for r in rs if polarity(r["body"], r["star"]) == "偏正"])[:6]
        h.append('<div class="card" style="margin-bottom:14px"><h3>%s</h3>' % html.escape(b))
        h.append('<div style="font-size:12px;color:var(--sub);margin:6px 0">负面/挑刺原话</div>')
        if neg:
            for r in neg:
                h.append('<div class="q"><span class="neg">%s★</span> %s</div>'
                         % (r["star"] or "—", html.escape(r["body"][:180])))
        else:
            h.append('<div class="q">本批样本未出现明显负面表述</div>')
        h.append('<div style="font-size:12px;color:var(--sub);margin:10px 0 6px">正面原话</div>')
        for r in pos:
            h.append('<div class="q"><span class="pos">%s★</span> %s</div>'
                     % (r["star"] or "—", html.escape(r["body"][:180])))
        h.append("</div>")

    h.append('<footer>数据来源为使用者提供的官方旗舰店评价导出。词频与关注点为规则统计，不含主观推断；'
             '样本量决定结论强度，样本低于 30 条时只作方向参考，不外推到品牌整体口碑。</footer>')
    h.append("</div></body></html>")

    out = "out/词云_竞品对比.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write("".join(h))
    print("OK", out, "样本", len(recs), "条", {b: stat[b]["n"] for b in brands})


if __name__ == "__main__":
    main()
