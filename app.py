"""
Armoire — Phase 4 Final
クローゼット登録 & 一覧 & コーデ提案 & コスメ登録 & メイク提案
& プロフィール設定 & お買い物アドバイザー（浪費ストッパー）
"""

import os
import io
import json
import uuid
import datetime
import requests
from pathlib import Path

import streamlit as st
from PIL import Image

# ════════════════════════════════════════════
# シークレット読み込み（st.secrets → 環境変数）
# ════════════════════════════════════════════
def _secret(key: str, default: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)

SUPABASE_URL     = _secret("SUPABASE_URL")
SUPABASE_KEY     = _secret("SUPABASE_KEY")
GEMINI_API_KEY_ENV = _secret("GEMINI_API_KEY")
OPENWEATHER_KEY  = _secret("OPENWEATHER_API_KEY")
OPENWEATHER_CITY = "Tokyo"
STORAGE_BUCKET   = "images"

def get_api_key() -> str:
    return st.session_state.get("gemini_api_key") or GEMINI_API_KEY_ENV

@st.cache_resource
def _get_sb():
    try:
        from supabase import create_client
    except ImportError:
        st.error("❌ supabase パッケージが不足しています。")
        st.stop()
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("❌ SUPABASE_URL / SUPABASE_KEY が未設定です。Streamlit Cloud の Secrets を確認してください。")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ════════════════════════════════════════════
# DB 初期化
# ════════════════════════════════════════════
def init_db():
    """Supabaseのテーブル存在確認"""
    sb = _get_sb()
    missing = []
    for table in ["clothing_items", "cosmetics", "user_profile"]:
        try:
            sb.table(table).select("id").limit(1).execute()
        except Exception:
            missing.append(table)
    if missing:
        st.error(f"⚠️ テーブルが存在しません: {', '.join(missing)}\nSupabase Dashboard → SQL Editor で作成してください。")
        st.stop()
    try:
        res = sb.table("user_profile").select("id").eq("id", 1).execute()
        if not res.data:
            sb.table("user_profile").insert({"id": 1, "updated_at": datetime.datetime.now().isoformat()}).execute()
    except Exception:
        pass

# ════════════════════════════════════════════
# DB — 服・アクセサリー CRUD
# ════════════════════════════════════════════
def save_item(image_url: str, tags: dict) -> int:
    sb  = _get_sb()
    now = datetime.datetime.now().isoformat()
    res = sb.table("clothing_items").insert({
        "image_url":     image_url,
        "category":      tags.get("category"),
        "sub_category":  tags.get("sub_category"),
        "color_main":    tags.get("color_main"),
        "color_sub":     tags.get("color_sub"),
        "material":      tags.get("material"),
        "season":        json.dumps(tags.get("season", []),     ensure_ascii=False),
        "style_tags":    json.dumps(tags.get("style_tags", []), ensure_ascii=False),
        "condition_note": tags.get("condition_note"),
        "created_at":    now,
    }).execute()
    return res.data[0]["id"] if res.data else 0

def fetch_all_items() -> list:
    sb  = _get_sb()
    res = sb.table("clothing_items").select("*").order("created_at", desc=True).execute()
    return res.data or []

def delete_item(item_id: int):
    sb  = _get_sb()
    res = sb.table("clothing_items").select("image_url").eq("id", item_id).execute()
    if res.data:
        delete_storage_image(res.data[0].get("image_url", ""))
    sb.table("clothing_items").delete().eq("id", item_id).execute()

def update_item(item_id: int, tags: dict):
    """アイテムのタグ情報を更新する"""
    sb  = _get_sb()
    res = sb.table("clothing_items").update({
        "category":       tags.get("category"),
        "sub_category":   tags.get("sub_category"),
        "color_main":     tags.get("color_main"),
        "color_sub":      tags.get("color_sub"),
        "material":       tags.get("material"),
        "season":         json.dumps(tags.get("season", []), ensure_ascii=False),
        "style_tags":     json.dumps(tags.get("style_tags", []), ensure_ascii=False),
        "condition_note": tags.get("condition_note"),
    }).eq("id", item_id).execute()
    return res


def update_wear_record(item_id: int):
    sb  = _get_sb()
    now = datetime.datetime.now().isoformat()
    res = sb.table("clothing_items").select("wear_count").eq("id", item_id).execute()
    current = res.data[0]["wear_count"] if res.data else 0
    sb.table("clothing_items").update({"wear_count": current + 1, "last_worn_at": now}).eq("id", item_id).execute()

# ════════════════════════════════════════════
# DB — コスメ CRUD
# ════════════════════════════════════════════
def save_cosmetic(image_url: str, tags: dict) -> int:
    sb  = _get_sb()
    now = datetime.datetime.now().isoformat()
    res = sb.table("cosmetics").insert({
        "image_url":            image_url,
        "category":             tags.get("category"),
        "brand":                tags.get("brand"),
        "product_name":         tags.get("product_name"),
        "color_name":           tags.get("color_name"),
        "color_number":         tags.get("color_number"),
        "finish":               tags.get("finish"),
        "personal_color_match": tags.get("personal_color_match"),
        "notes":                tags.get("notes"),
        "created_at":           now,
    }).execute()
    return res.data[0]["id"] if res.data else 0

def fetch_all_cosmetics() -> list:
    sb  = _get_sb()
    res = sb.table("cosmetics").select("*").order("created_at", desc=True).execute()
    return res.data or []

def delete_cosmetic(cid: int):
    sb  = _get_sb()
    res = sb.table("cosmetics").select("image_url").eq("id", cid).execute()
    if res.data:
        delete_storage_image(res.data[0].get("image_url", ""))
    sb.table("cosmetics").delete().eq("id", cid).execute()

def update_cosmetic(cid: int, tags: dict):
    """コスメのタグ情報を更新する"""
    sb  = _get_sb()
    sb.table("cosmetics").update({
        "category":              tags.get("category"),
        "brand":                 tags.get("brand"),
        "product_name":          tags.get("product_name"),
        "color_name":            tags.get("color_name"),
        "color_number":          tags.get("color_number"),
        "finish":                tags.get("finish"),
        "personal_color_match":  tags.get("personal_color_match"),
        "notes":                 tags.get("notes"),
    }).eq("id", cid).execute()


def update_cosmetic_use(cid: int):
    sb  = _get_sb()
    now = datetime.datetime.now().isoformat()
    res = sb.table("cosmetics").select("use_count").eq("id", cid).execute()
    current = res.data[0]["use_count"] if res.data else 0
    sb.table("cosmetics").update({"use_count": current + 1, "last_used_at": now}).eq("id", cid).execute()

# ════════════════════════════════════════════
# DB — プロフィール CRUD
# ════════════════════════════════════════════
def fetch_profile() -> dict:
    sb  = _get_sb()
    res = sb.table("user_profile").select("*").eq("id", 1).execute()
    return res.data[0] if res.data else {}

def save_profile(profile: dict):
    sb  = _get_sb()
    now = datetime.datetime.now().isoformat()
    sb.table("user_profile").upsert({
        "id":             1,
        "height_cm":      profile.get("height_cm", 165),
        "weight_kg":      profile.get("weight_kg", 52),
        "personal_color": profile.get("personal_color", ""),
        "ideal_style":    profile.get("ideal_style", ""),
        "job":            profile.get("job", ""),
        "lifestyle":      profile.get("lifestyle", ""),
        "updated_at":     now,
    }).execute()

# ════════════════════════════════════════════
# 画像処理
# ════════════════════════════════════════════
def remove_background(image_bytes: bytes) -> bytes:
    try:
        from rembg import remove
        return remove(image_bytes)
    except ImportError:
        st.warning("rembg がインストールされていません。背景透過をスキップします。")
        return image_bytes
    except Exception as e:
        st.warning(f"背景透過処理でエラー: {e}")
        return image_bytes

def upload_image(image_bytes: bytes, prefix: str = "img") -> str:
    """Supabase Storageに画像をアップロードして公開URLを返す"""
    sb = _get_sb()
    ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:8]
    filename = f"{prefix}_{ts}_{uid}.png"
    try:
        sb.storage.from_(STORAGE_BUCKET).upload(
            path=filename,
            file=image_bytes,
            file_options={"content-type": "image/png", "upsert": "true"},
        )
        return sb.storage.from_(STORAGE_BUCKET).get_public_url(filename)
    except Exception as e:
        st.warning(f"⚠️ 画像アップロード失敗: {e}")
        return ""

def delete_storage_image(image_url: str):
    if not image_url:
        return
    try:
        sb = _get_sb()
        filename = image_url.split("/")[-1].split("?")[0]
        sb.storage.from_(STORAGE_BUCKET).remove([filename])
    except Exception:
        pass

# ════════════════════════════════════════════
# Gemini API — 服タグ付け
# ════════════════════════════════════════════
TAGGER_SYSTEM_PROMPT = """
あなたはファッションアイテムを分析する専門家AIです。
送られた服の画像を見て、必ず以下のJSON形式のみで返してください。
余計な説明文・マークダウン記法（```json など）は不要です。JSONだけを返してください。

{
  "category": "トップス または ボトムス または アウター または ワンピース または バッグ または シューズ または アクセサリー または その他",
  "sub_category": "例: Tシャツ、デニムパンツ、トレンチコートなど",
  "color_main": "メインカラー（日本語）",
  "color_sub": "サブカラーがあれば文字列、なければ null",
  "material": "素材の推定（例: コットン、ポリエステル、ウール）",
  "season": ["春","夏","秋","冬"] のうち該当するものを配列で,
  "style_tags": ["カジュアル","フォーマル","フェミニン","ストリート","ナチュラル","クール","エレガント"] から最大3つを配列で,
  "condition_note": "目立った特徴や注意点があれば文字列、なければ null"
}
"""

