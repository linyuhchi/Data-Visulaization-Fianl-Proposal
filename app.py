import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import numpy as np
import yfinance as yf 

# 網頁基本設定 (設定為寬螢幕版面)
st.set_page_config(page_title="日圓匯率與觀光消費儀表板", layout="wide")

# ==========================================
# 資料庫連線與讀取函數
# ==========================================
@st.cache_data
def load_data():
    conn = sqlite3.connect('tourism_data.db')
    query = """
        SELECT country, t, PerEXP, EX, REX, GDPpc, NIGHTpc 
        FROM panel_data 
        ORDER BY country, t
    """
    raw_df = pd.read_sql_query(query, conn)
    conn.close()
    
    # 創造畫布專用座標 plot_t：大於等於 40 的期數往右平移 9 格，創造大空白
    raw_df['plot_t'] = raw_df['t'].apply(lambda x: x if x <= 39 else x + 9)
    
    # 在 39 與 40 之間塞入空值斷線 (plot_t 設為 44 讓它剛好落在空白區中間)
    dummy_rows = []
    for c in raw_df['country'].unique():
        dummy_rows.append({'country': c, 't': 39.5, 'plot_t': 44})
        
    dummy_df = pd.DataFrame(dummy_rows)
    processed_df = pd.concat([raw_df, dummy_df], ignore_index=True)
    
    # 按照畫圖座標排序
    processed_df = processed_df.sort_values(['country', 'plot_t']).reset_index(drop=True)
    
    return processed_df

# 載入處理後的完整資料
df = load_data()

# ==========================================
# 側邊欄設計 (Sidebar)
# ==========================================
st.sidebar.title("儀表板控制台")
page = st.sidebar.radio("請選擇頁面：", ["📊 跨國趨勢探索", "🧮 匯率變動模擬器", "📄 研究執行摘要"])

st.sidebar.divider()
st.sidebar.subheader("🔄 即時市場數據同步")

# 初始化 session_state
if 'real_time_rex_change' not in st.session_state:
    st.session_state.real_time_rex_change = 0.0

# 建立常見貨幣的 Yahoo Finance Ticker 對照表
# 建立完整的 Yahoo Finance Ticker 對照表 (涵蓋你追蹤資料中的主要國家)
currency_mapping = {
    'Taiwan': 'TWD=X',
    'South Korea': 'KRW=X',
    'China': 'CNY=X',
    'Hong Kong': 'HKD=X',
    'Thailand': 'THB=X',
    'Singapore': 'SGD=X',
    'Malaysia': 'MYR=X',
    'Indonesia': 'IDR=X',
    'Philippines': 'PHP=X',
    'Vietnam': 'VND=X',
    'India': 'INR=X',
    'UK': 'GBP=X',
    'Germany': 'EUR=X',
    'France': 'EUR=X',
    'Italy': 'EUR=X',
    'Spain': 'EUR=X',
    'Russia': 'RUB=X',
    'United States': 'USD',
    'Canada': 'CAD=X',
    'Mexico': 'MXN=X',
    'Australia': 'AUD=X'
}

# 讓使用者選擇要以哪個國家的貨幣作為即時更新的基準
available_countries = [c for c in currency_mapping.keys() if c in df['country'].unique()]
selected_api_country = st.sidebar.selectbox("選擇即時匯率基準國：", available_countries)

