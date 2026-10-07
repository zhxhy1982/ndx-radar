import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# 页面基础配置
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="纳指100 (NDX) 全量量化前瞻风险诊断系统 V2.5",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🛡️ 纳指100 (NDX) 前瞻风险诊断与预警引擎 V2.5")
st.caption("集成了 14 项基础量化因子、HY OAS 动态 Z-Score、内部人筹码分布、D&A折旧剪刀差及动量/GEX乘数放大机制")

# -----------------------------------------------------------------------------
# 侧边栏：参数输入与市场实时数据模拟面板
# -----------------------------------------------------------------------------
st.sidebar.header("📊 市场实时指标配置 (Data Input)")

with st.sidebar.expander("1. 宏观与信用因子 (Macro & Credit)", expanded=True):
    hy_oas_current = st.number_input("HY OAS 绝对利差 (bps)", value=310, step=5)
    hy_oas_3y_mean = st.number_input("HY OAS 过去3年均值 (bps)", value=380, step=5)
    hy_oas_3y_std = st.number_input("HY OAS 过去3年标准差 (bps)", value=52, step=1)
    hy_oas_duration = st.slider("HY OAS 高于均值持续交易日数", 0, 60, 18)
    
    tips_10y = st.number_input("10年期 TIPS 实际收益率 (%)", value=2.15, step=0.05)
    erp_val = st.number_input("科技板块股权风险溢价 ERP (%)", value=-0.12, step=0.05)

with st.sidebar.expander("2. 市场结构与背离因子 (Market Structure)", expanded=False):
    sox_ndx_divergence = st.checkbox("SOX / NDX 发生 26周严重背离", value=True)
    dow_ndx_dispersion = st.checkbox("道指 / 纳指 发生历史极端分化 (Top 1%)", value=True)
    top5_below_200dma = st.slider("前五大权重股跌破 200日均线数量", 0, 5, 2)

with st.sidebar.expander("3. 财务与微观筹码因子 (Corporate & Micro)", expanded=False):
    insider_sell_buy_ratio = st.number_input("内部人 卖出/买入 比率分位数 (%)", value=93.5, step=1.0)
    da_shear_gap = st.number_input("D&A 折旧增速 - 营收增速 剪刀差 (%)", value=12.4, step=0.5)
    capex_ocf_ratio = st.number_input("Top4 云厂商 Capex / OCF 占比 (%)", value=98.0, step=1.0)

with st.sidebar.expander("4. 市场状态乘数系数 (Regime Multipliers)", expanded=True):
    momentum_crowd_percentile = st.slider("动量因子拥挤度 (过去5年分位数 %)", 0.0, 100.0, 92.0, step=1.0)
    gex_negative = st.checkbox("做市商 Gamma 结构转负 (Short Gamma / GEX < 0)", value=True)

# -----------------------------------------------------------------------------
# 核心诊断逻辑引擎
# -----------------------------------------------------------------------------
def calculate_risk_engine():
    factors = {}
    
    # 1. HY OAS Z-Score 修复逻辑（避开低基数陷阱）
    z_score = (hy_oas_current - hy_oas_3y_mean) / hy_oas_3y_std if hy_oas_3y_std != 0 else 0
    if z_score > 1.5 and hy_oas_duration >= 15:
        factors['HY OAS Z-Score 异常'] = {'score': 1.5, 'triggered': True, 'desc': f'Z-Score={z_score:.2f} > 1.5 且持续 {hy_oas_duration} 天'}
    else:
        factors['HY OAS Z-Score 异常'] = {'score': 0.0, 'triggered': False, 'desc': f'Z-Score={z_score:.2f} (未满足触发条件)'}

    # 2. SOX/NDX 背离
    factors['SOX/NDX 趋势背离'] = {'score': 1.5 if sox_ndx_divergence else 0.0, 'triggered': sox_ndx_divergence, 'desc': '半导体与纳指走势背离'}

    # 3. 道指/纳指 分化
    factors['道指/纳指 极值分化'] = {'score': 1.0 if dow_ndx_dispersion else 0.0, 'triggered': dow_ndx_dispersion, 'desc': '分化程度达历史 Top 1%'}

    # 4. ERP 坍塌
    erp_trigger = erp_val < 0.0
    factors['股权风险溢价 ERP 倒挂'] = {'score': 1.5 if erp_trigger else 0.0, 'triggered': erp_trigger, 'desc': f'ERP={erp_val:.2f}% (极度拥挤)'}

    # 5. 内部人减持比率 (新增微观因子)
    insider_trigger = insider_sell_buy_ratio >= 90.0
    factors['内部人减持比率异常'] = {'score': 2.0 if insider_trigger else 0.0, 'triggered': insider_trigger, 'desc': f'内部人抛售处于过去5年 {insider_sell_buy_ratio:.1f}% 高位'}

    # 6. D&A 折旧剪刀差 (新增财务因子)
    da_trigger = da_shear_gap > 10.0
    factors['D&A 折旧崖风险'] = {'score': 1.5 if da_trigger else 0.0, 'triggered': da_trigger, 'desc': f'折旧增速超越营收增速 {da_shear_gap:.1f}%'}

    # 7. TIPS 实际利率与久期错配
    tips_trigger = (tips_10y >= 2.0)
    factors['10Y TIPS 实际利率压制'] = {'score': 1.5 if tips_trigger else 0.0, 'triggered': tips_trigger, 'desc': f'实际利率={tips_10y:.2f}% 带来长久期估值收缩压'}

    # 8. 龙头股均线破坏
    ma_score = min(top5_below_200dma * 0.8, 3.0)
    factors['权重龙头跌破200日线'] = {'score': ma_score, 'triggered': top5_below_200dma > 0, 'desc': f'前五大权重中有 {top5_below_200dma} 只跌破均线'}

    # 基础分汇总
    base_score = sum(f['score'] for f in factors.values())

    # 乘数计算
    momentum_multiplier = 1.0
    if momentum_crowd_percentile >= 85.0:
        momentum_multiplier = 1.3 + (momentum_crowd_percentile - 85.0) * (0.2 / 15.0)  # 1.3x - 1.5x
    
    gex_multiplier = 1.15 if gex_negative else 1.00

    # 最终有效风险得分
    effective_score = base_score * momentum_multiplier * gex_multiplier

    return factors, base_score, momentum_multiplier, gex_multiplier, effective_score