def analyze_clothing_with_gemini(image_bytes: bytes) -> dict:
    api_key = get_api_key()
    if not api_key:
        st.info("💡 GEMINI_API_KEY が未設定のため、デモ用タグを使用します。")
        return _demo_clothing_tags()
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=TAGGER_SYSTEM_PROMPT,
        )
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        response = model.generate_content(
            [pil_image, "この服のタグ情報をJSONで返してください。"],
            generation_config={"temperature": 0.1},
        )
        raw = _strip_json_fence(response.text.strip())
        return json.loads(raw)
    except json.JSONDecodeError as e:
        st.error(f"AIの返答をJSONとして解析できませんでした: {e}")
        return _demo_clothing_tags()
    except Exception as e:
        st.error(f"Gemini API エラー: {e}")
        return _demo_clothing_tags()

def _demo_clothing_tags() -> dict:
    return {
        "category": "トップス",
        "sub_category": "Tシャツ（デモ）",
        "color_main": "ホワイト",
        "color_sub": None,
        "material": "コットン",
        "season": ["春", "夏"],
        "style_tags": ["カジュアル", "ナチュラル"],
        "condition_note": "デモデータです。GEMINI_API_KEY を設定してください。",
    }

# ════════════════════════════════════════════
# Gemini API — コスメ分析
# ════════════════════════════════════════════
COSMETIC_SYSTEM_PROMPT = """
あなたはコスメ・ビューティーアイテムを分析する専門家AIです。
送られたコスメの画像を見て、必ず以下のJSON形式のみで返してください。
余計な説明文・マークダウン記法は不要です。JSONだけを返してください。

{
  "category": "リップ または アイシャドウ または チーク または ファンデーション または マスカラ または アイライナー または コンシーラー または ハイライター または ブロンザー または スキンケア または ネイル または その他",
  "brand": "ブランド名（推定、不明なら null）",
  "product_name": "商品名（推定、不明なら null）",
  "color_name": "色名（日本語、不明なら null）",
  "color_number": "色番号（あれば文字列、なければ null）",
  "finish": "マット または シマー または グリッター または サテン または クリーム または その他",
  "personal_color_match": "スプリング または サマー または オータム または ウィンター または 複数対応 （最も似合うパーソナルカラーを推定）",
  "notes": "特徴や注意点があれば文字列、なければ null"
}
"""

def analyze_cosmetic_with_gemini(image_bytes: bytes) -> dict:
    api_key = get_api_key()
    if not api_key:
        st.info("💡 GEMINI_API_KEY が未設定のため、デモ用タグを使用します。")
        return _demo_cosmetic_tags()
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=COSMETIC_SYSTEM_PROMPT,
        )
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        response = model.generate_content(
            [pil_image, "このコスメの情報をJSONで返してください。"],
            generation_config={"temperature": 0.1},
        )
        raw = _strip_json_fence(response.text.strip())
        return json.loads(raw)
    except json.JSONDecodeError as e:
        st.error(f"AIの返答をJSONとして解析できませんでした: {e}")
        return _demo_cosmetic_tags()
    except Exception as e:
        st.error(f"Gemini API エラー: {e}")
        return _demo_cosmetic_tags()

def _demo_cosmetic_tags() -> dict:
    return {
        "category": "リップ",
        "brand": "デモブランド",
        "product_name": "デモリップ（デモ）",
        "color_name": "コーラルレッド",
        "color_number": "01",
        "finish": "マット",
        "personal_color_match": "スプリング",
        "notes": "デモデータです。GEMINI_API_KEY を設定してください。",
    }

# ════════════════════════════════════════════
# Gemini API — コーデ提案
# ════════════════════════════════════════════
COORD_SYSTEM_PROMPT = """
あなたはプロのパーソナルスタイリストです。
ユーザーのクローゼット情報・プロフィールをもとに、最高のコーディネートを提案してください。
必ず以下のJSON形式のみで返してください（```json などは不要）。
item_idsには、提案で使用するアイテムのID番号（クローゼット内容の「ID:X」の数値）を必ず入れてください。

{
  "outfits": [
    {
      "title": "コーデのタイトル（例: モノトーンハンサム）",
      "occasion": "シーン（例: 仕事、デート、休日）",
      "items": ["アイテム説明1", "アイテム説明2", ...],
      "item_ids": [服（トップス・ボトムス・アウター・ワンピース）のIDリスト、3〜5点],
      "shoe_ids": [シューズカテゴリーのIDリスト、必ず1点],
      "accessory_ids": [アクセサリーカテゴリーのIDリスト、1〜5点。なければ []],
      "styling_tip": "スタイリングのポイント"
    }
  ],
  "general_advice": "全体的なアドバイス"
}
"""

def suggest_coord_with_gemini(items: list[dict], profile: dict, weather: dict | None = None, tpo: str = "") -> dict:
    api_key = get_api_key()
    if not api_key:
        return {"outfits": [], "general_advice": "APIキーを設定してください。"}
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=COORD_SYSTEM_PROMPT,
        )
        closet_text  = _format_closet_for_prompt(items)
        profile_text = _format_profile_for_prompt(profile)
        if weather:
            weather_text = (
                f"{weather['emoji']} {weather['main_jp']}（{weather['desc_ja']}）"
                f"　気温 {weather['temp']}℃ / 体感 {weather['feels']}℃"
                f"　湿度 {weather['humidity']}%"
            )
        else:
            weather_text = "（天気情報なし）"
        tpo_text = f"【今日のTPO・シーン】\n{tpo}" if tpo else ""
        prompt = f"""
【ユーザープロフィール】
{profile_text}

【今日の天気・気温】
{weather_text}

{tpo_text}

【クローゼット内容】
{closet_text}

上記のクローゼットから実際に着られる具体的なコーデを3パターン提案してください。
【重要】3パターン全て、指定されたTPO・シーン「{tpo}」に合ったコーデにしてください。
今日の天気と気温に必ず合わせてください（雨なら防水・暗色系、寒ければレイヤード等）。
プロフィールの理想スタイル・パーソナルカラーを必ず考慮してください。
【アイテム選定ルール】
- item_ids: 服（トップス・ボトムス・アウター・ワンピース）を3〜5点選ぶこと。バッグは含めないこと。
- shoe_ids: シューズカテゴリーから必ず1点選ぶこと。
- accessory_ids: アクセサリーカテゴリーから1〜5点選ぶこと。なければ空リスト。
"""
        response = model.generate_content(prompt, generation_config={"temperature": 0.7})
        raw = _strip_json_fence(response.text.strip())
        return json.loads(raw)
    except Exception as e:
        st.error(f"Gemini API エラー: {e}")
        return {"outfits": [], "general_advice": str(e)}

# ════════════════════════════════════════════
# Gemini API — メイク提案
# ════════════════════════════════════════════
MAKEUP_SYSTEM_PROMPT = """
あなたはプロのメイクアップアーティスト兼パーソナルカラリストです。
ユーザーのコスメコレクションとプロフィールをもとに、最高のメイクを提案してください。
必ず以下のJSON形式のみで返してください。

{
  "looks": [
    {
      "title": "メイクのタイトル",
      "occasion": "シーン",
      "steps": ["ステップ1", "ステップ2", ...],
      "products_used": ["使用コスメ1", "使用コスメ2", ...],
      "tip": "ポイント"
    }
  ],
  "general_advice": "全体的なアドバイス"
}
"""

def suggest_makeup_with_gemini(cosmetics: list[dict], profile: dict, tpo: str = "") -> dict:
    api_key = get_api_key()
    if not api_key:
        return {"looks": [], "general_advice": "APIキーを設定してください。"}
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=MAKEUP_SYSTEM_PROMPT,
        )
        cosme_text = _format_cosmetics_for_prompt(cosmetics)
        profile_text = _format_profile_for_prompt(profile)
        prompt = f"""
【ユーザープロフィール】
{profile_text}

【コスメコレクション】
{cosme_text}

上記のコスメから実際に使えるメイクルックを3パターン提案してください。
"""
        response = model.generate_content(prompt, generation_config={"temperature": 0.7})
        raw = _strip_json_fence(response.text.strip())
        return json.loads(raw)
    except Exception as e:
        st.error(f"Gemini API エラー: {e}")
        return {"looks": [], "general_advice": str(e)}

# ════════════════════════════════════════════
# Gemini API — お買い物アドバイザー（Phase 4）
# ════════════════════════════════════════════
SHOPPING_SYSTEM_PROMPT = """
あなたは厳しくも愛情深いファッション・ライフスタイルアドバイザーです。
ユーザーが「買おうとしている服」の画像と、現在の持ち物・プロフィールを渡します。
浪費を防ぎ、本当に必要なものだけを買えるよう、客観的かつ辛口に判定してください。

必ず以下のJSON形式のみで返してください（```json などは不要）。

{
  "verdict": "BUY または CAUTION または STOP",
  "verdict_reason": "判定の一言理由（20文字以内）",
  "similarity_score": 0〜100の整数（既存アイテムとの類似度。高いほど「すでに持っている」）,
  "waste_probability": 0〜100の整数（タンスの肥やしになる確率）,
  "advice": "詳細なアドバイス（200〜300文字。愛のある辛口で）",
  "similar_items": ["既存の似たアイテム説明1", "似たアイテム説明2"],
  "outfit_ideas": [
    {
      "title": "コーデタイトル",
      "description": "このアイテムを使ったコーデ説明（手持ちアイテムと組み合わせ）"
    }
  ],
  "cost_performance_note": "コスパ評価（価格が不明な場合はnull）"
}

判定基準:
- BUY: 既存と被りなく、着回しが豊富で、プロフィールのスタイルに合致する
- CAUTION: 一部条件を満たすが懸念点あり。慎重に検討すべき
- STOP: 似たアイテムを既に持っている、着回しが限定的、スタイルに合わない等
"""

