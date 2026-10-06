import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 1. 页面基本配置
st.set_page_config(
    page_title="纳指100 前瞻防熊预警系统 (13.5全量架构)", 
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ 纳斯达克100 (NDX) 前瞻防熊雷达系统")
st.caption("基于三道防线、双重门禁 (Dual-Gate) 与 13.5 加权前瞻评分模型 | 免密极速版")

# 2. 全量前瞻行情抓取 (全部为 Yahoo 免密接口)
@st.cache_data(ttl=3600)
def fetch_data():
    tickers = {
        'NDX': '^NDX',     # 纳指100
        'QQQE': 'QQQE',   # 纳指100等权重 (用于广度背离)
        'RUT': '^RUT',     # 罗素2000 (小盘股背离)
        'SOX': '^SOX',     # 费城半导体 (产业链先导)
        'HYG': 'HYG',     # 高收益债 ETF (信用风险)
        'LQD': 'LQD',     # 投资级债 ETF (信用风险基准)
        'TNX': '^TNX',     # 10年美债收益率
        'IRX': '^IRX',     # 13周短债收益率 (收益率曲线)
        'VIX': '^VIX',     # 近月恐慌指数
        'VIX3M': '^VIX3M'  # 3个月恐慌指数 (期限结构)
    }
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2)
    
    df = yf.download(list(tickers.values()), start=start_date, end=end_date)['Close']
    df = df.rename(columns={v: k for k, v in tickers.items()})
    
    # 填充可能缺失的少量非交易日数据
    df = df.ffill().bfill()
    ndx_k = yf.Ticker('^NDX').history(period='2y')
    return ndx_k, df

with st.spinner("正在拉取全球宏观、信用与微观暗涌数据..."):
    try:
        ndx_k, df = fetch_data()
        latest_date = ndx_k.index[-1].strftime('%Y-%m-%d')
        latest_close = ndx_k['Close'].iloc[-1]
    except Exception as e:
        st.error(f"行情拉取失败，请刷新页面重试: {e}")
        st.stop()

