import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import pandas as pd # pandasはFirestoreからのデータ処理には必須ではないが、データ確認に便利

# --- Configuration Settings ---
# Path to your Firebase service account key file
# ローカルで実行する場合は、このファイルがプロジェクトのルートディレクトリにあることを想定
SERVICE_ACCOUNT_KEY_PATH = 'firebase_service_account.json' 
COLLECTION_NAME = 'cases' # Firestoreのコレクション名
IMAGES_FOLDER_PATH = 'static/images' # 画像ファイルが置かれているフォルダのパス
# ----------------------------

# Initialize Firebase Admin SDK
try:
    # Firebase Admin SDKがまだ初期化されていない場合のみ初期化
    if not firebase_admin._apps:
        # 環境変数からJSON文字列を読み込む（Renderデプロイ時を想定）
        service_account_json_str = os.environ.get('SERVICE_ACCOUNT_JSON_DATA')
        if service_account_json_str:
            cred = credentials.Certificate(json.loads(service_account_json_str))
        else:
            # ローカル実行時で環境変数が設定されていない場合、ファイルから読み込む
            if os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
                cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
            else:
                raise FileNotFoundError(f"Service account key file not found at {SERVICE_ACCOUNT_KEY_PATH} and SERVICE_ACCOUNT_JSON_DATA env var not set.")
        
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase Admin SDK initialized successfully.")
except Exception as e:
    print(f"Error initializing Firebase Admin SDK: {e}")
    print("Please ensure 'firebase_service_account.json' is in the root directory OR SERVICE_ACCOUNT_JSON_DATA env var is set.")
    exit(1) # Firebaseの初期化に失敗したらスクリプトを終了

def check_image_consistency():
    print("\n--- 画像ファイル名の一致確認を開始します ---")

    # 1. Firestoreから画像ファイル名を取得
    print(f"1. Firestoreコレクション '{COLLECTION_NAME}' から画像ファイル名を取得中...")
    db_image_filenames_raw = {} # {小文字ファイル名: 元のファイル名} の辞書
    db_image_filenames_lower = set() # 小文字に統一したファイル名のセット
    
    try:
        docs = db.collection(COLLECTION_NAME).stream()
        for doc in docs:
            doc_data = doc.to_dict()
            image_filename = doc_data.get('写真') # "写真"フィールドからファイル名を取得
            if image_filename:
                original_filename = str(image_filename).strip()
                lower_filename = original_filename.lower()
                db_image_filenames_raw[lower_filename] = original_filename # 小文字キーで元の名前を保存
                db_image_filenames_lower.add(lower_filename)
        print(f"   Firestoreから {len(db_image_filenames_lower)} 個のユニークな画像ファイル名を取得しました。")
    except Exception as e:
        print(f"エラー: Firestoreからのデータ取得中に問題が発生しました: {e}")
        return

    # 2. ローカルのstatic/imagesフォルダから画像ファイル名を取得
    print(f"2. ローカルフォルダ '{IMAGES_FOLDER_PATH}' から画像ファイル名を取得中...")
    local_image_filenames_raw = {} # {小文字ファイル名: 元のファイル名} の辞書
    local_image_filenames_lower = set() # 小文字に統一したファイル名のセット
    
    if os.path.exists(IMAGES_FOLDER_PATH) and os.path.isdir(IMAGES_FOLDER_PATH):
        for filename in os.listdir(IMAGES_FOLDER_PATH):
            if os.path.isfile(os.path.join(IMAGES_FOLDER_PATH, filename)):
                original_filename = filename.strip()
                lower_filename = original_filename.lower()
                local_image_filenames_raw[lower_filename] = original_filename # 小文字キーで元の名前を保存
                local_image_filenames_lower.add(lower_filename)
        print(f"   ローカルフォルダから {len(local_image_filenames_lower)} 個の画像ファイルを見つけました。")
    else:
        print(f"エラー: 画像フォルダ '{IMAGES_FOLDER_PATH}' が見つからないか、ディレクトリではありません。")
        return

    # 3. 比較と不一致の報告
    print("\n--- 比較結果 ---")

    # データベースにはあるが、ローカルフォルダにないファイル (小文字比較)
    missing_in_local_lower = db_image_filenames_lower - local_image_filenames_lower
    if missing_in_local_lower:
        print("❌ Firestoreに登録されているが、ローカルフォルダに存在しない画像ファイル:")
        for filename_lower in sorted(list(missing_in_local_lower)):
            print(f"   - {db_image_filenames_raw.get(filename_lower, filename_lower)} (Firestoreに登録されているが、static/imagesにない)")
    else:
        print("✅ Firestoreに登録されている全ての画像ファイルがローカルフォルダに存在します。")

    # ローカルフォルダにはあるが、データベースに登録されていないファイル (小文字比較)
    not_referenced_in_db_lower = local_image_filenames_lower - db_image_filenames_lower
    if not_referenced_in_db_lower:
        print("\n⚠️ ローカルフォルダには存在するが、Firestoreのデータで参照されていない画像ファイル:")
        for filename_lower in sorted(list(not_referenced_in_db_lower)):
            print(f"   - {local_image_filenames_raw.get(filename_lower, filename_lower)} (static/imagesにあるが、Firestoreで参照されていない)")
    else:
        print("\n✅ ローカルフォルダ内の全ての画像ファイルがFirestoreのデータで参照されています。")

    # 大文字小文字の不一致の可能性（ヒント）
    print("\n--- 大文字小文字の不一致の可能性（ヒント） ---")
    case_mismatches = []
    for filename_lower in db_image_filenames_lower.intersection(local_image_filenames_lower):
        if db_image_filenames_raw[filename_lower] != local_image_filenames_raw[filename_lower]:
            case_mismatches.append(f"Firestore: '{db_image_filenames_raw[filename_lower]}' vs Local: '{local_image_filenames_raw[filename_lower]}'")
    
    if case_mismatches:
        print("⚠️ ファイル名の大文字小文字がFirestoreとローカルフォルダで一致しない可能性があります:")
        for mismatch in sorted(case_mismatches):
            print(f"   - {mismatch}")
        print("   -> **推奨: 全てのファイル名を小文字に統一してください。**")
    else:
        print("✅ 大文字小文字の不一致は見つかりませんでした。")

    if missing_in_local_lower or not_referenced_in_db_lower or case_mismatches:
        print("\n上記の問題を修正し、Excelデータを更新後、再度 `python initialize_db.py` を実行してください。")
    else:
        print("\n全ての画像ファイル名がFirestoreとローカルフォルダで一致しており、問題ありません。")
    
    print("\n--- 画像ファイル名の一致確認を終了します ---")

if __name__ == '__main__':
    check_image_consistency()