def analyze_shopping_with_gemini(
    item_image_bytes: bytes,
    items: list[dict],
    cosmetics: list[dict],
    profile: dict,
    price: float | None,
) -> dict:
    api_key = get_api_key()
    if not api_key:
        return _demo_shopping_result()
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=SHOPPING_SYSTEM_PROMPT,
        )
        pil_image = Image.open(io.BytesIO(item_image_bytes)).convert("RGB")
        closet_text  = _format_closet_for_prompt(items)
        cosme_text   = _format_cosmetics_for_prompt(cosmetics)
        profile_text = _format_profile_for_prompt(profile)
        price_text   = f"¥{price:,.0f}" if price else "未入力"

        prompt = f"""
【ユーザープロフィール】
{profile_text}

【現在のクローゼット（{len(items)}点）】
{closet_text if closet_text else "（まだ登録なし）"}

【現在のコスメ（{len(cosmetics)}点）】
{cosme_text if cosme_text else "（まだ登録なし）"}

【検討中のアイテム価格】
{price_text}

上記の画像のアイテムについて、購入すべきか厳しく判定してください。
着回し案は必ず手持ちのクローゼットアイテムとの具体的な組み合わせで3パターン以上提示してください。
"""
        response = model.generate_content(
            [pil_image, prompt],
            generation_config={"temperature": 0.3},
        )
        raw = _strip_json_fence(response.text.strip())
        return json.loads(raw)
    except json.JSONDecodeError as e:
        st.error(f"AIの返答をJSONとして解析できませんでした: {e}")
        return _demo_shopping_result()
    except Exception as e:
        st.error(f"Gemini API エラー: {e}")
        return _demo_shopping_result()

def _demo_shopping_result() -> dict:
    return {
        "verdict": "CAUTION",
        "verdict_reason": "APIキー未設定のデモ",
        "similarity_score": 60,
        "waste_probability": 40,
        "advice": "デモデータです。GEMINI_API_KEY を設定すると、実際の持ち物と照らし合わせた詳細な判定が受けられます。",
        "similar_items": ["デモ: 類似アイテム例"],
        "outfit_ideas": [
            {"title": "デモコーデ1", "description": "APIキーを設定してリアルな提案を受けましょう。"},
            {"title": "デモコーデ2", "description": "あなたのクローゼットに合わせた着回し案が届きます。"},
            {"title": "デモコーデ3", "description": "プロフィール情報も活用した最適提案が可能です。"},
        ],
        "cost_performance_note": None,
    }

# ════════════════════════════════════════════
# プロンプト用テキスト整形ヘルパー
# ════════════════════════════════════════════
def _format_profile_for_prompt(profile: dict) -> str:
    if not profile:
        return "（プロフィール未設定）"
    return (
        f"身長: {profile.get('height_cm', '不明')}cm / "
        f"体重: {profile.get('weight_kg', '不明')}kg\n"
        f"パーソナルカラー: {profile.get('personal_color', '不明')}\n"
        f"理想のスタイル: {profile.get('ideal_style', '不明')}\n"
        f"仕事: {profile.get('job', '不明')}\n"
        f"ライフスタイル: {profile.get('lifestyle', '不明')}"
    )

def _format_closet_for_prompt(items: list[dict]) -> str:
    if not items:
        return "（クローゼットにアイテムなし）"
    lines = []
    for it in items:
        season = _safe_json_loads(it.get("season", "[]"))
        style  = _safe_json_loads(it.get("style_tags", "[]"))
        lines.append(
            f"- ID:{it.get('id','')} {it.get('category','')} / {it.get('sub_category','')} "
            f"[{it.get('color_main','')}] 素材:{it.get('material','')} "
            f"季節:{','.join(season)} スタイル:{','.join(style)}"
        )
    return "\n".join(lines)

def _format_cosmetics_for_prompt(cosmetics: list[dict]) -> str:
    if not cosmetics:
        return "（コスメ未登録）"
    lines = []
    for c in cosmetics:
        lines.append(
            f"- {c.get('category','')} / {c.get('brand','')} "
            f"{c.get('product_name','')} [{c.get('color_name','')}] "
            f"フィニッシュ:{c.get('finish','')} "
            f"パーソナルカラー適合:{c.get('personal_color_match','')}"
        )
    return "\n".join(lines)

def _strip_json_fence(text: str) -> str:
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


# ════════════════════════════════════════════
# 天気 API（OpenWeatherMap）
# ════════════════════════════════════════════
WEATHER_EMOJI = {
    "Clear":        "☀️",
    "Clouds":       "☁️",
    "Rain":         "🌧",
    "Drizzle":      "🌦",
    "Thunderstorm": "⛈",
    "Snow":         "❄️",
    "Mist":         "🌫",
    "Fog":          "🌫",
    "Haze":         "🌁",
}

WEATHER_JP = {
    "Clear":        "晴れ",
    "Clouds":       "曇り",
    "Rain":         "雨",
    "Drizzle":      "小雨",
    "Thunderstorm": "雷雨",
    "Snow":         "雪",
    "Mist":         "霧",
    "Fog":          "霧",
    "Haze":         "もや",
}

def fetch_forecast(target_date) -> dict | None:
    """OpenWeatherMap 5日間予報から指定日の天気を取得して返す。"""
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/forecast"
            f"?q={OPENWEATHER_CITY}&appid={OPENWEATHER_KEY}"
            f"&units=metric&lang=ja&cnt=40"
        )
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        import datetime as dt
        target_str = target_date.strftime("%Y-%m-%d")
        # 対象日の予報を全て集めて平均
        entries = [e for e in data["list"] if e["dt_txt"].startswith(target_str)]
        if not entries:
            return None
        # 昼12時のデータを優先、なければ最初
        noon = [e for e in entries if "12:00" in e["dt_txt"]]
        entry = noon[0] if noon else entries[len(entries)//2]
        main_en = entry["weather"][0]["main"]
        desc_ja = entry["weather"][0]["description"]
        temp    = entry["main"]["temp"]
        feels   = entry["main"]["feels_like"]
        humidity= entry["main"]["humidity"]
        WEATHER_JP2 = {
            "Clear":"晴れ","Clouds":"曇り","Rain":"雨","Drizzle":"小雨",
            "Thunderstorm":"雷雨","Snow":"雪","Mist":"もや","Fog":"霧","Haze":"もや",
        }
        WEATHER_EMOJI2 = {
            "Clear":"☀️","Clouds":"☁️","Rain":"🌧","Drizzle":"🌦",
            "Thunderstorm":"⛈","Snow":"❄️","Mist":"🌫","Fog":"🌫","Haze":"🌫",
        }
        main_jp = WEATHER_JP2.get(main_en, main_en)
        emoji   = WEATHER_EMOJI2.get(main_en, "🌡")
        return {
            "emoji": emoji, "main_jp": main_jp, "desc_ja": desc_ja,
            "temp": round(temp, 1), "feels": round(feels, 1), "humidity": humidity,
        }
    except Exception:
        return None


def fetch_weather() -> dict | None:
    """OpenWeatherMap から現在の天気を取得して辞書で返す。失敗時は None。"""
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={OPENWEATHER_CITY}&appid={OPENWEATHER_KEY}"
            f"&units=metric&lang=ja"
        )
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        main_en   = data["weather"][0]["main"]        # 例: "Rain"
        desc_ja   = data["weather"][0]["description"] # 例: "小雨"
        temp      = round(data["main"]["temp"])
        feels     = round(data["main"]["feels_like"])
        humidity  = data["main"]["humidity"]
        return {
            "main_en":  main_en,
            "main_jp":  WEATHER_JP.get(main_en, main_en),
            "desc_ja":  desc_ja,
            "emoji":    WEATHER_EMOJI.get(main_en, "🌡"),
            "temp":     temp,
            "feels":    feels,
            "humidity": humidity,
        }
    except Exception as e:
        return None

def _safe_json_loads(val, default=None):
    if default is None:
        default = []
    try:
        return json.loads(val) if val else default
    except Exception:
        return default

# ════════════════════════════════════════════
# UI ヘルパー — バッジ
# ════════════════════════════════════════════
CATEGORY_EMOJI = {
    "トップス": "👕", "ボトムス": "👖", "アウター": "🧥",
    "ワンピース": "👗", "バッグ": "👜", "シューズ": "👟",
    "アクセサリー": "💍", "その他": "📦",
}
SEASON_COLOR = {"春": "#f9a8d4", "夏": "#86efac", "秋": "#fdba74", "冬": "#93c5fd"}

def season_badge(season_str: str) -> str:
    seasons = _safe_json_loads(season_str)
    badges = ""
    for s in seasons:
        color = SEASON_COLOR.get(s, "#e5e7eb")
        badges += (
            f'<span style="background:{color};color:#1f2937;'
            f'font-size:11px;padding:2px 8px;border-radius:9999px;'
            f'margin-right:4px;">{s}</span>'
        )
    return badges

def style_badges(style_str: str) -> str:
    tags = _safe_json_loads(style_str)
    badges = ""
    for t in tags:
        badges += (
            f'<span style="background:#e0e7ff;color:#3730a3;'
            f'font-size:11px;padding:2px 8px;border-radius:9999px;'
            f'margin-right:4px;">{t}</span>'
        )
    return badges

