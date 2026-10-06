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
st.caption("数据来源：Yahoo Finance | 自动化每日更新")

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
    
    # 抓取收盘价
    df = yf.download(list(tickers.values()), start=start_date, end=end_date)['Close']
    df = df.rename(columns={v: k for k, v in tickers.items()})
    
    # 抓取 K 线数据
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

# 3. 风险引擎算法
def evaluate_risk(ndx_k, close_df):
    score = 0.0
    reasons = []
    
    # 均线位置
    curr = ndx_k['Close'].iloc[-1]
    ma50 = ndx_k['Close'].rolling(50).mean().iloc[-1]
    ma200 = ndx_k['Close'].rolling(200).mean().iloc[-1]
    
    if curr < ma200:
        score += 2.0
        reasons.append("❌ 指数有效跌破 200 日均线 (牛熊分界线)")
    elif curr < ma50:
        score += 1.0
        reasons.append("⚠️ 指数跌破 50 日均线 (短期趋势受阻)")
        
    # 小盘股背离 (RUT/NDX)
    rut_ratio = close_df['RUT'] / close_df['NDX']
    rut_ma = rut_ratio.rolling(50).mean().iloc[-1]
    if rut_ratio.iloc[-1] < rut_ma * 0.96:
        score += 2.0
        reasons.append("⚠️ 罗素2000小盘股相对强弱严重背离 (资金退守大盘)")
        
    # 半导体背离 (SOX/NDX)
    sox_ratio = close_df['SOX'] / close_df['NDX']
    sox_ma = sox_ratio.rolling(50).mean().iloc[-1]
    if sox_ratio.iloc[-1] < sox_ma * 0.97:
        score += 1.5
        reasons.append("⚠️ SOX 半导体板块相对走弱 (科技产业链先导报警)")
        
    # VIX 恐慌指数
    vix = close_df['VIX'].iloc[-1]
    if vix > 30:
        score += 2.0
        reasons.append("🔥 VIX 恐慌指数飙升至 30 以上 (极度恐慌)")
    elif vix > 20:
        score += 1.0
        reasons.append("⚠️ VIX 处于 20 以上偏高区域 (市场波动加剧)")
        
    return score, reasons

risk_score, risk_reasons = evaluate_risk(ndx_k, close_df)

# 4. 看板展示
st.subheader(f"📅 交易日看板 ({latest_date})")

col1, col2, col3 = st.columns([1, 1, 2])
col1.metric("NDX 最新收盘价", f"{latest_close:,.2f}")
col2.metric("综合风控得分", f"{risk_score:.1f} / 10.0")

with col3:
    if risk_score >= 6.0:
        st.error("🚨 红色高危警报 (全面避险/高强度对冲)")
        st.write("建议动作：权益仓位降至 20%~30%，停止一切网格加仓，开启 OTM Put 尾部防御。")
    elif risk_score >= 3.5:
        st.warning("🟧 橙色防守警报 (结构性分化恶化)")
        st.write("建议动作：分批逢高分批落袋为安，暂停常规抄底，提高买入门槛至 -10% 以上。")
    elif risk_score >= 2.0:
        st.info("🟨 黄色预警 (晚周期分化阶段)")
        st.write("建议动作：全面清退杠杆，收缩 Beta 集中至现金流巨头。")
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