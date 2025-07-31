import sqlite3
from flask import Flask, render_template, jsonify, g, send_from_directory, request, redirect, url_for
import os
import pandas as pd 

# Firebase Imports
import firebase_admin
from firebase_admin import credentials, firestore
import json # サービスアカウントキーの読み込みに必要

# --- Configuration Settings ---
DATABASE = 'ryojo_customization.db' # SQLite database is no longer used for live app data
COLLECTION_NAME = 'cases' # Firestoreのコレクション名
# ----------------------------

# Unique version string for debugging
APP_VERSION = "2025-07-26_FINAL_FIX_V8" # バージョンを更新して確認しやすくします

# Firebase FirestoreクライアントをグローバルスコープでNoneに初期化
db = None 

app = Flask(__name__, static_folder='static', template_folder='templates')

# Helper function to get a database connection (for local SQLite fallback, if used)
def get_db():
    db_sqlite = getattr(g, '_database', None)
    if db_sqlite is None:
        # Connect to the database file
        db_sqlite = sqlite3.connect(DATABASE)
        # Configure row_factory to access columns by name (like a dictionary)
        db_sqlite.row_factory = sqlite3.Row 
    return db_sqlite

# Close the database connection when the application context ends (for local SQLite fallback)
@app.teardown_appcontext
def close_connection(exception):
    db_sqlite = getattr(g, '_database', None)
    if db_sqlite is not None:
        db_sqlite.close()

# Initialize Firebase Admin SDK
try:
    if not firebase_admin._apps:
        # 環境変数からJSON文字列を読み込む（Renderデプロイ時を想定）
        service_account_json_str = os.environ.get('SERVICE_ACCOUNT_JSON_DATA')
        if service_account_json_str:
            cred_dict = json.loads(service_account_json_str)
            cred = credentials.Certificate(cred_dict)
        else:
            # ローカル実行時で環境変数が設定されていない場合、ファイルから読み込む
            if os.path.exists('firebase_service_account.json'):
                cred = credentials.Certificate('firebase_service_account.json')
            else:
                raise FileNotFoundError("firebase_service_account.json が見つかりません。環境変数 SERVICE_ACCOUNT_JSON_DATA も未設定です。")
        
        firebase_admin.initialize_app(cred)
    db = firestore.client() 
    print("Firebase Admin SDK initialized successfully.")
except Exception as e:
    print(f"Error initializing Firebase Admin SDK: {e}")
    print("Firebase Admin SDKの初期化に失敗しました。サービスアカウントキーを確認してください。")
    raise 

# Helper function to get Firestore DB client
def get_firestore_db():
    if db is None:
        raise RuntimeError("Firestore DB client is not initialized. Check Firebase Admin SDK initialization.")
    return db

# --- Routing Definitions ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cases')
def cases_page():
    # 'category'クエリパラメータを取得し、デフォルトは'all'
    category_filter = request.args.get('category', 'all')
    return render_template('cases.html', category_filter=category_filter)

# @app.route('/cases/<category>') # このルーティングはもう使用しない
# def cases_by_category(category):
#     return render_template('cases.html', category_filter=category)

@app.route('/about')
def about_page():
    return render_template('about.html') 

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

# 新規追加: 統計ページへのルーティング
@app.route('/statistics')
def statistics_page():
    return render_template('statistics.html')

# ★新規追加: カスタマイズページへのルーティング
@app.route('/customize')
def customize_page():
    return render_template('customize.html')