# 3. 13.5 分全量前瞻风控引擎 + 双重门禁逻辑
def evaluate_advanced_risk(df):
    score = 0.0
    reasons = []
    
    # 门禁触发状态标记
    gate_a_triggered = False  # 结构门禁 (RUT/SOX/QQQE背离)
    gate_b_triggered = False  # 基本面/信用门禁 (HYG信用利差/收益率解挂)
    
    ndx_close = df['NDX']
    ndx_52w_high = ndx_close.rolling(252).max().iloc[-1]
    is_near_high = (ndx_close.iloc[-1] >= ndx_52w_high * 0.93) # 纳指处于高位 7% 范围内

    # ================= 第一道防线：强领先因子 (总分 8.0) =================
    
    # 1. 小盘股顶背离 (RUT/NDX) - 2.0 分
    rut_ratio = df['RUT'] / df['NDX']
    rut_sma50 = rut_ratio.rolling(50).mean().iloc[-1]
    rut_sma200 = rut_ratio.rolling(200).mean().iloc[-1]
    if is_near_high and (rut_sma50 / rut_sma200 < 0.95):
        score += 2.0
        gate_a_triggered = True
        reasons.append("⚠️ [第一防线] 纳指高位，但罗素2000/NDX 均线死叉 (SMA50/200 < 0.95)，小盘股提前失血 (+2.0分)")

    # 2. 半导体先导板块背离 (SOX/NDX) - 2.0 分
    sox_ratio = df['SOX'] / df['NDX']
    sox_sma20 = sox_ratio.rolling(20).mean().iloc[-1]
    sox_1y_low = sox_ratio.rolling(252).min().iloc[-1]
    if is_near_high and (sox_sma20 <= sox_1y_low * 1.02):
        score += 2.0
        gate_a_triggered = True
        reasons.append("⚠️ [第一防线] 纳指维持高位，但 SOX/NDX 相对强度跌至 1 年低位附近 (+2.0分)")

    # 3. 信用利差隐蔽走阔 (HYG/LQD 信用代理) - 2.0 分
    credit_ratio = df['HYG'] / df['LQD']
    credit_sma20 = credit_ratio.rolling(20).mean().iloc[-1]
    credit_sma50 = credit_ratio.rolling(50).mean().iloc[-1]
    if credit_sma20 < credit_sma50 * 0.985:
        score += 2.0
        gate_b_triggered = True
        reasons.append("🚨 [第一防线] 信用市场恶化！高收益债相对投资级债 (HYG/LQD) 显著走弱，机构避险 (+2.0分)")

    # 4. 10Y-3M 收益率曲线倒挂后“熊市解挂” - 2.0 分
    curve = df['TNX'] - df['IRX'] # 10Y - 13W
    min_curve_1y = curve.rolling(252).min().iloc[-1]
    if min_curve_1y < 0 and curve.iloc[-1] > (min_curve_1y + 0.6): # 曾倒挂，现快速陡峭化 60bps
        score += 2.0
        gate_b_triggered = True
        reasons.append("🚨 [第一防线] 美债收益率曲线经历深倒挂后剧烈解挂 (>60bps)，历史衰退前兆 (+2.0分)")

    # ================= 第二道防线：中领先因子 (总分 3.0) =================
    
    # 5. 市场广度恶化 (等权重 QQQE/NDX 背离) - 1.5 分
    breadth_ratio = df['QQQE'] / df['NDX']
    breadth_sma50 = breadth_ratio.rolling(50).mean().iloc[-1]
    if is_near_high and (breadth_ratio.iloc[-1] < breadth_sma50 * 0.97):
        score += 1.5
        gate_a_triggered = True
        reasons.append("⚠️ [第二防线] 广度严重失真！纳指仅靠超级权重拉抬，QQQE/NDX 比值跌破 50 日均线 (+1.5分)")

    # 6. 期权暗涌：VIX 期限结构收敛/倒挂 (VIX/VIX3M) - 1.5 分
    vix_ratio = df['VIX'] / df['VIX3M']
    if vix_ratio.iloc[-1] > 0.95:
        score += 1.5
        reasons.append("⚠️ [第二防线] 期权暗涌！近月 VIX/3个月 VIX3M > 0.95，机构高位大量抢购短到期 Put 对冲 (+1.5分)")

    # ================= 第三道防线：确认与杀估值因子 (总分 2.5) =================
    
    # 7. 利率急涨杀估值 (10年美债 20日变化率) - 1.5 分
    tnx_change_20d = (df['TNX'].iloc[-1] - df['TNX'].iloc[-20]) / df['TNX'].iloc[-20]
    if tnx_change_20d > 0.10 and is_near_high:
        score += 1.5
        reasons.append(f"⚠️ [第三防线] 10年美债收益率近20日急涨 {tnx_change_20d*100:.1f}%，科技股估值遭遇挤压 (+1.5分)")

    # 8. 短期动能转弱 (NDX 跌破 20日均线且拐头) - 1.0 分
    ma20 = ndx_close.rolling(20).mean()
    if ndx_close.iloc[-1] < ma20.iloc[-1] and ma20.iloc[-1] < ma20.iloc[-3]:
        score += 1.0
        reasons.append("⚠️ [第三防线] 纳指跌破 20 日均线且 20 日线已向下拐头 (+1.0分)")

    return score, reasons, gate_a_triggered, gate_b_triggered

risk_score, risk_reasons, gate_a, gate_b = evaluate_advanced_risk(df)

# 4. 判定“双重门禁”与预警等级
def get_strategy_signal(score, gate_a, gate_b):
    if score >= 7.0:
        if gate_a and gate_b:
            return "RED", "🚨 红色高危预警 (确认 >30% 深度内生型熊市)", "门禁 A (结构背离) 与 门禁 B (基本面/信用) **同时触发**！这不是假警报，请全面避险。"
        elif gate_a and not gate_b:
            return "ORANGE_FALSE_ALARM_DEFENSE", "🟧 橙色防护 (高分但属于假警报防御区)", "门禁 A 已触发，但门禁 B (信用/衰退) 未确认。**防止被假警报甩下车**，仅防守不盲目杀跌。"
        else:
            return "ORANGE", "🟧 橙色防守预警 (结构严重恶化)", "风险得分达到高危区，但尚未触及双重门禁，启动分批锁利策略。"
    elif score >= 3.5:
        return "YELLOW", "🟨 黄色警惕 (晚周期/暗涌显现)", "出现早期结构性背离或期权高位对冲迹象，需暂停杠杆并拉大网格间隔。"
    else:
        return "GREEN", "🟩 绿色安全状态 (微观结构健康)", "市场无明显前瞻背离信号，按常规网格与定投计划正常运行。"

