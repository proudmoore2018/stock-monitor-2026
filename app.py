import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import requests
import json
import os
import numpy as np

# ================= 1. 页面基础设置 =================
st.set_page_config(page_title="国内科技股核心公司", layout="wide", page_icon="💻")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOTES_FILE = os.path.join(BASE_DIR, "stock_notes.json")

# ================= 2. 定义股票池 =================
STOCK_POOL = {
    "1️⃣ 存储芯片": ["301308", "001309", "688525", "603986", "688766", "688008", "688123"],
    "2️⃣ 光通信/光模块": ["300308", "300502", "300394", "002281", "601869", "600487", "600522", "300548", "688498", "688807", "002396", "601138", "000063", "600498"],
    "3️⃣ PCB/覆铜板": ["300476", "002463", "600183", "688183", "002938", "002916"],
    "4️⃣ 封测/功率半导体": ["600584", "002156", "688820", "603005", "688396", "605111", "300373", "600460", "300623"],
    "5.1 材料-先进封装/树脂": ["688535", "688300", "688720", "605589", "601208", "603002"],
    "5.2 材料-电子布/铜箔/基材": ["301526", "600176", "002636", "301217", "603256", "603186", "300699", "300398", "301338"],
    "5.3 材料-半导体化学品/特气": ["300037", "600160", "603938", "688596", "300346", "002409"],
    "5.4 材料-MLCC/被动元器件": ["000636", "002138", "603738", "300285", "605376"],
    "5.5 材料-石英/光学/合金": ["300395", "002222", "000657", "600549", "688234", "600206"],
    "6️⃣ 半导体设备/零部件": ["688012", "002371", "688072", "688037", "688120", "688361", "300604", "300567", "688126", "605358", "688233", "300260", "300666", "688019", "688146", "688268", "300236"],
    "7️⃣ 其他重点关注": ["688599", "603778", "300852", "002335"]
}
DEFAULT_ADV = "细分赛道核心标的"

# ================= 3. 笔记管理 =================
def load_notes():
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def save_notes(notes_dict):
    try:
        with open(NOTES_FILE, 'w', encoding='utf-8') as f: json.dump(notes_dict, f, ensure_ascii=False, indent=4)
    except Exception as e: st.error(f"保存失败: {e}")

if 'notes' not in st.session_state: st.session_state.notes = load_notes()

# ================= 4. 数据获取引擎 (海外防卡死版) =================
def _format_tencent_code(code):
    if code.startswith(('6', '688', '000', '399')): return f"sh{code}" if code.startswith(('6', '000')) else f"sz{code}"
    elif code.startswith(('0', '3')): return f"sz{code}"
    return f"bj{code}" 

@st.cache_data(ttl=10) # 海外网络波动，缓存设为10秒
def get_tencent_realtime(codes_list):
    if not codes_list: return pd.DataFrame()
    tencent_codes = [_format_tencent_code(c) for c in codes_list]
    url = f"http://qt.gtimg.cn/q={','.join(tencent_codes)}"
    try:
        # 强制 3 秒超时，防止海外服务器请求国内接口无限卡死
        response = requests.get(url, timeout=3) 
        response.encoding = 'gbk'
        data_list = []
        for line in response.text.strip().split('\n'):
            if '="' not in line: continue
            raw = line.split('="')[1].strip('";').split('~')
            if len(raw) > 38:
                try:
                    data_list.append({
                        '代码': raw[2], '名称': raw[1], '最新价': float(raw[3]) if raw[3] else 0.0,
                        '涨跌幅': float(raw[32]) if raw[32] else 0.0,
                        '涨跌额': round(float(raw[3]) - float(raw[4]), 2) if raw[3] and raw[4] else 0.0,
                        '成交额': float(raw[37]) * 10000 if raw[37] else 0.0, 
                        '换手率': float(raw[38]) if raw[38] else 0.0
                    })
                except: continue
        return pd.DataFrame(data_list)
    except requests.exceptions.Timeout:
        st.warning("⚠️ 腾讯行情接口请求超时 (海外网络波动)，请稍后刷新页面。")
        return pd.DataFrame()
    except Exception: 
        return pd.DataFrame()

# ⚠️ 注意：这里彻底删除了 get_fund_flow_rank (全市场资金流向)，它是导致海外卡死的元凶！

# ================= 5. 颜色与买点评估函数 =================
def format_change(val):
    if pd.isna(val): return "⚪ -"
    if val > 0: return f"🔴 +{val:.2f}%"
    elif val < 0: return f"🟢 {val:.2f}%"
    else: return f"⚪ {val:.2f}%"

