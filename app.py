import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import io
from rate_tables import PLANS, PLANS_GENDER, EXCHANGE_RATE, BASE_COUPON_USD, \
    COUPON_FIXED_YEARS, LV_PAYMENT_YEARS, COUPON_START_YEAR, LV_ANNUAL_HKD, \
    DEFAULT_PLAN, DEFAULT_AGE, DEFAULT_GENDER, ALL_PLANS

# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def lookup_premium(plan: str, age: int, gender: str) -> float | None:
    if plan in PLANS_GENDER:
        return PLANS_GENDER[plan].get(gender, {}).get(age)
    if plan in PLANS:
        return PLANS[plan].get(age)
    return None


def build_projection(plan: str, gender: str, start_age: int, inflation: float):
    rows, cum_prem, cum_coupon, cum_net = [], 0.0, 0.0, 0.0
    last_base = None
    for year_idx, age in enumerate(range(start_age, 101)):
        base = lookup_premium(plan, age, gender)
        if base is None or base == 0:
            base = last_base if last_base else 0
        else:
            last_base = base
        if base == 0:
            continue

        vhis_hkd = base * (1 + inflation) ** year_idx
        vhis_usd = vhis_hkd / EXCHANGE_RATE

        policy_year = year_idx + 1
        if policy_year < COUPON_START_YEAR:
            coupon_usd = 0.0
        elif policy_year <= COUPON_FIXED_YEARS:
            coupon_usd = BASE_COUPON_USD
        else:
            coupon_usd = BASE_COUPON_USD * (1 + inflation) ** (policy_year - COUPON_FIXED_YEARS)
        coupon_hkd = coupon_usd * EXCHANGE_RATE

        lv_payment_hkd = LV_ANNUAL_HKD if policy_year <= LV_PAYMENT_YEARS else 0.0
        net_hkd = vhis_hkd - coupon_hkd
        cum_prem   += vhis_hkd
        cum_coupon += coupon_hkd
        cum_net    += net_hkd

        rows.append({
            "Year": policy_year, "Age": age,
            "VHIS_Base_HKD":     round(base, 2),
            "VHIS_Premium_HKD":  round(vhis_hkd, 2),
            "VHIS_Premium_USD":  round(vhis_usd, 2),
            "Coupon_USD":        round(coupon_usd, 2),
            "Coupon_HKD":        round(coupon_hkd, 2),
            "LV_Payment_HKD":    round(lv_payment_hkd, 2),
            "Net_Outflow_HKD":   round(net_hkd, 2),
            "Cum_Premium_HKD":   round(cum_prem, 2),
            "Cum_Coupon_HKD":    round(cum_coupon, 2),
            "Cum_Net_HKD":       round(cum_net, 2),
        })
    import pandas as pd
    return pd.DataFrame(rows) if rows else None