if st.sidebar.button("🌐 獲取今日雙邊交叉匯率"):
    with st.sidebar.status("正在獲取即時金融數據..."):
        try:
            # 1. 抓取 USD/JPY 即時匯率 (1美元兌換多少日圓)
            jpy_data = yf.Ticker("JPY=X").history(period="1d")
            jpy_per_usd = jpy_data['Close'].iloc[0]
            
            # 2. 抓取 來源國/USD 即時匯率，並計算雙邊名目匯率 (EX = JPY / Source_Currency)
            if currency_mapping[selected_api_country] == 'USD':
                current_ex = jpy_per_usd
                st.sidebar.caption(f"即時 JPY/USD: {jpy_per_usd:.2f}")
            else:
                source_ticker = currency_mapping[selected_api_country]
                source_data = yf.Ticker(source_ticker).history(period="1d")
                source_per_usd = source_data['Close'].iloc[0]
                # 計算交叉匯率
                current_ex = jpy_per_usd / source_per_usd
                st.sidebar.caption(f"即時 JPY/USD: {jpy_per_usd:.2f} | {source_ticker.replace('=X', '')}/USD: {source_per_usd:.2f}")
            
            # 3. 從資料庫中抓取該國最後一期 (基準期) 的匯率 (EX)
            latest_t = df['t'].max()
            baseline_ex = df[(df['country'] == selected_api_country) & (df['t'] == latest_t)]['EX'].values[0]
            
            # 4. 計算變動百分比
            pct_change = ((current_ex - baseline_ex) / baseline_ex) * 100
            st.session_state.real_time_rex_change = round(pct_change, 1)
            
            # 5. 💡 核心新增：根據迴歸係數 0.148 即時計算整體旅客消費的預估變動幅度
            api_expected_exp_change = pct_change * 0.148
            
            # 顯示匯率變動成功提示
            st.sidebar.success(f"計算完成！相較於研究基準，該國貨幣對日圓變動 {pct_change:+.2f}%")
            
            # 💡 直接接在抓取實際匯率的變動幅度後，動態跳出消費變動結果
            if api_expected_exp_change > 0:
                st.sidebar.info(f"🔮 **市場即時推估結論**：\n基於雙向固定效果模型，此匯率變動預期將帶動整體訪日旅客的人均消費總額 **顯著增加 {api_expected_exp_change:+.2f}%**。")
            else:
                st.sidebar.warning(f"🔮 **市場即時推估結論**：\n基於雙向固定效果模型，此匯率變動預期將導致整體訪日旅客的人均消費總額 **減少 {abs(api_expected_exp_change):.2f}%**。")
            
        except Exception as e:
            st.error(f"獲取資料失敗: {e}")

# 顯示目前的數據狀態說明
st.sidebar.caption(f"ℹ️ 說明：透過獲取最新 USD/JPY 與來源國兌美元匯率，計算即時雙邊名目匯率變動，並假設短期 CPI 維持最新一期水準。")

# ==========================================
# 頁面 1: 跨國趨勢探索
# ==========================================
if page == "📊 跨國趨勢探索":
    st.title("訪日旅客消費與匯率趨勢探索")
    st.markdown("透過下方選單，比較不同來源國旅客在日本的消費金額與匯率變動關聯。")
    
    # 建立多選單，讓使用者選擇國家
    country_list = df['country'].unique().tolist()
    # 預設選取台灣與韓國
    default_countries = ['Taiwan', 'South Korea'] if 'Taiwan' in country_list and 'South Korea' in country_list else [country_list[0]]
    
    selected_countries = st.multiselect("選擇要比較的國家：", country_list, default=default_countries)
    
    if selected_countries:
        filtered_df = df[df['country'].isin(selected_countries)]
        
        # 💡 關鍵修正：手動指定你想要在 X 軸上顯示的 t 期數
        desired_t_labels = [0, 10, 20, 30, 39, 40, 48]
        
        # 將真實的 t 轉換為畫布上的 plot_t 座標 (大於等於 40 的要加上 9 格的偏移量)
        tick_vals = [t if t <= 39 else t + 9 for t in desired_t_labels]
        
        # 標籤文字就是你指定的數字
        tick_texts = [str(t) for t in desired_t_labels]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("人均消費總額走勢 (PerEXP)")
            fig_exp = px.line(filtered_df, x='plot_t', y='PerEXP', color='country', markers=True)
            
            # 套用客製化刻度
            fig_exp.update_xaxes(
                tickvals=tick_vals, 
                ticktext=tick_texts, 
                title_text="時間期數 (t)"
            )
            st.plotly_chart(fig_exp, width='stretch')
            
        with col2:
            st.subheader("實質雙邊匯率走勢 (REX)")
            fig_rex = px.line(filtered_df, x='plot_t', y='REX', color='country', markers=True)
            
            # 套用客製化刻度
            fig_rex.update_xaxes(
                tickvals=tick_vals, 
                ticktext=tick_texts, 
                title_text="時間期數 (t)"
            )
            st.plotly_chart(fig_rex, width='stretch')