def format_fund(val):
    if pd.isna(val): return "⚪ -"
    val_wan = val / 10000 
    if val_wan > 0: return f"🔴 +{val_wan:.0f}万"
    elif val_wan < 0: return f"🟢 {val_wan:.0f}万"
    else: return f"⚪ {val_wan:.0f}万"

def evaluate_buy_signal(short_sig, mid_sig, fund_val, premium):
    if short_sig == "🚀 短线出击" and pd.notna(fund_val) and fund_val > 0: return "🎯 右侧追击"
    if mid_sig in ["🛡️ 中线多头", "🔄 中线筑底"] and pd.notna(premium) and premium < 5.0: return "🛡️ 左侧潜伏"
    if short_sig == "👀 缩量企稳" and mid_sig in ["🛡️ 中线多头", "🔄 中线筑底"]: return "👀 缩量企稳"
    return "⏸️ 暂无买点"

# ================= 6. 量化指标计算引擎 =================
def calculate_signals(df):
    if df is None or df.empty or len(df) < 60: return "⏸️ 数据不足", "⏸️ 数据不足"
    close = df['收盘'].astype(float)
    volume = df['成交量'].astype(float)
    ma5, ma10 = close.rolling(5).mean(), close.rolling(10).mean()
    ma20, ma60 = close.rolling(20).mean(), close.rolling(60).mean()
    vol_ma5 = volume.rolling(5).mean().shift(1) 
    vol_ratio = volume.iloc[-1] / vol_ma5.iloc[-1] if vol_ma5.iloc[-1] > 0 else 1.0
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + (gain / (loss + 1e-10))))
    exp12, exp26 = close.ewm(span=12, adjust=False).mean(), close.ewm(span=26, adjust=False).mean()
    dif, dea = exp12 - exp26, (exp12 - exp26).ewm(span=9, adjust=False).mean()

    curr_close, curr_ma5, curr_ma10 = close.iloc[-1], ma5.iloc[-1], ma10.iloc[-1]
    curr_ma20, curr_ma60 = ma20.iloc[-1], ma60.iloc[-1]
    curr_rsi, curr_dif, curr_dea = rsi.iloc[-1], dif.iloc[-1], dea.iloc[-1]

    if curr_rsi > 75: short_sig = "⚠️ 短线超买"
    elif curr_close > curr_ma5 and curr_ma5 > curr_ma10 and vol_ratio > 1.5: short_sig = "🚀 短线出击"
    elif curr_close < curr_ma5 and vol_ratio < 0.8: short_sig = "📉 短线走弱"
    else: short_sig = "⏸️ 短线震荡"

    if curr_close > curr_ma20 and curr_ma20 > curr_ma60 and curr_dif > curr_dea and curr_dif > 0: mid_sig = "🛡️ 中线多头"
    elif curr_close > curr_ma20 and curr_dif > curr_dea and curr_dif < 0: mid_sig = "🔄 中线筑底"
    elif curr_close < curr_ma20 and curr_ma20 < curr_ma60: mid_sig = "❄️ 中线空头"
    else: mid_sig = "⏸️ 中线震荡"

    return short_sig, mid_sig

@st.cache_data(ttl=3600) 
def get_kline_indicators(symbol):
    try:
        # 增加超时控制
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
        short_sig, mid_sig = calculate_signals(df)
        return {"short": short_sig, "mid": mid_sig, "df": df.tail(60)}
    except: return {"short": "❌ 获取失败", "mid": "❌ 获取失败", "df": pd.DataFrame()}

def get_eastmoney_url(code):
    code = str(code)
    if code.startswith(('6', '9')): return f"http://quote.eastmoney.com/sh{code}.html"
    elif code.startswith(('0', '2', '3')): return f"http://quote.eastmoney.com/sz{code}.html"
    elif code.startswith(('4', '8')): return f"http://quote.eastmoney.com/bj{code}.html"
    return f"https://so.eastmoney.com/web/s?keyword={code}"

# ================= 7. 侧边栏 =================
st.sidebar.header("📂 板块导航")
selected_sector = st.sidebar.radio("选择关注的板块", list(STOCK_POOL.keys()))
target_codes = STOCK_POOL[selected_sector]

st.sidebar.markdown("---")
with st.sidebar.expander("☁️ 云端使用说明", expanded=False):
    st.markdown("""
    **⚠️ 为什么主表格没有“主力资金”了？**
    - 获取全市场 5000 只股票的资金数据，会导致海外服务器**严重超时卡死**。
    - 为了保证网页秒开，主表格已精简。
    - **主力资金、短中线雷达、买点评估**，已移至下方的 **“深度体检区”**，选中个股后按需加载。
    """)