# ════════════════════════════════════════════
# ページ: プロフィール設定
# ════════════════════════════════════════════
def page_profile_settings():
    st.header("👤 プロフィール設定")
    st.caption("あなたの情報を登録して、AIの提案精度を上げましょう。")

    profile = fetch_profile()

    with st.form("profile_form"):
        st.subheader("📏 体型情報")
        col1, col2 = st.columns(2)
        with col1:
            height_cm = st.number_input(
                "身長 (cm)", min_value=140, max_value=200,
                value=int(profile.get("height_cm", 165)), step=1,
            )
        with col2:
            weight_kg = st.number_input(
                "体重 (kg)", min_value=30, max_value=150,
                value=int(profile.get("weight_kg", 52)), step=1,
            )

        st.subheader("🎨 スタイル情報")
        personal_color_options = [
            "スプリングタイプ（イエローベース・明るい）",
            "サマータイプ（ブルーベース・柔らかい）",
            "オータムタイプ（イエローベース・深み）",
            "ウィンタータイプ（ブルーベース・コントラスト強め）",
            "不明・診断未済",
        ]
        current_pc = profile.get("personal_color", personal_color_options[3])
        pc_index = next(
            (i for i, o in enumerate(personal_color_options) if o == current_pc),
            3,
        )
        personal_color = st.selectbox(
            "パーソナルカラー", personal_color_options, index=pc_index
        )

        ideal_style_options = [
            "ハンサム女子（知的・クール・エッジ。過度に可愛くならない）",
            "フェミニン（花柄・ワンピ・可愛らしさ重視）",
            "カジュアルシック（抜け感・リラックスしつつ上品）",
            "ストリート（スニーカー・ビッグシルエット・トレンド感）",
            "ナチュラル（素材感・アース系・ゆったり）",
            "エレガント（上品・高級感・フォーマル寄り）",
            "スポーティ（機能性・動きやすさ・アクティブ）",
            "その他（自由入力）",
        ]
        current_is = profile.get("ideal_style", ideal_style_options[0])
        is_index = next(
            (i for i, o in enumerate(ideal_style_options) if o == current_is),
            0,
        )
        ideal_style = st.selectbox(
            "理想のスタイル", ideal_style_options, index=is_index
        )
        if ideal_style == "その他（自由入力）":
            ideal_style = st.text_input(
                "理想のスタイルを入力してください",
                value=current_is if current_is not in ideal_style_options else "",
            )

        st.subheader("💼 ライフスタイル情報")
        job = st.text_input(
            "お仕事・活動",
            value=profile.get("job", "外資系スポーツアパレルメーカー勤務"),
            placeholder="例: 外資系スポーツアパレルメーカー勤務",
        )
        lifestyle = st.text_area(
            "ライフスタイル・日常の傾向",
            value=profile.get("lifestyle", "子供なし。仕事・友人・自分磨き中心"),
            placeholder="例: 子供なし。仕事・友人・自分磨き中心",
            height=100,
        )

        submitted = st.form_submit_button(
            "💾 プロフィールを保存する", type="primary", use_container_width=True
        )

    if submitted:
        save_profile({
            "height_cm": height_cm,
            "weight_kg": weight_kg,
            "personal_color": personal_color,
            "ideal_style": ideal_style,
            "job": job,
            "lifestyle": lifestyle,
        })
        st.success("✅ プロフィールを保存しました！")
        st.balloons()

    # 現在の設定プレビュー
    st.divider()
    st.subheader("📋 現在の設定")
    updated = profile.get("updated_at", "")
    if updated:
        try:
            dt = datetime.datetime.fromisoformat(updated)
            st.caption(f"最終更新: {dt.strftime('%Y年%m月%d日 %H:%M')}")
        except Exception:
            pass

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.metric("身長", f"{profile.get('height_cm', '未設定')} cm")
        st.metric("パーソナルカラー", profile.get('personal_color', '未設定')[:8] + "…"
                  if len(str(profile.get('personal_color', ''))) > 8 else profile.get('personal_color', '未設定'))
    with col_p2:
        st.metric("体重", f"{profile.get('weight_kg', '未設定')} kg")
    st.info(f"🎯 理想のスタイル: {profile.get('ideal_style', '未設定')}")
    if profile.get("job"):
        st.info(f"💼 仕事: {profile.get('job')}")

# ════════════════════════════════════════════
# ページ: クローゼット登録
# ════════════════════════════════════════════
def page_register():
    st.header("👕 クローゼット登録")
    st.caption("服を撮影またはアップロードしてください。AIが自動でタグを付けます。")

    # session_state 初期化
    if "clothing_tags" not in st.session_state:
        st.session_state["clothing_tags"] = None
    if "clothing_image" not in st.session_state:
        st.session_state["clothing_image"] = None

    input_method = st.radio(
        "画像の入力方法",
        ["📁 ファイルをアップロード", "📷 カメラで撮影"],
        horizontal=True,
    )

    image_bytes = None
    if input_method == "📁 ファイルをアップロード":
        uploaded = st.file_uploader(
            "画像ファイルを選択（JPG / PNG / HEIC）",
            type=["jpg", "jpeg", "png", "heic", "heif", "webp"],
        )
        if uploaded:
            raw = uploaded.getvalue()
            if uploaded.name.lower().endswith((".heic", ".heif")):
                try:
                    import pillow_heif
                    heif_file = pillow_heif.read_heif(raw)
                    pil_img = Image.frombytes(
                        heif_file.mode, heif_file.size, heif_file.data,
                        "raw", heif_file.mode, heif_file.stride,
                    )
                    buf = io.BytesIO()
                    pil_img.save(buf, format="PNG")
                    image_bytes = buf.getvalue()
                except Exception as e:
                    st.warning(f"HEIC変換失敗: {e}")
                    image_bytes = raw
            else:
                image_bytes = raw
    else:
        camera_img = st.camera_input("服を画面に映して撮影してください")
        if camera_img:
            image_bytes = camera_img.getvalue()

    if not image_bytes:
        st.info("画像を入力すると、AIが自動でタグ付けして登録します。")
        st.session_state["clothing_tags"] = None
        st.session_state["clothing_image"] = None
        return

    col_orig, col_removed = st.columns(2)
    with col_orig:
        st.subheader("元画像")
        st.image(image_bytes, use_container_width=True)

    with st.spinner("🖼 背景を透過中..."):
        processed_bytes = remove_background(image_bytes)

    with col_removed:
        st.subheader("背景透過後")
        st.image(processed_bytes, use_container_width=True)

    st.divider()

    # ── Step1: AIタグ付けボタン ──
    if not st.session_state.get("clothing_tags"):
        with st.spinner("🤖 AIが服を分析中..."):
            tags = analyze_clothing_with_gemini(processed_bytes)
        st.session_state["clothing_tags"] = tags
        st.session_state["clothing_image"] = processed_bytes

    # ── Step2: タグ編集＆保存（session_stateにタグがある場合に表示）──
    if st.session_state.get("clothing_tags"):
        tags = st.session_state["clothing_tags"]

        st.subheader("🏷 取得したタグ情報")
        c1, c2, c3 = st.columns(3)
        CATS = ["トップス", "ボトムス", "アウター", "ワンピース",
                "バッグ", "シューズ", "アクセサリー", "その他"]
        with c1:
            tags["category"] = st.selectbox(
                "カテゴリー", CATS,
                index=CATS.index(tags.get("category")) if tags.get("category") in CATS else 7,
                key="cl_category",
            )
            tags["sub_category"] = st.text_input(
                "サブカテゴリー", value=tags.get("sub_category") or "", key="cl_sub"
            )
        with c2:
            tags["color_main"] = st.text_input(
                "メインカラー", value=tags.get("color_main") or "", key="cl_color_main"
            )
            tags["color_sub"] = st.text_input(
                "サブカラー", value=tags.get("color_sub") or "", key="cl_color_sub"
            )
        with c3:
            tags["material"] = st.text_input(
                "素材", value=tags.get("material") or "", key="cl_material"
            )

        season_opts = ["春", "夏", "秋", "冬"]
        current_season = _safe_json_loads(
            tags.get("season") if isinstance(tags.get("season"), str)
            else json.dumps(tags.get("season", []))
        )
        tags["season"] = st.multiselect("季節", season_opts, default=current_season, key="cl_season")

        style_opts = ["カジュアル", "フォーマル", "フェミニン",
                      "ストリート", "ナチュラル", "クール", "エレガント"]
        current_style = _safe_json_loads(
            tags.get("style_tags") if isinstance(tags.get("style_tags"), str)
            else json.dumps(tags.get("style_tags", []))
        )
        tags["style_tags"] = st.multiselect("スタイルタグ", style_opts, default=current_style, key="cl_style")
        tags["condition_note"] = st.text_area(
            "メモ・特記事項", value=tags.get("condition_note") or "", height=80, key="cl_note"
        )

        st.divider()
        if st.button("💾 この内容でDBに保存する", type="primary", use_container_width=True, key="cl_save"):
            with st.spinner("☁️ 画像をクラウドに保存中..."):
                image_url = upload_image(st.session_state["clothing_image"], "clothing")
            item_id = save_item(image_url, tags)
            st.success(f"✅ 登録完了！（ID: {item_id}）クローゼット一覧で確認できます。")
            st.session_state["clothing_tags"] = None
            st.session_state["clothing_image"] = None
            st.balloons()

