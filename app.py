# --- サイドバーのデータ管理エリア ---
with st.sidebar:
    st.markdown("---")
    st.subheader("データ管理")
    
    if st.button('🔄 データを更新'):
        st.cache_data.clear()
        st.rerun()

    # 2025-26など、Webから取得している場合に「エクセル形式」で書き出す機能
    if not os.path.exists(csv_file) and not df_history.empty:
        st.info("現在のWebデータをエクセル形式のCSVで保存できます。")
        
        # --- 見やすいマトリックス形式に変換 ---
        # 1. 縦に並んでいるデータを[選手名]をインデックス、[date, m_label]を列に変換
        pivot_df = df_history.pivot(index='player', columns=['date', 'm_label'], values='point')
        
        # 2. 列名を日付だけに整理（2行構成にする準備）
        # 日付行
        dates_row = [""] + [pd.to_datetime(c[0]).strftime('%Y/%m/%d') for c in pivot_df.columns]
        # 試合番号行 (第1試合 -> 1, 第2試合 -> 2)
        match_row = [""] + [c[1].replace("第", "").replace("試合", "") for c in pivot_df.columns]
        
        # 3. CSV用の文字列を作成
        output_csv = ",".join(dates_row) + "\n"
        output_csv += ",".join(match_row) + "\n"
        
        # 選手ごとのスコア行を追加
        # 全選手（設定ファイルにいる全員）を出すためにPLAYER_TO_OWNERのキーを使う
        all_players_in_season = sorted(list(PLAYER_TO_OWNER.keys()))
        for p in all_players_in_season:
            row_data = [p]
            for col in pivot_df.columns:
                val = pivot_df.loc[p, col] if p in pivot_df.index else ""
                row_data.append(str(val) if pd.notna(val) else "")
            output_csv += ",".join(row_data) + "\n"
        
        # ダウンロードボタン
        st.download_button(
            label="💾 現在のデータをCSVで保存",
            data=output_csv.encode('cp932'), # エクセルで開くためにShift-JIS
            file_name=f"history_{selected_season}.csv",
            mime="text/csv",
        )
