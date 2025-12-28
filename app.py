import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import plotly.express as px
import json
import os

# --- ページ設定 ---
st.set_page_config(page_title="M-POG Archives", layout="wide")

# ==========================================
# 1. 外部の設定ファイル (JSON) を読み込む
# ==========================================
CONFIG_FILE = "draft_configs.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        st.error(f"設定ファイル {CONFIG_FILE} が見つかりません。")
        return {}

ARCHIVE_CONFIG = load_config()

if not ARCHIVE_CONFIG:
    st.stop()

# サイドバーで年度を選択
selected_season = st.sidebar.selectbox("表示するシーズンを選択", list(ARCHIVE_CONFIG.keys()), index=0)

# 選択された年度の設定をセット
SEASON_START = ARCHIVE_CONFIG[selected_season]["start_date"]
SEASON_END = ARCHIVE_CONFIG[selected_season]["end_date"]
TEAM_CONFIG = ARCHIVE_CONFIG[selected_season]["teams"]
PLAYER_TO_OWNER = {p: owner for owner, config in TEAM_CONFIG.items() for p in config['players']}

# --- スタイル設定 (CSS) ---
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
# 2. データ取得・フィルタリング
# ==========================================
def filter_point(text):
    if not text or "--" in text: return None
    clean = text.replace('▲', '-').replace(' ', '').replace('pts', '')
    found = re.findall(r'[0-9.\-]', clean)
    return "".join(found) if found else None

@st.cache_data(ttl=1800)
def get_filtered_history(season_start, season_end):
    # 本来は年度に応じて「公式サイトから取る」か「過去CSVから取る」か分岐させる土台
    # 現時点では公式サイトから取得し、期間外を弾く
    url = "https://m-league.jp/games/"
    headers = {"User-Agent": "Mozilla/5.0"}
    history = []
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        for container in soup.find_all(class_="c-modal2"):
            m_id = container.get('id', '')
            date_match = re.search(r'(\d{8})', m_id)
            if not date_match: continue
            
            date_str = date_match.group(1)
            # 期間外のデータをガード
            if not (season_start <= date_str <= season_end):
                continue
            
            names_raw = container.find_all(class_="p-gamesResult__name")
            points_raw = container.find_all(class_="p-gamesResult__point")
            valid = []
            for n_tag, p_tag in zip(names_raw, points_raw):
                name = n_tag.get_text(strip=True)
                p_val = filter_point(p_tag.get_text(strip=True))
                if name in PLAYER_TO_OWNER and p_val:
                    valid.append({"name": name, "point": float(p_val)})
            
            for i in range(0, len(valid), 4):
                chunk = valid[i:i+4]
                if len(chunk) < 4: continue
                m_idx = (i // 4) + 1
                for p_data in chunk:
                    history.append({
                        "date": date_str, "m_label": f"第{m_idx}試合", "match_uid": f"{date_str}_{m_id}_{m_idx}",
                        "player": p_data["name"], "point": p_data["point"], "owner": PLAYER_TO_OWNER[p_data["name"]]
                    })
        return pd.DataFrame(history)
    except: return pd.DataFrame()

df_history = get_filtered_history(SEASON_START, SEASON_END)

# --- 以下、表示ロジック ---
if df_history.empty:
    st.warning(f"{selected_season} のデータが見つかりません。")
else:
    # 集計
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
        for m_uid in df_latest['match_uid'].unique():
            df_m = df_latest[df_latest['match_uid'] == m_uid].sort_values("point", ascending=False)
            st.write(f"**{df_m['m_label'].iloc[0]}**")
            html = '<table class="pog-table"><tr><th>選手</th><th>オーナー</th><th>ポイント</th></tr>'
            for row in df_m.itertuples():
                bg = TEAM_CONFIG[row.owner]['bg_color']
                html += f'<tr style="background-color:{bg}"><td>{row.player}</td><td>{row.owner}</td><td>{row.point:+.1f}</td></tr>'
            st.markdown(html + '</table>', unsafe_allow_html=True)

    st.write("---")
    st.markdown('<div class="section-label">📈 ポイント推移グラフ</div>', unsafe_allow_html=True)
    daily = df_history.groupby(['date', 'owner'])['point'].sum().unstack().fillna(0).cumsum().reset_index()
    daily['date'] = pd.to_datetime(daily['date']).dt.strftime('%m/%d')
    df_plot = daily.melt(id_vars='date', var_name='オーナー', value_name='累計pt')
    fig_line = px.line(df_plot, x='date', y='累計pt', color='オーナー', color_discrete_map={k: v['color'] for k, v in TEAM_CONFIG.items()}, markers=True)
    st.plotly_chart(fig_line, use_container_width=True)

    st.markdown('<div class="section-label">📊 チーム別内訳</div>', unsafe_allow_html=True)
    row_owners = [list(TEAM_CONFIG.keys())[:2], list(TEAM_CONFIG.keys())[2:]]
    for group in row_owners:
        c1, c2 = st.columns(2)
        for i, name in enumerate(group):
            with [c1, c2][i]:
                df_sub = df_players[df_players["オーナー"] == name].sort_values("ポイント", ascending=True)
                fig_bar = px.bar(df_sub, y="選手", x="ポイント", orientation='h', color_discrete_sequence=[TEAM_CONFIG[name]['color']], text_auto='.1f', title=f"【{name}】")
                st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown('<div class="section-label">👤 個人ランキング</div>', unsafe_allow_html=True)
    html = '<table class="pog-table"><tr><th>Rank</th><th>選手</th><th>オーナー</th><th>ポイント</th></tr>'
    for i, row in enumerate(df_players.itertuples(), 1):
        bg = TEAM_CONFIG[row.オーナー]['bg_color']
        html += f'<tr style="background-color:{bg}"><td>{i}</td><td>{row.選手}</td><td>{row.オーナー}</td><td>{row.ポイント:+.1f}</td></tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

with st.sidebar:
    if st.button('🔄 更新'):
        st.cache_data.clear()
        st.rerun()
