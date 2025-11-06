# -*- coding: utf-8 -*-
import os, re, json, time, yaml, feedparser, math, hashlib
from pathlib import Path
from urllib.parse import urlparse, urljoin
from langdetect import detect, DetectorFactory
from dotenv import dotenv_values
from anthropic import Anthropic
import requests
from model_helper import create_message_with_fallback
from fact_checker import fact_check_article, print_fact_check_result, llm_fact_check_article, print_llm_fact_check_result
from requests.auth import HTTPBasicAuth
from difflib import SequenceMatcher

DetectorFactory.seed = 0
BASE = Path(__file__).resolve().parent.parent
CFG  = yaml.safe_load(open(BASE/"config"/"config.yaml","r",encoding="utf-8"))
ENV  = dotenv_values(BASE/".env")
STATE_DIR = BASE/"state"; STATE_DIR.mkdir(exist_ok=True)

POSTED_URLS_PATH = STATE_DIR/"posted_urls.json"
DOMAIN_PATH      = STATE_DIR/"domain_last.json"
FINGER_PATH      = STATE_DIR/"posted_fingerprints.json"
IMG_HISTORY_PATH = STATE_DIR/"featured_image_history.json"

def load_json(p):
    if p.exists():
        try: return json.loads(p.read_text(encoding="utf-8"))
        except: return {}
    return {}