# ★新規追加: カスタマイズページ用のAPIエンドポイント
@app.route('/api/customize_cases')
def get_customize_cases_api():
    print("--- DEBUG START: get_customize_cases_api function entered ---")
    firestore_db = get_firestore_db()
    
    docs = firestore_db.collection(COLLECTION_NAME).stream()
    all_raw_cases = []
    for doc in docs:
        doc_data = doc.to_dict()
        doc_data['事例'] = doc.id 
        all_raw_cases.append(doc_data)

    if not all_raw_cases:
        print("DEBUG: No raw cases found for customize cases.")
        return jsonify([])

    df = pd.DataFrame(all_raw_cases)

    # '発意'が「個人」または「自治会」の事例のみをフィルタリング
    # Excelのセルに複数の発意がカンマ区切りで入っている可能性も考慮
    filtered_df = df[
        df['発意'].apply(lambda x: isinstance(x, str) and ('個人' in x or '自治会' in x))
    ].copy() 

    print(f"DEBUG: Filtered customize cases: {len(filtered_df)} items")

    grouped_cases = []
    RYOJO_CENTER_LAT = 34.240  
    RYOJO_CENTER_LON = 132.550 

    # '整備名'でグループ化
    group_by_column = '整備名' 
    if group_by_column not in filtered_df.columns or filtered_df[group_by_column].isnull().all():
        print(f"WARNING: '{group_by_column}' column not found or is empty for customize cases. Falling back to grouping by '事例'.")
        group_by_column = '事例' 

    try:
        grouped_df = filtered_df.groupby(group_by_column)
        print(f"DEBUG: GroupBy successful for customize cases. Number of groups: {len(grouped_df.groups.keys())}") 
    except Exception as e:
        print(f"ERROR: GroupBy failed on column '{group_by_column}' for customize cases: {e}") 
        raise 

    for group_key, group in grouped_df: 
        is_area_wide_case = False 
        description_html = "" 

        map_representative_row = group.dropna(subset=['緯度', '経度']).iloc[0] if not group.dropna(subset=['緯度', '経度']).empty else None
        
        card_title = str(group_key).strip()

        subtitle_content = group['発言内容'].iloc[0] if not group['発言内容'].isnull().all() else '代表的な発言内容なし'
        display_representative_row = group.iloc[0] 

        category_map = {
            'R': '道路整備', 'C': '自治会', 'K': 'キーパーソン', 'D': '災害', 'O': 'その他'
        }

        # 概要情報 (summary_attributes_html_final)
        summary_parts = []
        for col in ['整備', '目的', '発意', '実行', '費用', '契機', '時期', '所有', '管理', '利用']: 
            unique_values = group[col].dropna().unique().tolist()
            if unique_values:
                summary_parts.append(f"<strong>{col}:</strong> {', '.join(map(str, unique_values))}") 
        
        summary_attributes_html_final = "" 
        if summary_parts:
            summary_attributes_html_final = "".join([f"<p>{part}</p>" for part in summary_parts]) 
        else:
            summary_attributes_html_final = "<p>概要情報がありません。</p>"

        # ヒアリング内容 (statements_html_final) - 各発言に詳細要素を紐付け、整備ごとにグループ化
        statements_html_final = ""
        statements_by_seibi_type = {} 
        for _, r in group.iterrows(): 
            statement_content = r.get('発言内容', '')
            seibi_type_for_statement = str(r.get('整備', 'その他整備')).strip() 
            
            if statement_content and statement_content != '不明':
                details_for_this_statement = []
                for col in ['発言者', '目的', '発意', '時期']: 
                    val = r.get(col)
                    if val and str(val).strip() != '不明':
                        details_for_this_statement.append(f"{col}: {str(val).strip()}")
                
                formatted_individual_statement = f"<p><strong>・{statement_content}</strong>"
                if details_for_this_statement:
                    formatted_individual_statement += f"<br>({', '.join(details_for_this_statement)})</p>"
                else:
                    formatted_individual_statement += "</p>"
                
                if seibi_type_for_statement not in statements_by_seibi_type:
                    statements_by_seibi_type[seibi_type_for_statement] = []
                statements_by_seibi_type[seibi_type_for_statement].append(formatted_individual_statement)

        if statements_by_seibi_type:
            for seibi_type, statements_list in statements_by_seibi_type.items():
                statements_html_final += f"<h5>{seibi_type}:</h5>" 
                statements_html_final += "<div>" + "".join(statements_list) + "</div>"
        else:
            statements_html_final = "<p>発言内容がありません。</p>"

        description_for_mapbox = summary_attributes_html_final + "<h4>ヒアリング内容:</h4>" + statements_html_final

        print(f"DEBUG (API): Case '{group_key}' - Final summary_attributes_html: '{summary_attributes_html_final}'")
        print(f"DEBUG (API): Case '{group_key}' - Final statements_html: '{statements_html_final}'")


        lat = None
        lon = None
        img_url = None

        if map_representative_row is not None:
            lat = map_representative_row['緯度']
            lon = map_representative_row['経度']
            img_url = map_representative_row.get('写真', None)
        else:
            if group_key and str(group_key).startswith('R'): 
                lat = RYOJO_CENTER_LAT
                lon = RYOJO_CENTER_LON
                is_area_wide_case = True 
                print(f"DEBUG: Assigning default center to R-case {group_key} as no specific lat/lon found.")
            else:
                print(f"DEBUG: Case {group_key} (non-R or no ID) has no specific lat/lon. No pin will be placed.")

        original_case_id_for_category = group['事例'].iloc[0] if '事例' in group.columns else str(group_key)
        first_char_of_id = str(original_case_id_for_category)[0] if original_case_id_for_category else '不明'
        japanese_category = category_map.get(first_char_of_id, 'その他')

        # 発言者リストを生成
        unique_speakers = group['発言者'].dropna().unique().tolist()
        speakers_list_html = ', '.join(map(str, unique_speakers)) if unique_speakers else '不明'


        grouped_cases.append({
            'id': group_key, 
            'name': card_title, 
            'subtitle': subtitle_content, 
            'description': description_for_mapbox, 
            'latitude': lat, 
            'longitude': lon, 
            'image_url': img_url, 
            'category': first_char_of_id, 
            'display_category_jp': japanese_category, 
            'is_area_wide': is_area_wide_case,
            'summary_attributes_html': summary_attributes_html_final, 
            'statements_html': statements_html_final,
            'speakers_list_html': speakers_list_html, # 発言者リストを追加
            # 新規追加: 発意と所有の値を直接渡す
            'initiative_for_card': group['発意'].dropna().iloc[0] if not group['発意'].dropna().empty else None,
            'ownership_for_card': group['所有'].dropna().iloc[0] if not group['所有'].dropna().empty else None
        })
    
    print(f"DEBUG (API): Finished processing all groups. Total grouped cases: {len(grouped_cases)}") 
    print("--- DEBUG END: get_cases_api function exited ---") 
    return jsonify(grouped_cases)

