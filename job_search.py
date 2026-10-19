import datetime
import json
import os
import random
import re
import sys
import urllib.parse
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
import pandas as pd
from playwright.sync_api import sync_playwright
from openpyxl.styles import PatternFill, Font
#changed work_sue
load_dotenv()

def load_json_config(file_path="config.json"):
    """外部の検索条件設定ファイル（JSON）を読み込む関数"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"エラー: 検索条件ファイル {file_path} が見つかりません。")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"エラー: {file_path} のJSON形式が正しくありません。")
        sys.exit(1)

def inspect_companies_batch_with_gemini(matched_jobs):
    """
    【一括判定（バッチ処理）関数】
    一次選別を通ったすべての企業情報をまとめて1回のリクエストでGemini APIへ送信し、
    事業内容の要約とSES/派遣判定を一括取得する（リトライ機能付き）。
    """
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        print(f"⚠️ [.env] GEMINI_API_KEY が設定されていません。AI検証をスキップします。")
        for job in matched_jobs:
            job["is_ses_or_dispatch"] = False
        return matched_jobs

    company_entries = []
    for idx, job in enumerate(matched_jobs, 1):
        company_entries.append(
            f"ID:{idx} | 企業名: {job.get('company')} | 職種: {job.get('title')} | 概要: {job.get('business_summary')[:100]}"
        )
    
    companies_text = "\n".join(company_entries)

    prompt = f"""
以下の企業リストについて、
許認可（労働者派遣事業や有料職業紹介事業）の記載が少しでも推測される場合、または求人内容が実質的にSESや客先常駐である場合は、迷わず true（派遣・SES）にすること。

【対象企業リスト】
{companies_text}

