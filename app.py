import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import plotly.express as px
import json
import os

# --- 1. ページ基本設定 ---
st.set_page_config(page_title="M-POG Archives", layout="wide")

# ==========================================
# 2. 外部設定ファイルの読み込み
# ==========================================
CONFIG_FILE = "draft_configs.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

ARCHIVE_CONFIG = load_config()
if not ARCHIVE_CONFIG:
    st.error("設定ファイル draft_configs.json が見つかりません。")
    st.stop()

selected_season = st.sidebar.selectbox("表示するシーズンを選択", list(ARCHIVE_CONFIG.keys()), index=0)

conf = ARCHIVE_CONFIG[selected_season]
SEASON_START = conf["start_date"]
SEASON_END = conf["end_date"]
TEAM_CONFIG = conf["teams"]
PLAYER_TO_OWNER = {p: owner for owner, c in TEAM_CONFIG.items() for p in c['players']}

# --- スタイル設定 ---
st.markdown("""
<style>
    .pog-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
    .pog-table th { background-color: #444; color: white !important; padding: 10px; border: 1px solid #333; }
    .pog-table td { border: 1px solid #ddd; padding: 10px; text-align: center; color: #000000 !important; font-weight: bold; }
    .section-label { font-weight: bold; margin: 20px 0 10px 0; font-size: 1.2rem; border-left: 6px solid #444; padding-left: 10px; color: #333; }
</style>
""", unsafe_allow_html=True)

st.title(f"🀄 M-POG {selected_season}")

# ==========================================
# 3. データ処理ロジック
# ==========================================

def load_history_from_csv(file_path):
    if not os.path.exists(file_path): return pd.DataFrame()
    try: raw_df = pd.read_csv(file_path, header=None, encoding='cp932')
    except: raw_df = pd.read_csv(file_path, header=None, encoding='utf-8')
    
    dates_row = raw_df.iloc[0].tolist()
    match_nums = raw_df.iloc[1].tolist()
    history = []
    
    for i in range(2, len(raw_df)):
        player_name = str(raw_df.iloc[i, 0]).strip()
        if not player_name or player_name == "nan" or player_name not in PLAYER_TO_OWNER: continue
        for col in range(1, len(raw_df.columns)):
            val = raw_df.iloc[i, col]
            if pd.isna(val) or str(val).strip() == "": continue
            try: score = float(str(val).replace(' ', ''))
            except: continue
            d_val = dates_row[col]
            if pd.isna(d_val) or str(d_val).strip() in ["", "nan"]:
                for back in range(col, 0, -1):
                    if not pd.isna(dates_row[back]) and str(dates_row[back]).strip() not in ["", "nan"]:
                        d_val = dates_row[back]
                        break
            if not d_val: continue
            try:
                dt = pd.to_datetime(d_val)
                date_str = dt.strftime('%Y%m%d')
            except: continue
            m_num = int(float(match_nums[col])) if pd.notna(match_nums[col]) else 1
            history.append({
                "date": date_str, "m_label": f"第{m_num}試合", "match_uid": f"{date_str}_{m_num}",
                "player": player_name, "point": score, "owner": PLAYER_TO_OWNER[player_name]
            })
    return pd.DataFrame(history)

