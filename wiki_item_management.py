import json
import os
import urllib.request #Discordに通知を送るために追加
import gspread
from gspread_formatting import(
    batch_updater,
    CellFormat,
    Color,
    TextFormat,
    Borders,
    Border
)

#各種設定（パスやID）
JSON_KEY_FILE = r"credentials.json"
SPREADSHEET_ID ="YOUR_SPREADSHEET_ID_HERE"
SHEET_NAME="シート1"

#Discordのwebhook URL
DISCORD_WEBHOOK_URL="YOUR_DISCORD_WEBHOOK_URL_HERE"

#GoogleシートAPTの認証とスプレッドシートの接続
gc = gspread.service_account(filename=JSON_KEY_FILE)
spreadsheet = gc.open_by_key(SPREADSHEET_ID)

#指定したワークシートを開く
try:
    management_sheet = spreadsheet.worksheet(SHEET_NAME)
except gspread.exceptions.WorksheetNotFound:
    management_sheet = spreadsheet.add_worksheet(title=SHEET_NAME,rows="1000",cols="20")

#各ファイルとカテゴリ名リスト
WIKI_JSON_FILES = [
    {"path": "wiki_data.json", "category": "武器"},
    {"path": "wiki_data2.json", "category": "アイテム記録"},
    {"path": "wiki_data3.json", "category": "貴重品倉庫"},
    {"path": "wiki_data4.json", "category": "設備"},
    {"path": "wiki_data5.json", "category": "装備"},
    {"path": "wiki_data6.json", "category": "基質"},
    {"path": "wiki_data7.json", "category": "脅威"},
    {"path": "wiki_data8.json", "category": "システム図面"},
    {"path": "wiki_data9.json", "category": "オペレーター攻略"}
]

#【追加】Discordにメッセージを送信する関数
def send_discord_notification(message):
    if not DISCORD_WEBHOOK_URL or "あなたのURL" in DISCORD_WEBHOOK_URL:
        print("Discord Webhook URLが設定されていないため、通知をスキップします。")
        return
    paylond={"content":message}
    headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0"}

    try:
        req=urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=json.dumps(paylond).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req)as res:
            if res.status==204 or res.status==200:
                print("Discordへ通知が成功しました！")
            else:
                print("Discord通知で予期しないステータスが返しました:{res.staus}")
    except Exception as e:
        print(f"Dsicordへの通知中にエラーが発生しました：{e}")

#指定されたJSONファイルから【全データ】を抽出したステータス判定
def exctract_all_items_from_file(file_path, category_name):
    if not os.path.exists(file_path):
        print(f"注意：{file_path}が見つからないためスキップします。")
        return []
    
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            res_json = json.load(f)
        except Exception as e:
            print(f"JSONファイルの読み込みエラー({file_path}): {e}")
            return []
        
    # データの入れ物や関数を、すべてこの関数の「内側」に引き込みます
    all_items = []

    def find_items_recursive(data):
        if isinstance(data, dict):
            if "name" in data and "itemId" in data:
                all_items.append(data)
            for value in data.values():
                find_items_recursive(value)
        elif isinstance(data, list):
            for item in data:
                find_items_recursive(item)

    
    find_items_recursive(res_json)

    file_data = []

    for item in all_items:
        item_name = str(item.get("name", "")).strip()
        raw_id = str(item.get("itemId", "")).strip()
        if not raw_id or raw_id == "None":
            raw_id = str(item.get("id", "")).strip()
        
        caption = item.get("caption", [])
        status_val = item.get("status", None)
        published = item.get("publishedAtTs", None)

        if not raw_id or not item_name or raw_id == "None":
            continue
        if item_name in ["エンドフィールドwiki", "武器", "レア度", "属性"]:
            continue
        if "★" in item_name or "片手剣" in item_name or "拳銃" in item_name:
            continue

        is_edited = False

        # 判定ルール①：公開タイムスタンプがある、またはstatus2以上なら編集済み
        if published is not None or (status_val is not None and status_val >= 2):
            is_edited = True

        # 判定ルール②：caption(説明文)がリストで、中身があれば編集済み
        # 判定ルール②：caption(説明文)の中身をチェック
        # リストの中に文字以外（辞書など）が入っていても絶対にエラーにならないように安全化
        if isinstance(caption, list) and len(caption) > 0:
            caption_parts = []
            for c in caption:
                if isinstance(c, str):
                    caption_parts.append(c)
                else:
                    caption_parts.append(str(c)) # 文字以外も強制的に文字に変換
            caption_str = "".join(caption_parts).strip()
        else:
            caption_str = str(caption).strip()

        if caption_str and caption_str != "None" and caption_str != "[]" and caption_str != "{}":
            is_edited = True
        
        # 最終的な文字決定（名前を status_text に統一して波線を消しました）
        if is_edited:
            status_text = "完了"
        else:
            status_text = "未完了"
        
        wiki_url = f"https://wiki.skport.com/endfield/detail?mainTypeId=1&subTypeId=2&gameEntryId={raw_id}&header=0"

        # 1つずつのアイテム行を作成する
        file_data.append([
            raw_id,
            item_name,
            category_name,
            status_text,
            wiki_url
        ])

    # 💡 正しいインデント位置に戻したため、return の波線も消えます！
    return file_data