# API endpoint to return statistics data
@app.route('/api/statistics')
def get_statistics_api():
    print("--- DEBUG START: get_statistics_api function entered ---")
    firestore_db = get_firestore_db()
    
    docs = firestore_db.collection(COLLECTION_NAME).stream()
    all_raw_cases = []
    for doc in docs:
        doc_data = doc.to_dict()
        doc_data['事例'] = doc.id 
        all_raw_cases.append(doc_data)

    if not all_raw_cases:
        print("DEBUG: No raw cases found for statistics.")
        return jsonify({})

    df = pd.DataFrame(all_raw_cases)
        # ★修正: '発意'が「個人」または「自治会」の事例のみをフィルタリング
    filtered_df = df[
        df['発意'].apply(lambda x: isinstance(x, str) and ('個人' in x or '自治会' in x))
    ].copy()

    if filtered_df.empty:
        print("DEBUG: No customize cases found for statistics after filtering.")
        return jsonify({})

    statistics_data = {}

    # 各カテゴリの集計
    # '整備' (Maintenance Type)
    seibi_counts = {}
    for item_list in df['整備'].dropna():
        for item in str(item_list).split(','): 
            item = item.strip()
            if item and item != '不明':
                seibi_counts[item] = seibi_counts.get(item, 0) + 1
    statistics_data['整備'] = seibi_counts

    # '目的' (Purpose)
    purpose_counts = {}
    for item_list in df['目的'].dropna():
        for item in str(item_list).split(','):
            item = item.strip()
            if item and item != '不明':
                purpose_counts[item] = purpose_counts.get(item, 0) + 1
    statistics_data['目的'] = purpose_counts

    # '発意' (Initiative)
    initiative_counts = {}
    for item_list in df['発意'].dropna():
        for item in str(item_list).split(','):
            item = item.strip()
            if item and item != '不明':
                initiative_counts[item] = initiative_counts.get(item, 0) + 1
    statistics_data['発意'] = initiative_counts

    # '時期' (Period)
    period_counts = {}
    for item_list in df['時期'].dropna():
        for item in str(item_list).split(','):
            item = item.strip()
            if item and item != '不明':
                period_counts[item] = period_counts.get(item, 0) + 1
    statistics_data['時期'] = period_counts

    # Other categories can be added similarly (e.g., '実行', '費用', '所有', '管理', '利用')
    
    print(f"DEBUG: Statistics data generated: {statistics_data}")
    return jsonify(statistics_data)