# ════════════════════════════════════════════
# ページ: クローゼット一覧
# ════════════════════════════════════════════
def page_list():
    st.header("👗 クローゼット一覧")
    items = fetch_all_items()

    if not items:
        st.info("まだ服が登録されていません。「クローゼット登録」から追加してください。")
        return

    with st.expander("🔍 絞り込みフィルター", expanded=False):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            filter_cat = st.multiselect(
                "カテゴリー",
                ["トップス", "ボトムス", "アウター", "ワンピース",
                 "バッグ", "シューズ", "アクセサリー", "その他"],
            )
        with col_f2:
            filter_season = st.multiselect("季節", ["春", "夏", "秋", "冬"])
        with col_f3:
            filter_style = st.multiselect(
                "スタイル",
                ["カジュアル", "フォーマル", "フェミニン",
                 "ストリート", "ナチュラル", "クール", "エレガント"],
            )

    def item_matches(item):
        if filter_cat and item.get("category") not in filter_cat:
            return False
        if filter_season:
            s_list = _safe_json_loads(item.get("season", "[]"))
            if not any(s in s_list for s in filter_season):
                return False
        if filter_style:
            t_list = _safe_json_loads(item.get("style_tags", "[]"))
            if not any(t in t_list for t in filter_style):
                return False
        return True

    filtered = [it for it in items if item_matches(it)]
    st.caption(f"全 {len(items)} 件 → 表示中 {len(filtered)} 件")

    if not filtered:
        st.warning("条件に一致するアイテムがありません。")
        return

    COLS = 3
    for i in range(0, len(filtered), COLS):
        cols = st.columns(COLS)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(filtered):
                break
            with col:
                _render_item_card(filtered[idx])

def _render_item_card(item: dict):
    img_path = item.get("image_url") or ""
    emoji = CATEGORY_EMOJI.get(item.get("category", ""), "📦")

    if img_path and img_path.startswith("http"):
        st.image(img_path, use_container_width=True)
    else:
        st.markdown(
            f'<div style="background:#f3f4f6;height:160px;display:flex;'
            f'align-items:center;justify-content:center;border-radius:8px;'
            f'font-size:48px;">{emoji}</div>',
            unsafe_allow_html=True,
        )

    cat = item.get("category") or "不明"
    sub = item.get("sub_category") or ""
    color = item.get("color_main") or ""
    material = item.get("material") or ""
    season_html = season_badge(item.get("season", "[]"))
    style_html  = style_badges(item.get("style_tags", "[]"))
    note = item.get("condition_note") or ""

    st.markdown(f"""
    <div style="padding:8px 2px 12px;">
      <p style="font-weight:500;font-size:14px;margin:0 0 2px;">
        {emoji} {cat}
        {'<span style="color:#6b7280;font-size:12px;"> / ' + sub + '</span>' if sub else ''}
      </p>
      {'<p style="font-size:12px;color:#374151;margin:2px 0;">🎨 ' + color + ('　' + material if material else '') + '</p>' if color else ''}
      <div style="margin:4px 0;">{season_html}</div>
      <div style="margin:4px 0;">{style_html}</div>
      {'<p style="font-size:11px;color:#9ca3af;margin:4px 0 0;">' + note + '</p>' if note else ''}
    </div>
    """, unsafe_allow_html=True)

    with st.expander("⚙ 操作", expanded=False):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("👕 着用記録", key=f"wear_{item['id']}", use_container_width=True):
                update_wear_record(item["id"])
                st.success("記録しました！")
                st.rerun()
        with col_b:
            edit_key = f"edit_mode_{item['id']}"
            if st.button("✏️ 編集", key=f"edit_{item['id']}", use_container_width=True):
                st.session_state[edit_key] = not st.session_state.get(edit_key, False)
        with col_c:
            if st.button("🗑 削除", key=f"del_{item['id']}", use_container_width=True):
                delete_item(item["id"])
                st.success("削除しました。")
                st.rerun()

    # 編集フォーム
    if st.session_state.get(f"edit_mode_{item['id']}", False):
        st.markdown("---")
        st.markdown("**✏️ アイテム情報を編集**")

        cat_opts = ["トップス", "ボトムス", "アウター", "ワンピース",
                    "バッグ", "シューズ", "アクセサリー", "その他"]
        e_cat = st.selectbox("カテゴリー", cat_opts,
                              index=cat_opts.index(item.get("category","その他"))
                              if item.get("category") in cat_opts else 0,
                              key=f"ecat_{item['id']}")
        e_sub = st.text_input("サブカテゴリー", value=item.get("sub_category") or "",
                               key=f"esub_{item['id']}")
        e_color = st.text_input("メインカラー", value=item.get("color_main") or "",
                                 key=f"ecol_{item['id']}")
        e_material = st.text_input("素材", value=item.get("material") or "",
                                    key=f"emat_{item['id']}")

        season_opts = ["春", "夏", "秋", "冬"]
        current_season = _safe_json_loads(item.get("season", "[]"))
        e_season = st.multiselect("季節", season_opts, default=current_season,
                                   key=f"esea_{item['id']}")

        style_opts = ["カジュアル", "フォーマル", "フェミニン",
                      "ストリート", "ナチュラル", "クール", "エレガント"]
        current_style = _safe_json_loads(item.get("style_tags", "[]"))
        e_style = st.multiselect("スタイルタグ", style_opts, default=current_style,
                                  key=f"esty_{item['id']}")

        e_note = st.text_area("メモ・特記事項（コーデ提案の参考になります）",
                               value=item.get("condition_note") or "",
                               height=80, key=f"enote_{item['id']}")

        if st.button("💾 変更を保存", type="primary",
                     use_container_width=True, key=f"esave_{item['id']}"):
            updated_tags = {
                "category": e_cat,
                "sub_category": e_sub,
                "color_main": e_color,
                "material": e_material,
                "season": e_season,
                "style_tags": e_style,
                "condition_note": e_note,
            }
            update_item(item["id"], updated_tags)
            st.success("✅ 更新しました！")
            st.session_state[f"edit_mode_{item['id']}"] = False
            st.rerun()

