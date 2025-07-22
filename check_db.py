import sqlite3

DATABASE = 'ryojo_customization.db'
TABLE_NAME = 'cases'

def check_data():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row # カラム名でアクセスできるようにする
    cursor = conn.cursor()

    print(f"--- Table '{TABLE_NAME}' Schema ---")
    cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
    schema = cursor.fetchall()
    for col in schema:
        print(f"  Column: {col['name']}, Type: {col['type']}, NotNull: {col['notnull']}")
    print("---------------------------------")

    print(f"--- Data from '{TABLE_NAME}' Table (first 10 rows) ---")
    cursor.execute(f'SELECT * FROM {TABLE_NAME} LIMIT 10') # 最初の10件だけ表示
    rows = cursor.fetchall()

    if not rows:
        print("No data found.")
    else:
        # ヘッダーを表示
        print(" | ".join([col[0] for col in cursor.description]))
        print("-" * (len(" | ".join([col[0] for col in cursor.description]))))
        # データを表示
        for row in rows:
            row_values = []
            for key in row.keys():
                value = row[key]
                if isinstance(value, str):
                    row_values.append(value.strip()) # 文字列の場合は前後の空白を削除
                else:
                    row_values.append(str(value))
            print(" | ".join(row_values))

    print("---------------------------------")
    conn.close()

if __name__ == '__main__':
    check_data()