@st.cache_data(ttl=1800)
def get_web_history(season_start, season_end):
    """シンプルに全データを取得し、4人ずつ試合番号を振る"""
    url = "https://m-league.jp/games/"
    headers = {"User-Agent": "Mozilla/5.0"}
    history = []
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # モーダル（試合詳細）を探す
        for container in soup.find_all(class_=re.compile(r'c-modal')):
            date_match = re.search(r'(\d{8})', container.get('id', ''))
            if not date_match: continue
            date_str = date_match.group(1)
            if not (str(season_start) <= date_str <= str(season_end)): continue
            
            # 名前とポイントをすべて抜き出す
            names = container.find_all(class_=re.compile(r'name'))
            pts = container.find_all(class_=re.compile(r'point'))
            
            valid_list = []
            for n, p in zip(names, pts):
                name = n.get_text(strip=True)
                p_raw = p.get_text(strip=True).replace('▲', '-').replace('pts', '').replace(' ', '')
                p_val = "".join(re.findall(r'[0-9.\-]', p_raw))
                if name in PLAYER_TO_OWNER and p_val:
                    valid_list.append({"name": name, "point": float(p_val)})
            
            # 取得したリストを「4人ずつ」試合として分ける
            for i in range(0, len(valid_list), 4):
                chunk = valid_list[i:i+4]
                if len(chunk) < 4: continue # 4人揃っていない場合は飛ばす
                m_num = (i // 4) + 1
                for p_data in chunk:
                    history.append({
                        "date": date_str, 
                        "m_label": f"第{m_num}試合", 
                        "match_uid": f"{date_str}_{m_num}",
                        "player": p_data["name"], 
                        "point": p_data["point"], 
                        "owner": PLAYER_TO_OWNER[p_data["name"]]
                    })
        return pd.DataFrame(history)
    except:
        return pd.DataFrame()

# --- 実行 ---
csv_file = f"history_{selected_season}.csv"
if os.path.exists(csv_file):
    df_history = load_history_from_csv(csv_file)
else:
    df_history = get_web_history(SEASON_START, SEASON_END)

# ==========================================
# 4. 画面表示
# ==========================================
if df_history.empty:
    st.warning(f"データが1件も取得できませんでした。日付設定を確認してください。")
else:
    # 集計ロジック
    total_pts = df_history.groupby('player')['point'].sum()
    pog_summary, player_all = [], []
    for owner, cfg in TEAM_CONFIG.items():
        score = sum([total_pts.get(p, 0) for p in cfg['players']])
        pog_summary.append({"オーナー": owner, "合計": round(score, 1)})
        for p in cfg['players']:
            player_all.append({"選手": p, "オーナー": owner, "ポイント": round(total_pts.get(p, 0), 1)})
    
    df_teams = pd.DataFrame(pog_summary).sort_values("合計", ascending=False)
    df_players = pd.DataFrame(player_all).sort_values("ポイント", ascending=False)

    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.markdown('<div class="section-label">🏆 総合順位</div>', unsafe_allow_html=True)
        html = '<table class="pog-table"><tr><th>順位</th><th>オーナー</th><th>合計</th></tr>'
        for i, row in enumerate(df_teams.itertuples(), 1):
            bg = TEAM_CONFIG[row.オーナー]['bg_color']
            html += f'<tr style="background-color:{bg}"><td>{i}</td><td>{row.オーナー}</td><td>{row.合計:+.1f}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

    with col2:
        latest_date = df_history['date'].max()
        st.markdown(f'<div class="section-label">🀄 最新結果 ({latest_date[4:6]}/{latest_date[6:]})</div>', unsafe_allow_html=True)
        df_latest = df_history[df_history['date'] == latest_date]
        # 試合ごとに分割表示
        for m_uid in sorted(df_latest['match_uid'].unique()):
            df_m = df_latest[df_latest['match_uid'] == m_uid].sort_values("point", ascending=False)
            st.write(f"**{df_m['m_label'].iloc[0]}**")
            html = '<table class="pog-table"><tr><th>選手</th><th>オーナー</th><th>ポイント</th></tr>'
            for row in df_m.itertuples():
                bg = TEAM_CONFIG[row.owner]['bg_color']
                html += f'<tr style="background-color:{bg}"><td>{row.player}</td><td>{row.owner}</td><td>{row.point:+.1f}</td></tr>'
            st.markdown(html + '</table>', unsafe_allow_html=True)

    # グラフ表示
    st.write("---")
    st.markdown('<div class="section-label">📈 ポイント推移グラフ</div>', unsafe_allow_html=True)
    daily = df_history.groupby(['date', 'owner'])['point'].sum().unstack().fillna(0).cumsum().reset_index()
    daily['date'] = pd.to_datetime(daily['date']).dt.strftime('%m/%d')
    df_plot = daily.melt(id_vars='date', var_name='オーナー', value_name='累計pt')
    fig_line = px.line(df_plot, x='date', y='累計pt', color='オーナー', 
                      color_discrete_map={k: v['color'] for k, v in TEAM_CONFIG.items()}, markers=True)
    st.plotly_chart(fig_line, use_container_width=True)

# --- 5. 管理機能 ---
with st.sidebar:
    st.markdown("---")
    if st.button('🔄 データを更新'):
        st.cache_data.clear()
        st.rerun()