st.sidebar.caption(f"📁 笔记路径: `{NOTES_FILE}`")

# ================= 8. 核心看板 (海外极速版) =================
st.title("💻 国内科技股核心公司")

# 8.1 大盘指数
index_codes = ["000001", "399001", "399006"]
index_data = get_tencent_realtime(index_codes)
cols = st.columns(3)
index_names = {"000001": "上证指数", "399001": "深证成指", "399006": "创业板指"}
for i, code in enumerate(index_codes):
    with cols[i]:
        row = index_data[index_data['代码'] == code]
        if not row.empty:
            r = row.iloc[0]
            st.metric(label=index_names[code], value=f"{r['最新价']:.2f}", delta=f"{r['涨跌幅']:.2f}%")
        else:
            st.metric(label=index_names[code], value="暂无数据")

st.markdown("---")

# 8.2 主监控表格 (极致精简，保证秒开)
st.subheader("📋 核心个股实时监控")
pause_refresh = st.checkbox("⏸️ 暂停行情刷新", value=False)

sector_data = get_tencent_realtime(target_codes)

if not sector_data.empty:
    sector_data = sector_data.sort_values(by='涨跌幅', ascending=False).reset_index(drop=True)
    sector_data['成交额(万)'] = (sector_data['成交额'] / 10000).round(0)
    
    # 注入笔记
    sector_data['核心优势'] = sector_data['代码'].apply(lambda x: st.session_state.notes.get(x, {}).get('adv', DEFAULT_ADV))
    sector_data['合理入手价'] = sector_data['代码'].apply(lambda x: st.session_state.notes.get(x, {}).get('target_price', 0.0))
    
    def calc_premium(row):
        if row['合理入手价'] > 0 and row['最新价'] > 0:
            return round((row['最新价'] - row['合理入手价']) / row['合理入手价'] * 100, 1)
        return None
    sector_data['溢价率(%)'] = sector_data.apply(calc_premium, axis=1)

    # 生成带颜色的显示列
    sector_data['涨跌幅_display'] = sector_data['涨跌幅'].apply(format_change)

    # ⚠️ 移除了主力资金列，防止海外卡死
    display_cols = ['代码', '名称', '最新价', '涨跌幅_display', '核心优势', '合理入手价', '溢价率(%)', '换手率', '成交额(万)']
    editor_df = sector_data[display_cols].copy()

    edited_df = st.data_editor(
        editor_df,
        column_config={
            "代码": st.column_config.TextColumn(disabled=True, width="small"),
            "名称": st.column_config.TextColumn(disabled=True, width="medium"),
            "最新价": st.column_config.NumberColumn(disabled=True, format="%.2f", width="small"),
            "涨跌幅_display": st.column_config.TextColumn("涨跌幅", disabled=True, width="small"),
            "核心优势": st.column_config.TextColumn("核心优势 (双击编辑)", width="large"),
            "合理入手价": st.column_config.NumberColumn("合理入手价(±10%)", format="%.2f", width="medium"),
            "溢价率(%)": st.column_config.NumberColumn(disabled=True, format="%.1f", width="small"),
            "换手率": st.column_config.NumberColumn(disabled=True, format="%.2f", width="small"),
            "成交额(万)": st.column_config.NumberColumn(disabled=True, format="%.0f", width="medium"),
        },
        hide_index=True, use_container_width=True, height=450,
        key=f"stock_editor_{selected_sector}", disabled=pause_refresh 
    )

    # 保存逻辑
    if not edited_df.empty:
        notes_updated = False
        for idx in edited_df.index:
            code = edited_df.loc[idx, '代码']
            new_adv = str(edited_df.loc[idx, '核心优势']).strip() if pd.notna(edited_df.loc[idx, '核心优势']) else DEFAULT_ADV
            if not new_adv: new_adv = DEFAULT_ADV
            new_price = float(edited_df.loc[idx, '合理入手价']) if pd.notna(edited_df.loc[idx, '合理入手价']) else 0.0
            
            old_adv = editor_df.loc[idx, '核心优势'] if idx in editor_df.index else DEFAULT_ADV
            old_price = editor_df.loc[idx, '合理入手价'] if idx in editor_df.index else 0.0
            
            if str(new_adv) != str(old_adv) or float(new_price) != float(old_price):
                if code not in st.session_state.notes: st.session_state.notes[code] = {}
                st.session_state.notes[code]['adv'] = new_adv
                st.session_state.notes[code]['target_price'] = new_price
                notes_updated = True
        if notes_updated:
            save_notes(st.session_state.notes)
            st.toast("✅ 笔记已保存！", icon="💾")
