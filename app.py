def load_history_from_csv(file_path):
    if not os.path.exists(file_path):
        return pd.DataFrame()
    
    try:
        # encoding='cp932' は日本のExcel書き出しCSVで一般的な文字コードです
        raw_df = pd.read_csv(file_path, header=None, encoding='cp932')
    except:
        raw_df = pd.read_csv(file_path, header=None, encoding='utf-8')
    
    # データの位置を特定
    # 1行目(index 0): 日付
    # 2行目(index 1): 試合番号
    # 3行目以降(index 2~): [選手名, スコア1, スコア2, ...]
    
    dates_row = raw_df.iloc[0].values
    match_nums = raw_df.iloc[1].values
    
    history = []
    
    # 3行目（index 2）から最終行までループ
    for i in range(2, len(raw_df)):
        player_name = str(raw_df.iloc[i, 0]).strip()
        
        # 名前が空、またはドラフト設定にいない選手はスキップ
        if not player_name or player_name == "nan" or player_name not in PLAYER_TO_OWNER:
            continue
        
        # 2列目（index 1）から最終列までスコアをチェック
        for col in range(1, len(raw_df.columns)):
            val = raw_df.iloc[i, col]
            
            # 数字（スコア）が入っていないセルは飛ばす
            if pd.isna(val) or str(val).strip() == "":
                continue
            
            # 日付の補完（左側の列を探索）
            d_val = None
            for back in range(col, 0, -1):
                temp_d = str(dates_row[back]).strip()
                if temp_d != "" and temp_d != "nan":
                    d_val = temp_d
                    break
            
            if not d_val:
                continue
                
            # 試合番号の取得
            try:
                m_idx = int(float(match_nums[col]))
            except:
                m_idx = 1 # 万が一取れなければ第1試合とする
            
            # 日付のパース (2024/9/16 等に対応)
            try:
                dt = pd.to_datetime(d_val)
                date_str = dt.strftime('%Y%m%d')
            except:
                continue
                
            history.append({
                "date": date_str,
                "m_label": f"第{m_idx}試合",
                "match_uid": f"{date_str}_{m_idx}",
                "player": player_name,
                "point": float(val),
                "owner": PLAYER_TO_OWNER[player_name]
            })
            
    return pd.DataFrame(history)
