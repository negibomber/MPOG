import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import plotly.express as px
from datetime import datetime

# ==========================================
# 1. 設定・データ定義
# ==========================================
SEASON_NAME = "2025-26"
TEAM_CONFIG = {
    "どら": {"color": "#FF4B4B", "bg_color": "#FF4B4B", "players": ["瑞原明奈", "竹内元太", "石井一馬", "内川幸太郎", "多井隆晴", "日向藍子", "鈴木たろう", "HIRO柴田", "滝沢和典", "東城りお"]},
    "よしたに": {"color": "#00CC96", "bg_color": "#00CC96", "players": ["堀慎吾", "鈴木優", "渡辺太", "下石戟", "松本吉弘", "小林剛", "醍醐大", "阿久津翔太", "浅見真紀", "三浦智博"]},
    "ねぎし": {"color": "#636EFA", "bg_color": "#636EFA", "players": ["仲林圭", "白鳥翔", "園田賢", "佐々木寿人", "伊達朱里紗", "勝又健志", "渋川難波", "本田朋広", "浅井堂岐", "瀬戸熊直樹"]},
    "ひかえ": {"color": "#AB63FA", "bg_color": "#AB63FA", "players": ["二階堂亜樹", "逢川恵夢", "黒沢咲", "鈴木大介", "高宮まり", "岡田紗佳", "萩原聖人", "茅森早香", "永井孝典", "中田花奈"]}
}
PLAYER_TO_OWNER = {p: owner for owner, config in TEAM_CONFIG.items() for p in config['players']}

st.set_page_config(page_title=f"M-POG {SEASON_NAME}", layout="wide")

# スタイル：背景色を塗りつぶさず、左側のボーダーラインで色を表現する（視認性重視）
st.markdown("""
<style>
    .pog-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; color: #31333F; }
    .pog-table th { background-color: #f0f2f6; border-bottom: 2px solid #ccc; padding: 10px; text-align: center; font-size: 0.8rem; color: #31333F; }
    .pog-table td { border-bottom: 1px solid #eee; padding: 12px 8px; text-align: center; font-size: 0.9rem; background-color: white !important; color: black !important; }
    .team-border { border-left: 8px solid; }
    .section-label { font-weight: bold; margin: 20px 0 10px 0; font-size: 1.2rem; color: #1f77b4; display: flex; align-items: center; }
</style>
""", unsafe_allow_html=True)

st.title(f"🀄 M-POG {SEASON_NAME}")

# ==========================================
# 2. データ取得（堅牢版）
# ==========================================
def filter_point(text):
    if not text or "--" in text: return None
    clean_text = text.replace('▲', '-').replace(' ', '').replace('pts', '')
    found = re.findall(r'[0-9.\-]', clean_text)
    return "".join(found) if found else None

@st.cache_data(ttl=1800)
def get_detailed_history():
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

df_history = get_detailed_history()

if df_history.empty:
    st.warning("対局データが取得できませんでした。更新ボタンを押してください。")
else:
    # 総合順位
    total_pts = df_history.groupby('player')['point'].sum()
    pog_summary = []
    player_all = []
    for owner, cfg in TEAM_CONFIG.items():
        score = sum([total_pts.get(p, 0) for p in cfg['players']])
        pog_summary.append({"オーナー": owner, "合計": round(score, 1)})
        for p in cfg['players']:
            player_all.append({"選手": p, "オーナー": owner, "ポイント": round(total_pts.get(p, 0), 1)})
    
    df_teams = pd.DataFrame(pog_summary).sort_values("合計", ascending=False)
    df_players = pd.DataFrame(player_all).sort_values("ポイント", ascending=False)

    # --- レイアウト ---
    col1, col2 = st.columns([1, 1.2])

    with col1:
        st.markdown('<div class="section-label">🏆 総合順位</div>', unsafe_allow_html=True)
        html = '<table class="pog-table"><tr><th>順位</th><th>オーナー</th><th>合計</th></tr>'
        for i, row in enumerate(df_teams.itertuples(), 1):
            color = TEAM_CONFIG[row.オーナー]['color']
            html += f'<tr><td>{i}</td><td class="team-border" style="border-left-color:{color}">{row.オーナー}</td><td>{row.合計:+.1f}</td></tr>'
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
                color = TEAM_CONFIG[row.owner]['color']
                html += f'<tr><td>{row.player}</td><td class="team-border" style="border-left-color:{color}">{row.owner}</td><td>{row.point:+.1f}</td></tr>'
            st.markdown(html + '</table>', unsafe_allow_html=True)

    # --- グラフ ---
    st.write("---")
    st.markdown('<div class="section-label">📈 推移グラフ</div>', unsafe_allow_html=True)
    daily = df_history.groupby(['date', 'owner'])['point'].sum().unstack().fillna(0).cumsum().reset_index()
    daily['date'] = pd.to_datetime(daily['date']).dt.strftime('%m/%d')
    df_plot = daily.melt(id_vars='date', var_name='オーナー', value_name='累計pt')
    fig = px.line(df_plot, x='date', y='累計pt', color='オーナー', color_discrete_map={k: v['color'] for k, v in TEAM_CONFIG.items()}, markers=True)
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='black', margin=dict(l=0,r=0,t=30,b=0))
    st.plotly_chart(fig, use_container_width=True)

    # --- 個人ランキング ---
    st.markdown('<div class="section-label">👤 個人ランキング</div>', unsafe_allow_html=True)
    html = '<table class="pog-table"><tr><th>Rank</th><th>選手</th><th>オーナー</th><th>pt</th></tr>'
    for i, row in enumerate(df_players.itertuples(), 1):
        color = TEAM_CONFIG[row.オーナー]['color']
        html += f'<tr><td>{i}</td><td>{row.選手}</td><td class="team-border" style="border-left-color:{color}">{row.オーナー}</td><td>{row.ポイント:+.1f}</td></tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

with st.sidebar:
    if st.button('🔄 データを強制更新'):
        st.cache_data.clear()
        st.rerun()