# ==========================================
# 3. メイン実行処理
# ==========================================
def main():
    print("=== 全アイテム管理・自動色分けを開始します ===")
    
    all_items_list = []
    seen_ids = set()

    # 1. すべてのJSONファイルからデータを集めるループ
    for file_info in WIKI_JSON_FILES:
        item_from_file = exctract_all_items_from_file(file_info["path"], file_info["category"])

        for row in item_from_file:
            raw_id = row[0]
            if raw_id in seen_ids:
                continue
            seen_ids.add(raw_id)
            all_items_list.append(row)
            
    if not all_items_list:
        print("アイテムが見つかりません。")
        return

    # 全体の完了・未完了件数をカウント
    count_done = 0
    count_todo = 0
    for row in all_items_list:
        if row[3] == "完了":
            count_done += 1
        else:
            count_todo += 1
    
    total_count = len(all_items_list)
    print(f"結合完了！全アイテムデータを重複なしで【{len(all_items_list)}件】検出しました")
    print("Googleのスプレッドシートへ入力中…")

    try:
        gc = gspread.service_account(filename=JSON_KEY_FILE)
        sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    except Exception as e:
        print(f"接続・承認エラー: {e}")
        return
    
    try:
        header = [["ID", "名前", "カテゴリ", "状況", "確認URL"]]
        all_rows = header + all_items_list

        sheet.clear()
        sheet.update(values=all_rows, range_name="A1")

        summary_table = [
            ["進捗状況", "件数"],
            ["完了", count_done],
            ["未完了", count_todo],
            ["合計", total_count]
        ]

        print("完了（緑）、未完了（赤）のデザイン運用中…")
        
        # 💡 ここでgspread_formattingの正式なお作法（オブジェクト）を作成します
        from gspread_formatting import CellFormat, textFormat

        thin_border = Border(style="SOLID", color=color(0.8, 0.8, 0.8))
        all_borders = Borders(top=thin_border, bottom=thin_border, left=thin_border, right=thin_border)
        
        GREEN_BG = color(0.85, 0.93, 0.85)
        RED_BG = color(0.96, 0.86, 0.86)

        done_rows = []
        todo_rows = []

        for idx, row_data in enumerate(all_items_list, start=2):
            if row_data[3] == "完了":
                done_rows.append(idx)
            else:
                todo_rows.append(idx)

        with batch_updater(sheet.spreadsheet) as batch:

            # ①ヘッダー行のデザイン（黒、白）を正式なCellFormatで定義
            header_format = CellFormat(
                backgroundColor=color(0.26, 0.26, 0.26),
                textFormat=textFormat(foregroundColor=color(1.0, 1.0, 1.0), bold=True, fontSize=11),
                horizontalAlignment="CENTER",
                borders=all_borders
            )
            batch.format_cell_range(sheet, "A1:E1", header_format)

            # ②右側の集計表ヘッダー行のデザイン(G1:H1)
            batch.format_cell_range(sheet, "G1:H1", header_format)

            # ③集計表の中身（G2:H4）のデザイン
            summary_body_format = CellFormat(
                backgroundColor=color(1.0, 1.0, 1.0),
                textFormat=textFormat(bold=False, fontSize=10),
                horizontalAlignment="CENTER",
                borders=all_borders
            )
            batch.format_cell_range(sheet, "G2:H4", summary_body_format)

            # 合計行(G4:H4)だけ太文字にする
            total_row_format = CellFormat(
                backgroundColor=color(0.95, 0.95, 0.95),
                textFormat=textFormat(bold=True, fontSize=10),
                borders=all_borders
            )
            batch.format_cell_range(sheet, "G4:H4", total_row_format)
            
            pairs = []
            
            # 「完了」の行をリストに追加
            if done_rows:
                center_green = CellFormat(backgroundColor=GREEN_BG, horizontalAlignment="CENTER", borders=all_borders)
                left_green = CellFormat(backgroundColor=GREEN_BG, horizontalAlignment="LEFT", borders=all_borders)
                for r in done_rows:
                    pairs.append((f"A{r}:D{r}", center_green))
                    pairs.append((f"E{r}", left_green))

            # 「未完了」の行をリストに追加
            if todo_rows:
                center_red = CellFormat(backgroundColor=RED_BG, horizontalAlignment="CENTER", borders=all_borders)
                left_red = CellFormat(backgroundColor=RED_BG, horizontalAlignment="LEFT", borders=all_borders)
                for r in todo_rows:
                    pairs.append((f"A{r}:D{r}", center_red))
                    pairs.append((f"E{r}", left_red))

            # 正式なフォーマットオブジェクトが1件でもあればGoogleへ送信
            if pairs:
                batch.format_cell_ranges(sheet, pairs)
        
        # 集計表の数値を書き込み
        sheet.update(values=summary_table, range_name="G1:H4")
        
        print("シートの説明文を書き込んでいます...")

        # シートG6～G11まで文字を流し込む
        sheet.update_acell('G6', 'このシートについて')
        sheet.update_acell('G7', '※このシートはPythonで作られています。')
        sheet.update_acell('G8', '※表を確認し、編集に取り組んでください。緑色は編集完了、赤色は未編集です。')
        sheet.update_acell('G9', '※確認URLをクリックしますと、状況を確認することができます。')
        sheet.update_acell('G10', '※シートはいじらないようにしてください。編集完了するとDeveloperが自動更新します。')
        sheet.update_acell('G11', '※右の表を確認しますと、進捗状況と件数を確認することができます。')

        print("説明文のデザインを整えています...")
        
        info_header_format = CellFormat(
            backgroundColor=color(1.0, 0.92, 0.65),  # 薄い黄色
            textFormat=textFormat(bold=True, foregroundColor=color(0.0, 0.0, 0.0))
        )
        info_body_format = CellFormat(
            backgroundColor=color(1.0, 1.0, 1.0),  # 白背景
            textFormat=textFormat(foregroundColor=color(0.0, 0.0, 0.0))
        )

        # 6行目を黄色見出し、7〜11行目を白背景に装飾
        format_cell_ranges(sheet, [
            ("G6:L6", info_header_format),
            ("G7:L11", info_body_format)
        ])
    
        print("説明文の自動生成が全て完了しました！")

        success_msg = f"✅すべてのファイルの統合、およびスプレッドシートの自動色分け完了しました！"
        print(success_msg)

        # Discordへ通知を飛ばします
        send_discord_notification(success_msg)
        
        spreadsheet_url = f"https://docs.google.com/spreadsheets/d/1ufrU34QtaIDT4iGYmkE27PltBDB6yuWO00kZpurcUuo/edit?gid=0#gid=0"
        print(f"➡スプレッドシートを確認する{spreadsheet_url}")

        # Discord送信用
        discord_msg = f"☛スプレッドシートの自動更新が完了しました!\n **現在の進捗状況**\n・完了：{count_done}件\n・未完了：{count_todo}件\n・全体の合計{total_count}件\n 確認：{spreadsheet_url}"
        send_discord_notification(discord_msg)

    except Exception as e:
        print(f"スプレッドシート処理エラー: {e}")

if __name__ == "__main__":
    main()
