import sqlite3
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import os
import json 

# --- 設定項目（ここをあなたの環境に合わせて修正してください） ---
# Path to your Firebase service account key file
SERVICE_ACCOUNT_KEY_PATH = 'firebase_service_account.json' # ダウンロードしたJSONファイル名に置き換える
EXCEL_FILE = 'customization_data.xlsx' # あなたのExcelファイル名
COLLECTION_NAME = 'cases' # Firestoreのコレクション名（例: 'cases'）
SHEET_NAME = 'code' # ★重要: Excelファイル内のデータがあるシート名に正確に合わせる！
# -----------------------------------------------------------------

# Initialize Firebase Admin SDK
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
        firebase_admin.initialize_app(cred)
    db = firestore.client() # Firestoreクライアントをグローバル変数'db'に割り当て
    print("Firebase Admin SDK initialized successfully.")
except Exception as e:
    print(f"Error initializing Firebase Admin SDK: {e}")
    print("Please ensure 'firebase_service_account.json' is in the root directory and is valid.")
    exit(1) 

def init_firestore_collection():
    """Firestoreコレクションを初期化（既存データを全て削除）する関数"""
    print(f"Initializing Firestore collection '{COLLECTION_NAME}'...")
    try:
        docs = db.collection(COLLECTION_NAME).stream()
        for doc in docs:
            doc.reference.delete()
        print(f"Existing documents in '{COLLECTION_NAME}' deleted.")
    except Exception as e:
        print(f"Error deleting existing documents: {e}")

def import_data_to_firestore():
    """Excelファイルからデータを読み込み、Firestoreに投入する関数"""
    if not os.path.exists(EXCEL_FILE):
        print(f"エラー: Excelファイル '{EXCEL_FILE}' が見つかりません。ファイルパスを確認してください。")
        return

    conn = None 
    try:
        df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME, header=0) 
        
        df['緯度'] = pd.to_numeric(df['緯度'], errors='coerce')
        df['経度'] = pd.to_numeric(df['経度'], errors='coerce')
        
        print(f"Importing {len(df)} rows from Excel to Firestore...")
        
        for index, row in df.iterrows():
            doc_data = row.where(pd.notnull(row), None).to_dict() 
            
            doc_id = str(doc_data.get('事例')) 

            # '事例'カラムをdoc_dataから削除しない (app.pyで参照するため)
            # '事例名'カラムもFirestoreに保存されるように、doc_dataにそのまま含める
            # Excelに'事例名'列がない場合はNoneになる

            if 'date_added' not in doc_data or doc_data['date_added'] is None:
                doc_data['date_added'] = firestore.SERVER_TIMESTAMP 

            db.collection(COLLECTION_NAME).document(doc_id).set(doc_data) 
            
        print(f"Data imported successfully from Excel to Firestore collection '{COLLECTION_NAME}'.")

    except Exception as e:
        print(f"データのインポート中にエラーが発生しました: {e}")
    finally: 
        if conn and isinstance(conn, sqlite3.Connection): 
            conn.close()

if __name__ == '__main__':
    try:
        import firebase_admin
    except ImportError:
        print("firebase-adminライブラリが見つかりません。インストールしています...")
        os.system("pip install firebase-admin")
        print("インストールが完了しました。スクリプトを再度実行してください。")
        exit(0)

    init_firestore_collection() 
    import_data_to_firestore()