st.set_page_config(
    page_title="VHIS + LV15 Offset Calculator",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# MANULIFE BRAND DESIGN SYSTEM
# Primary:   #00A758  (Manulife Green)
# Dark:      #1A1A2E  (deep navy / near-black for sidebar)
# Secondary: #00583C  (deep forest green, hover/active)
# Accent:    #F5A623  (warm amber — contrast pop for alerts/crossover)
# Surface:   #F4F9F6  (very light mint background)
# Card:      #FFFFFF
# Text:      #1C2B1E  (near-black green-tinted text)
# Muted:     #6B7C74  (grey-green muted text)
# Success:   #00A758  (same as primary — coupon covers premium)
# Warning:   #E8A020  (amber — premium exceeds coupon)
# Error:     #C0392B  (red for crossover milestone)
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  /* ── Global reset & typography ── */
  html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  }

  /* ── Page background ── */
  .stApp { background-color: #F4F9F6; }
  .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1280px; }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #00583C 0%, #003D2A 100%) !important;
    border-right: none;
  }
  [data-testid="stSidebar"] * { color: #E8F5EE !important; }
  [data-testid="stSidebar"] .stSelectbox label,
  [data-testid="stSidebar"] .stSlider label,
  [data-testid="stSidebar"] .stRadio label { 
    color: #A8D5BC !important; 
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  [data-testid="stSidebar"] .stMarkdown h2 {
    color: #FFFFFF !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.04em;
  }
  [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.15) !important; margin: 0.75rem 0; }
  [data-testid="stSidebar"] [data-testid="stMetric"] {
    background: rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.4rem;
  }
  [data-testid="stSidebar"] [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 1rem !important; }
  [data-testid="stSidebar"] [data-testid="stMetricLabel"] { color: #A8D5BC !important; font-size: 0.72rem !important; }

  /* ── Sidebar params strip ── */
  .sidebar-param {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.45rem 0.75rem; background: rgba(255,255,255,0.09);
    border-radius: 7px; margin-bottom: 0.35rem;
  }
  .sidebar-param-label { font-size: 0.72rem; color: #A8D5BC; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
  .sidebar-param-value { font-size: 0.88rem; color: #FFFFFF; font-weight: 700; }

  /* ── App header banner ── */
  .app-header {
    background: linear-gradient(135deg, #00583C 0%, #00A758 60%, #00C46A 100%);
    color: white;
    padding: 1.6rem 2.2rem;
    border-radius: 14px;
    margin-bottom: 1.6rem;
    box-shadow: 0 6px 24px rgba(0,87,60,0.22);
    position: relative;
    overflow: hidden;
  }
  .app-header::before {
    content: '';
    position: absolute;
    top: -40px; right: -40px;
    width: 200px; height: 200px;
    background: rgba(255,255,255,0.06);
    border-radius: 50%;
  }
  .app-header::after {
    content: '';
    position: absolute;
    bottom: -60px; right: 80px;
    width: 160px; height: 160px;
    background: rgba(255,255,255,0.04);
    border-radius: 50%;
  }
  .app-header h1 {
    margin: 0 0 0.3rem;
    font-size: 1.65rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    position: relative; z-index: 1;
  }
  .app-header p {
    margin: 0;
    opacity: 0.88;
    font-size: 0.88rem;
    font-weight: 400;
    position: relative; z-index: 1;
  }
  .app-header .header-badge {
    display: inline-block;
    background: rgba(255,255,255,0.18);
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: 20px;
    padding: 0.2rem 0.7rem;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 0.55rem;
    position: relative; z-index: 1;
  }

  /* ── Metric cards ── */
  .metric-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 12px rgba(0,87,60,0.06);
    border-top: 3px solid #00A758;
    margin-bottom: 0.9rem;
    transition: box-shadow 0.2s ease;
  }
  .metric-card:hover { box-shadow: 0 4px 16px rgba(0,87,60,0.13); }
  .metric-card.green  { border-top-color: #00A758; }
  .metric-card.amber  { border-top-color: #F5A623; }
  .metric-card.red    { border-top-color: #C0392B; }
  .metric-card.violet { border-top-color: #7C5CBF; }
  .metric-label {
    font-size: 0.72rem;
    color: #6B7C74;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 0.3rem;
  }
  .metric-value {
    font-size: 1.85rem;
    font-weight: 800;
    color: #1C2B1E;
    line-height: 1.1;
    letter-spacing: -0.02em;
  }
  .metric-value.green  { color: #00583C; }
  .metric-value.amber  { color: #C17D10; }
  .metric-value.red    { color: #C0392B; }
  .metric-value.violet { color: #7C5CBF; }
  .metric-sub {
    font-size: 0.75rem;
    color: #9BB0A4;
    margin-top: 0.2rem;
    font-weight: 400;
  }

  /* ── Insight / callout box ── */
  .insight-box {
    background: linear-gradient(135deg, #F0FBF5 0%, #E6F7EE 100%);
    border: 1px solid #B8E6CE;
    border-left: 4px solid #00A758;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin: 0.9rem 0;
    font-size: 0.875rem;
    color: #1C3A28;
    line-height: 1.6;
  }
  .insight-box b { color: #00583C; }

  /* ── Section divider ── */
  .section-divider {
    height: 1px;
    background: linear-gradient(90deg, #B8E6CE 0%, #E8F5EE 100%);
    margin: 1rem 0;
    border: none;
  }

  /* ── Tab styling ── */
  .stTabs [data-baseweb="tab-list"] {
    background: #E8F5EE;
    border-radius: 10px;
    padding: 4px;
    gap: 2px;
  }
  .stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.875rem;
    color: #4A7060;
    padding: 0.5rem 1rem;
    transition: all 0.18s ease;
  }
  .stTabs [aria-selected="true"] {
    background: #FFFFFF !important;
    color: #00583C !important;
    box-shadow: 0 1px 4px rgba(0,87,60,0.12);
  }
  .stTabs [data-baseweb="tab-panel"] { padding-top: 1.25rem; }

  /* ── Data table colour scheme ── */
  /* Row: coupon covers premium → mint green */
  .table-row-green td { background-color: #E8F9EF !important; color: #1C3A28 !important; }
  /* Row: premium exceeds coupon → soft amber */
  .table-row-amber td { background-color: #FEF6E4 !important; color: #4A3000 !important; }

  /* Override Streamlit's default dataframe colours */
  [data-testid="stDataFrame"] table { border-collapse: collapse; }
  [data-testid="stDataFrame"] thead th {
    background: #00583C !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 10px 14px !important;
    border-bottom: 2px solid #00A758 !important;
  }
  [data-testid="stDataFrame"] tbody tr:nth-child(even) td {
    background-color: #F4F9F6 !important;
  }
  [data-testid="stDataFrame"] tbody tr:nth-child(odd) td {
    background-color: #FFFFFF !important;
  }
  [data-testid="stDataFrame"] tbody tr:hover td {
    background-color: #E0F5EB !important;
  }
  [data-testid="stDataFrame"] td {
    font-size: 0.83rem !important;
    padding: 8px 14px !important;
    color: #1C2B1E !important;
    border-bottom: 1px solid #E8F0EC !important;
  }

  /* ── Download button ── */
  .stDownloadButton > button {
    background: #00A758 !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.55rem 1.4rem !important;
    transition: background 0.18s ease;
  }
  .stDownloadButton > button:hover { background: #00583C !important; }

  /* ── Legend badges ── */
  .legend-badge {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 0.3rem 0.85rem;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-right: 0.5rem;
  }
  .legend-badge.green { background: #E8F9EF; color: #00583C; border: 1px solid #B8E6CE; }
  .legend-badge.amber { background: #FEF6E4; color: #A06000; border: 1px solid #F5D68A; }

  /* ── Milestone card ── */
  .milestone-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 1.1rem 1.3rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    margin-bottom: 0.75rem;
  }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.markdown("---")
    st.markdown("### 🏥 VHIS Plan")
    plan = st.selectbox(
        "Plan Name", ALL_PLANS,
        index=ALL_PLANS.index(DEFAULT_PLAN) if DEFAULT_PLAN in ALL_PLANS else 0
    )
    st.markdown("### 👤 Insured Person")
    gender = st.radio("Gender", ["Male", "Female"],
                      index=1 if DEFAULT_GENDER == "Female" else 0,
                      horizontal=True)
    age = st.slider("Current Age", min_value=0, max_value=85, value=DEFAULT_AGE, step=1)
    st.markdown("### 📈 Assumptions")
    inflation_label = st.radio(
        "Medical Inflation Rate",
        ["5% per annum", "7% per annum"], index=1
    )
    inflation_rate = 0.07 if "7%" in inflation_label else 0.05
    st.markdown("---")
    st.markdown("### 📌 LV Plan Parameters")
    st.markdown(f"""
    <div class="sidebar-param">
      <span class="sidebar-param-label">Exchange Rate</span>
      <span class="sidebar-param-value">HKD {EXCHANGE_RATE:.4f}/USD</span>
    </div>
    <div class="sidebar-param">
      <span class="sidebar-param-label">Annual Coupon</span>
      <span class="sidebar-param-value">US${BASE_COUPON_USD:,.0f}</span>
    </div>
    <div class="sidebar-param">
      <span class="sidebar-param-label">Coupon Start</span>
      <span class="sidebar-param-value">Year {COUPON_START_YEAR}</span>
    </div>
    <div class="sidebar-param">
      <span class="sidebar-param-label">LV Payment Term</span>
      <span class="sidebar-param-value">{LV_PAYMENT_YEARS} Years</span>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="app-header">
  <div class="header-badge">🏥 Manulife VHIS</div>
  <h1>LV15 Premium Offset Calculator</h1>
  <p>Visualise how your Savings Plan (LV15) coupons offset rising VHIS medical insurance premiums over time — from age {age} to 100.</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# COMPUTE
# ─────────────────────────────────────────────────────────────────────────────
df = build_projection(plan, gender, age, inflation_rate)

if df is None or df.empty:
    st.error(f"⚠️ No premium data found for **{plan}** / {gender} at age {age}. "
             "Please select a different plan or age.")
    st.stop()

base_premium   = df.iloc[0]["VHIS_Base_HKD"]
total_premiums = df["VHIS_Premium_HKD"].sum()
total_coupons  = df["Coupon_HKD"].sum()
total_lv_paid  = df["LV_Payment_HKD"].sum()
total_net      = df["Net_Outflow_HKD"].sum()
final_prem     = df.iloc[-1]["VHIS_Premium_HKD"]
final_coupon   = df.iloc[-1]["Coupon_HKD"]
offset_pct     = (total_coupons / total_premiums * 100) if total_premiums > 0 else 0

crossover_row = df[(df["Coupon_HKD"] > 0) & (df["VHIS_Premium_HKD"] > df["Coupon_HKD"])].head(1)
crossover_age = int(crossover_row["Age"].iloc[0]) if not crossover_row.empty else None

breakeven_row = df[df["Cum_Coupon_HKD"] >= df["Cum_Premium_HKD"]].head(1)
breakeven_age = int(breakeven_row["Age"].iloc[0]) if not breakeven_row.empty else None

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊  Dashboard", "📈  Interactive Chart", "📋  Data Table"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    col_l, col_r = st.columns([3, 2], gap="large")

    with col_l:
        st.markdown(f"#### 💰 Lifetime Financial Summary &nbsp; <small style='color:#9BB0A4;font-weight:400;font-size:0.8rem;'>Age {age} → 100</small>", unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f"""
            <div class="metric-card green">
              <div class="metric-label">Total VHIS Premiums</div>
              <div class="metric-value">HK${total_premiums/1e6:.2f}M</div>
              <div class="metric-sub">Cumulative Age {age}→100</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
            <div class="metric-card green">
              <div class="metric-label">Total LV Coupons Received</div>
              <div class="metric-value green">HK${total_coupons/1e6:.2f}M</div>
              <div class="metric-sub">≈ US${total_coupons/EXCHANGE_RATE:,.0f}</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""
            <div class="metric-card amber">
              <div class="metric-label">Net Out-of-Pocket</div>
              <div class="metric-value amber">HK${total_net/1e6:.2f}M</div>
              <div class="metric-sub">After coupon offset</div>
            </div>""", unsafe_allow_html=True)

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Current Age", f"{age}")
        with c2: st.metric(f"Base Premium", f"HK${base_premium:,.0f}", help=f"Age {age} base rate")
        with c3: st.metric("Premium @ Age 100", f"HK${final_prem:,.0f}")
        with c4: st.metric("Coupon @ Age 100", f"HK${final_coupon:,.0f}")

        st.markdown(f"""
        <div class="insight-box">
          <b>📌 Coupon Coverage:</b> The LV15 savings plan coupons offset <b>{offset_pct:.1f}%</b>
          of total VHIS lifetime premiums — delivering <b>HK${total_coupons:,.0f}</b> in value
          against HK${total_premiums:,.0f} in premiums.<br><br>
          <b>💡 Cost Efficiency:</b> The LV plan requires only a <b>{LV_PAYMENT_YEARS}-year
          payment commitment</b> (total HK${total_lv_paid:,.0f}), yet generates coupons
          continuously through age 100.
        </div>
        """, unsafe_allow_html=True)

    with col_r:
        st.markdown("#### 🎯 Key Milestones")

        # Donut chart
        fig_donut = go.Figure(go.Pie(
            labels=["Net Out-of-Pocket", "LV Coupon Offset"],
            values=[max(total_net, 0), total_coupons],
            hole=0.62,
            marker=dict(
                colors=["#E8F5EE", "#00A758"],
                line=dict(color=["#B8E6CE", "#00583C"], width=2),
            ),
            textinfo="percent",
            textfont=dict(size=13, color=["#6B7C74", "#FFFFFF"]),
            hovertemplate="%{label}<br>HK$%{value:,.0f}<extra></extra>",
            rotation=90,
        ))
        fig_donut.add_annotation(
            text=f"<b>{offset_pct:.0f}%</b><br><span style='font-size:11px'>offset</span>",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color="#00583C", family="Inter"),
            xanchor="center", yanchor="middle",
        )
        fig_donut.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.12, xanchor="center", x=0.5,
                        font=dict(size=12, color="#4A7060")),
            margin=dict(t=10, b=30, l=10, r=10),
            height=220,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_donut, use_container_width=True)

        # Milestone cards
        if crossover_age:
            st.markdown(f"""
            <div class="milestone-card" style="border-left:4px solid #C0392B;">
              <div class="metric-label" style="color:#C0392B;">⚠️ Premium Exceeds Coupon</div>
              <div class="metric-value red" style="font-size:1.5rem;">Age {crossover_age}</div>
              <div class="metric-sub">Annual VHIS cost exceeds LV coupon from this age</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="milestone-card" style="border-left:4px solid #00A758;">
              <div class="metric-label" style="color:#00A758;">✅ Coupon Always Covers</div>
              <div class="metric-value green" style="font-size:1.5rem;">Full Coverage</div>
              <div class="metric-sub">LV coupon exceeds VHIS premium throughout</div>
            </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div class="milestone-card" style="border-left:4px solid #7C5CBF;">
          <div class="metric-label" style="color:#7C5CBF;">📈 Inflation Scenario</div>
          <div class="metric-value violet" style="font-size:1.5rem;">{int(inflation_rate*100)}% p.a.</div>
          <div class="metric-sub">Applied to premium growth &amp; post-yr 15 coupon escalation</div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — INTERACTIVE CHART
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    view_toggle = st.radio(
        "View Mode",
        ["Annual Cash Flows", "Cumulative Totals"],
        horizontal=True,
        key="view_toggle"
    )

    # Manulife chart colours
    MAN_GREEN      = "#00A758"
    MAN_DARK_GREEN = "#00583C"
    MAN_AMBER      = "#F5A623"
    MAN_RED        = "#C0392B"
    MAN_VIOLET     = "#7C5CBF"
    MAN_LIGHT      = "#E8F5EE"

    chart_layout = dict(
        hovermode="x unified",
        height=500,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FAFCFB",
        font=dict(family="Inter", color="#4A7060"),
        xaxis=dict(
            title="Age",
            gridcolor="#E8F0EC",
            linecolor="#C8DDD4",
            tickfont=dict(size=11),
            title_font=dict(size=12, color="#6B7C74"),
        ),
        yaxis=dict(
            gridcolor="#E8F0EC",
            linecolor="#C8DDD4",
            tickformat=",.0f",
            tickfont=dict(size=11),
            title_font=dict(size=12, color="#6B7C74"),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            font=dict(size=12),
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#C8DDD4",
            borderwidth=1,
        ),
        margin=dict(t=40, b=50, l=60, r=20),
    )

    if view_toggle == "Annual Cash Flows":
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df["Age"], y=df["VHIS_Premium_HKD"],
            name="VHIS Annual Premium",
            marker=dict(color=MAN_DARK_GREEN, opacity=0.82, line=dict(width=0)),
            hovertemplate="Age %{x}<br><b>Premium:</b> HK$%{y:,.0f}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=df["Age"], y=df["Coupon_HKD"],
            name="LV Annual Coupon",
            marker=dict(color=MAN_GREEN, opacity=0.85, line=dict(width=0)),
            hovertemplate="Age %{x}<br><b>Coupon:</b> HK$%{y:,.0f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=df["Age"], y=df["Net_Outflow_HKD"],
            name="Net Annual Outflow",
            mode="lines",
            line=dict(color=MAN_AMBER, width=2.5, dash="solid"),
            hovertemplate="Age %{x}<br><b>Net:</b> HK$%{y:,.0f}<extra></extra>",
        ))
        # Annotations
        fig.add_vline(
            x=age + COUPON_START_YEAR - 1,
            line=dict(dash="dot", color=MAN_GREEN, width=1.5),
            annotation=dict(text="Coupon starts", font=dict(size=11, color=MAN_GREEN), bgcolor="rgba(255,255,255,0.8)"),
            annotation_position="top right",
        )
        if crossover_age:
            fig.add_vline(
                x=crossover_age,
                line=dict(dash="dash", color=MAN_RED, width=1.5),
                annotation=dict(text=f"Premium > Coupon (Age {crossover_age})", font=dict(size=11, color=MAN_RED), bgcolor="rgba(255,255,255,0.8)"),
                annotation_position="top left",
            )
        fig.update_layout(barmode="group", yaxis_title="HKD (HK$)",
                          title=dict(text=f"Annual Cash Flows — {plan} | {gender} | {int(inflation_rate*100)}% inflation",
                                     font=dict(size=13, color="#1C2B1E")),
                          **chart_layout)
        st.plotly_chart(fig, use_container_width=True)

    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["Age"], y=df["Cum_Premium_HKD"],
            name="Cumulative Premiums",
            fill="tozeroy",
            line=dict(color=MAN_DARK_GREEN, width=2.5),
            fillcolor="rgba(0,88,60,0.1)",
            hovertemplate="Age %{x}<br><b>Cum. Premium:</b> HK$%{y:,.0f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=df["Age"], y=df["Cum_Coupon_HKD"],
            name="Cumulative Coupons",
            fill="tozeroy",
            line=dict(color=MAN_GREEN, width=2.5),
            fillcolor="rgba(0,167,88,0.12)",
            hovertemplate="Age %{x}<br><b>Cum. Coupon:</b> HK$%{y:,.0f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=df["Age"], y=df["Cum_Net_HKD"],
            name="Cumulative Net Outflow",
            line=dict(color=MAN_AMBER, width=2, dash="dash"),
            hovertemplate="Age %{x}<br><b>Cum. Net:</b> HK$%{y:,.0f}<extra></extra>",
        ))
        if breakeven_age:
            fig.add_vline(
                x=breakeven_age,
                line=dict(dash="dot", color=MAN_VIOLET, width=1.5),
                annotation=dict(text=f"Break-even (Age {breakeven_age})", font=dict(size=11, color=MAN_VIOLET), bgcolor="rgba(255,255,255,0.8)"),
                annotation_position="top right",
            )
        fig.update_layout(yaxis_title="Cumulative HKD (HK$)",
                          title=dict(text=f"Cumulative Cash Flows — {plan} | {gender} | {int(inflation_rate*100)}% inflation",
                                     font=dict(size=13, color="#1C2B1E")),
                          **chart_layout)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"""
    <div class="insight-box">
      <b>🗺️ Chart Guide:</b>
      <b style="color:#00583C;">Dark green bars/area</b> = VHIS annual premiums (age-based rates × {int(inflation_rate*100)}% p.a. inflation).
      <b style="color:#00A758;">Green bars/area</b> = LV15 coupons — flat US$3,650 for policy years 1–15, then growing at {int(inflation_rate*100)}% p.a.
      <b style="color:#C17D10;">Amber line</b> = net annual or cumulative out-of-pocket after the coupon offset.
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — DATA TABLE
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown(
        f"#### 📋 Year-by-Year Projection &nbsp;"
        f"<small style='color:#9BB0A4;font-weight:400;font-size:0.82rem;'>"
        f"{plan} &nbsp;|&nbsp; {gender} &nbsp;|&nbsp; Age {age}→100 &nbsp;|&nbsp; {int(inflation_rate*100)}% Inflation"
        f"</small>",
        unsafe_allow_html=True
    )

    display_df = df[[
        "Year", "Age",
        "VHIS_Premium_HKD", "VHIS_Premium_USD",
        "Coupon_USD", "Coupon_HKD",
        "LV_Payment_HKD", "Net_Outflow_HKD",
        "Cum_Premium_HKD", "Cum_Coupon_HKD", "Cum_Net_HKD",
    ]].copy()
    display_df.columns = [
        "Year", "Age",
        "VHIS Premium (HKD)", "VHIS Premium (USD)",
        "LV Coupon (USD)", "LV Coupon (HKD)",
        "LV Policy Payment (HKD)", "Net Outflow (HKD)",
        "Cum. Premiums (HKD)", "Cum. Coupons (HKD)", "Cum. Net (HKD)",
    ]

    def highlight_rows(row):
        coupon = row["LV Coupon (HKD)"]
        prem   = row["VHIS Premium (HKD)"]
        # Manulife green: coupon covers premium
        if coupon > 0 and prem <= coupon:
            return [
                "background-color:#E3F7EC; color:#0B3D21;"
                "border-bottom:1px solid #B8E6CE;"
            ] * len(row)
        # Manulife amber: premium exceeds coupon (risk zone)
        elif coupon > 0 and prem > coupon:
            return [
                "background-color:#FEF6E4; color:#4A3000;"
                "border-bottom:1px solid #F5D68A;"
            ] * len(row)
        # No coupon yet (year 1) — very light
        return ["background-color:#F9FDFB;"] * len(row)

    hkd_fmt = {c: "HK${:,.0f}" for c in display_df.columns if "HKD" in c}
    usd_fmt = {c: "US${:,.0f}" for c in display_df.columns if "USD" in c}
    fmt = {**hkd_fmt, **usd_fmt, "Year": "{:d}", "Age": "{:d}"}

    styled = (
        display_df.style
        .apply(highlight_rows, axis=1)
        .format(fmt)
        .set_table_styles([
            {"selector": "thead th",
             "props": [("background-color", "#00583C"), ("color", "#FFFFFF"),
                       ("font-weight", "700"), ("font-size", "0.76rem"),
                       ("text-transform", "uppercase"), ("letter-spacing", "0.04em"),
                       ("padding", "10px 14px"), ("border-bottom", "2px solid #00A758")]},
            {"selector": "tbody td",
             "props": [("font-size", "0.82rem"), ("padding", "8px 14px")]},
            {"selector": "tbody tr:hover td",
             "props": [("background-color", "#D6F2E5 !important")]},
        ])
    )

    st.dataframe(styled, use_container_width=True, height=520)

    # Legend
    st.markdown("""
    <div style="margin-top:0.6rem; display:flex; gap:0.5rem; flex-wrap:wrap;">
      <span class="legend-badge green">🟢 &nbsp;Coupon ≥ Premium (covered)</span>
      <span class="legend-badge amber">🟡 &nbsp;Premium > Coupon (net outflow)</span>
    </div>
    """, unsafe_allow_html=True)

    import io as _io
    csv_buf = _io.StringIO()
    display_df.to_csv(csv_buf, index=False)
    st.download_button(
        label="⬇️  Download as CSV",
        data=csv_buf.getvalue(),
        file_name=f"Manulife_VHIS_LV15_{plan}_{gender}_Age{age}.csv",
        mime="text/csv",
    )

# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='text-align:center; color:#9BB0A4; font-size:0.75rem; padding:0.5rem 0;'>"
    f"Manulife VHIS + LV15 Offset Calculator &nbsp;·&nbsp; "
    f"For illustrative purposes only &nbsp;·&nbsp; Not financial advice &nbsp;·&nbsp; "
    f"HKD/USD {EXCHANGE_RATE} &nbsp;·&nbsp; Powered by Streamlit"
    f"</div>",
    unsafe_allow_html=True,
)