# ==========================================
# 頁面 2: 訪日外國旅客整體消費模擬器
# ==========================================
elif page == "🧮 匯率變動模擬器":
    st.title("🧮 訪日外國旅客整體消費模擬器")
    
    st.markdown("""
    > **💡 經濟學實證模型結論**
    > 考量單一來源國樣本數限制與固定效果設定之嚴謹性，本模擬器採用全樣本雙向固定效果模型（Two-way Fixed Effects）之整體估計結果：
    > 1. **實質匯率效果**：實質匯率上升 1%（日圓相對貶值），整體訪日旅客人均消費總額顯著增加 **0.148%**。
    > 2. **停留天數效果**：人均停留天數每增加 1 天，整體人均消費總額顯著增加 **2.20%**。
    """)
    
    st.divider()
    
    # 建立左右佈局：左邊放參數控制，右邊放整體預測結果
    col_input, col_output = st.columns([1, 2])
    
    with col_input:
        st.subheader("⚙️ 總體參數設定")
        
        # 參數 1：實質匯率
        rex_change = st.slider(
            "假設實質匯率變動幅度 (%)：", 
            min_value=-30.0, 
            max_value=30.0, 
            value=10.0, 
            step=1.0,
            key="rex_slider"
        )
        
        # 參數 2：人均停留天數 (增加或減少幾天)
        night_change = st.slider(
            "假設整體人均停留天數變動 (天)：", 
            min_value=-4, 
            max_value=10, 
            value=2, 
            step=1,
            key="night_slider"
        )
        
        # 計算總和百分比變動幅度
        expected_exp_change_pct = (rex_change * 0.148) + (night_change * 2.2)

        # 動態顯示邊際效果貢獻
        st.info(f"""
        **整體邊際效益試算：**
        * 匯率貢獻：{rex_change * 0.148:+.2f}%
        * 停留天數貢獻：{night_change * 2.2:+.2f}%
        * **總預期消費變動：{expected_exp_change_pct:+.2f}%**
        """)

    # 核心預測邏輯 (針對整體全樣本)
    # 1. 取得最新一期 (最大 t 值) 的資料，並計算「整體平均消費」作為基準點
    latest_t = df['t'].max()
    latest_df = df[df['t'] == latest_t]
    avg_base_exp = latest_df['PerEXP'].mean()
    
    # 2. 預測新消費金額
    predicted_avg_exp = avg_base_exp * (1 + expected_exp_change_pct / 100)
    diff_amount = predicted_avg_exp - avg_base_exp
    
    with col_output:
        st.subheader("📊 整體消費模擬預測 (全樣本平均)")
        
        # 放大顯示整體平均的指標卡
        st.metric(
            label="整體外國旅客預估人均消費 (日圓)",
            value=f"¥ {int(predicted_avg_exp):,}",
            delta=f"{expected_exp_change_pct:+.2f}% (¥ {int(diff_amount):+,})"
        )
        
        # 建立簡單乾淨的 DataFrame 供畫圖使用
        chart_df = pd.DataFrame({
            'Scenario': ['目前實際消費基準 (平均)', '模擬預估消費 (平均)'],
            'Consumption': [avg_base_exp, predicted_avg_exp]
        })
        