level, level_title, level_desc = get_strategy_signal(risk_score, gate_a, gate_b)

# 5. 看板展示
st.subheader(f"📅 交易日微观结构看板 ({latest_date})")

col1, col2, col3 = st.columns([1, 1, 2])
col1.metric("NDX 最新收盘价", f"{latest_close:,.2f}")
col2.metric("前瞻风控加权得分", f"{risk_score:.1f} / 13.5")

with col3:
    if level == "RED":
        st.error(f"{level_title}")
        st.write(f"**动作建议**：{level_desc} 股票仓位降至 **20%~30%**，余下 70%+ 转移至 3个月美债或货币基金。全量冻结网格抄底。")
    elif level == "ORANGE_FALSE_ALARM_DEFENSE":
        st.warning(f"{level_title}")
        st.write(f"**动作建议**：{level_desc} 保留 **60%~70%** 核心仓位，配置 OTM Put 领口对冲，清退高 Beta 零盈利杂毛股。")
    elif level == "ORANGE":
        st.warning(f"{level_title}")
        st.write(f"**动作建议**：开启逢高分批落袋，每月/反弹固定卖出 10% 股票仓位，提高现金比例至 30%+。")
    elif level == "YELLOW":
        st.info(f"{level_title}")
        st.write(f"**动作建议**：全面清退所有高倍数杠杆 (TQQQ/融资)，网格加仓门槛由 -5% 拉大至 **-10%~-12%**。")
    else:
        st.success(f"{level_title}")
        st.write(f"**动作建议**：大盘内部微观结构良好，无顶背离，正常运行既定交易计划。")

# 6. 显示双重门禁状态
st.markdown("---")
st.subheader("🚪 双重门禁确认状态 (Dual-Gate Validation)")
g_col1, g_col2 = st.columns(2)

with g_col1:
    if gate_a:
        st.error("❌ 门禁 A (市场结构门禁)：已触发 (RUT/SOX/QQQE 相对强弱显现严重背离)")
    else:
        st.success("✅ 门禁 A (市场结构门禁)：正常 (小盘股与半导体等广度正常)")

with g_col2:
    if gate_b:
        st.error("❌ 门禁 B (基本面/信用门禁)：已触发 (HYG 信用利差走阔 或 收益率曲线熊市解挂)")
    else:
        st.success("✅ 门禁 B (基本面/信用门禁)：正常 (信用市场与无风险利率利差安全)")

# 7. 详细因子计算日志
with st.expander("🔍 点击查看今日 13.5 分全量前瞻因子触发详情"):
    if risk_reasons:
        for r in risk_reasons:
            st.write(r)
    else:
        st.write("✅ 今日未检测到任何顶背离、期权暗涌、信用压力或利率挤压，内部结构非常健康。")

# 8. Plotly 交互图表：NDX 与 信用/广度背离指标
st.subheader("📊 NDX 与底层前瞻背离指标走势对比")

fig = go.Figure()
fig.add_trace(go.Scatter(x=df.index, y=df['NDX'], mode='lines', name='NDX 纳指100', line=dict(color='cyan', width=2)))
fig.add_trace(go.Scatter(x=df.index, y=df['NDX'].rolling(50).mean(), mode='lines', name='50日均线', line=dict(color='orange', width=1)))

fig.update_layout(
    xaxis_rangeslider_visible=False,
    height=450,
    margin=dict(l=10, r=10, t=10, b=10),
    template="plotly_dark",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

st.plotly_chart(fig, use_container_width=True)