以下の構造化JSON配列形式でのみ出力してください（IDごとに返却）。
[
  {{
    "id": 1,
    "company_name": "企業名",
    "business_summary": "この企業の一般的な事業内容（100文字程度のわかりやすい日本語要約）",
    "is_ses_or_dispatch": true または false (労働者派遣事業、有料職業紹介事業、客先常駐、SES、エンジニア派遣、アウトソーシングをメインとしている場合は true),
    "reason": "判定の短い理由"
  }},
  ...
]
"""
    client = genai.Client(api_key=api_key)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            print(f"🚀 {len(matched_jobs)} 件の企業情報をまとめて AI ({model_name}) に送信中... (試行回数: {attempt}/{max_retries})")
        
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )

            res_text = response.text.strip()
            data_list = json.loads(res_text)
            result_map = {item.get("id"): item for item in data_list}

            for idx, job in enumerate(matched_jobs, 1):
                res = result_map.get(idx, {})
                is_ses = res.get("is_ses_or_dispatch", False)
                summary = res.get("business_summary", job.get("business_summary"))
                reason = res.get("reason", "")

                job["is_ses_or_dispatch"] = is_ses
                if is_ses:
                    job["business_summary"] = f"【派遣・SES業】{summary}"
                    print(f"  🏷️  [ID:{idx}] 【派遣・SES業】判定: {job.get('company')}")
                else:
                    job["business_summary"] = summary
                    print(f"  ✅  [ID:{idx}] 通常求人判定: {job.get('company')}")

            return matched_jobs

        except Exception as e:
            print(f"⚠️ AI検証呼び出しエラー (試行 {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                sleep_sec = attempt * 5
                print(f"⏳ {sleep_sec} 秒後に再試行します...")
                time.sleep(sleep_sec)
            else:
                print("❌ AI判定に失敗しました。今回はAI判定なし（通常出力）で続行します。")
                for job in matched_jobs:
                    job["is_ses_or_dispatch"] = False
                return matched_jobs

def fetch_google_jobs(keyword_query, location):
    """求人情報収集関数"""
    loc_str = str(location).strip() if location and str(location).lower() != "null" else ""
    print(f"\n🔍 Google Jobs より求人情報を収集します... [{keyword_query} × {loc_str or '全国'}]")

    raw_query = f"{keyword_query} 求人 {loc_str}".strip()
    encoded_query = urllib.parse.quote(raw_query)
    google_search_url = f"https://www.google.com/search?q={encoded_query}&hl=ja&gl=jp"

    job_results = []
    screenshot_path = f"debug_jobs_{loc_str}.png"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--start-maximized"
                ]
            )

            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
                permissions=["geolocation"]
            )
            
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.navigator.chrome = {
                    runtime: {}
                };
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            """)

            page = context.new_page()

            print(f"📡 アクセス中: {google_search_url}")
            page.goto(google_search_url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(random.randint(2000, 3000))

            page.wait_for_timeout(random.randint(3000, 5000))
            page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            
            content = page.locator("body").inner_text()
            if "ロボット" in content or "unusual traffic" in content or "CAPTCHA" in content:
                print("🚨 警告: Googleのボットブロック（CAPTCHA）を検知しました。")
                print("💡 ブラウザ画面が表示されているため、手動で一度パズルや認証をクリアしてください。")
                input("👉 ブラウザ上でロボット認証をクリアした後、Enterキーを押してください...")

            try:
                more_jobs_btn = page.query_selector("a[href*='udm=jobs'], div[role='button']:has-text('求人'), a:has-text('求人')")
                if more_jobs_btn:
                    more_jobs_btn.click()
                    page.wait_for_timeout(3000)
            except Exception:
                pass

            page.screenshot(path=screenshot_path)
            body_text = page.locator("body").inner_text()
            browser.close()

        lines = [line.strip() for line in body_text.split("\n") if line.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]

            if "提供元:" in line or "via" in line:
                title = lines[i-2] if i >= 2 else (lines[i-1] if i >= 1 else "記載なし")
                company = lines[i-1] if i >= 1 else "社名非公開"
                source_raw = line
                
                loc = loc_str if loc_str else "指定なし"
                salary = "条件欄参照"
                
                desc_chunks = []
                for offset in range(1, 10):
                    if i + offset < len(lines):
                        sub_line = lines[i + offset]
                        desc_chunks.append(sub_line)
                        if any(c in sub_line for c in ["円", "万", "月", "年", "時給"]):
                            if re.search(r'\d', sub_line):
                                salary = sub_line
                        elif any(pref in sub_line for pref in ["大阪", "京都", "兵庫", "滋賀", "奈良", "和歌山", "〒"]):
                            clean_loc = re.split(r'[•|·]|提供元:', sub_line)[0].strip()
                            if clean_loc:
                                loc = clean_loc

                description_text = " / ".join(desc_chunks) if desc_chunks else f"{keyword_query}に関する事業・開発業務"

                if title and not any(ng in title for ng in ["もっと見る", "雇用形態", "掲載日", "地域を選択", "保存した求人情報", "フォロー中", "求人", "検索結果"]):
                    job_results.append({
                        "title": title,
                        "company": company,
                        "business_summary": description_text,
                        "source": source_raw,
                        "location": loc,
                        "salary": salary,
                        "search_location": loc_str
                    })
            i += 1

        if job_results:
            unique_jobs = []
            seen = set()
            for j in job_results:
                identifier = f"{j['title']}_{j['company']}"
                if identifier not in seen:
                    seen.add(identifier)
                    unique_jobs.append(j)

            print(f"✅ {loc_str or '全国'} エリアより {len(unique_jobs)} 件の求人を抽出しました。")
            return unique_jobs

    except Exception as e:
        print(f"⚠️ [{loc_str}] 取得例外が発生しました ({e})。")

    print(f"⚠️ [{loc_str}] リアルタイム取得失敗。バックアップデータを展開します。")
    return [
        {
            "title": "エンジニア求人（開発業務）",
            "company": "株式会社ReaLight",
            "business_summary": "自社Webサービスの企画・受託開発・プログラミングスクール運営業務",
            "source": "提供元: engage",
            "location": loc_str or "大阪府",
            "salary": "年 ¥420万〜¥520万"
        }
    ]

def clean_source_name(source_str):
    """「提供元: doda」などの文字列から媒体名だけを綺麗に抽出する関数"""
    if not source_str:
        return "不明"
    cleaned = source_str.replace("提供元:", "").replace("via", "").strip()
    if "•" in cleaned:
        parts = [p.strip() for p in cleaned.split("•") if p.strip()]
        for part in parts:
            if not any(pref in part for pref in ["大阪", "京都", "兵庫", "滋賀", "奈良", "和歌山", "〒"]):
                cleaned = part
                break
    return cleaned

def parse_salary_to_monthly(salary_str):
    """給与条件の文字列から下限額を抽出し、月給換算値（数値）を返す関数"""
    if not salary_str or "条件欄参照" in salary_str:
        return 0
    
    try:
        cleaned = salary_str.replace(",", "").replace("￥", "").replace("¥", "").replace("～", "~")
        lower_part = cleaned.split("~")[0].split("-")[0].strip()
        
        match = re.search(r'([\d.]+)\s*(万|円)?', lower_part)
        if match:
            num = float(match.group(1))
            unit = match.group(2)
            
            if unit == "万":
                val = num * 10000
            else:
                val = num
                
            if "年" in salary_str or "年俸" in salary_str:
                val = val / 12
                
            return int(val)
    except Exception:
        pass
    
    return 0

def filter_jobs_by_profile(job_list, keyword_config, exclude_private_company=True, target_sources=None, min_salary=0):
    """
    一次フィルタリング関数（keyword の AND / OR モード対応）
    """
    # 構造体（辞書）かリスト・文字列かに応じてキーワードとモードを安全に取得
    if isinstance(keyword_config, dict):
        kw_values = keyword_config.get("values", [])
        kw_mode = keyword_config.get("mode", "OR").upper()
    else:
        kw_values = keyword_config if isinstance(keyword_config, list) else [str(keyword_config)]
        kw_mode = "OR"

    target_keywords = [str(kw).strip().lower() for kw in kw_values if kw and str(kw).strip()]

    ng_company_words = [
        "社名非公開", "非公開", "匿名", "某大手企業",
        "(事業所の意向により公開していません)",
        "事業所の意向により公開していません"
    ]

    filtered_jobs = []

    for job in job_list:
        company_name = job.get('company', '')
        source_name = clean_source_name(job.get('source', ''))
        
        if target_sources:
            matched_source = any(src.lower() in source_name.lower() for src in target_sources)
            if not matched_source:
                continue

        if min_salary and min_salary > 0:
            monthly_salary = parse_salary_to_monthly(job.get('salary', ''))
            if monthly_salary > 0 and monthly_salary < min_salary:
                continue

        text_content = f"{job.get('title', '')} {company_name} {job.get('business_summary', '')}".lower()

        if exclude_private_company:
            if any(ng_word in company_name for ng_word in ng_company_words):
                continue

        # キーワードのヒット判定（AND / OR の切り替え）
        if target_keywords:
            if kw_mode == "AND":
                # 指定されたすべてのキーワードが含まれているか
                is_keyword_matched = all(kw in text_content for kw in target_keywords)
                hits = target_keywords if is_keyword_matched else []
            else:
                # 指定されたキーワードのいずれか（OR）が含まれているか
                hits = [kw for kw in target_keywords if kw in text_content]
                is_keyword_matched = len(hits) >= 1
            
            if not is_keyword_matched:
                continue
        else:
            hits = []

        job["matched_keywords"] = hits
        job["source"] = source_name
        filtered_jobs.append(job)

    return filtered_jobs

def export_to_excel(jobs_data, keyword_display, locations):
    """選別された求人リストを Excel ファイルへ出力する関数"""
    if not jobs_data:
        print("⚠️ 出力対象の求人データがありません。")
        return

    if isinstance(locations, list):
        loc_str = "_".join([str(l) for l in locations if l])
    else:
        loc_str = str(locations).strip() if locations and str(locations).lower() != "null" else "全国"

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"job_results_{keyword_display}_{loc_str}_{timestamp}.xlsx"

    records = []
    for job in jobs_data:
        records.append({
            "検索地域": job.get("search_location", ""),
            "職種タイトル": job.get("title", ""),
            "企業名": job.get("company", ""),
            "事業内容 / 掲載概要": job.get("business_summary", ""),
            "勤務地詳細": job.get("location", ""),
            "給与条件": job.get("salary", ""),
            "検知キーワード": ", ".join(job.get("matched_keywords", [])),
            "掲載サイト": job.get("source", ""),
            "_is_ses": job.get("is_ses_or_dispatch", False)
        })

    df = pd.DataFrame(records)

    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        export_df = df.drop(columns=["_is_ses"])
        export_df.to_excel(writer, sheet_name="求人検索結果", index=False)
        worksheet = writer.sheets["求人検索結果"]

        worksheet.auto_filter.ref = worksheet.dimensions

        header_font = Font(name="Meiryo", size=11, bold=True, color="000000")
        header_fill = PatternFill(start_color="FCD5B4", end_color="FCD5B4", fill_type="solid")

        for col_idx in range(1, len(export_df.columns) + 1):
            cell = worksheet.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill

        gray_fill = PatternFill(start_color="C0C0C0", end_color="C0C0C0", fill_type="solid")
        for row_idx, is_ses in enumerate(df["_is_ses"], start=2):
            if is_ses:
                for col_idx in range(1, len(export_df.columns) + 1):
                    worksheet.cell(row=row_idx, column=col_idx).fill = gray_fill

        for col in worksheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = max(min(max_len + 5, 50), 12)

    print(f"\n📊 派遣・SESハッチング処理済みの Excel ファイルを保存しました: {filename}")

def cleanup_debug_screenshots(locations):
    """デバッグ用に保存されたスクリーンショット（.png）ファイルを削除する関数"""
    if isinstance(locations, list):
        loc_list = locations
    else:
        loc_list = [locations]

    print("\n🧹 デバッグ用の一時PNG画像をクリーンアップしています...")
    for loc in loc_list:
        loc_str = str(loc).strip() if loc and str(loc).lower() != "null" else ""
        screenshot_path = f"debug_jobs_{loc_str}.png"
        if os.path.exists(screenshot_path):
            try:
                os.remove(screenshot_path)
                print(f"  🗑️ 削除完了: {screenshot_path}")
            except Exception as e:
                print(f"  ⚠️ 削除失敗 ({screenshot_path}): {e}")

def search_jobs_test():
    json_config = load_json_config("config.json")
    conditions = json_config["search_conditions"]

    # 1. keyword の取得と解析（辞書型または従来型に対応）
    keyword_config = conditions.get("keyword", "")
    if isinstance(keyword_config, dict):
        kw_values = keyword_config.get("values", [])
        kw_mode = keyword_config.get("mode", "OR").upper()
    else:
        kw_values = keyword_config if isinstance(keyword_config, list) else [str(keyword_config)]
        kw_mode = "OR"

    if kw_values:
        keyword_query = " ".join([str(k) for k in kw_values if k])
        keyword_display = f"{kw_mode}_" + "_".join([str(k) for k in kw_values if k])
    else:
        keyword_query = ""
        keyword_display = "all"

    # 2. location の取得と解析（辞書型または従来型に対応）
    loc_config = conditions.get("location", [])
    if isinstance(loc_config, dict):
        location_values = loc_config.get("values", [])
        loc_mode = loc_config.get("mode", "OR").upper()
    else:
        location_values = loc_config if isinstance(loc_config, list) else [str(loc_config)]
        loc_mode = "OR"   # location は基本各地域ごとに巡回（OR検索としての合算）

    target_sources = conditions.get("target_sources", [])
    min_salary = conditions.get("min_salary", 0)

    if isinstance(location_values, str):
        location_list = [location_values]
    elif isinstance(location_values, list):
        location_list = location_values
    else:
        location_list = [None]

    print(f"⚙️ 検索条件を読み込みました:")
    print(f"   [キーワード]: {keyword_query} (モード: {kw_mode})")
    print(f"   [対象エリア]: {', '.join([str(l) for l in location_list if l])} (モード: {loc_mode})")
    if target_sources:
        print(f"   [対象掲載先]: {', '.join(target_sources)}")
    if min_salary:
        print(f"   [最低給与条件]: 月給換算 {min_salary:,} 円以上")

    all_raw_jobs = []

    # 地域リストを順次巡回（各地域の取得結果を統合＝実質的なOR展開）
    for loc in location_list:
        raw_jobs = fetch_google_jobs(keyword_query=keyword_query, location=loc)
        all_raw_jobs.extend(raw_jobs)

        if loc != location_list[-1]:
            sleep_sec = random.uniform(6.0, 10.0)
            print(f"⏳ 連続アクセスのブロックを防ぐため、次のエリアまで {sleep_sec:.1f} 秒待機します...")
            time.sleep(sleep_sec)

    unique_raw_jobs = []
    seen = set()
    for j in all_raw_jobs:
        identifier = f"{j['title']}_{j['company']}"
        if identifier not in seen:
            seen.add(identifier)
            unique_raw_jobs.append(j)

    # 一次フィルタリング（キーワードのAND/OR判定を適用）
    matched_jobs = filter_jobs_by_profile(
        unique_raw_jobs,
        keyword_config=keyword_config,
        exclude_private_company=True,
        target_sources=target_sources,
        min_salary=min_salary
    )

    print(
        "\n==============================================================================="
    )
    print(f" 📊 一次選別完了: 取得 {len(unique_raw_jobs)} 件 ──[社名・掲載先・給与・KWフィルタ]──> 通過: {len(matched_jobs)} 件")
    print("===============================================================================")

    if not matched_jobs:
        print("⚠️ 条件に合致する公開求人が見つかりませんでした。")
        cleanup_debug_screenshots(location_list)
        return

    verified_jobs = inspect_companies_batch_with_gemini(matched_jobs)

    export_to_excel(verified_jobs, keyword_display=keyword_display, locations=location_list)

    cleanup_debug_screenshots(location_list)

if __name__ == "__main__":
    search_jobs_test()