def save_json(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")

def load_posted_urls():
    s=set()
    if POSTED_URLS_PATH.exists():
        try:
            for u in json.loads(POSTED_URLS_PATH.read_text(encoding="utf-8")):
                s.add(norm_url(u))
        except: pass
    old = STATE_DIR/"posted.json"
    if old.exists():
        try:
            d=json.loads(old.read_text(encoding="utf-8"))
            for u in d.keys(): s.add(norm_url(u))
        except: pass
    return s

def save_posted_urls(s:set):
    POSTED_URLS_PATH.write_text(json.dumps(sorted(s),ensure_ascii=False,indent=2),encoding="utf-8")

def strip_html(s): return re.sub(r"<[^>]+>","", s or "").strip()

def norm_url(u:str)->str:
    u=(u or "").strip()
    u=re.sub(r"#.*$","",u); u=re.sub(r"/+$","",u)
    return u

def guess_lang(t):
    t=(t or "").strip()
    if not t: return "unknown"
    try: return detect(t)
    except: return "unknown"

def domain_ok(domain, domain_last, cooldown_days):
    ts=domain_last.get(domain); 
    return True if not ts else (time.time()-ts) > cooldown_days*86400

def mark_domain(domain, domain_last):
    if domain: domain_last[domain]=time.time()

def clean_for_fingerprint(text:str)->str:
    t=strip_html(text)
    t=t.lower()
    t=re.sub(r"https?://\S+","",t)
    t=re.sub(r"[^ぁ-んァ-ン一-龥a-z0-9\s]", " ", t)
    t=re.sub(r"\s+"," ",t).strip()
    return t

def shingles(text, k=8):
    toks=text.split()
    return [" ".join(toks[i:i+k]) for i in range(max(1,len(toks)-k+1))]

def simhash(text, bits=64):
    v=[0]*bits
    for sh in shingles(text, k=8):
        h=int(hashlib.md5(sh.encode("utf-8")).hexdigest(),16)
        for i in range(bits):
            v[i]+=1 if (h>>i)&1 else -1
    out=0
    for i in range(bits):
        if v[i]>0: out|=(1<<i)
    return out

def hamdist(a,b):
    x=a^b; c=0
    while x: 
        x&=x-1; c+=1
    return c

def fingerprint_record(title:str, summary:str):
    base=clean_for_fingerprint((title or "")+" "+(summary or ""))
    if not base: base="(empty)"
    return {
        "sha1": hashlib.sha1(base.encode("utf-8")).hexdigest(),
        "simhash": simhash(base),
        "title": title[:120],
        "created_at": time.time()
    }

def select_featured_image():
    """ランダムに画像を選択（連続3回同じ画像を避ける）"""
    import random
    
    # 設定から画像IDリストを取得
    media_ids = CFG.get("wordpress", {}).get("featured_image", {}).get("random_media_ids", [])
    if not media_ids:
        return None
    
    # 履歴ファイルを読み込み
    history = load_json(IMG_HISTORY_PATH)
    recent = history.get("recent_images", [])
    
    # 連続3回同じ画像を避けるため、最近使った2つを除外
    available = [img_id for img_id in media_ids if img_id not in recent[-2:]]
    
    # 利用可能な画像がない場合は全てから選択
    if not available:
        available = media_ids
    
    # ランダム選択
    selected = random.choice(available)
    
    # 履歴更新（最新3件まで保持）
    recent.append(selected)
    recent = recent[-3:]  # 最新3件のみ保持
    
    # 履歴保存
    history["recent_images"] = recent
    history["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_json(IMG_HISTORY_PATH, history)
    
    return selected

def is_near_duplicate(title:str, summary:str, fp_list:list, sha1_dup=True, simhash_thresh=3, title_sim=0.92):
    base=clean_for_fingerprint((title or "")+" "+(summary or ""))
    if not base: return False
    sha1=hashlib.sha1(base.encode("utf-8")).hexdigest()
    sh=simhash(base)
    for r in fp_list:
        try:
            if sha1_dup and r.get("sha1")==sha1: 
                return True
            if "simhash" in r and hamdist(int(r["simhash"]), sh) <= simhash_thresh:
                return True
            t=r.get("title") or ""
            if t and SequenceMatcher(None, t.lower(), (title or "").lower()).ratio() >= title_sim:
                return True
        except: 
            continue
    return False

def safe_html_cleanup(html):
    html=re.sub(r"<!--.*?-->", "", html, flags=re.S)
    html=re.sub(r"</?(script|style|section|table|iframe|form|noscript)\b[^>]*>.*?</\1>", "", html, flags=re.I|re.S)
    html=re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", html, flags=re.I|re.S)
    allowed=("h1","h3","p","ul","li","div","strong","em","code")
    def keep(m):
        tag=m.group(1).lower()
        return m.group(0) if tag in allowed else ""
    html=re.sub(r"</?([a-zA-Z0-9]+)\b[^>]*>", lambda m: keep(m), html)
    def noattrs(m):
        tag=m.group(1); closing=m.group(0).startswith("</")
        return f"</{tag}>" if closing else f"<{tag}>"
    html=re.sub(r"</?([a-zA-Z0-9]+)(\s+[^>]*)?>", noattrs, html)
    if len(html)>12000: html=html[:12000]+"…"
    return html

def entry_published_ts(e):
    try:
        from time import mktime
        if getattr(e,"published_parsed",None): return mktime(e.published_parsed)
        if getattr(e,"updated_parsed",None): return mktime(e.updated_parsed)
    except: pass
    return None

def score_candidate(c, sel, client):
    W = sel["weights"]
    now = time.time()
    freshness=0.0
    if c.get("ts"):
        hours=max(1,(now-c["ts"])/3600.0)
        freshness=max(0.0,min(1.0, math.exp(-hours/72.0)))
    lang_score = sel.get("ja_priority",1.0) if c["lang"].startswith("ja") else sel.get("en_priority",0.8)
    src_w = sel.get("source_weights",{}).get(c["domain"], 1.0)
    kw_score = 0.0
    title_lower=c["title"]
    for kw in sel.get("keyword_boosts",[]):
        if kw.lower() in title_lower.lower():
            kw_score += 0.05
    kw_score=min(1.0, kw_score)
    prompt = f"""次のニュースが、LLM/生成AI領域で日本のビジネス読者にとって「話題になる/価値が高い」かを0.0〜1.0で数値のみ返答。
特に公式発表・カンファレンス・DevDay・API更新・新機能リリースは高評価。説明不要。
タイトル: {c["title"]}
要約: {c["summary"]}"""
    try:
        msg = create_message_with_fallback(
            client,
            system="数値評価器。0.0〜1.0の実数のみを返す。",
            messages=[{"role":"user","content":prompt}],
            max_tokens=20,
            temperature=0.0
        )
        txt="".join([p.text for p in msg.content if p.type=="text"]).strip()
        m=re.findall(r"[0-1](?:\.\d+)?", txt)
        vir=float(m[0]) if m else 0.5
    except Exception:
        vir=0.5
    score = (W["freshness"]*freshness +
             W["source"]*( (src_w-0.8)/0.4*0.5 ) +
             W["language"]*lang_score +
             W["keyword"]*kw_score +
             W["llm_virality"]*vir)
    return max(0.0, min(1.0, score))

def pick_candidates(top_n=5):
    """
    記事候補を取得し、スコアの高い順にtop_n件を返す

    Returns:
        candidates: 候補記事のリスト（スコア順）
        posted_urls: 投稿済みURLセット
        domain_last: ドメイン最終投稿時刻
        fp_list: フィンガープリントリスト
    """
    sel=CFG.get("selection",{})
    feeds=CFG.get("fetch",{}).get("feeds",[])
    posted_urls=load_posted_urls()
    domain_last=load_json(DOMAIN_PATH)
    fp_list=load_json(FINGER_PATH).get("items",[])
    cand_limit=sel.get("candidate_limit",50)
    scan_per_feed=sel.get("max_scan_per_feed",10)
    cooldown=sel.get("domain_cooldown_days",1)
    client=Anthropic(api_key=ENV.get("ANTHROPIC_API_KEY"))
    cands=[]
    for f in feeds:
        url=f.get("url");
        if not url: continue
        d=feedparser.parse(url)
        for e in d.entries[:scan_per_feed]:
            title=strip_html(getattr(e,"title",""))
            link=(getattr(e,"link","") or "").strip()
            if not link: continue
            nlink=norm_url(link)
            if nlink in posted_urls:
                continue
            summary=strip_html(getattr(e,"summary","") or getattr(e,"description",""))
            if is_near_duplicate(title, summary, fp_list, sha1_dup=True, simhash_thresh=3, title_sim=0.92):
                continue
            dom=urlparse(link).netloc
            if not domain_ok(dom, domain_last, cooldown):
                continue
            ts=entry_published_ts(e)
            lang=guess_lang((title+" "+summary)[:1000])
            cands.append({"title":title,"link":link,"summary":summary,"domain":dom,"ts":ts,"lang":lang,"source":d.feed.get("title",url)})
            if len(cands)>=cand_limit: break
        if len(cands)>=cand_limit: break
    if not cands: return [], posted_urls, domain_last, fp_list
    scored=[]
    for c in cands:
        s=score_candidate(c, sel, client)
        scored.append((s,c))
    scored.sort(key=lambda x: x[0], reverse=True)
    # 上位top_n件を返す
    top_candidates = [item[1] for item in scored[:top_n]]
    return top_candidates, posted_urls, domain_last, fp_list

def main():
    WP_URL=(ENV.get("WP_URL","") or "").rstrip("/")+"/"
    WP_USER=(ENV.get("WP_USER","") or "")
    WP_PASS=(ENV.get("WP_APP_PASSWORD","") or "")
    if not (WP_URL and WP_USER and WP_PASS):
        raise SystemExit("WP接続情報不足")
    wp_cfg=(CFG.get("wordpress") or {})
    cats=wp_cfg.get("category_ids") or []
    status=wp_cfg.get("status","publish")

    # 複数の候補を取得（上位5件）
    candidates, posted_urls, domain_last, fp_list = pick_candidates(top_n=5)
    if not candidates:
        print("未投稿の候補が見つかりません。終了。"); return

    print(f"\n{len(candidates)}件の候補記事を取得しました。")

    client=Anthropic(api_key=ENV.get("ANTHROPIC_API_KEY"))
    system="""あなたは技術ニュースライターです。

【記事作成の原則】
- ニュース記事として事実を正確に伝える
- 専門知識のない読者でも理解できるよう丁寧に説明する
- 読者にとっての意味や影響を明示する

【文章ルール】
- 1文は20語以内を目安に、短く簡潔に
- 1段落は3-5文以内
- 専門用語は初出時に必ず説明（「○○とは、～のことです」）
- 具体的な数値・日付・固有名詞を使う
- 曖昧な表現を避ける

【HTMLタグ】
- h1, h3, p, ul, li, div, strong, em, codeのみ使用
- コードブロックマーカー（```html など）は絶対に出力しない
- HTMLタグの外にテキストを書かない"""

    # 候補を順に試す
    for idx, best in enumerate(candidates, 1):
        print(f"\n{'='*70}")
        print(f"候補 {idx}/{len(candidates)}: {best['title'][:60]}...")
        print(f"{'='*70}")

        user=f"""以下の元記事から、わかりやすい日本語ニュース記事を作成してください。

【記事構成】

1. メタディスクリプション（120字以内）
<p data-meta="description">【誰が】【何を】【いつ】。【主な内容1文】。【影響1文】。</p>

2. タイトル（H1、50-60文字）
<h1>【事実を簡潔に】</h1>

3. リード段落（300-400字）※重要：丁寧にわかりやすく説明
<p>
【第1文】いつ、誰が、何をしたか（5W1H）
【第2-3文】その内容の詳細、重要なポイント
【第4-5文】なぜこれが重要なのか、背景
【第6文】読者への影響や意味
</p>

4. 本文（H3見出しで整理、全体で1,500-2,000字）

<h3>【具体的な見出し】</h3>
<p>
・発表内容の詳細
・数値やデータがあれば具体的に
・専門用語は「○○とは、～のことです。【具体例】」の形で説明
</p>

<h3>背景と経緯</h3>
<p>
・なぜこのニュースが出たのか
・これまでの経緯
・業界の状況
</p>

<h3>技術的な詳細（該当する場合）</h3>
<p>
・どんな技術・仕組みか
・従来との違い
・具体的にどう動作するか
※難しい概念は身近な例えで説明
</p>

<h3>できること・できないこと</h3>
<p>
【文章形式で説明】
この技術により、【具体的にできること】が可能になります。例えば、【具体例1】や【具体例2】といった使い方が考えられます。

一方で、【まだ難しいこと】もあります。【制約や限界を説明】。【時期】には【改善の見込み】でしょう。
</p>

<h3>私たちへの影響</h3>
<p>
【読者の視点で】
このニュースは、【対象読者】に【どんな影響】を与えます。

【短期的な影響】については、【具体的に】。
【中長期的な影響】としては、【予測】が考えられます。

ただし、【注意点や留意事項】。
</p>

5. 出典
<div class="source"><strong>出典：</strong>【元記事タイトル】（【ドメイン】）</div>

【重要な指示】
- リード段落は特に丁寧に、300-400字かけて説明する
- 逆ピラミッド構造：重要な情報を最初に
- 箇条書きは必要最小限、基本は文章で説明
- 「できること・できないこと」「影響」は文章形式
- 専門用語には必ず説明と具体例をつける

元記事情報：
- タイトル: {best['title']}
- リンク: {best['link']}
- 要約: {best['summary']}
- ドメイン: {best['domain']}
- 言語: {best['lang']}

HTMLのみで出力してください。Markdown禁止。コードブロックマーカーは使用禁止。""".strip()

        print("\n[記事生成中...]")
        msg=create_message_with_fallback(client, system=system, messages=[{"role":"user","content":user}])
        html="".join([p.text for p in msg.content if p.type=="text"]).strip()

        if not html:
            print("❌ 生成が空。次の候補へ。")
            continue

        # Phase 1: ルールベースのファクトチェック
        print("\n[Phase 1: ルールベースのファクトチェック中...]")
        fact_check_result = fact_check_article(best, html)
        print_fact_check_result(fact_check_result)

        if not fact_check_result["passed"]:
            print(f"❌ Phase 1 不合格。この記事を破棄して次の候補へ。\n")
            continue

        print("✅ Phase 1 合格！")

        # Phase 2: LLMベースのファクトチェック
        print("\n[Phase 2: LLMベースのファクトチェック中...]")
        llm_result = llm_fact_check_article(best, html, client)
        print_llm_fact_check_result(llm_result)

        if not llm_result["passed"]:
            print(f"❌ Phase 2 不合格（スコア: {llm_result['score']}/100）。この記事を破棄して次の候補へ。\n")
            continue

        # 両方のファクトチェック合格 → 投稿処理
        print(f"✅ Phase 2 合格（スコア: {llm_result['score']}/100）！")
        print("✅ 全てのファクトチェックに合格！記事を投稿します。\n")

        meta=""
        m=re.search(r'<p[^>]*data-meta=["\\\']description["\\\'][^>]*>(.*?)</p>', html, flags=re.I|re.S)
        if m:
            meta=re.sub(r"<[^>]+>","",m.group(1)).strip()
            if len(meta)>120: meta=meta[:119]+"…"
        html=safe_html_cleanup(html)
        mt=re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.I|re.S)
        title=re.sub(r"<[^>]+>","",mt.group(1)).strip()[:62] if mt else "(自動生成)AIニュース"

        url=urljoin(WP_URL,"wp-json/wp/v2/posts")
        payload={"title":title,"content":html,"status":status,"categories":cats,"excerpt":meta}

        # アイキャッチ画像をランダム選択
        featured_img_id = select_featured_image()
        if featured_img_id:
            payload["featured_media"] = featured_img_id
            print(f"アイキャッチ画像: ID {featured_img_id}")

        r=requests.post(url,auth=HTTPBasicAuth(WP_USER,WP_PASS),json=payload,timeout=40)
        print("POST STATUS:", r.status_code)
        try:
            data=r.json()
            print(json.dumps({k:data.get(k) for k in["id","status","link","date","categories"]},ensure_ascii=False,indent=2))
            if r.status_code==201:
                posted_urls.add(norm_url(best["link"]))
                save_posted_urls(posted_urls)
                fp_list = load_json(FINGER_PATH).get("items",[])
                fp_list.append(fingerprint_record(best["title"], best["summary"]))
                if len(fp_list) > 2000:
                    fp_list = fp_list[-1000:]
                save_json(FINGER_PATH, {"items": fp_list})
                domain_last=load_json(DOMAIN_PATH); domain_last[best["domain"]] = time.time(); save_json(DOMAIN_PATH, domain_last)
                print("\n✅ 記事投稿成功！")
                return  # 成功したら終了
        except Exception as e:
            print(f"投稿エラー: {e}")
            print(r.text[:500])
            continue  # エラーの場合は次の候補へ

    print("\n❌ すべての候補記事がファクトチェックまたは投稿に失敗しました。")

if __name__=="__main__":
    main()