# ★新規追加: 歴史年表データを提供するAPIエンドポイント
@app.route('/api/historical_summary')
def get_historical_summary_api():
    print("--- DEBUG START: get_historical_summary_api function entered ---")
    firestore_db = get_firestore_db()
    
    docs = firestore_db.collection(COLLECTION_NAME).stream()
    all_raw_cases = []
    for doc in docs:
        doc_data = doc.to_dict()
        doc_data['事例'] = doc.id 
        all_raw_cases.append(doc_data)

    if not all_raw_cases:
        print("DEBUG: No raw cases found for historical summary.")
        return jsonify({})

    df = pd.DataFrame(all_raw_cases)

    # '時期'でグループ化し、各時期のユニークな'整備'を収集
    # NaNを考慮し、時期がない場合は'不明な時期'にまとめる
    df['時期_clean'] = df['時期'].apply(lambda x: str(x).strip() if pd.notnull(x) and str(x).strip() != '不明' else '不明な時期')
    df['整備_clean'] = df['整備'].apply(lambda x: str(x).strip() if pd.notnull(x) and str(x).strip() != '不明' else '不明な整備')

    # 時期ごとに整備をまとめる
    historical_summary = {}
    for period, group in df.groupby('時期_clean'):
        unique_seibi_in_period = group['整備_clean'].dropna().unique().tolist()
        # カンマ区切りの整備を個別に展開してユニークにする
        expanded_seibi = set()
        for seibi_item in unique_seibi_in_period:
            for s in seibi_item.split(','):
                s_clean = s.strip()
                if s_clean and s_clean != '不明な整備':
                    expanded_seibi.add(s_clean)
        
        if expanded_seibi:
            historical_summary[period] = sorted(list(expanded_seibi))
    
    # 時系列順にソート (簡易的なソート、より複雑な時期表現にはカスタムソートが必要)
    # 例: '戦前', '昭和20年代', '昭和40年代', '昭和52年', '昭和64年', '10年前', '20年前', '25~30年前', '最近', '不明な時期'
    # ここでは辞書キーの文字列順でソート
    sorted_historical_summary = dict(sorted(historical_summary.items()))

    print(f"DEBUG: Historical summary data generated: {sorted_historical_summary}")
    return jsonify(sorted_historical_summary)


