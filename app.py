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
    "どら": {"color": "#ffadad", "bg_color": "#fff2f2", "players": ["瑞原明奈", "竹内元太", "石井一馬", "内川幸太郎", "多井隆晴", "日向藍子", "鈴木たろう", "HIRO柴田", "滝沢和典", "東城りお"]},
    "よしたに": {"color": "#caffbf", "bg_color": "#f6fff5", "players": ["堀慎吾", "鈴木優", "渡辺太", "下石戟", "松本吉弘", "小林剛", "醍醐大", "阿久津翔太", "浅見真紀", "三浦智博"]},
    "ねぎし": {"color": "#a0c4ff", "bg_color": "#f2f7ff", "players": ["仲林圭", "白鳥翔", "園田賢", "佐々木寿人", "伊達朱里紗", "勝又健志", "渋川難波", "本田朋広", "浅井堂岐", "瀬戸熊直樹"]},
    "ひかえ": {"color": "#d3d3d3", "bg_color": "#f9f9f9", "players": ["二階堂亜樹", "逢川恵夢", "黒沢咲", "鈴木大介", "高宮まり", "岡田紗佳", "萩原聖人", "茅森早香", "永井孝典", "中田花奈"]}
}

PLAYER_TO_OWNER = {p: owner for owner, config in TEAM_CONFIG.items() for p in config['players']}

st.set_page_config(page_title=f"M-POG {SEASON_NAME}", layout="wide")

# スタイル定義
st.markdown("""
<style>
    .pog-table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 13px; margin-bottom: 20px; }
    .pog-table th { background-color: #444; color: white; border: 1px solid #333; padding: 6px; text-align: center; }
    .pog-table td { border: 1px solid #ddd; padding: 6px; text-align: center; white-space: nowrap; }
    .section-label { font-weight: bold; margin: 15px 0 5px 0; color: #111; font-size: 1rem; border-left: 4px solid #444; padding-left: 8px; }
</style>
""", unsafe_allow_html=True)

st.title(f"🏆 Mリーグ POG {SEASON_NAME}")

# ==========================================
# 2. データ取得（4人ずつの正確な分割）
# ==========================================
def filter_point(text):
    clean_text = text.replace('▲', '-')
    found = re.findall(r'[0-9.\-]', clean_text)
    return "".join(found)

