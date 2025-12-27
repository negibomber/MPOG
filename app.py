import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import plotly.express as px

# 1. 設定
SEASON_NAME = "2025-26"
TEAM_CONFIG = {
    "どら": {"color": "#FF4B4B", "players": ["瑞原明奈", "竹内元太", "石井一馬", "内川幸太郎", "多井隆晴", "日向藍子", "鈴木たろう", "HIRO柴田", "滝沢和典", "東城りお"]},
    "よしたに": {"color": "#00CC96", "players": ["堀慎吾", "鈴木優", "渡辺太", "下石戟", "松本吉弘", "小林剛", "醍醐大", "阿久津翔太", "浅見真紀", "三浦智博"]},
    "ねぎし": {"color": "#636EFA", "players": ["仲林圭", "白鳥翔", "園田賢", "佐々木寿人", "伊達朱里紗", "勝又健志", "渋川難波", "本田朋広", "浅井堂岐", "瀬戸熊直樹"]},
    "ひかえ": {"color": "#AB63FA", "players": ["二階堂亜樹", "逢川恵夢", "黒沢咲", "鈴木大介", "高宮まり", "岡田紗佳", "萩原聖人", "茅森早香", "永井孝典", "中田花奈"]}
}
PLAYER_TO_OWNER = {p: owner for owner, config in TEAM_CONFIG.items() for p in config['players']}

st.set_page_config(page_title=f"M-POG", layout="centered") # スマホで見やすいよう中央寄せに

st.title(f"🏆 M-POG {SEASON_NAME}")

# 2. データ取得関数
def filter_point(text):
    if not text or "--" in text: return None
    clean = text.replace('▲', '-').replace(' ', '').replace('pts', '')
    found = re.findall(r'[0-9.\-]', clean)
    return "".join(found) if found else None

@st.cache_data(ttl=600)
def get_data():
    url = "https://m-league.jp/games/"
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        history = []
        for container in soup.find_all(class_="c-modal2"):
            m_id = container.get('id', '')
            date_match = re.search(r'(\d{8})', m_id)
            if not date_match: continue
            date_str = date_match.group(1)
            
            names = container.find_all(class_="p-gamesResult__name")
            points = container.find_all(class_="p-gamesResult__point")
            
            for n_tag, p_tag in zip(names, points):
                p_name = n_tag.get_text(strip=True)
                p_val = filter_point(p_tag.get_text(strip=True))
                if p_name in PLAYER_TO_OWNER and p_val is not None:
                    history.append({
                        "日付": date_str,
                        "選手": p_name,
                        "ポイント": float(p_val),
                        "オーナー": PLAYER_TO_OWNER[p_name]
                    })
        return pd.DataFrame(history)
    except:
        return pd.DataFrame()

df = get_data()

# 3. 表示部分
if df.empty:
    st.error("対局データが見つかりません。公式サイトの結果がまだ更新されていない可能性があります。")
else:
    # 総合順位
    st.header("📊 総合順位")
    summary = df.groupby("オーナー")["ポイント"].sum().reset_index()
    summary = summary.sort_values("ポイント", ascending=False).reset_index(drop=True)
    summary.index += 1 # 1位から表示
    st.table(summary) # スマホで一番安定する表形式

    # 最新結果
    latest_date = df["日付"].max()
    st.header(f"🀄 最新結果 ({latest_date})")
    df_latest = df[df["日付"] == latest_date][["選手", "オーナー", "ポイント"]]
    st.table(df_latest.sort_values("ポイント", ascending=False))

    # 推移グラフ
    st.header("📈 ポイント推移")
    df_sorted = df.sort_values("日付")
    df_pivot = df_sorted.pivot_table(index="日付", columns="オーナー", values="ポイント", aggfunc="sum").fillna(0).cumsum()
    
    # グラフ：スマホでも消えにくい標準的なplotly
    fig = px.line(df_pivot, markers=True)
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)

with st.sidebar:
    if st.button('🔄 データを強制更新'):
        st.cache_data.clear()
        st.rerun()
