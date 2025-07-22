import sqlite3 # SQLite関連のコードは参照されませんが、互換性のため残す
from flask import Flask, render_template, jsonify, g, send_from_directory, request, redirect, url_for
import os
import pandas as pd 

# Firebase Imports
import firebase_admin
from firebase_admin import credentials, firestore
import json # サービスアカウントキーの読み込みに必要

# --- Configuration Settings ---
SERVICE_ACCOUNT_KEY_PATH = 'firebase_service_account.json' # ★ダウンロードしたJSONファイル名に置き換える
COLLECTION_NAME = 'cases' # Firestoreのコレクション名
# ----------------------------

app = Flask(__name__, static_folder='static', template_folder='templates')

# Initialize Firebase Admin SDK
try:
    # Firebase Admin SDKがまだ初期化されていない場合のみ初期化
    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
        firebase_admin.initialize_app(cred)
    db = firestore.client() # Firestoreクライアントを取得
    print("Firebase Admin SDK initialized successfully.")
except Exception as e:
    print(f"Error initializing Firebase Admin SDK: {e}")
    print("Please ensure 'firebase_service_account.json' is in the root directory and is valid.")
    exit(1) # Firebaseの初期化に失敗したらアプリケーションを終了

# Helper function to get Firestore DB client (replaces SQLite get_db)
def get_firestore_db():
    return db

# FlaskのgオブジェクトはFirestoreクライアントでは不要ですが、既存の構造に合わせる
# @app.teardown_appcontext はFirestoreクライアントでは不要

# --- Routing Definitions ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cases')
def cases_page():
    return render_template('cases.html', category_filter='all')

@app.route('/cases/<category>')
def cases_by_category(category):
    return render_template('cases.html', category_filter=category)

@app.route('/about')
def about_page():
    return render_template('about.html') 

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

# API endpoint to return customization cases (includes grouping logic)
@app.route('/api/cases')
def get_cases_api():
    print("--- DEBUG START: get_cases_api function entered ---") 
    
    firestore_db = get_firestore_db() # Firestoreクライアントを取得
    
    # Firestoreから全てのドキュメントを取得
    docs = firestore_db.collection(COLLECTION_NAME).stream()
    all_raw_cases = []
    for doc in docs:
        doc_data = doc.to_dict()
        doc_data['事例'] = doc.id # FirestoreのドキュメントIDを"事例"カラムとして使用
        all_raw_cases.append(doc_data)

    print(f"DEBUG: Raw cases fetched from Firestore: {len(all_raw_cases)} items") 
    if not all_raw_cases:
        print("DEBUG: No raw cases found in Firestore. Returning empty list.") 
        return jsonify([])

    # Pandas DataFrameに変換してグループ化処理を行う
    df = pd.DataFrame(all_raw_cases)
    
    # 緯度・経度が数値であることを確認し、NaNにする
    df['緯度'] = pd.to_numeric(df['緯度'], errors='coerce')
    df['経度'] = pd.to_numeric(df['経度'], errors='coerce')
    
    grouped_cases = []
    
    # 両城地区のデフォルト中心座標 (例)
    RYOJO_CENTER_LAT = 34.240  
    RYOJO_CENTER_LON = 132.550 

    # "事例" カラムでグループ化
    try:
        grouped_df = df.groupby('事例')
        print(f"DEBUG: GroupBy successful. Number of groups: {len(grouped_df.groups.keys())}") 
    except Exception as e:
        print(f"ERROR: GroupBy failed: {e}") 
        raise # GroupByに失敗したら例外を再スロー

    for case_id, group in grouped_df: 
        is_area_wide_case = False # 各グループの処理開始時に初期化

        # 地図表示のための代表点を見つける (緯度・経度がある行を優先)
        map_representative_row = group.dropna(subset=['緯度', '経度']).iloc[0] if not group.dropna(subset=['緯度', '経度']).empty else None
        
        # ポップアップ/サイドバー用の代表行（緯度経度なくてもOK）
        display_representative_row = group.iloc[0]

        # カテゴリの日本語変換マップ
        category_map = {
            'R': '道路整備',
            'C': '自治会',
            'K': 'キーパーソン',
            'D': '災害',
            'O': 'その他'
        }

        # ユニークな項目の収集
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

        # HTML形式の概要部分を構築
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

        # 全ての発言内容を収集
        all_statements_html = []
        for _, r in group.iterrows():
            statement_content = r.get('発言内容', '')
            if statement_content and statement_content != '不明':
                all_statements_html.append(f"<p>・{statement_content}</p>")

        # ポップアップ/サイドバー表示用の詳細HTMLを構築
        description_html = ""
        if summary_parts:
            description_html += "<p>" + "</p><p>".join(summary_parts) + "</p>"
        
        description_html += "<h4>ヒアリング内容:</h4>"
        if all_statements_html:
            description_html += "<div>" + "".join(all_statements_html) + "</div>"
        else:
            description_html += "<p>発言内容がありません。</p>"

        # 地図のピンに使う緯度・経度と写真ファイル名を取得
        lat = None
        lon = None
        img_url = None

        if map_representative_row is not None:
            lat = map_representative_row['緯度']
            lon = map_representative_row['経度']
            img_url = map_representative_row.get('写真', None)
        else:
            # 緯度経度がない場合、Rカテゴリならデフォルト中心座標を割り当てる
            if case_id and case_id.startswith('R'):
                lat = RYOJO_CENTER_LAT
                lon = RYOJO_CENTER_LON
                is_area_wide_case = True 
                print(f"DEBUG: Assigning default center to R-case {case_id} as no specific lat/lon found.")
            else:
                print(f"DEBUG: Case {case_id} (non-R or no ID) has no specific lat/lon. No pin will be placed.")

        # カテゴリの決定と日本語変換
        first_char_of_id = case_id[0] if case_id else '不明'
        japanese_category = category_map.get(first_char_of_id, 'その他')

        # 最終的なデータ構造をリストに追加
        grouped_cases.append({
            'id': case_id, 
            'name': f"事例 {case_id}", 
            'subtitle': display_representative_row.get('発言内容', '代表的な発言内容なし'), 
            'description': description_html, 
            'latitude': lat, 
            'longitude': lon, 
            'image_url': img_url, 
            'category': first_char_of_id, 
            'display_category_jp': japanese_category, 
            'is_area_wide': is_area_wide_case 
        })
    
    print(f"DEBUG: Finished processing all groups. Total grouped cases: {len(grouped_cases)}") 
    print("--- DEBUG END: get_cases_api function exited ---") 
    return jsonify(grouped_cases)