@st.cache_data(ttl=1800)
def get_detailed_history():
    url = "https://m-league.jp/games/"
    headers = {"User-Agent": "Mozilla/5.0"}
    history = []
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        match_containers = soup.find_all(class_="c-modal2")
        for container in match_containers:
            m_id = container.get('id', '')
            date_match = re.search(r'(\d{8})', m_id)
            if not date_match: continue
            date_str = date_match.group(1)
            names = [n.get_text(strip=True) for n in container.find_all(class_="p-gamesResult__name") if n.get_text(strip=True) != "選手名"]
            points = [p.get_text(strip=True).split(' ')[0] for p in container.find_all(class_="p-gamesResult__point")]
            valid_entries = []
            for n, p in zip(names, points):
                p_str = filter_point(p)
                if p_str and n in PLAYER_TO_OWNER:
                    valid_entries.append({"name": n, "point": float(p_str)})
            for i in range(0, len(valid_entries), 4):
                match_players = valid_entries[i:i+4]
                if len(match_players) < 4: continue
                match_index = (i // 4) + 1
                match_uid = f"{date_str}_{m_id}_{match_index}"
                for p_data in match_players:
                    history.append({
                        "date": date_str, "match_uid": match_uid, "match_label": f"第{match_index}試合",
                        "player": p_data["name"], "point": p_data["point"], "owner": PLAYER_TO_OWNER[p_data["name"]]
                    })
        return pd.DataFrame(history)
    except: return pd.DataFrame()

# ==========================================
# 3. メイン処理
# ==========================================
df_history = get_detailed_history()

if df_history.empty:
    st.info("データを読み込み中...")
else:
    latest_date = df_history['date'].max()
    display_date = datetime.strptime(latest_date, '%Y%m%d').strftime('%m/%d')
    
    # 集計
    latest_pts = df_history.groupby('player')['point'].sum()
    pog_summary, player_list = [], []
    for owner, config in TEAM_CONFIG.items():
        total = 0
        for p in config['players']:
            pts = latest_pts.get(p, 0.0)
            total += pts
            player_list.append({"選手": p, "オーナー": owner, "ポイント": round(pts, 1)})
        pog_summary.append({"オーナー": owner, "合計": round(total, 1)})
    
    df_teams = pd.DataFrame(pog_summary).sort_values("合計", ascending=False)
    df_teams.insert(0, "順位", range(1, len(df_teams) + 1))
    df_players = pd.DataFrame(player_list).sort_values("ポイント", ascending=False)
    df_players.insert(0, "Rank", range(1, len(df_players) + 1))

    # --- レイアウト：順位と最新結果 ---
    col_l, col_r = st.columns([1, 1.2])
    with col_l:
        st.subheader("🏆 総合順位")
        html = '<table class="pog-table"><tr><th>順位</th><th>オーナー</th><th>合計pt</th></tr>'
        for _, row in df_teams.iterrows():
            bg = TEAM_CONFIG[row['オーナー']]['bg_color']
            html += f'<tr style="background-color:{bg}"><td>{row["順位"]}</td><td>{row["オーナー"]}</td><td>{row["合計"]:+.1f}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

    with col_r:
        st.subheader(f"⚾ 最新結果 ({display_date})")
        df_latest = df_history[df_history['date'] == latest_date]
        m_uids = df_latest['match_uid'].unique()
        for m_uid in m_uids:
            df_m = df_latest[df_latest['match_uid'] == m_uid].sort_values("point", ascending=False)
            st.markdown(f'<div class="section-label">{df_m["match_label"].iloc[0]}</div>', unsafe_allow_html=True)
            html = '<table class="pog-table"><tr><th>選手名</th><th>オーナー</th><th>ポイント</th></tr>'
            for _, row in df_m.iterrows():
                bg = TEAM_CONFIG[row['owner']]['bg_color']
                html += f'<tr style="background-color:{bg}"><td>{row["player"]}</td><td>{row["owner"]}</td><td>{row["point"]:+.1f}</td></tr>'
            st.markdown(html + '</table>', unsafe_allow_html=True)

    # --- グラフ：推移 ---
    st.write("---")
    st.subheader("📈 ポイント推移")
    daily_stats = df_history.groupby(['date', 'owner'])['point'].sum().reset_index()
    df_pivot = daily_stats.pivot(index='date', columns='owner', values='point').fillna(0)
    df_cumulative = pd.concat([pd.DataFrame([[0]*4], columns=df_pivot.columns, index=["20250915"]), df_pivot]).sort_index().cumsum().reset_index().rename(columns={'index': 'date'})
    df_plot = df_cumulative.melt(id_vars='date', var_name='オーナー', value_name='累計pt')
    df_plot['日付'] = pd.to_datetime(df_plot['date']).dt.strftime('%m/%d')
    fig_line = px.line(df_plot, x='日付', y='累計pt', color='オーナー', color_discrete_map={k: v['color'] for k, v in TEAM_CONFIG.items()}, markers=True)
    st.plotly_chart(fig_line, use_container_width=True)

    # --- 棒グラフ：チーム別内訳 (復活！) ---
    st.subheader("📊 チーム別・個人貢献度")
    rows = [list(TEAM_CONFIG.keys())[:2], list(TEAM_CONFIG.keys())[2:]]
    for row_owners in rows:
        cols = st.columns(2)
        for i, owner_name in enumerate(row_owners):
            with cols[i]:
                df_sub = df_players[df_players["オーナー"] == owner_name].sort_values("ポイント", ascending=True)
                fig_sub = px.bar(df_sub, y="選手", x="ポイント", orientation='h', color_discrete_sequence=[TEAM_CONFIG[owner_name]['color']], text_auto='.1f', title=f"【{owner_name}】")
                fig_sub.update_layout(plot_bgcolor='rgba(0,0,0,0)', height=300, margin=dict(l=0,r=20,t=40,b=0), yaxis_title="")
                st.plotly_chart(fig_sub, use_container_width=True)

    # --- ランキング：個人 ---
    st.subheader("👤 個人成績ランキング")
    html = '<table class="pog-table"><tr><th>Rank</th><th>選手</th><th>オーナー</th><th>ポイント</th></tr>'
    for _, row in df_players.iterrows():
        bg = TEAM_CONFIG[row['オーナー']]['bg_color']
        html += f'<tr style="background-color:{bg}"><td>{int(row["Rank"])}</td><td>{row["選手"]}</td><td>{row["オーナー"]}</td><td>{row["ポイント"]:+.1f}</td></tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

with st.sidebar:
    if st.button('🔄 更新'):
        st.cache_data.clear()
        st.rerun()