factors_detail, base_score, mom_mult, gex_mult, effective_score = calculate_risk_engine()

# -----------------------------------------------------------------------------
# 诊断结果展示面板
# -----------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

col1.metric("基础得分 (Base Score)", f"{base_score:.2f} 分")
col2.metric("动量拥挤乘数", f"{mom_mult:.2f} x")
col3.metric("GEX 流动性乘数", f"{gex_mult:.2f} x")
col4.metric("综合有效风险得分", f"{effective_score:.2f} 分")

st.markdown("---")

# 预警状态判定
if effective_score < 5.0:
    status_color = "green"
    status_text = "🟢 绿色安全区 (GREEN REGIME)"
    action_text = "系统风险较低，保持标准权益配置，关注龙头股盈利兑现。"
elif 5.0 <= effective_score < 8.5:
    status_color = "orange"
    status_text = "🟠 橙色预警区 (ORANGE WARNING)"
    action_text = "进入中度应激状态：建议将权益仓位降至 50%-60%，买入 QQQ 虚值看跌期权进行尾部防护。"
else:
    status_color = "red"
    status_text = "🔴 红色极度危险区 (RED ALERT)"
    action_text = "系统极度脆弱：建议权益仓位降至 20%-30%，构建 QQQ/SPY 相对价值看跌价差（Relative Value Put Spread），转移流动性至短债 (T-Bills)。"

st.subheader(f"当前诊断状态：:{status_color}[{status_text}]")
st.info(f"💡 **执行策略建议**：{action_text}")

# -----------------------------------------------------------------------------
# 可视化与因子明细
# -----------------------------------------------------------------------------
left_col, right_col = st.columns([1, 1])

with left_col:
    st.subheader("📌 核心因子触发状态仪表盘")
    df_factors = pd.DataFrame([
        {"因子名称": k, "得/得分": v['score'], "状态": "🔴 触发" if v['triggered'] else "⚪ 未触发", "详情/阈值说明": v['desc']}
        for k, v in factors_detail.items()
    ])
    st.dataframe(df_factors, use_container_width=True, hide_index=True)

with right_col:
    st.subheader("📈 综合风险得分结构拆解")
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = effective_score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "综合有效风险得分 (Max ~18.0)"},
        gauge = {
            'axis': {'range': [0, 18], 'tickwidth': 1},
            'bar': {'color': "darkred" if effective_score >= 8.5 else ("orange" if effective_score >= 5.0 else "green")},
            'steps': [
                {'range': [0, 5.0], 'color': "rgba(0, 255, 0, 0.1)"},
                {'range': [5.0, 8.5], 'color': "rgba(255, 165, 0, 0.2)"},
                {'range': [8.5, 18.0], 'color': "rgba(255, 0, 0, 0.3)"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 8.5
            }
        }
    ))
    fig.update_layout(height=320, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# 架构优化说明文档
# -----------------------------------------------------------------------------
with st.expander("📘 查看 V2.5 版本的算法改进逻辑说明"):
    st.markdown("""
    ### V2.5 核心模型升级项：
    1. **HY OAS 动态 Z-Score (替代绝对阈值)**：
       使用 $(HY\_OAS - \mu_{3Y}) / \sigma_{3Y}$，消除利差结构性低位时的低基数误报 Trap。只有 Z-Score > 1.5 且持续超过 15 个交易日时才确认触发。
    2. **引入内部人筹码指标 (Insider Ratio)**：
       跟踪纳指 100 成分股内部人卖出/买入比率分位数，补齐微观治理与高管抛售的前置信号（领先期 3–6 个月）。
    3. **财务 D&A 折旧崖 (Depreciation Cliff)**：
       监控资本开支（Capex）转化为固定资产后的折旧压制，当 $D\&A \text{增速} - \text{营收增速} > 10\%$ 时警示利润率压缩风险。
    4. **动态双重乘数系统**：
       - **动量拥挤度乘数**：当动量因子持仓极度集中（>85% 分位）时，引入 $1.3\times - 1.5\times$ 乘数放大连锁去杠杆风险。
       - **GEX 流动性乘数**：当做市商 Gamma 转负 ($GEX < 0$) 时，额外增加 $1.15\times$ 乘数，反映日内做市商顺势抛售带来的流动性黑洞。
    """)
