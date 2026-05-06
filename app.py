import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VHIS + LV15 Offset Calculator",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main theme colours */
    :root {
        --primary: #1a4f8a;
        --accent:  #e8a020;
        --bg-card: #f7f9fc;
        --text:    #1a2340;
    }

    .main { background-color: #f0f4fa; }

    /* Header banner */
    .app-header {
        background: linear-gradient(135deg, #1a4f8a 0%, #2c6fbe 100%);
        color: white; padding: 1.5rem 2rem; border-radius: 12px;
        margin-bottom: 1.5rem; box-shadow: 0 4px 16px rgba(26,79,138,.25);
    }
    .app-header h1 { margin: 0; font-size: 1.7rem; font-weight: 700; }
    .app-header p  { margin: .3rem 0 0; opacity: .85; font-size: .9rem; }

    /* Metric cards */
    .metric-card {
        background: white; border-radius: 10px; padding: 1.2rem 1.5rem;
        box-shadow: 0 2px 10px rgba(0,0,0,.07); border-left: 5px solid var(--primary);
        margin-bottom: .8rem;
    }
    .metric-label { font-size: .8rem; color: #6b7280; font-weight: 600;
                    text-transform: uppercase; letter-spacing: .05em; }
    .metric-value { font-size: 1.8rem; font-weight: 800; color: var(--primary); }
    .metric-sub   { font-size: .78rem; color: #9ca3af; margin-top: .2rem; }

    /* Insight box */
    .insight-box {
        background: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px;
        padding: .9rem 1.2rem; margin: .8rem 0; font-size: .88rem;
    }

    /* Crossover badge */
    .badge-green { background:#dcfce7; color:#166534; padding:.3rem .8rem;
                   border-radius:20px; font-weight:700; font-size:.85rem; }
    .badge-red   { background:#fee2e2; color:#991b1b; padding:.3rem .8rem;
                   border-radius:20px; font-weight:700; font-size:.85rem; }

    /* Sidebar tweaks */
    [data-testid="stSidebar"] { background: #1a2340; }
    [data-testid="stSidebar"] * { color: #d1d9e6 !important; }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stSlider label { color: #93aed3 !important; font-size:.82rem; }

    /* Tab styling */
    .stTabs [data-baseweb="tab"] { font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_workbook_data(file_bytes: bytes) -> dict:
    """Parse Excel workbook into structured dicts for quick lookup."""
    xf = io.BytesIO(file_bytes)
    sheets = pd.read_excel(xf, sheet_name=None, header=None)

    result = {
        "beta": {},
        "plans": {},          # plan_name -> {age -> premium_hkd}
        "plans_with_gender": {},  # plan_name -> {"Male": {age->prem}, "Female": {age->prem}}
    }

    # ── beta parameters ──────────────────────────────────────────────────────
    beta = sheets.get("beta", pd.DataFrame())
    for _, row in beta.iterrows():
        key = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
        val = row.iloc[3] if pd.notna(row.iloc[3]) else None
        if key and val is not None:
            result["beta"][key] = val

    # ── Helper: extract (Age -> premium) pairs from two contiguous columns ───
    def extract_plan(df, age_col, prem_col, start_row=2):
        d = {}
        for i in range(start_row, len(df)):
            age = df.iloc[i, age_col]
            prem = df.iloc[i, prem_col]
            if pd.notna(age) and pd.notna(prem):
                try:
                    a = int(float(str(age).replace("*", "").strip()))
                    p = float(prem)
                    if 0 <= a <= 130 and p >= 0:
                        d[a] = p
                except (ValueError, TypeError):
                    pass
        return d

    # ── Supreme sheet ─────────────────────────────────────────────────────────
    sup = sheets.get("Supreme", pd.DataFrame())
    # Block 1: rows 0-122 (header at row 0, data rows 2+)
    for col_pair in [(0,1),(2,3),(4,5),(6,7),(8,9),(10,11),(12,13),(14,15)]:
        hdr = sup.iloc[0, col_pair[1]]
        if pd.notna(hdr) and str(hdr).strip() not in ("x",""):
            result["plans"][str(hdr).strip()] = extract_plan(sup, col_pair[0], col_pair[1])
    # Block 2: rows 124-246 (header at row 124, data rows 126+)
    if len(sup) > 125:
        for col_pair in [(0,1),(2,3),(4,5),(6,7)]:
            hdr = sup.iloc[124, col_pair[1]]
            if pd.notna(hdr) and str(hdr).strip() not in ("x",""):
                result["plans"][str(hdr).strip()] = extract_plan(sup, col_pair[0], col_pair[1], start_row=126)
    # Block 3: rows 248-end (header at row 248, data rows 250+) – 晉悅優選
    if len(sup) > 250:
        for col_pair in [(0,1),(2,3),(4,5),(6,7),(8,9)]:
            if col_pair[1] < sup.shape[1]:
                hdr = sup.iloc[248, col_pair[1]]
                if pd.notna(hdr) and str(hdr).strip():
                    result["plans"][str(hdr).strip()] = extract_plan(sup, col_pair[0], col_pair[1], start_row=250)

    # ── SupremeLite sheet ─────────────────────────────────────────────────────
    sl = sheets.get("SupremeLite", pd.DataFrame())
    # Block 1: header row 0, data 2+
    for col_pair in [(0,1),(2,3),(4,5),(6,7)]:
        if col_pair[1] < sl.shape[1]:
            hdr = sl.iloc[0, col_pair[1]]
            if pd.notna(hdr):
                result["plans"][str(hdr).strip()] = extract_plan(sl, col_pair[0], col_pair[1])
    # Block 2: header row 124, data 126+
    if len(sl) > 126:
        for col_pair in [(0,1),(2,3),(4,5),(6,7)]:
            if col_pair[1] < sl.shape[1]:
                hdr = sl.iloc[124, col_pair[1]]
                if pd.notna(hdr) and str(hdr).strip():
                    result["plans"][str(hdr).strip()] = extract_plan(sl, col_pair[0], col_pair[1], start_row=126)

    # ── First sheet – has Male/Female split ───────────────────────────────────
    fi = sheets.get("First", pd.DataFrame())
    # Block 1: row 0 = plan group name, row 1 = Male/Female, data from row 2
    # col layout: (none, plan, none, none, none, plan2, ...) for row 0
    # row 1: (none, Male, none, Female, none, Male, none, Female, ...)
    def extract_first_block(fi_df, start_col, data_start_row=2):
        """Extract Male & Female series from 4-col group starting at start_col."""
        hdr_row = 0 if data_start_row == 2 else 124
        plan_name = fi_df.iloc[hdr_row, start_col + 1]
        if not pd.notna(plan_name) or not str(plan_name).strip():
            return None, None, None
        name = str(plan_name).strip()
        male_d, female_d = {}, {}
        for i in range(data_start_row, len(fi_df)):
            age_m = fi_df.iloc[i, start_col]
            pm    = fi_df.iloc[i, start_col + 1]
            pf    = fi_df.iloc[i, start_col + 3]
            if pd.notna(age_m) and pd.notna(pm):
                try:
                    a = int(float(str(age_m).replace("*","").strip()))
                    if 0 <= a <= 130:
                        male_d[a]   = float(pm)
                        if pd.notna(pf):
                            female_d[a] = float(pf)
                except (ValueError, TypeError):
                    pass
        return name, male_d, female_d

    # Block 1 (rows 0-123): 6 plan groups, 4 cols each
    for g in range(6):
        sc = g * 4
        if sc + 3 < fi.shape[1]:
            name, m, f = extract_first_block(fi, sc, data_start_row=2)
            if name:
                result["plans_with_gender"][name] = {"Male": m, "Female": f}

    # Block 2 (rows 124-247): 3 plan groups
    if len(fi) > 126:
        for g in range(3):
            sc = g * 4
            if sc + 3 < fi.shape[1]:
                name, m, f = extract_first_block(fi, sc, data_start_row=126)
                if name:
                    result["plans_with_gender"][name] = {"Male": m, "Female": f}

    return result


# ─────────────────────────────────────────────────────────────────────────────
# PREMIUM LOOKUP
# ─────────────────────────────────────────────────────────────────────────────

def lookup_base_premium(plan_name: str, age: int, gender: str, data: dict) -> float | None:
    """Return the BASE (age-0 in calculation) annual premium in HKD."""
    # Gender-sensitive plans (First sheet)
    if plan_name in data["plans_with_gender"]:
        g_data = data["plans_with_gender"][plan_name].get(gender, {})
        return g_data.get(age)
    # Gender-neutral plans
    if plan_name in data["plans"]:
        return data["plans"][plan_name].get(age)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# CALCULATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

EXCHANGE_RATE = 7.8264
BASE_COUPON_USD = 3650.0
COUPON_FIXED_YEARS = 15   # coupon stays flat for first 15 policy years
LV_PAYMENT_YEARS = 5      # LV plan paid over 5 years
COUPON_START_YEAR = 2     # coupon starts from 2nd policy anniversary


def build_projection(
    plan_name: str,
    gender: str,
    current_age: int,
    inflation_rate: float,
    data: dict,
) -> pd.DataFrame | None:
    """
    Build year-by-year projection from current_age to age 100.

    Columns:
      Year, Age, VHIS_Premium_HKD, VHIS_Premium_USD,
      Coupon_USD, Coupon_HKD,
      LV_Annual_Payment_HKD,
      Net_Outflow_USD, Net_Outflow_HKD,
      Cumulative_Premium_HKD, Cumulative_Coupon_HKD, Cumulative_Net_HKD
    """
    rows = []
    cum_prem = 0.0
    cum_coupon = 0.0
    cum_net = 0.0

    for year_idx, age in enumerate(range(current_age, 101)):
        # ── VHIS premium ──────────────────────────────────────────────────────
        base = lookup_base_premium(plan_name, age, gender, data)
        if base is None:
            # Extrapolate: use last known premium
            if rows:
                base = rows[-1]["VHIS_Base_HKD"]
            else:
                return None

        # Inflated premium = base_at_age * (1 + r)^year_idx
        # Note: the Excel tables show age-based rates already reflecting
        # the actuarial age risk table.  Inflation is applied on TOP.
        vhis_hkd = base * ((1 + inflation_rate) ** year_idx)
        vhis_usd = vhis_hkd / EXCHANGE_RATE

        # ── LV coupon ─────────────────────────────────────────────────────────
        policy_year = year_idx + 1   # 1-based policy year
        if policy_year < COUPON_START_YEAR:
            coupon_usd = 0.0
        elif policy_year <= COUPON_FIXED_YEARS:
            coupon_usd = BASE_COUPON_USD
        else:
            # After year 15: coupon grows at the selected inflation rate
            extra_years = policy_year - COUPON_FIXED_YEARS
            coupon_usd = BASE_COUPON_USD * ((1 + inflation_rate) ** extra_years)

        coupon_hkd = coupon_usd * EXCHANGE_RATE

        # ── LV savings plan annual payment (5-year payment term) ─────────────
        # From beta: 每年保費 (annual premium) for the LV plan
        lv_annual = float(data["beta"].get("每年保費", 7692)) * EXCHANGE_RATE
        lv_payment_hkd = lv_annual if policy_year <= LV_PAYMENT_YEARS else 0.0

        # ── Net outflow ───────────────────────────────────────────────────────
        net_usd = vhis_usd - coupon_usd
        net_hkd = vhis_hkd - coupon_hkd

        cum_prem   += vhis_hkd
        cum_coupon += coupon_hkd
        cum_net    += net_hkd

        rows.append({
            "Year":                  policy_year,
            "Age":                   age,
            "VHIS_Base_HKD":         base,
            "VHIS_Premium_HKD":      round(vhis_hkd, 2),
            "VHIS_Premium_USD":      round(vhis_usd, 2),
            "Coupon_USD":            round(coupon_usd, 2),
            "Coupon_HKD":            round(coupon_hkd, 2),
            "LV_Payment_HKD":        round(lv_payment_hkd, 2),
            "Net_Outflow_USD":       round(net_usd, 2),
            "Net_Outflow_HKD":       round(net_hkd, 2),
            "Cum_Premium_HKD":       round(cum_prem, 2),
            "Cum_Coupon_HKD":        round(cum_coupon, 2),
            "Cum_Net_HKD":           round(cum_net, 2),
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.markdown("---")

    uploaded = st.file_uploader(
        "📂 Upload Excel Data File",
        type=["xlsx"],
        help="Upload the VHIS + LV15 rate Excel file to refresh all data.",
    )

    # Use uploaded file or bundled default
    DEFAULT_PATH = "/mnt/user-data/uploads/Walter-LV15起offsetVHIS.xlsx"
    file_bytes = None
    if uploaded:
        file_bytes = uploaded.read()
        st.success("✅ Custom file loaded")
    else:
        try:
            with open(DEFAULT_PATH, "rb") as f:
                file_bytes = f.read()
            st.info("📋 Using default data file")
        except FileNotFoundError:
            st.warning("⚠️ No data file found. Please upload one above.")

    st.markdown("---")

    if file_bytes:
        with st.spinner("Loading rate tables…"):
            data = load_workbook_data(file_bytes)

        # Build full plan list
        all_plans = sorted(
            list(data["plans"].keys()) + list(data["plans_with_gender"].keys())
        )

        # Defaults from beta sheet
        default_plan   = str(data["beta"].get("計劃", all_plans[0] if all_plans else "")).strip()
        default_age    = int(data["beta"].get("年齡", 40))
        default_gender = str(data["beta"].get("性別", "Female")).strip()

        if default_plan not in all_plans and all_plans:
            default_plan = all_plans[0]

        st.markdown("### 🏥 VHIS Plan")
        plan = st.selectbox("Plan Name", all_plans,
                            index=all_plans.index(default_plan) if default_plan in all_plans else 0)

        st.markdown("### 👤 Insured Person")
        gender = st.radio("Gender", ["Male", "Female"],
                          index=0 if default_gender == "Male" else 1,
                          horizontal=True)

        age = st.slider("Current Age", min_value=0, max_value=85,
                        value=min(max(default_age, 0), 85), step=1)

        st.markdown("### 📈 Assumptions")
        inflation_label = st.radio(
            "Medical Inflation Rate",
            ["5% per annum", "7% per annum"],
            index=1,
            horizontal=False,
        )
        inflation_rate = 0.07 if "7%" in inflation_label else 0.05

        st.markdown("---")
        st.markdown("### 📌 LV Plan Parameters")
        exch = float(data["beta"].get("匯率", EXCHANGE_RATE))
        coupon_usd_input = float(data["beta"].get("提取金額", BASE_COUPON_USD))
        st.metric("Exchange Rate", f"HKD {exch:.4f} / USD")
        st.metric("Annual Coupon", f"US${coupon_usd_input:,.0f}")
        st.metric("Coupon Start", f"Year {COUPON_START_YEAR}")
        st.metric("LV Payment Term", f"{LV_PAYMENT_YEARS} Years")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PANEL – landing state when no data
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="app-header">
  <h1>🏥 VHIS + LV15 Premium Offset Calculator</h1>
  <p>Visualise how your Savings Plan (LV) coupons offset rising VHIS medical premiums over time.</p>
</div>
""", unsafe_allow_html=True)

if not file_bytes:
    st.markdown("""
    <div style="text-align:center; padding: 4rem 2rem;">
        <div style="font-size:5rem;">📂</div>
        <h2>Please Upload Your Data File</h2>
        <p style="color:#6b7280; max-width:500px; margin:auto;">
        Upload the <b>VHIS + LV15 Excel rate file</b> using the sidebar to begin.
        The app will automatically parse all plan rate tables and calculate
        your personalised projection.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# COMPUTE PROJECTION
# ─────────────────────────────────────────────────────────────────────────────

df = build_projection(plan, gender, age, inflation_rate, data)

if df is None or df.empty:
    st.error(f"⚠️ No premium data found for **{plan}** / {gender} at age {age}. "
             "Please choose a different plan or age.")
    st.stop()

# Key derived metrics
base_premium     = df.iloc[0]["VHIS_Base_HKD"]
total_premiums   = df["VHIS_Premium_HKD"].sum()
total_coupons    = df["Coupon_HKD"].sum()
total_lv_paid    = df["LV_Payment_HKD"].sum()
total_net        = df["Net_Outflow_HKD"].sum()
final_age_prem   = df.iloc[-1]["VHIS_Premium_HKD"]
final_age_coupon = df.iloc[-1]["Coupon_HKD"]

# Find crossover: first year where annual premium > coupon AND coupon > 0
crossover_row = df[(df["Coupon_HKD"] > 0) & (df["VHIS_Premium_HKD"] > df["Coupon_HKD"])].head(1)
crossover_age = int(crossover_row["Age"].iloc[0]) if not crossover_row.empty else None

# Find where cumulative coupon >= cumulative premium (break-even in cumulative terms)
breakeven_row = df[df["Cum_Coupon_HKD"] >= df["Cum_Premium_HKD"]].head(1)
breakeven_age = int(breakeven_row["Age"].iloc[0]) if not breakeven_row.empty else None

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────

tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📈 Interactive Chart", "📋 Data Table"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 – DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    col_l, col_r = st.columns([3, 2])

    with col_l:
        st.markdown("### 💰 Lifetime Financial Summary (Age {} → 100)".format(age))

        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f"""
            <div class="metric-card">
              <div class="metric-label">Total VHIS Premiums</div>
              <div class="metric-value">HK${total_premiums/1e6:.2f}M</div>
              <div class="metric-sub">Age {age} → 100 cumulative</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
            <div class="metric-card" style="border-left-color:#10b981;">
              <div class="metric-label">Total LV Coupons Received</div>
              <div class="metric-value" style="color:#10b981;">HK${total_coupons/1e6:.2f}M</div>
              <div class="metric-sub">US${total_coupons/exch:,.0f} at {exch}</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""
            <div class="metric-card" style="border-left-color:#e8a020;">
              <div class="metric-label">Net Out-of-Pocket</div>
              <div class="metric-value" style="color:#e8a020;">HK${total_net/1e6:.2f}M</div>
              <div class="metric-sub">After coupon offset</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Current Age", f"{age}")
        with c2:
            st.metric("Base Premium (Age {})".format(age), f"HK${base_premium:,.0f}")
        with c3:
            st.metric("Premium at Age 100", f"HK${final_age_prem:,.0f}")
        with c4:
            st.metric("Coupon at Age 100", f"HK${final_age_coupon:,.0f}")

        # Offset ratio
        offset_pct = (total_coupons / total_premiums * 100) if total_premiums > 0 else 0
        st.markdown(f"""
        <div class="insight-box">
        📌 <b>Coupon Coverage:</b> Over the projection period, LV coupons cover
        <b>{offset_pct:.1f}%</b> of total VHIS premiums — saving you
        <b>HK${total_coupons:,.0f}</b> out of HK${total_premiums:,.0f} in premiums.<br><br>
        💡 The LV plan only requires a <b>{LV_PAYMENT_YEARS}-year payment</b>
        (HK${total_lv_paid:,.0f} total), yet generates coupons through age 100.
        </div>
        """, unsafe_allow_html=True)

    with col_r:
        st.markdown("### 🎯 Key Milestones")

        # Annual premium vs coupon donut
        fig_donut = go.Figure(go.Pie(
            labels=["Net Out-of-Pocket", "LV Coupon Offset"],
            values=[max(total_net, 0), total_coupons],
            hole=0.6,
            marker_colors=["#1a4f8a", "#10b981"],
            textinfo="label+percent",
            hovertemplate="%{label}: HK$%{value:,.0f}<extra></extra>",
        ))
        fig_donut.update_layout(
            title=dict(text="Lifetime Premium Breakdown", font=dict(size=14)),
            showlegend=False,
            margin=dict(t=40, b=10, l=10, r=10),
            height=230,
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_donut, use_container_width=True)

        # Milestones
        if crossover_age:
            st.markdown(f"""
            <div class="metric-card" style="border-left-color:#ef4444;">
              <div class="metric-label">⚠️ Annual Premium Exceeds Coupon</div>
              <div class="metric-value" style="color:#ef4444;">Age {crossover_age}</div>
              <div class="metric-sub">From this age, VHIS cost > LV coupon each year</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="metric-card" style="border-left-color:#10b981;">
              <div class="metric-label">✅ Coupon Always Covers Premium</div>
              <div class="metric-value" style="color:#10b981;">Never crossed</div>
              <div class="metric-sub">LV coupon exceeds VHIS premium throughout</div>
            </div>""", unsafe_allow_html=True)

        inflation_pct = int(inflation_rate * 100)
        st.markdown(f"""
        <div class="metric-card" style="border-left-color:#6366f1;">
          <div class="metric-label">📈 Inflation Assumption</div>
          <div class="metric-value" style="color:#6366f1;">{inflation_pct}% p.a.</div>
          <div class="metric-sub">Applied to both premium growth & coupon escalation</div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 – INTERACTIVE CHART
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    view_toggle = st.radio(
        "View Mode",
        ["Annual Cash Flows", "Cumulative Totals"],
        horizontal=True,
    )

    if view_toggle == "Annual Cash Flows":
        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=df["Age"], y=df["VHIS_Premium_HKD"],
            name="VHIS Annual Premium",
            marker_color="#1a4f8a",
            opacity=0.85,
            hovertemplate="Age %{x}<br>Premium: HK$%{y:,.0f}<extra></extra>",
        ))

        fig.add_trace(go.Bar(
            x=df["Age"], y=df["Coupon_HKD"],
            name="LV Annual Coupon",
            marker_color="#10b981",
            opacity=0.85,
            hovertemplate="Age %{x}<br>Coupon: HK$%{y:,.0f}<extra></extra>",
        ))

        fig.add_trace(go.Scatter(
            x=df["Age"], y=df["Net_Outflow_HKD"],
            name="Net Annual Outflow",
            mode="lines+markers",
            line=dict(color="#e8a020", width=2.5),
            marker=dict(size=4),
            hovertemplate="Age %{x}<br>Net: HK$%{y:,.0f}<extra></extra>",
        ))

        # Coupon start line
        fig.add_vline(
            x=age + COUPON_START_YEAR - 1, line_dash="dot",
            line_color="#10b981", annotation_text="Coupon Starts",
            annotation_position="top right",
        )

        # Crossover line
        if crossover_age:
            fig.add_vline(
                x=crossover_age, line_dash="dash",
                line_color="#ef4444", annotation_text=f"Premium > Coupon (Age {crossover_age})",
                annotation_position="top left",
            )

        fig.update_layout(
            barmode="group",
            title=f"Annual VHIS Premium vs LV Coupon — {plan} ({gender}, {int(inflation_rate*100)}% inflation)",
            xaxis_title="Age",
            yaxis_title="HKD (HK$)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
            height=520,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(248,250,252,1)",
            xaxis=dict(gridcolor="#e5e7eb"),
            yaxis=dict(gridcolor="#e5e7eb", tickformat=",.0f"),
        )
        st.plotly_chart(fig, use_container_width=True)

    else:  # Cumulative
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=df["Age"], y=df["Cum_Premium_HKD"],
            name="Cumulative Premiums Paid",
            fill="tozeroy",
            line=dict(color="#1a4f8a", width=2.5),
            fillcolor="rgba(26,79,138,0.15)",
            hovertemplate="Age %{x}<br>Cum. Premium: HK$%{y:,.0f}<extra></extra>",
        ))

        fig.add_trace(go.Scatter(
            x=df["Age"], y=df["Cum_Coupon_HKD"],
            name="Cumulative Coupons Received",
            fill="tozeroy",
            line=dict(color="#10b981", width=2.5),
            fillcolor="rgba(16,185,129,0.15)",
            hovertemplate="Age %{x}<br>Cum. Coupon: HK$%{y:,.0f}<extra></extra>",
        ))

        fig.add_trace(go.Scatter(
            x=df["Age"], y=df["Cum_Net_HKD"],
            name="Cumulative Net Outflow",
            line=dict(color="#e8a020", width=2, dash="dash"),
            hovertemplate="Age %{x}<br>Cum. Net: HK$%{y:,.0f}<extra></extra>",
        ))

        if breakeven_age:
            fig.add_vline(
                x=breakeven_age, line_dash="dot",
                line_color="#8b5cf6",
                annotation_text=f"Break-Even Age {breakeven_age}",
                annotation_position="top right",
            )

        fig.update_layout(
            title=f"Cumulative Cash Flows — {plan} ({gender}, {int(inflation_rate*100)}% inflation)",
            xaxis_title="Age",
            yaxis_title="Cumulative HKD (HK$)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
            height=520,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(248,250,252,1)",
            xaxis=dict(gridcolor="#e5e7eb"),
            yaxis=dict(gridcolor="#e5e7eb", tickformat=",.0f"),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Annotation below chart
    st.markdown(f"""
    <div class="insight-box">
    📊 <b>How to read this chart:</b>
    The <b style="color:#1a4f8a;">blue bars/area</b> show VHIS annual premiums rising with age and inflation ({int(inflation_rate*100)}% p.a.).
    The <b style="color:#10b981;">green bars/area</b> show LV coupons — flat at US$3,650 for the first 15 years,
    then growing at {int(inflation_rate*100)}% p.a. thereafter.
    The <b style="color:#e8a020;">orange line</b> is the net out-of-pocket after coupon offset.
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 – DATA TABLE
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown(f"### 📋 Year-by-Year Projection: **{plan}** | {gender} | Age {age}→100 | {int(inflation_rate*100)}% Inflation")

    # Prepare display dataframe
    display_df = df[[
        "Year", "Age",
        "VHIS_Premium_HKD", "VHIS_Premium_USD",
        "Coupon_USD", "Coupon_HKD",
        "LV_Payment_HKD",
        "Net_Outflow_HKD",
        "Cum_Premium_HKD", "Cum_Coupon_HKD", "Cum_Net_HKD",
    ]].copy()

    display_df.columns = [
        "Year", "Age",
        "VHIS Premium (HKD)", "VHIS Premium (USD)",
        "LV Coupon (USD)", "LV Coupon (HKD)",
        "LV Policy Payment (HKD)",
        "Net Outflow (HKD)",
        "Cum. Premiums (HKD)", "Cum. Coupons (HKD)", "Cum. Net (HKD)",
    ]

    # Colour rows where premium > coupon
    def highlight_crossover(row):
        if row["LV Coupon (HKD)"] > 0 and row["VHIS Premium (HKD)"] > row["LV Coupon (HKD)"]:
            return ["background-color: #fff3cd"] * len(row)
        elif row["LV Coupon (HKD)"] >= row["VHIS Premium (HKD)"] and row["LV Coupon (HKD)"] > 0:
            return ["background-color: #d1fae5"] * len(row)
        return [""] * len(row)

    hkd_cols = [c for c in display_df.columns if "HKD" in c or "USD" in c]
    fmt = {c: "HK${:,.0f}" if "HKD" in c else "US${:,.0f}" for c in hkd_cols}

    styled = (
        display_df.style
        .apply(highlight_crossover, axis=1)
        .format(fmt)
        .format({"Year": "{:d}", "Age": "{:d}"})
    )

    st.dataframe(styled, use_container_width=True, height=520)

    st.markdown("""
    🟢 Green rows: LV coupon ≥ VHIS premium (coupon covers cost)
    🟡 Yellow rows: VHIS premium > LV coupon (net positive outflow)
    """)

    # Download button
    csv_buf = io.StringIO()
    display_df.to_csv(csv_buf, index=False)
    st.download_button(
        label="⬇️ Download as CSV",
        data=csv_buf.getvalue(),
        file_name=f"VHIS_LV15_Projection_{plan}_{gender}_Age{age}.csv",
        mime="text/csv",
    )

# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:#9ca3af; font-size:.78rem;'>"
    "VHIS + LV15 Offset Calculator · For illustrative purposes only · "
    "Not financial advice · Exchange rate: HKD/USD 7.8264"
    "</div>",
    unsafe_allow_html=True,
)
