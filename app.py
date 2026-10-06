import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta

# 1. 页面基本设置
st.set_page_config(
    page_title="纳指100 熊市前瞻预警系统", 
    page_icon="📈",
    layout="wide"
)

st.title("📈 纳斯达克100 (NDX) 每日风控预警雷达")
st.caption("数据来源：Yahoo Finance | 自动化每日更新 (13.5全量评分架构)")

# 2. 数据获取模块
@st.cache_data(ttl=3600)
def fetch_data():
    tickers = {
        'NDX': '^NDX',
        'RUT': '^RUT',
        'SOX': '^SOX',
        'VIX': '^VIX'
    }
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2)
    
    df = yf.download(list(tickers.values()), start=start_date, end=end_date)['Close']
    df = df.rename(columns={v: k for k, v in tickers.items()})
    
    ndx_k = yf.Ticker('^NDX').history(period='2y')
    return ndx_k, df

with st.spinner("正在拉取全球市场最新行情，请稍候..."):
    try:
        ndx_k, close_df = fetch_data()
        latest_date = ndx_k.index[-1].strftime('%Y-%m-%d')
        latest_close = ndx_k['Close'].iloc[-1]
    except Exception as e:
        st.error(f"行情拉取失败，请刷新页面重试: {e}")
        st.stop()

# 3. 风险引擎算法 (按 13.5 总分架构计算)
def evaluate_risk(ndx_k, close_df):
    score = 0.0
    reasons = []
    
    # 均线位置 (确认因子，最高2.0分)
    curr = ndx_k['Close'].iloc[-1]
    ma50 = ndx_k['Close'].rolling(50).mean().iloc[-1]
    ma200 = ndx_k['Close'].rolling(200).mean().iloc[-1]
    
    if curr < ma200:
        score += 2.0
        reasons.append("❌ 指数有效跌破 200 日均线 (+2.0分)")
    elif curr < ma50:
        score += 1.0
        reasons.append("⚠️ 指数跌破 50 日均线 (+1.0分)")
        
    # 小盘股背离 RUT/NDX (强领先结构，2.0分)
    rut_ratio = close_df['RUT'] / close_df['NDX']
    rut_ma = rut_ratio.rolling(50).mean().iloc[-1]
    if rut_ratio.iloc[-1] < rut_ma * 0.95:
        score += 2.0
        reasons.append("⚠️ 罗素2000小盘股相对强弱严重背离 (+2.0分)")
        
    # 半导体背离 SOX/NDX (强领先周期，2.0分)
    sox_ratio = close_df['SOX'] / close_df['NDX']
    sox_ma = sox_ratio.rolling(50).mean().iloc[-1]
    if sox_ratio.iloc[-1] < sox_ma * 0.96:
        score += 2.0
        reasons.append("⚠️ SOX 半导体板块相对走弱 (+2.0分)")
        
    # VIX 恐慌情绪 (1.5分)
    vix = close_df['VIX'].iloc[-1]
    if vix > 30:
        score += 1.5
        reasons.append("🔥 VIX 恐慌指数飙升至 30 以上 (+1.5分)")
    elif vix > 20:
        score += 0.8
        reasons.append("⚠️ VIX 处于 20 以上偏高区域 (+0.8分)")
        
    return score, reasons

risk_score, risk_reasons = evaluate_risk(ndx_k, close_df)

# 4. 看板展示
st.subheader(f"📅 交易日看板 ({latest_date})")

col1, col2, col3 = st.columns([1, 1, 2])
col1.metric("NDX 最新收盘价", f"{latest_close:,.2f}")
col2.metric("综合风控得分", f"{risk_score:.1f} / 13.5")

with col3:
    if risk_score >= 7.0:
        st.error("🚨 红色高危警报 (全面启动防熊策略)")
        st.write("建议动作：权益仓位降至 20%~30%，冻结所有网格抄底，全量开启 OTM Put 防守。")
    elif risk_score >= 4.5:
        st.warning("🟧 橙色防守警报 (结构性分化恶化)")
        st.write("建议动作：分批逢高落袋为安，暂停常规抄底，配置领口对冲策略。")
    elif risk_score >= 2.5:
        st.info("🟨 黄色预警 (晚周期/内部分化)")
        st.write("建议动作：全面清退高倍杠杆，网格加仓门槛拉大至 -10% 以上。")
    else:
        st.success("🟩 绿色安全状态 (牛市多头格局)")
        st.write("建议动作：按常规网格与定投计划正常运行。")

with st.expander("🔍 查看今日风险因子触发详情"):
    if risk_reasons:
        for r in risk_reasons:
            st.write(r)
    else:
        st.write("✅ 今日无高风险因子触发，市场内部结构正常。")

st.markdown("---")

# 5. K线图
st.subheader("📊 纳斯达克 100 交互式 K 线图")

fig = go.Figure(data=[go.Candlestick(
    x=ndx_k.index,
    open=ndx_k['Open'],
    high=ndx_k['High'],
    low=ndx_k['Low'],
    close=ndx_k['Close'],
    name="NDX"
)])

fig.add_trace(go.Scatter(x=ndx_k.index, y=ndx_k['Close'].rolling(50).mean(), mode='lines', name='50日均线', line=dict(color='orange', width=1.5)))
fig.add_trace(go.Scatter(x=ndx_k.index, y=ndx_k['Close'].rolling(200).mean(), mode='lines', name='200日均线', line=dict(color='blue', width=2)))

fig.update_layout(
    xaxis_rangeslider_visible=False,
    height=550,
    margin=dict(l=10, r=10, t=10, b=10),
    template="plotly_dark"
)

st.plotly_chart(fig, use_container_width=True)