else:
    st.warning("⚠️ 未获取到实时数据，可能是海外服务器网络波动，请尝试刷新页面 (按 F5)。")

# ================= 9. 深度体检区 (按需加载单只股票数据) =================
st.markdown("---")
if not sector_data.empty:
    name_map = dict(zip(sector_data['代码'], sector_data['名称']))
    col_sel, col_btn = st.columns([3, 1])
    with col_sel:
        selected_stock_code = st.selectbox(
            "🔍 选择个股进行深度量化体检 (含主力资金与买卖点)", 
            sector_data['代码'].tolist(), 
            format_func=lambda x: f"{name_map.get(x, '未知')} ({x})"
        )
    with col_btn:
        st.link_button("🔗 东方财富详情页", get_eastmoney_url(selected_stock_code), use_container_width=True)

    if selected_stock_code:
        stock_name = name_map.get(selected_stock_code, '未知')
        stock_adv = st.session_state.notes.get(selected_stock_code, {}).get('adv', DEFAULT_ADV)
        target_p = st.session_state.notes.get(selected_stock_code, {}).get('target_price', 0.0)
        premium_val = sector_data[sector_data['代码'] == selected_stock_code]['溢价率(%)'].iloc[0]
        
        with st.spinner(f"⏳ 正在拉取 {stock_name} 的 K线、资金与量化指标..."):
            # 1. 获取 K 线与短中线信号
            indicators = get_kline_indicators(selected_stock_code)
            kline_data = indicators["df"]
            short_sig = indicators["short"]
            mid_sig = indicators["mid"]
            
            # 2. 获取单只股票的资金与估值 (单只请求在海外通常能成功)
            fund_val = np.nan
            res = {"pe": "-", "pb": "-", "main_net": "-"}
            try:
                market = "sh" if selected_stock_code.startswith(('6','9')) else "sz"
                fund_df = ak.stock_individual_fund_flow(stock=selected_stock_code, market=market)
                if not fund_df.empty:
                    fund_val = fund_df['主力净流入-净额'].iloc[-1]
                    res["main_net"] = format_fund(fund_val)
            except: pass
            
            try:
                ind_df = ak.stock_a_indicator_lg(symbol=selected_stock_code)
                if not ind_df.empty:
                    res["pe"] = f"{ind_df['pe_ttm'].iloc[-1]:.1f}"
                    res["pb"] = f"{ind_df['pb'].iloc[-1]:.2f}"
            except: pass

            # 3. 计算买点
            buy_sig = evaluate_buy_signal(short_sig, mid_sig, fund_val, premium_val)

        st.subheader(f"🩺 {stock_name} 深度体检报告")
        metric_cols = st.columns(4)
        metric_cols[0].metric("市盈率 (PE)", res["pe"])
        metric_cols[1].metric("市净率 (PB)", res["pb"])
        metric_cols[2].metric("今日主力资金", res["main_net"])
        
        # 买点信号高亮
        if "右侧" in buy_sig:
            metric_cols[3].metric("🎯 买点评估", buy_sig, delta="适合追涨", delta_color="normal")
        elif "左侧" in buy_sig or "企稳" in buy_sig:
            metric_cols[3].metric("🎯 买点评估", buy_sig, delta="适合低吸", delta_color="normal")
        else:
            metric_cols[3].metric("🎯 买点评估", buy_sig, delta="建议观望", delta_color="off")
        
        st.caption(f"**量化诊断**：短线 [{short_sig}] | 中线 [{mid_sig}] | 溢价率 [{premium_val}%]")

        if not kline_data.empty:
            fig = go.Figure(data=[go.Candlestick(
                x=kline_data['日期'], open=kline_data['开盘'], high=kline_data['最高'],
                low=kline_data['最低'], close=kline_data['收盘'],
                increasing_line_color='#ef4444', decreasing_line_color='#22c55e' 
            )])
            ma20 = kline_data['收盘'].rolling(20).mean()
            fig.add_trace(go.Scatter(x=kline_data['日期'], y=ma20, mode='lines', name='MA20(中线)', line=dict(color='orange', width=1)))
            if target_p > 0:
                fig.add_hline(y=target_p, line_dash="dash", line_color="blue", 
                              annotation_text=f"心理价: {target_p}", annotation_position="bottom right")
            fig.update_layout(
                title=f"💡 核心优势: {stock_adv}",
                xaxis_rangeslider_visible=False, height=500,
                template="plotly_white", margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)