# API endpoint to add a new case
@app.route('/api/cases/add', methods=['POST'])
def add_case():
    if request.method == 'POST':
        data = request.get_json() 

        事例 = data.get('事例') 
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

        firestore_db = get_firestore_db() # Firestore DBクライアントを取得
        try:
            # ドキュメントIDとして"事例"を使用
            doc_id = str(事例)
            # ドキュメントデータを辞書として準備
            doc_data = {
                '発言者': 発言者,
                '発言内容': 発言内容,
                '整備': 整備,
                '目的': 目的,
                '発意': 発意,
                '実行': 実行,
                '費用': 費用,
                '契機': 契機,
                '時期': 時期,
                '所有': 所有,
                '管理': 管理,
                '利用': 利用,
                '緯度': 緯度,
                '経度': 経度,
                '写真': 写真,
                'date_added': firestore.SERVER_TIMESTAMP # Firestoreのサーバータイムスタンプ
            }
            # Firestoreにドキュメントを追加
            firestore_db.collection(COLLECTION_NAME).document(doc_id).set(doc_data)

            return jsonify({'success': True, 'message': '事例が追加されました。'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'データの追加に失敗しました: {str(e)}'}), 500

# API endpoint to update an existing case
@app.route('/api/cases/update', methods=['POST'])
def update_case():
    if request.method == 'POST':
        data = request.get_json()
        
        事例 = data.get('事例') 
        緯度 = data.get('緯度') 
        経度 = data.get('経度') 
        写真 = data.get('写真') 

        if not 事例: 
            return jsonify({'success': False, 'message': '事例IDは必須です。'}), 400

        firestore_db = get_firestore_db() # Firestore DBクライアントを取得
        try:
            doc_id = str(事例)
            # 更新するフィールドのみを辞書として準備
            update_data = {
                '発言者': data.get('発言者'),
                '発言内容': data.get('発言内容'),
                '整備': data.get('整備'),
                '目的': data.get('目的'),
                '発意': data.get('発意'),
                '実行': data.get('実行'),
                '費用': data.get('費用'),
                '契機': data.get('契機'),
                '時期': data.get('時期'),
                '所有': data.get('所有'),
                '管理': data.get('管理'),
                '利用': data.get('利用'),
                '緯度': 緯度,
                '経度': 経度,
                '写真': 写真
            }
            # Firestoreのドキュメントを更新
            firestore_db.collection(COLLECTION_NAME).document(doc_id).update(update_data)

            return jsonify({'success': True, 'message': '事例が更新されました。'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'データの更新に失敗しました: {str(e)}'}), 500

# API endpoint to delete a case
@app.route('/api/cases/delete', methods=['POST'])
def delete_case():
    if request.method == 'POST':
        data = request.get_json()
        事例 = data.get('事例') 

        if not 事例:
            return jsonify({'success': False, 'message': '削除する事例IDが指定されていません。'}), 400

        firestore_db = get_firestore_db() # Firestore DBクライアントを取得
        try:
            doc_id = str(事例)
            # Firestoreのドキュメントを削除
            firestore_db.collection(COLLECTION_NAME).document(doc_id).delete()

            return jsonify({'success': True, 'message': f'事例 {事例} が削除されました。'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'データの削除に失敗しました: {str(e)}'}), 500

# Route to serve image files from the static/images folder
@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(os.path.join(app.root_path, 'static', 'images'), filename)

if __name__ == '__main__':
    app.run(debug=True)