# API endpoint to return customization cases (includes grouping logic)
@app.route('/api/cases')
def get_cases_api():
    print(f"--- DEBUG START: get_cases_api function entered (Version: {APP_VERSION}) ---") 
    
    firestore_db = get_firestore_db() 
    
    docs = firestore_db.collection(COLLECTION_NAME).stream()
    all_raw_cases = []
    for doc in docs:
        doc_data = doc.to_dict()
        # '事例'カラムをドキュメントIDとして使用し、doc_dataにも含める
        doc_data['事例'] = doc.id 
        all_raw_cases.append(doc_data)

    print(f"DEBUG: Raw cases fetched from DB: {len(all_raw_cases)} items") 
    if not all_raw_cases:
        print("DEBUG: No raw cases found in DB. Returning empty list.") 
        return jsonify([])

    df = pd.DataFrame(all_raw_cases)
    
    df['緯度'] = pd.to_numeric(df['緯度'], errors='coerce')
    df['経度'] = pd.to_numeric(df['経度'], errors='coerce')
    
    grouped_cases = []
    
    RYOJO_CENTER_LAT = 34.240  
    RYOJO_CENTER_LON = 132.550 

    try:
        # '事例' (Case ID) でグループ化
        grouped_df = df.groupby('整備名')
        print(f"DEBUG: GroupBy successful. Number of groups: {len(grouped_df.groups.keys())}") 
    except Exception as e:
        print(f"ERROR: GroupBy failed: {e}") 
        raise 

    for case_id, group in grouped_df: 
        print(f"DEBUG: Processing case_id: '{case_id}'") 
        
        is_area_wide_case = False 
        description_html = "" 

        map_representative_row = group.dropna(subset=['緯度', '経度']).iloc[0] if not group.dropna(subset=['緯度', '経度']).empty else None
        
        # '整備名'カラムが存在すればそれを使用、なければ '事例 {case_id}' を使用
        case_name_from_excel = group['整備名'].iloc[0] if '整備名' in group.columns and not group['整備名'].iloc[0] is None else f"事例 {case_id}"
        display_representative_row = group.iloc[0]

        # Debug: Check representative row content
        print(f"DEBUG: display_representative_row for '{case_id}': {display_representative_row.get('発言内容', 'N/A')}") 

        category_map = {
            'R': '道路整備', 'C': '自治会', 'K': 'キーパーソン', 'D': '災害', 'O': 'その他'
        }

        unique_seibi_types = group['整備'].dropna().unique().tolist() 
        unique_purposes = group['目的'].dropna().unique().tolist()
        unique_initiatives = group['発意'].dropna().unique().tolist()
        unique_executions = group['実行'].dropna().unique().tolist()
        unique_costs = group['費用'].dropna().unique().tolist()
        unique_triggers = group['契機'].dropna().unique().tolist()
        unique_periods = group['時期'].dropna().unique().tolist()
        unique_ownerships = group['所有'].dropna().unique().tolist()
        unique_managements = group['管理'].dropna().unique().tolist()
        unique_usages = group['利用'].dropna().unique().tolist()

        summary_parts = []
        if unique_seibi_types: summary_parts.append(f"<strong>整備:</strong> {', '.join(unique_seibi_types)}") 
        if unique_purposes: summary_parts.append(f"<strong>目的:</strong> {', '.join(unique_purposes)}")
        if unique_initiatives: summary_parts.append(f"<strong>発意:</strong> {', '.join(unique_initiatives)}")
        if unique_executions: summary_parts.append(f"<strong>実行:</strong> {', '.join(unique_executions)}")
        if unique_costs: summary_parts.append(f"<strong>費用:</strong> {', '.join(unique_costs)}")
        if unique_triggers: summary_parts.append(f"<strong>契機:</strong> {', '.join(unique_triggers)}")
        if unique_periods: summary_parts.append(f"<strong>時期:</strong> {', '.join(unique_periods)}")
        if unique_ownerships: summary_parts.append(f"<strong>所有:</strong> {', '.join(unique_ownerships)}")
        if unique_managements: summary_parts.append(f"<strong>管理:</strong> {', '.join(unique_managements)}")
        if unique_usages: summary_parts.append(f"<strong>利用:</strong> {', '.join(unique_usages)}")

        summary_attributes_html_final = "" 
        if summary_parts:
            summary_attributes_html_final = "".join([f"<p>{part}</p>" for part in summary_parts]) 
        else:
            summary_attributes_html_final = "<p>概要情報がありません。</p>"

        all_statements_html = []
        for _, r in group.iterrows():
            statement_content = r.get('発言内容', '')
            seibi_type_for_statement = str(r.get('整備', 'その他整備')).strip() 
            
            if statement_content and statement_content != '不明':
                statement_details = []
                if seibi_type_for_statement and seibi_type_for_statement != 'その他整備': statement_details.append(f"整備: {seibi_type_for_statement}")
                if r.get('発言者') and r.get('発言者') != '不明': statement_details.append(f"発言者: {r.get('発言者')}")
                if r.get('目的') and r.get('目的') != '不明': statement_details.append(f"目的: {r.get('目的')}")
                if r.get('発意') and r.get('発意') != '不明': statement_details.append(f"発意: {r.get('発意')}")
                if r.get('時期') and r.get('時期') != '不明': statement_details.append(f"時期: {r.get('時期')}")
                
                formatted_individual_statement = f"<p><strong>・{statement_content}</strong>"
                if statement_details:
                    formatted_individual_statement += f"<br>({', '.join(statement_details)})</p>"
                else:
                    formatted_individual_statement += "</p>"
                
                all_statements_html.append(formatted_individual_statement)

        statements_only_html_final = ""
        if all_statements_html:
            statements_only_html_final = "".join(all_statements_html) 
        else:
            statements_only_html_final = "<p>発言内容がありません。</p>"

        description_html += "<h4>ヒアリング内容:</h4>"
        if all_statements_html:
            description_html += "<div>" + "".join(all_statements_html) + "</div>"
        else:
            description_html += "<p>発言内容がありません。</p>"

        # Debug: Print the generated HTML content
        print(f"DEBUG (API): Case '{case_id}' - Final summary_attributes_html: '{summary_attributes_html_final}'")
        print(f"DEBUG (API): Case '{case_id}' - Final statements_only_html: '{statements_only_html_final}'")


        lat = None
        lon = None
        img_url = None

        if map_representative_row is not None:
            lat = map_representative_row['緯度']
            lon = map_representative_row['経度']
            img_url = map_representative_row.get('写真', None)
        else:
            if case_id and case_id.startswith('R'):
                lat = RYOJO_CENTER_LAT
                lon = RYOJO_CENTER_LON
                is_area_wide_case = True 
                print(f"DEBUG: Assigning default center to R-case {case_id} as no specific lat/lon found.")
            else:
                print(f"DEBUG: Case {case_id} (non-R or no ID) has no specific lat/lon. No pin will be placed.")

        first_char_of_id = case_id[0] if case_id else '不明'
        japanese_category = category_map.get(first_char_of_id, 'その他')

        grouped_cases.append({
            'id': case_id, 
            'name': case_name_from_excel, # ★修正: '整備名'カラムの値を使用
            'subtitle': display_representative_row.get('発言内容', '代表的な発言内容なし'), 
            'description': description_html, 
            'latitude': lat, 
            'longitude': lon, 
            'image_url': img_url, 
            'category': first_char_of_id, 
            'display_category_jp': japanese_category, 
            'is_area_wide': is_area_wide_case,
            'summary_attributes_html': summary_attributes_html_final, # 概要情報のみ
            'statements_html': statements_only_html_final # 構造化された発言内容のみ
        })
    
    print(f"DEBUG (API): Finished processing all groups. Total grouped cases: {len(grouped_cases)}") 
    print("--- DEBUG END: get_cases_api function exited ---") 
    return jsonify(grouped_cases)