# 繪製前後對比的長條圖
        fig_sim = px.bar(
            chart_df, 
            x='Scenario', 
            y='Consumption', 
            # 💡 關鍵修正：直接把 color='Scenario' 刪除！不讓 Plotly 有理由去分組
            text_auto='.0f',
            title=f"整體訪日旅客消費變化情境（匯率 {rex_change:+.0f}%, 天數 {night_change:+.0f}天）",
            labels={'Consumption': '人均消費總額 (日圓)', 'Scenario': '情境比較'}
        )
        
        fig_sim.update_layout(showlegend=False)
        # 💡 關鍵修正：在這裡「手動」給兩根柱子不同的顏色 (Plotly 預設的藍色與紅色)
        fig_sim.update_traces(
            marker_color=['#636EFA', '#EF553B'], 
            textfont_size=16, 
            textangle=0, 
            textposition="outside", 
            cliponaxis=False,
            width=0.4
        )
        st.plotly_chart(fig_sim, width='stretch')

# ==========================================
# 頁面 3: 研究執行摘要
# ==========================================
# (保留你原本的 elif page == "📄 研究執行摘要": 下方的程式碼)
# ==========================================
# 頁面 3: 研究執行摘要
# ==========================================
elif page == "📄 研究執行摘要":
    st.title("📄 研究執行摘要 (Executive Summary)")
    
    # 建立一個美觀的白底卡片容器來放置摘要，模擬 A4 紙張的視覺感
    with st.container(border=True):
        st.markdown("""
        <h2 style='text-align: center;'>訪日外國旅客消費之總體經濟決定因素<br>實質匯率與停留天數之實證分析</h2>
        <p style='text-align: center;'><b>研究者：林昱錡 (Yuh-Chi, Lin) | 國立台灣大學經濟學系</b></p>
        
        ---
        
        ### 壹、 研究動機與背景 (Background & Motivation)
        近年來，日本入境觀光產業蓬勃發展，同時伴隨著日圓匯率的劇烈波動。直觀而言，日圓貶值會降低外國旅客的旅遊成本，進而刺激消費。然而，不同來源國的所得水準與旅客行為存在顯著異質性。本研究旨在透過跨國追蹤資料（Panel Data），嚴謹量化「實質雙邊匯率」與「停留天數」對訪日旅客人均消費總額的實質邊際衝擊，以提供觀光政策與商業訂價之實證依據。
        
        ### 貳、 資料來源與實證模型 (Data & Methodology)
        本專案彙整了日本觀光廳與多國總體經濟指標，建構跨國追蹤資料集。為解決跨國樣本間的潛在內生性問題（Endogeneity）與遺漏變數偏誤（Omitted Variable Bias），本研究採用**雙向固定效果模型 (Two-way Fixed Effects, TWFE)**：
        * **被解釋變數 ($Y$)**：各來源國訪日旅客之「人均消費總額」取自然對數 ($\ln(PerEXP)$)。
        * **核心解釋變數 ($X$)**：實質雙邊匯率取自然對數 ($\ln(REX)$)、人均停留天數 ($NIGHTpc$)。
        * **控制變數與模型設定**：控制來源國人均所得 ($\ln(GDPpc)$)，並嚴格加入「國家固定效果」與「時間固定效果」，以吸收不隨時間改變的國家特徵與全域性的總體經濟衝擊。
        
        ### 參、 核心實證結果 (Empirical Findings)
        迴歸分析結果顯示，在控制其他條件不變下，核心變數皆呈現統計顯著性，具體經濟意涵如下：
        1. **實質匯率彈性 (Exchange Rate Elasticity)**：
           實質雙邊匯率對數的估計係數為 **0.148**。這表示當日圓實質相對貶值 **1%** 時，訪日旅客的人均消費總額平均將顯著提升 **0.148%**。此結果證實了匯率貶值確實具備「消費創造效果」。
        2. **停留天數半彈性 (Length of Stay Semi-elasticity)**：
           人均停留天數的估計係數為 **0.022**。這表示當旅客在日平均停留時間每延長 **1 天**，其人均消費總額將顯著增加 **2.20%**。
        
        > *本網頁儀表板整合了上述計量迴歸模型之參數，提供即時動態之情境模擬功能。*
        """, unsafe_allow_html=True)