# ════════════════════════════════════════════
# ページ: コーデ提案
# ════════════════════════════════════════════
def page_suggest():
    st.header("✨ おすすめコーデ提案")
    st.caption("AIがあなたのクローゼットとプロフィールから最適なコーデを提案します。")

    items   = fetch_all_items()
    profile = fetch_profile()

    if not items:
        st.warning("クローゼットにアイテムがありません。まず服を登録してください。")
        return

    # ── 天気ブロック ──
    st.markdown("### 🌍 日付と天気")

    import datetime as _dt
    today = _dt.date.today()
    date_options = [today + _dt.timedelta(days=i) for i in range(5)]
    date_labels = []
    for d in date_options:
        if d == today:
            date_labels.append(f"今日 ({d.strftime('%m/%d')})")
        elif d == today + _dt.timedelta(days=1):
            date_labels.append(f"明日 ({d.strftime('%m/%d')})")
        else:
            date_labels.append(d.strftime("%m/%d (%a)"))

    selected_label = st.selectbox("📅 日付を選択", date_labels, key="date_select")
    selected_date  = date_options[date_labels.index(selected_label)]

    if st.session_state.get("weather_date") != str(selected_date):
        st.session_state["weather_date"]    = str(selected_date)
        st.session_state["weather_main_jp"] = None
        st.session_state["weather_data"]    = None

    if st.session_state.get("weather_main_jp") is None:
        with st.spinner("天気情報を取得中..."):
            if selected_date == today:
                w = fetch_weather()
            else:
                w = fetch_forecast(selected_date)
        if w:
            st.session_state["weather_main_jp"] = w["main_jp"]
            st.session_state["weather_temp"]    = w["temp"]
            st.session_state["weather_data"]    = w
            st.success(
                f"{w['emoji']} {w['main_jp']}（{w['desc_ja']}）　"
                f"気温 {w['temp']}℃ / 体感 {w['feels']}℃　湿度 {w['humidity']}%"
            )
        else:
            st.warning("天気の取得に失敗しました。手動で入力してください。")

    # 天気・気温の手動上書き入力
    WEATHER_OPTIONS = ["晴れ", "曇り", "小雨", "雨", "雷雨", "雪", "霧", "もや"]
    default_weather = st.session_state.get("weather_main_jp", "晴れ")
    default_temp    = st.session_state.get("weather_temp", 20)

    w_idx = WEATHER_OPTIONS.index(default_weather) if default_weather in WEATHER_OPTIONS else 0

    col_w1, col_w2 = st.columns(2)
    with col_w1:
        selected_weather = st.selectbox(
            "☀️ 天気",
            WEATHER_OPTIONS,
            index=w_idx,
            key="weather_select",
        )
    with col_w2:
        selected_temp = st.number_input(
            "🌡 気温 (℃)",
            min_value=-20,
            max_value=45,
            value=int(default_temp),
            step=1,
            key="weather_temp_input",
        )

    # 選択値から weather dict を組み立て（手動上書き対応）
    stored_weather = st.session_state.get("weather_data")
    if stored_weather and stored_weather.get("main_jp") == selected_weather:
        # APIデータそのままに気温だけ上書き
        weather_for_ai = dict(stored_weather)
        weather_for_ai["temp"] = selected_temp
    else:
        # 手動入力モード
        weather_for_ai = {
            "emoji":    next((v for k,v in WEATHER_EMOJI.items()
                              if WEATHER_JP.get(k) == selected_weather), "🌡"),
            "main_jp":  selected_weather,
            "desc_ja":  selected_weather,
            "temp":     selected_temp,
            "feels":    selected_temp,
            "humidity": 0,
        }

    st.divider()

    # ── TPO選択 ──
    st.markdown("### 👔 TPO・シーン")
    TPO_OPTIONS = [
        "オフィス・仕事", "商談・プレゼン", "カジュアルデート",
        "友人とのランチ・お出かけ", "週末お出かけ", "スポーツ・アクティブ",
        "パーティー・特別な席", "旅行", "自宅リラックス"
    ]
    selected_tpo = st.selectbox("🎯 今日のシーン", TPO_OPTIONS, key="tpo_select")

    st.divider()

    with st.expander("📋 プロフィール確認", expanded=False):
        st.text(_format_profile_for_prompt(profile))

    st.info(f"クローゼット {len(items)} 点 ✕ 天気「{selected_weather} {selected_temp}℃」でコーデを提案します。")

    if st.button("✨ AIにコーデを提案してもらう", type="primary", use_container_width=True):
        with st.spinner("🤖 スタイリスト AI がコーデを考えています..."):
            result = suggest_coord_with_gemini(items, profile, weather_for_ai, tpo=selected_tpo)
            st.session_state["coord_result"] = result
            st.session_state["stylist_chat"] = []  # 新しい提案ごとにチャットリセット

    # ── コーデ結果表示（session_stateから常に再描画）──
    if st.session_state.get("coord_result"):
        outfits = st.session_state["coord_result"].get("outfits", [])
        advice  = st.session_state["coord_result"].get("general_advice", "")

        if advice:
            st.info(f"💬 {advice}")

        # IDをキーにした画像辞書を作成（高速ルックアップ用）
        item_image_map = {it["id"]: it.get("image_url", "") for it in items if it.get("id")}

        for i, outfit in enumerate(outfits):
            with st.expander(
                f"🎨 コーデ {i+1}: {outfit.get('title', '')} — {outfit.get('occasion', '')}",
                expanded=True,
            ):
                outfit_items = outfit.get("items", [])
                item_ids     = outfit.get("item_ids", [])

                # アイテムリスト＋サムネイル表示
                for oi in outfit_items:
                    st.markdown(f"- {oi}")

                # item_ids に一致する画像をサムネイル表示
                if item_ids:
                    thumb_urls = []
                    for iid in item_ids:
                        url = item_image_map.get(int(iid) if isinstance(iid, (int, float)) else iid, "")
                        if url and url.startswith("http"):
                            thumb_urls.append(url)
                    if thumb_urls:
                        st.markdown("**📸 使用アイテム**")
                        cols = st.columns(min(len(thumb_urls), 4))
                        for j, url in enumerate(thumb_urls[:4]):
                            with cols[j]:
                                st.image(url, use_container_width=True)

                tip = outfit.get("styling_tip", "")
                if tip:
                    st.success(f"💡 ポイント: {tip}")

        # ── スタイリストへの追加質問 ──
        st.divider()
        st.markdown("### 💬 スタイリストに質問する")
        st.caption("提案されたコーデについて、さらに詳しく聞いてみましょう。")

        if "stylist_chat" not in st.session_state:
            st.session_state["stylist_chat"] = []

        # チャット履歴表示
        for msg in st.session_state["stylist_chat"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # 質問入力
        if question := st.chat_input("例：Tシャツはインする？出す？どちらがいい？"):
            st.session_state["stylist_chat"].append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            # AIに質問
            with st.chat_message("assistant"):
                with st.spinner("スタイリストが考えています..."):
                    try:
                        import google.generativeai as genai
                        genai.configure(api_key=get_api_key())
                        model = genai.GenerativeModel(
                            model_name="gemini-2.5-flash",
                            system_instruction=COORD_SYSTEM_PROMPT,
                        )
                        # コンテキストとして提案結果と質問を渡す
                        context = f"提案したコーデ内容：\n{st.session_state.get('coord_result', {})}\n\nユーザープロフィール：\n{_format_profile_for_prompt(profile)}"
                        chat_prompt = f"{context}\n\n上記のコーデ提案を踏まえて、以下の質問に答えてください：\n{question}"
                        resp = model.generate_content(chat_prompt, generation_config={"temperature": 0.7})
                        answer = resp.text.strip()
                    except Exception as e:
                        answer = f"エラーが発生しました：{e}"
                st.markdown(answer)
                st.session_state["stylist_chat"].append({"role": "assistant", "content": answer})

# ════════════════════════════════════════════
# ページ: コスメ登録
# ════════════════════════════════════════════
def page_cosmetic_register():
    st.header("💄 マイ・コスメ登録")
    st.caption("コスメを撮影またはアップロードしてください。AIが自動で分析します。")

    # session_state 初期化
    if "cosme_tags" not in st.session_state:
        st.session_state["cosme_tags"] = None
    if "cosme_image" not in st.session_state:
        st.session_state["cosme_image"] = None

    input_method = st.radio(
        "画像の入力方法",
        ["📁 ファイルをアップロード", "📷 カメラで撮影"],
        horizontal=True,
        key="cosme_input",
    )

    image_bytes = None
    if input_method == "📁 ファイルをアップロード":
        uploaded = st.file_uploader(
            "コスメ画像を選択（JPG / PNG / HEIC）",
            type=["jpg", "jpeg", "png", "heic", "heif", "webp"],
            key="cosme_upload",
        )
        if uploaded:
            raw = uploaded.getvalue()
            if uploaded.name.lower().endswith((".heic", ".heif")):
                try:
                    import pillow_heif
                    heif_file = pillow_heif.read_heif(raw)
                    pil_img = Image.frombytes(
                        heif_file.mode, heif_file.size, heif_file.data,
                        "raw", heif_file.mode, heif_file.stride,
                    )
                    buf = io.BytesIO()
                    pil_img.save(buf, format="PNG")
                    image_bytes = buf.getvalue()
                except Exception as e:
                    st.warning(f"HEIC変換失敗: {e}")
                    image_bytes = raw
            else:
                image_bytes = raw
    else:
        camera_img = st.camera_input("コスメを撮影してください", key="cosme_cam")
        if camera_img:
            image_bytes = camera_img.getvalue()

    if not image_bytes:
        st.info("コスメの画像を入力してください。AIが自動で情報を抽出します。")
        st.session_state["cosme_tags"] = None
        st.session_state["cosme_image"] = None
        return

    st.image(image_bytes, caption="アップロード画像", use_container_width=True)

    st.divider()

    # ── Step1: AI分析ボタン ──
    if st.button("✨ AIに分析してもらう", type="primary", use_container_width=True, key="cosme_analyze"):
        with st.spinner("🤖 AIがコスメを分析中..."):
            tags = analyze_cosmetic_with_gemini(image_bytes)
        st.session_state["cosme_tags"] = tags
        st.session_state["cosme_image"] = image_bytes

    # ── Step2: タグ編集＆保存（session_stateにタグがある場合に表示）──
    if st.session_state.get("cosme_tags"):
        tags = st.session_state["cosme_tags"]

        st.subheader("🏷 取得したタグ情報")
        COSME_CATS = ["リップ", "アイシャドウ", "チーク", "ファンデーション",
                      "マスカラ", "アイライナー", "コンシーラー", "ハイライター",
                      "ブロンザー", "スキンケア", "ネイル", "その他"]
        c1, c2 = st.columns(2)
        with c1:
            tags["category"] = st.selectbox(
                "カテゴリー", COSME_CATS,
                index=COSME_CATS.index(tags.get("category")) if tags.get("category") in COSME_CATS else 11,
                key="cosme_cat",
            )
            tags["brand"]        = st.text_input("ブランド名", value=tags.get("brand") or "", key="cosme_brand")
            tags["product_name"] = st.text_input("商品名", value=tags.get("product_name") or "", key="cosme_pname")
        with c2:
            tags["color_name"]   = st.text_input("色名", value=tags.get("color_name") or "", key="cosme_cname")
            tags["color_number"] = st.text_input("色番号", value=tags.get("color_number") or "", key="cosme_cnum")
            FINISH_OPTS = ["マット", "シマー", "グリッター", "サテン", "クリーム", "その他"]
            tags["finish"] = st.selectbox(
                "フィニッシュ", FINISH_OPTS,
                index=FINISH_OPTS.index(tags.get("finish")) if tags.get("finish") in FINISH_OPTS else 5,
                key="cosme_finish",
            )
        PC_OPTS = ["スプリング", "サマー", "オータム", "ウィンター", "複数対応"]
        tags["personal_color_match"] = st.selectbox(
            "パーソナルカラー適合", PC_OPTS,
            index=PC_OPTS.index(tags.get("personal_color_match")) if tags.get("personal_color_match") in PC_OPTS else 4,
            key="cosme_pc",
        )
        tags["notes"] = st.text_area(
            "メモ", value=tags.get("notes") or "", height=80, key="cosme_notes"
        )

        st.divider()
        if st.button("💾 コスメを登録する", type="primary", use_container_width=True, key="cosme_save"):
            with st.spinner("☁️ 画像をクラウドに保存中..."):
                image_url = upload_image(st.session_state["cosme_image"], "cosme")
            cid = save_cosmetic(image_url, tags)
            st.success(f"✅ 登録完了！（ID: {cid}）コスメ一覧で確認できます。")
            st.session_state["cosme_tags"] = None
            st.session_state["cosme_image"] = None
            st.balloons()

# ════════════════════════════════════════════
# ページ: コスメ一覧
# ════════════════════════════════════════════
def page_cosmetic_list():
    st.header("🧴 マイ・コスメ一覧")
    cosmetics = fetch_all_cosmetics()

    if not cosmetics:
        st.info("まだコスメが登録されていません。「マイ・コスメ登録」から追加してください。")
        return

    with st.expander("🔍 絞り込みフィルター", expanded=False):
        col_f1, col_f2 = st.columns(2)
        COSME_CATS = ["リップ", "アイシャドウ", "チーク", "ファンデーション",
                      "マスカラ", "アイライナー", "コンシーラー", "ハイライター",
                      "ブロンザー", "スキンケア", "ネイル", "その他"]
        with col_f1:
            filter_cosme_cat = st.multiselect("カテゴリー", COSME_CATS, key="filter_cosme_cat")
        with col_f2:
            PC_OPTS = ["スプリング", "サマー", "オータム", "ウィンター", "複数対応"]
            filter_pc = st.multiselect("パーソナルカラー適合", PC_OPTS, key="filter_pc")

    filtered = [
        c for c in cosmetics
        if (not filter_cosme_cat or c.get("category") in filter_cosme_cat)
        and (not filter_pc or c.get("personal_color_match") in filter_pc)
    ]
    st.caption(f"全 {len(cosmetics)} 件 → 表示中 {len(filtered)} 件")

    # 今日使ったコスメ一括登録
    st.divider()
    with st.expander("💋 今日使ったコスメを記録する", expanded=False):
        used_ids = st.multiselect(
            "今日使ったコスメを選択",
            options=[c["id"] for c in cosmetics],
            format_func=lambda cid: next(
                (f"{c.get('brand','')} {c.get('product_name','')} [{c.get('color_name','')}]"
                 for c in cosmetics if c["id"] == cid), str(cid)
            ),
        )
        if st.button("✅ 使用履歴を記録", use_container_width=True):
            recorded = 0
            for cid in used_ids:
                try:
                    update_cosmetic_use(int(cid))
                    recorded += 1
                except Exception:
                    pass
            st.success(f"🎉 {recorded}点のコスメ使用履歴を更新しました！")
            st.balloons()

    COLS = 3
    for i in range(0, len(filtered), COLS):
        cols = st.columns(COLS)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(filtered):
                break
            c = filtered[idx]
            with col:
                image_url = c.get("image_url", "")
                if image_url and image_url.startswith("http"):
                    st.image(image_url, use_container_width=True)
                else:
                    st.markdown(
                        '<div style="background:#fdf2f8;height:120px;display:flex;'
                        'align-items:center;justify-content:center;border-radius:8px;'
                        'font-size:36px;">💄</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(f"""
                <div style="padding:4px 0 8px;">
                  <p style="font-weight:600;font-size:13px;margin:0;">
                    {c.get('brand','')} {c.get('product_name','')}
                  </p>
                  <p style="font-size:12px;color:#6b7280;margin:2px 0;">
                    {c.get('category','')} / {c.get('color_name','')}
                  </p>
                  <p style="font-size:11px;color:#9ca3af;margin:0;">
                    使用回数: {c.get('use_count', 0)}回
                  </p>
                </div>
                """, unsafe_allow_html=True)
                with st.expander("⚙ 操作", expanded=False):
                    col_e, col_d = st.columns(2)
                    with col_e:
                        edit_key = f"edit_cosme_{c['id']}"
                        if st.button("✏️ 編集", key=f"editbtn_cosme_{c['id']}", use_container_width=True):
                            st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                    with col_d:
                        if st.button("🗑 削除", key=f"del_cosme_{c['id']}", use_container_width=True):
                            delete_cosmetic(c["id"])
                            st.success("削除しました。")
                            st.rerun()

                # コスメ編集フォーム
                if st.session_state.get(f"edit_cosme_{c['id']}", False):
                    st.markdown("---")
                    st.markdown("**✏️ コスメ情報を編集**")
                    cosme_cats = ["ベースメイク", "アイメイク", "リップ", "チーク",
                                  "ハイライト・シェーディング", "ネイル", "スキンケア", "その他"]
                    current_cat = c.get("category", "その他")
                    ec_cat = st.selectbox("カテゴリー", cosme_cats,
                                          index=cosme_cats.index(current_cat) if current_cat in cosme_cats else 0,
                                          key=f"ec_cat_{c['id']}")
                    ec_brand = st.text_input("ブランド", value=c.get("brand") or "", key=f"ec_brand_{c['id']}")
                    ec_name  = st.text_input("品名", value=c.get("product_name") or "", key=f"ec_name_{c['id']}")
                    ec_color = st.text_input("カラー名", value=c.get("color_name") or "", key=f"ec_color_{c['id']}")
                    ec_num   = st.text_input("カラー番号", value=c.get("color_number") or "", key=f"ec_num_{c['id']}")
                    finish_opts = ["マット", "セミマット", "グロス", "シマー", "ラメ", "自然な艶", "その他"]
                    current_finish = c.get("finish", "その他")
                    ec_finish = st.selectbox("仕上がり", finish_opts,
                                             index=finish_opts.index(current_finish) if current_finish in finish_opts else 0,
                                             key=f"ec_finish_{c['id']}")
                    pc_opts = ["◎ ベスト", "○ 良い", "△ 普通", "× 合わない"]
                    current_pc = c.get("personal_color_match", "○ 良い")
                    ec_pc = st.selectbox("パーソナルカラー適合性", pc_opts,
                                         index=pc_opts.index(current_pc) if current_pc in pc_opts else 1,
                                         key=f"ec_pc_{c['id']}")
                    ec_notes = st.text_area("メモ・特記事項", value=c.get("notes") or "",
                                            height=80, key=f"ec_notes_{c['id']}")

                    if st.button("💾 変更を保存", type="primary",
                                 use_container_width=True, key=f"ec_save_{c['id']}"):
                        update_cosmetic(c["id"], {
                            "category": ec_cat,
                            "brand": ec_brand,
                            "product_name": ec_name,
                            "color_name": ec_color,
                            "color_number": ec_num,
                            "finish": ec_finish,
                            "personal_color_match": ec_pc,
                            "notes": ec_notes,
                        })
                        st.success("✅ 更新しました！")
                        st.session_state[f"edit_cosme_{c['id']}"] = False
                        st.rerun()

# ════════════════════════════════════════════
# ページ: メイク提案
# ════════════════════════════════════════════
def page_makeup():
    st.header("💋 メイク・ビューティー提案")
    st.caption("AIがコスメコレクションとプロフィールから最適なメイクを提案します。")

    cosmetics = fetch_all_cosmetics()
    profile   = fetch_profile()

    if not cosmetics:
        st.warning("コスメが登録されていません。まずコスメを登録してください。")
        return

    with st.expander("📋 プロフィール確認", expanded=False):
        st.text(_format_profile_for_prompt(profile))

    # ── TPO選択 ──
    st.markdown("### 👔 TPO・シーン")
    MAKEUP_TPO = [
        "オフィス・デイリー", "商談・フォーマル", "デート",
        "友人とのランチ・お出かけ", "パーティー・特別な席",
        "週末カジュアル", "スポーツ・アクティブ"
    ]
    selected_makeup_tpo = st.selectbox("🎯 今日のシーン", MAKEUP_TPO, key="makeup_tpo_select")

    st.info(f"コスメ {len(cosmetics)} 点からメイクを提案します。")

    if st.button("💋 AIにメイクを提案してもらう", type="primary", use_container_width=True):
        with st.spinner("🤖 メイクアップアーティスト AI が考えています..."):
            result = suggest_makeup_with_gemini(cosmetics, profile, tpo=selected_makeup_tpo)

        looks  = result.get("looks", [])
        advice = result.get("general_advice", "")

        if advice:
            st.info(f"💬 {advice}")

        for i, look in enumerate(looks):
            with st.expander(
                f"💄 ルック {i+1}: {look.get('title', '')} — {look.get('occasion', '')}",
                expanded=True,
            ):
                steps = look.get("steps", [])
                for s_idx, step in enumerate(steps):
                    st.markdown(f"{s_idx+1}. {step}")
                products = look.get("products_used", [])
                if products:
                    st.markdown("**使用コスメ:**")
                    for p in products:
                        st.markdown(f"- {p}")
                tip = look.get("tip", "")
                if tip:
                    st.success(f"💡 ポイント: {tip}")

# ════════════════════════════════════════════
# ページ: お買い物アドバイザー（Phase 4）
# ════════════════════════════════════════════
def page_shopping_advisor():
    st.header("🛍 お買い物アドバイザー")
    st.caption("購入を迷っているアイテムの写真を見せてください。AIが持ち物と照らし合わせて厳しく判定します。")

    # ── 入力エリア ──
    col_input, col_preview = st.columns([1, 1])

    with col_input:
        st.subheader("📸 検討中のアイテム")
        input_method = st.radio(
            "画像の入力方法",
            ["📁 ファイルをアップロード", "📷 カメラで撮影"],
            horizontal=True,
            key="shopping_input_method",
        )

        image_bytes = None
        if input_method == "📁 ファイルをアップロード":
            uploaded = st.file_uploader(
                "画像ファイルを選択（JPG / PNG）",
                type=["jpg", "jpeg", "png"],
                key="shopping_upload",
            )
            if uploaded:
                image_bytes = uploaded.getvalue()
        else:
            camera_img = st.camera_input(
                "ショップで見つけたアイテムを撮影", key="shopping_cam"
            )
            if camera_img:
                image_bytes = camera_img.getvalue()

        st.subheader("💰 価格（任意）")
        price_input = st.number_input(
            "価格を入力（円）",
            min_value=0,
            max_value=1_000_000,
            value=0,
            step=100,
            help="価格を入力するとコスパも判定します。0のままでも判定できます。",
            key="shopping_price",
        )
        price = float(price_input) if price_input > 0 else None

    with col_preview:
        if image_bytes:
            st.subheader("プレビュー")
            st.image(image_bytes, use_container_width=True)
            if price:
                st.metric("検討価格", f"¥{price:,.0f}")
        else:
            st.markdown("""
            <div style="background:#f8fafc;border:2px dashed #cbd5e1;border-radius:12px;
            height:280px;display:flex;align-items:center;justify-content:center;
            flex-direction:column;color:#94a3b8;font-size:14px;">
              <div style="font-size:48px;margin-bottom:8px;">🛍</div>
              <div>アイテムの画像を入力してください</div>
            </div>
            """, unsafe_allow_html=True)

    if not image_bytes:
        st.info("👆 購入を検討しているアイテムの写真をアップロードまたは撮影してください。")
        return

    st.divider()

    # ── 判定ボタン ──
    if st.button(
        "🤖 AIに購入を相談する", type="primary", use_container_width=True, key="shopping_analyze"
    ):
        items     = fetch_all_items()
        cosmetics = fetch_all_cosmetics()
        profile   = fetch_profile()

        with st.spinner("🧠 AIがあなたのクローゼットと照らし合わせて判定中..."):
            result = analyze_shopping_with_gemini(
                image_bytes, items, cosmetics, profile, price
            )

        _render_shopping_result(result, price)

def _render_shopping_result(result: dict, price: float | None):
    """判定結果をverdictに応じて色を変えて表示する"""
    verdict       = result.get("verdict", "CAUTION")
    verdict_reason = result.get("verdict_reason", "")
    similarity    = result.get("similarity_score", 0)
    waste_prob    = result.get("waste_probability", 0)
    advice        = result.get("advice", "")
    similar_items = result.get("similar_items", [])
    outfit_ideas  = result.get("outfit_ideas", [])
    cost_note     = result.get("cost_performance_note")

    # ── カラー設定 ──
    if verdict == "BUY":
        bg_grad   = "linear-gradient(135deg, #064e3b 0%, #065f46 50%, #047857 100%)"
        accent    = "#10b981"
        text_col  = "#ecfdf5"
        badge_bg  = "#059669"
        badge_text = "✅ BUY — 買って良し！"
        emoji_big = "🛍✨"
        glow      = "0 0 30px rgba(16,185,129,0.4)"
    elif verdict == "STOP":
        bg_grad   = "linear-gradient(135deg, #7f1d1d 0%, #991b1b 50%, #b91c1c 100%)"
        accent    = "#f87171"
        text_col  = "#fff1f2"
        badge_bg  = "#dc2626"
        badge_text = "🚫 STOP — 買わないで！"
        emoji_big = "🛑💸"
        glow      = "0 0 30px rgba(248,113,113,0.4)"
    else:  # CAUTION
        bg_grad   = "linear-gradient(135deg, #78350f 0%, #92400e 50%, #b45309 100%)"
        accent    = "#fbbf24"
        text_col  = "#fffbeb"
        badge_bg  = "#d97706"
        badge_text = "⚠️ CAUTION — 慎重に！"
        emoji_big = "🤔💭"
        glow      = "0 0 30px rgba(251,191,36,0.4)"

    # ── メインヴァーディクトカード ──
    st.markdown(f"""
    <div style="
        background: {bg_grad};
        border-radius: 20px;
        padding: 36px 32px;
        text-align: center;
        box-shadow: {glow}, 0 20px 60px rgba(0,0,0,0.3);
        margin: 24px 0;
    ">
      <div style="font-size:56px;margin-bottom:12px;">{emoji_big}</div>
      <div style="
          display:inline-block;
          background:{badge_bg};
          color:white;
          font-size:22px;
          font-weight:800;
          padding:10px 28px;
          border-radius:50px;
          letter-spacing:1px;
          margin-bottom:16px;
          box-shadow: 0 4px 15px rgba(0,0,0,0.2);
      ">{badge_text}</div>
      <div style="color:{text_col};font-size:16px;opacity:0.9;margin-top:8px;">
        {verdict_reason}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── スコアメトリクス ──
    col_s1, col_s2 = st.columns(2)

    def score_bar(score: int, label: str, danger_high: bool = True):
        """スコアバーを返す"""
        if danger_high:
            color = "#ef4444" if score >= 70 else "#f59e0b" if score >= 40 else "#10b981"
        else:
            color = "#10b981" if score >= 70 else "#f59e0b" if score >= 40 else "#ef4444"
        return f"""
        <div style="margin-bottom:12px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span style="font-size:13px;font-weight:600;">{label}</span>
            <span style="font-size:16px;font-weight:800;color:{color};">{score}%</span>
          </div>
          <div style="background:#e5e7eb;border-radius:999px;height:10px;overflow:hidden;">
            <div style="background:{color};width:{score}%;height:100%;
                        border-radius:999px;transition:width 0.5s;"></div>
          </div>
        </div>
        """

    with col_s1:
        st.markdown(score_bar(similarity, "🔁 既存アイテムとの類似度", danger_high=True),
                    unsafe_allow_html=True)
    with col_s2:
        st.markdown(score_bar(waste_prob, "🗑 タンスの肥やし確率", danger_high=True),
                    unsafe_allow_html=True)

    # ── アドバイス ──
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #1e1b4b, #312e81);
        border-left: 5px solid {accent};
        border-radius: 12px;
        padding: 20px 24px;
        margin: 20px 0;
    ">
      <div style="color:#a5b4fc;font-size:12px;font-weight:700;
                  letter-spacing:2px;margin-bottom:8px;">💬 AIアドバイス</div>
      <div style="color:#e0e7ff;font-size:15px;line-height:1.8;">
        {advice}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 似たアイテム警告 ──
    if similar_items:
        st.markdown("#### ⚠️ 既に持っている似たアイテム")
        for si in similar_items:
            st.markdown(f"""
            <div style="background:#fef3c7;border:1px solid #fcd34d;border-radius:8px;
                        padding:10px 16px;margin:6px 0;font-size:14px;color:#92400e;">
              👗 {si}
            </div>
            """, unsafe_allow_html=True)

    # ── 着回しアイデア ──
    if outfit_ideas:
        st.markdown("#### 👗 手持ちとの着回しアイデア")
        for idx, idea in enumerate(outfit_ideas):
            title = idea.get("title", f"コーデ {idx+1}")
            desc  = idea.get("description", "")
            number_colors = ["#6366f1", "#8b5cf6", "#ec4899", "#14b8a6", "#f59e0b"]
            nc = number_colors[idx % len(number_colors)]
            st.markdown(f"""
            <div style="
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-left: 4px solid {nc};
                border-radius: 12px;
                padding: 16px 20px;
                margin: 10px 0;
                box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            ">
              <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                <div style="
                    background:{nc};color:white;
                    width:28px;height:28px;border-radius:50%;
                    display:flex;align-items:center;justify-content:center;
                    font-weight:800;font-size:13px;flex-shrink:0;
                ">{idx+1}</div>
                <div style="font-weight:700;font-size:15px;color:#1f2937;">{title}</div>
              </div>
              <div style="color:#4b5563;font-size:14px;line-height:1.7;padding-left:38px;">
                {desc}
              </div>
            </div>
            """, unsafe_allow_html=True)

    # ── コスパ評価 ──
    if cost_note:
        st.markdown(f"""
        <div style="
            background: #f0fdf4;
            border: 1px solid #86efac;
            border-radius: 10px;
            padding: 14px 18px;
            margin-top: 16px;
        ">
          <span style="font-weight:700;color:#166534;">💰 コスパ評価：</span>
          <span style="color:#15803d;font-size:14px;">{cost_note}</span>
        </div>
        """, unsafe_allow_html=True)

    # ── 最終判定バナー（もう一度強調） ──
    if verdict == "BUY":
        st.success("🎉 AIの判定: **購入をおすすめします！** あなたのスタイルにぴったりです。")
    elif verdict == "STOP":
        st.error("🛑 AIの判定: **購入を見送ってください。** タンスの肥やしになる可能性が高いです。")
    else:
        st.warning("⚠️ AIの判定: **慎重に検討してください。** メリット・デメリットを十分考えて。")

# ════════════════════════════════════════════
# メイン
# ════════════════════════════════════════════
def main():
    st.set_page_config(
        page_title="Armoire",
        page_icon="👗",
        layout="centered",
        initial_sidebar_state="expanded",
    )

    init_db()

    if "gemini_api_key" not in st.session_state:
        st.session_state["gemini_api_key"] = GEMINI_API_KEY_ENV

    # ─── サイドバー ───
    with st.sidebar:
        st.markdown("""
            <div style="text-align:center;padding:12px 0 8px;">
              <span style="font-size:32px;">👗</span><br>
              <span style="font-size:22px;font-weight:600;letter-spacing:2px;">Armoire</span><br>
              <span style="font-size:12px;color:#9ca3af;">Your personal style intelligence</span>
            </div>
        """, unsafe_allow_html=True)
        st.divider()

        page = st.radio(
            "メニュー",
            [
                "📷 クローゼット登録",
                "👗 クローゼット一覧",
                "✨ おすすめコーデ提案",
                "💄 マイ・コスメ登録",
                "🧴 マイ・コスメ一覧",
                "💋 メイク・ビューティー提案",
                "🛍 お買い物アドバイザー",
                "👤 プロフィール設定",
            ],
            label_visibility="collapsed",
        )
        st.divider()

        st.caption("🔑 Gemini API キー設定")
        st.text_input(
            "APIキー",
            type="password",
            placeholder="AIzaSy...",
            label_visibility="collapsed",
            key="gemini_api_key",
        )

        items     = fetch_all_items()
        cosmetics = fetch_all_cosmetics()
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric("服・アクセ", f"{len(items)} 件")
        with col_m2:
            st.metric("コスメ", f"{len(cosmetics)} 件")

        three_days_ago = (
            datetime.datetime.now() - datetime.timedelta(days=3)
        ).isoformat()
        recently_worn = sum(
            1 for it in items
            if it.get("last_worn_at") and it["last_worn_at"] > three_days_ago
        )
        if recently_worn:
            st.metric("直近3日で着用", f"{recently_worn} 件")

    # ─── メインコンテンツ ───
    if page == "👤 プロフィール設定":
        page_profile_settings()
    elif page == "📷 クローゼット登録":
        page_register()
    elif page == "👗 クローゼット一覧":
        page_list()
    elif page == "✨ おすすめコーデ提案":
        page_suggest()
    elif page == "💄 マイ・コスメ登録":
        page_cosmetic_register()
    elif page == "🧴 マイ・コスメ一覧":
        page_cosmetic_list()
    elif page == "💋 メイク・ビューティー提案":
        page_makeup()
    elif page == "🛍 お買い物アドバイザー":
        page_shopping_advisor()


if __name__ == "__main__":
    main()