@app.route('/api/cases/add', methods=['POST'])
def add_case():
    if request.method == 'POST':
        data = request.get_json() 

        事例 = data.get('事例') 
        整備名 = data.get('整備名') # 新しく取得
        発言者 = data.get('発言者')
        発言内容 = data.get('発言内容')
        整備 = data.get('整備') 
        目的 = data.get('目的')
        発意 = data.get('発意')
        実行 = data.get('実行')
        費用 = data.get('費用')
        契機 = data.get('契機')
        時期 = data.get('時期')
        所有 = data.get('所有')
        管理 = data.get('管理')
        利用 = data.get('利用')
        緯度 = data.get('緯度') 
        経度 = data.get('経度') 
        写真 = data.get('写真') 

        if not 事例: 
            return jsonify({'success': False, 'message': '事例IDは必須です。'}), 400

        db = get_db() 
        try:
            if 'firebase_admin' in globals() and firebase_admin._apps:
                firestore_db = get_firestore_db()
                doc_id = str(事例)
                doc_data = {
                    '整備名': 整備名, # 事例名を追加
                    '発言者': 発言者, '発言内容': 発言内容, '整備': 整備, '目的': 目的, '発意': 発意, 
                    '実行': 実行, '費用': 費用, '契機': 契機, '時期': 時期, '所有': 所有, 
                    '管理': 管理, '利用': 利用, '緯度': 緯度, '経度': 経度, '写真': 写真, 
                    'date_added': firestore.SERVER_TIMESTAMP 
                }
                firestore_db.collection(COLLECTION_NAME).document(doc_id).set(doc_data)

            else: 
                conn = sqlite3.connect(DATABASE)
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO cases (事例, 整備名, 発言者, 発言内容, 整備, 目的, 発意, 実行, 費用, 契機, 時期, 所有, 管理, 利用, 緯度, 経度, 写真)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (事例, 整備名, 発言者, 発言内容, 整備, 目的, 発意, 実行,費用, 契機, 時期, 所有, 管理, 利用, 緯度, 経度, 写真)) 
                conn.commit()
                conn.close()

            return jsonify({'success': True, 'message': '事例が追加されました。'})
        except Exception as e:
            if 'firebase_admin' not in globals() or not firebase_admin._apps:
                if 'conn' in locals() and conn:
                    conn.rollback()
            return jsonify({'success': False, 'message': f'データの追加に失敗しました: {str(e)}'}), 500

    @app.route('/api/cases/update')
    def update_case():
        if request.method == 'POST':
            data = request.get_json()
            
            事例 = data.get('事例') 
            緯度 = data.get('緯度') 
            経度 = data.get('経度') 
            写真 = data.get('写真') 

            if not 事例: 
                return jsonify({'success': False, 'message': '事例IDは必須です。'}), 400

            firestore_db = get_firestore_db() 
            try:
                doc_id = str(事例)
                update_data = {
                    '整備名': 整備名, 
                    '発言者': data.get('発言者'), '発言内容': data.get('発言内容'), '整備': data.get('整備'), 
                    '目的': data.get('目的'), '発意': data.get('発意'), '実行': data.get('実行'), 
                    '費用': data.get('費用'), '契機': data.get('契機'), '時期': data.get('時期'), 
                    '所有': data.get('所有'), '管理': data.get('管理'), '利用': data.get('利用'), 
                    '緯度': 緯度, '経度': 経度, '写真': 写真
                }
                firestore_db.collection(COLLECTION_NAME).document(doc_id).update(update_data)

                return jsonify({'success': True, 'message': '事例が更新されました。'})
            except Exception as e:
                return jsonify({'success': False, 'message': f'データの更新に失敗しました: {str(e)}'}), 500

    @app.route('/api/cases/delete', methods=['POST'])
    def delete_case():
        if request.method == 'POST':
            data = request.get_json()
            事例 = data.get('事例') 

            if not 事例:
                return jsonify({'success': False, 'message': '削除する事例IDが指定されていません。'}), 400

            firestore_db = get_firestore_db() 
            try:
                doc_id = str(事例)
                firestore_db.collection(COLLECTION_NAME).document(doc_id).delete()

                return jsonify({'success': True, 'message': f'事例 {事例} が削除されました。'})
            except Exception as e:
                return jsonify({'success': False, 'message': f'データの削除に失敗しました: {str(e)}'}), 500

    @app.route('/images/<path:filename>')
    def serve_image(filename):
        return send_from_directory(os.path.join(app.root_path, 'static', 'images'), filename)

if __name__ == '__main__':
    app.run(debug=True)
