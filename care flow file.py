from __future__ import annotations

import itertools
import json
import time as _time
import re
import traceback
from dataclasses import dataclass
from functools import wraps
from html import escape
from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

import careflow_pm as pm
import careflow_core as core



# ---------- BRAND ASSETS (logo) ----------
_MARK_BODY = (
    '<defs><linearGradient id="cfg" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#14B8A6"/><stop offset="1" stop-color="#0B5F63"/></linearGradient></defs>'
    '<rect width="64" height="64" rx="18" fill="url(#cfg)"/>'
    '<path d="M10 35h10l5-14 8 26 6-18h15" fill="none" stroke="#fff" stroke-width="4.5" '
    'stroke-linecap="round" stroke-linejoin="round"/>'
    '<circle cx="54" cy="29" r="4.5" fill="#FF6B4A" stroke="#fff" stroke-width="2"/>'
)
LOGO_MARK_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">' + _MARK_BODY + '</svg>'
LOGO_WORDMARK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 190 44">'
    '<svg x="0" y="0" width="44" height="44" viewBox="0 0 64 64">' + _MARK_BODY + '</svg>'
    '<text x="56" y="31" font-family="Inter,Segoe UI,Helvetica,Arial,sans-serif" font-size="26" '
    'font-weight="700" letter-spacing="-0.6" fill="#FFFFFF">Care<tspan fill="#5EEAD4">Flow</tspan></text></svg>'
)
_ASSET_DIR = Path(__file__).parent / "assets"
_MARK_FILE = _ASSET_DIR / "careflow_mark.svg"
_WORDMARK_FILE = _ASSET_DIR / "careflow_wordmark.svg"


def _dark_wordmark(accent):  # dark-text wordmark for the light themes
    return LOGO_WORDMARK_SVG.replace('fill="#FFFFFF">Care<tspan fill="#5EEAD4">', f'fill="#14141F">Care<tspan fill="{accent}">')


LOGO_WORDMARK_AURORA_SVG = _dark_wordmark("#0D9488")
_WORDMARK_AURORA_FILE = _ASSET_DIR / "careflow_wordmark_aurora.svg"
try:  # (re)create the logo files so the app is self-contained
    _ASSET_DIR.mkdir(exist_ok=True)
    for _p, _svg in ((_MARK_FILE, LOGO_MARK_SVG), (_WORDMARK_FILE, LOGO_WORDMARK_SVG),
                     (_WORDMARK_AURORA_FILE, LOGO_WORDMARK_AURORA_SVG)):
        if not _p.exists() or _p.read_text(encoding="utf-8") != _svg:
            _p.write_text(_svg, encoding="utf-8")
except Exception:  # noqa: BLE001 - read-only file system: fall back to emoji icon
    pass

try:
    st.set_page_config(page_title="CareFlow | Clinical Pathway Process Mining",
                       page_icon=str(_MARK_FILE) if _MARK_FILE.exists() else "♥", layout="wide")
except Exception:  # noqa: BLE001
    st.set_page_config(page_title="CareFlow | Clinical Pathway Process Mining", page_icon="♥", layout="wide")


# ---------- CAREFLOW AUTHENTICATION ----------
from supabase import create_client

def get_supabase_client():
    """One client per browser session: a shared (cached) client would mix up different users' sign-ins."""
    if "cf_sb_client" not in st.session_state:
        st.session_state["cf_sb_client"] = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    return st.session_state["cf_sb_client"]

try:
    supabase = get_supabase_client()
except Exception:
    st.error(
        "Authentication setup error. Check SUPABASE_URL "
        "and SUPABASE_KEY in Streamlit Cloud Secrets."
    )
    st.stop()

if "careflow_user" not in st.session_state:
    st.session_state.careflow_user = None

if not st.session_state.careflow_user:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        html, body, p, label, h1, h2, h3, button, input, .stMarkdown { font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif; }
        [data-testid="stAppViewContainer"] {
            background: radial-gradient(900px 480px at 6% -6%,#D3EEEA 0%,transparent 60%),
                        radial-gradient(800px 440px at 100% 100%,#EDE9FE 0%,transparent 55%), #F3F7FC;
        }
        [data-testid="stHeader"] { background: transparent; }
        footer { visibility:hidden; }
        .block-container { padding-top: 2.6rem !important; max-width: 1400px !important; }
        .cf-brand { display:flex; align-items:center; gap:14px; margin:2px 0 22px 2px; }
        .cf-brand svg { width:56px; height:56px; filter:drop-shadow(0 8px 16px rgba(15,118,110,.28)); }
        .cf-brand-title { font-size:clamp(28px,3.6vw,38px); font-weight:800; letter-spacing:-1.2px; line-height:1.05; color:#153451; }
        .cf-brand-title span { color:#0D9488; }
        .cf-brand-sub { font-size:14px; color:#5E6B78; margin-top:4px; }
        .cf-topline { text-align:right; color:#5E6B78; font-size:13px; padding:16px 6px 22px; }
        [data-testid="stVerticalBlockBorderWrapper"] { background:#fff; border:1px solid #DCE3E9 !important;
            border-radius:20px !important; padding:clamp(6px,1.2vw,16px); box-shadow:0 18px 44px rgba(11,37,48,.08); }
        [data-testid="stForm"] { border:0 !important; padding:0 !important; }
        .cf-login-title { font-size:clamp(26px,3.2vw,32px); font-weight:800; color:#153451; letter-spacing:-.8px; }
        .cf-login-sub { color:#5E6B78; margin:4px 0 14px; font-size:15px; }
        .cf-trust { text-align:center; color:#5E6B78; font-size:12px; padding:10px 4px 2px; }
        .cf-hero { min-height:250px; border-radius:24px; padding:clamp(20px,3vw,38px); overflow:hidden;
                   background:radial-gradient(circle at 88% 18%,rgba(124,111,224,.35),transparent 42%),radial-gradient(circle at 78% 92%,rgba(229,139,168,.35),transparent 40%),linear-gradient(135deg,#F1F0FC,#E4E0FA);
                   border:1px solid rgba(255,255,255,.8); box-shadow:0 14px 34px rgba(11,37,48,.08); }
        .cf-kicker { color:#0D9488; text-transform:uppercase; letter-spacing:2px; font-size:11px; font-weight:800; }
        .cf-hero-title { max-width:480px; color:#153451; font-size:clamp(30px,4vw,44px); line-height:1.12; font-weight:800;
                         letter-spacing:-1.2px; margin:12px 0; }
        .cf-hero-title span { color:#0D9488; }
        .cf-hero-copy { max-width:400px; color:#44525F; font-size:15px; line-height:1.65; }
        .cf-feature-row { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:18px 0; }
        .cf-feature { background:#fff; border:1px solid #DCE3E9; border-radius:16px; padding:14px 8px; text-align:center;
                      color:#14202B; font-size:12.5px; font-weight:600; line-height:1.35; }
        .cf-feature-icon { width:44px; height:44px; margin:0 auto 8px; border-radius:12px; background:#E3F4F1;
                           display:flex; align-items:center; justify-content:center; font-size:21px; }
        .cf-photo-caption { font-size:12px; color:#44525F; font-weight:600; padding-top:4px; }
        [data-testid="stImage"] img { border-radius:14px; object-fit:cover; }
        div[data-testid="stFormSubmitButton"] button { background:linear-gradient(100deg,#0D9488,#0B5F63) !important;
          color:white !important; border:0 !important; border-radius:12px !important; min-height:48px; font-weight:700 !important; }
        div[data-testid="stFormSubmitButton"] button:hover { filter:brightness(1.08); }
        div[data-testid="stTextInput"] input { border-radius:10px !important; }
        [data-baseweb="tab-list"] { background:#E8EEF1 !important; border-radius:12px !important; padding:4px; gap:4px; }
        [data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display:none !important; }
        button[data-baseweb="tab"] { color:#5E6B78 !important; border-radius:9px !important; font-weight:600; }
        button[data-baseweb="tab"][aria-selected="true"] { color:#0D9488 !important; background:#fff !important;
                                                           box-shadow:0 1px 4px rgba(11,37,48,.12); }
        @media (max-width: 700px) {
          .cf-topline { text-align:left; padding:0 4px 12px; }
          .cf-feature-row { grid-template-columns:repeat(2,minmax(0,1fr)); }
          .cf-hero { min-height:220px; }
        }
        </style>
        """ + f"""
        <div class="cf-brand">
          {LOGO_MARK_SVG}
          <div><div class="cf-brand-title">Care<span>Flow</span></div>
          <div class="cf-brand-sub">Clinical Pathway Process Mining</div></div>
        </div>
        <div class="cf-topline">Better Insights &nbsp; · &nbsp; Smoother Pathways &nbsp; · &nbsp; Healthier Tomorrows</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """<style>
        @keyframes cf-l-rise { from { opacity:0; transform:translateY(18px); } }
        @keyframes cf-l-blur { from { opacity:0; filter:blur(12px); transform:translateY(8px); } }
        [data-testid="stAppViewContainer"] { background:radial-gradient(900px 480px at 6% -6%,#C9C3F4 0%,transparent 60%),
          radial-gradient(800px 440px at 100% 100%,#F7DBE6 0%,transparent 55%),#F1F0FC !important; }
        .cf-brand-title span, .cf-hero-title span, .cf-kicker { color:#7C6FE0 !important; }
        .cf-brand-title, .cf-login-title, .cf-hero-title { color:#14141F !important; }
        .cf-feature-icon { background:#EDE9FE !important; }
        [data-testid="stVerticalBlockBorderWrapper"] { border-color:#C9C3F4 !important; box-shadow:0 18px 44px rgba(90,80,160,.12) !important; }
        div[data-testid="stFormSubmitButton"] button { background:#16161D !important; border-radius:999px !important; }
        button[data-baseweb="tab"][aria-selected="true"] { color:#7C6FE0 !important; }
        .cf-hero { background:radial-gradient(circle at 88% 18%,rgba(124,111,224,.35),transparent 42%),radial-gradient(circle at 78% 92%,rgba(229,139,168,.35),transparent 40%),linear-gradient(135deg,#F1F0FC,#E4E0FA) !important; }
        .cf-brand { animation:cf-l-blur .8s cubic-bezier(.2,.8,.2,1) backwards; }
        .cf-topline { animation:cf-l-rise .7s ease .15s backwards; }
        [data-testid="stVerticalBlockBorderWrapper"] { animation:cf-l-rise .7s cubic-bezier(.2,.8,.2,1) .15s backwards; }
        .cf-hero { animation:cf-l-rise .8s cubic-bezier(.2,.8,.2,1) .3s backwards; }
        .cf-feature { animation:cf-l-rise .6s cubic-bezier(.2,.8,.2,1) backwards; transition:transform .25s; }
        .cf-feature:nth-child(1) { animation-delay:.45s; } .cf-feature:nth-child(2) { animation-delay:.55s; }
        .cf-feature:nth-child(3) { animation-delay:.65s; } .cf-feature:nth-child(4) { animation-delay:.75s; }
        .cf-feature:hover { transform:translateY(-4px); }
        @media (prefers-reduced-motion: reduce) { * { animation:none !important; transition:none !important; } }
        </style>""",
        unsafe_allow_html=True,
    )

    if st.session_state.pop("cf_timeout_notice", None):
        st.info("You were signed out after a period of inactivity. Please sign in again.")

    login_col, hero_col = st.columns([0.88, 1.42], gap="large", vertical_alignment="top")

    with login_col:
        with st.container(border=True):
            st.markdown(
                '<div class="cf-login-title">Welcome back</div>'
                '<div class="cf-login-sub">Sign in to open your clinical analytics workspace.</div>',
                unsafe_allow_html=True,
            )
            login_tab, signup_tab = st.tabs(["Sign in", "Create account"])

            with login_tab:
                with st.form("careflow_login_form"):
                    login_email = st.text_input("Email address", placeholder="you@hospital.org")
                    login_password = st.text_input("Password", type="password", placeholder="Enter your password")
                    login_submit = st.form_submit_button("Sign in  →", use_container_width=True)
                if login_submit:
                    try:
                        result = supabase.auth.sign_in_with_password({
                            "email": login_email.strip(), "password": login_password
                        })
                        if result.session and result.user:
                            st.session_state.careflow_user = {"id": result.user.id, "email": result.user.email}
                            st.rerun()
                        else:
                            st.error("Login unsuccessful. Please try again.")
                    except Exception:
                        st.error("Login failed. Check your email and password or verify your email address.")

            with signup_tab:
                with st.form("careflow_signup_form"):
                    signup_email = st.text_input("Email address", placeholder="you@hospital.org", key="signup_email")
                    signup_password = st.text_input("Create password", type="password", key="signup_password",
                                                    placeholder="At least 8 characters")
                    confirm_password = st.text_input("Confirm password", type="password", key="confirm_password",
                                                     placeholder="Re-enter your password")
                    signup_submit = st.form_submit_button("Create account", use_container_width=True)
                if signup_submit:
                    if not signup_email.strip():
                        st.error("Enter your email address.")
                    elif len(signup_password) < 8:
                        st.error("Use a password of at least 8 characters.")
                    elif signup_password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            result = supabase.auth.sign_up({"email": signup_email.strip(), "password": signup_password})
                            if result.session and result.user:
                                st.session_state.careflow_user = {"id": result.user.id, "email": result.user.email}
                                st.success("Account created successfully.")
                                st.rerun()
                            else:
                                st.success("Registration received. Check your email to verify your account, then sign in.")
                        except Exception:
                            st.error("Signup failed. Check your email, password requirements, and Supabase authentication settings.")

            st.markdown(
                '<div class="cf-trust">🔒 Secure access &nbsp; · &nbsp; Your account and data are protected</div>',
                unsafe_allow_html=True,
            )

    with hero_col:
        st.markdown(
            '<div class="cf-hero"><div class="cf-kicker">Clinical intelligence for better care</div>'
            '<div class="cf-hero-title">Transforming Patient Flow with <span>Data-Driven Insights</span></div>'
            '<div class="cf-hero-copy">CareFlow helps healthcare teams analyze clinical pathways, improve coordination, '
            'and support better operational decisions.</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="cf-feature-row">'
            '<div class="cf-feature"><div class="cf-feature-icon">📊</div>Clinical<br>Analytics</div>'
            '<div class="cf-feature"><div class="cf-feature-icon">🧭</div>Pathway<br>Analysis</div>'
            '<div class="cf-feature"><div class="cf-feature-icon">📑</div>Reports &amp;<br>Insights</div>'
            '<div class="cf-feature"><div class="cf-feature-icon">🛡️</div>Governance<br>&amp; Security</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="cf-feature-row" style="grid-template-columns:repeat(3,minmax(0,1fr))">'
            '<div class="cf-feature"><div class="cf-feature-icon">🩺</div>Clinical care</div>'
            '<div class="cf-feature"><div class="cf-feature-icon">🛏️</div>Patient flow</div>'
            '<div class="cf-feature"><div class="cf-feature-icon">👩‍⚕️</div>Care teams</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="text-align:right;color:#0D9488;font-style:italic;font-weight:700;'
            'font-size:18px;padding:12px 8px;">Smarter care starts with better data.</div>',
            unsafe_allow_html=True,
        )

    st.stop()

# ---------- END CAREFLOW AUTHENTICATION ----------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {
  --cf-bg:#F3F7FC; --cf-card:#FFFFFF; --cf-primary:#0D9488; --cf-primary-dark:#0B7A70; --cf-navy:#153451;
  --cf-accent:#D97706; --cf-blue:#2563EB; --cf-lavender:#EDE9FE; --cf-red:#DC2626; --cf-ink:#14202B; --cf-muted:#5E6B78; --cf-border:#DCE3E9;
  /* legacy aliases (older rules / pages keep working) */
  --cf-ivory:#E6EEF1; --cf-ivory-card:#FFFFFF; --cf-emerald:#0D9488; --cf-emerald-dark:#153451; --cf-vermillion:#D97706;
  --cf-ink-soft:#44525F;
}
html, body, .stApp, .stMarkdown, p, label, h1, h2, h3, h4, button, input, textarea {
  font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif; }
.block-container { width:100%; max-width:1640px; padding-top:3.6rem; padding-bottom:2.5rem;
  padding-left:clamp(.75rem,2.2vw,2.2rem); padding-right:clamp(.75rem,2.2vw,2.2rem); }
[data-testid="stAppViewContainer"] { background:var(--cf-bg) !important; color:var(--cf-ink) !important; }
[data-testid="stHeader"] { background:rgba(243,247,252,.85) !important; backdrop-filter:blur(8px); }
footer { visibility:hidden; }

/* ---------- sidebar: deep navy, teal highlight for the selected page ---------- */
[data-testid="stSidebar"], [data-testid="stSidebar"] > div,
[data-testid="stSidebar"] [data-testid="stSidebarContent"], [data-testid="stSidebar"] [data-testid="stSidebarUserContent"],
[data-testid="stSidebar"] [data-testid="stVerticalBlock"], [data-testid="stSidebar"] [data-testid="stElementContainer"],
[data-testid="stSidebar"] [data-testid="stBottom"], [data-testid="stSidebar"] [data-testid="stExpander"] { background:#153451 !important; }
[data-testid="stSidebar"] { border-right:1px solid rgba(255,255,255,.08) !important; }
[data-testid="stSidebar"] * { color:#E8EEF4 !important; }
[data-testid="stSidebarHeader"] { padding:1.1rem 1rem .5rem; }
[data-testid="stLogo"] { height:2.3rem; }
[data-testid="stSidebar"] hr { border-color:rgba(255,255,255,.16) !important; }
[data-testid="stSidebarNav"] a, [data-testid="stSidebarNavLink"] { background:transparent !important; border-radius:10px !important;
  margin:2px 0 !important; transition:background .15s; }
[data-testid="stSidebarNavLink"]:hover, [data-testid="stSidebarNav"] a:hover { background:rgba(255,255,255,.08) !important; }
[data-testid="stSidebarNav"] a[aria-current="page"], [data-testid="stSidebarNavLink"][aria-current="page"] {
  background:var(--cf-primary) !important; box-shadow:0 4px 12px rgba(13,148,136,.35); font-weight:600; }
[data-testid="stSidebar"] [aria-current="page"], [data-testid="stSidebar"] [aria-current="page"] * { color:#fff !important; }
[data-testid="stSidebarNavSeparator"], [data-testid="stSidebarNav"] span[class*="Header"] {
  opacity:.65; text-transform:uppercase; letter-spacing:.08em; font-size:.68rem; }
[data-testid="stSidebar"] .stButton button { background:rgba(255,255,255,.07) !important; border:1px solid rgba(255,255,255,.28) !important; border-radius:10px !important; }
[data-testid="stSidebar"] .stButton button:hover { background:rgba(13,148,136,.35) !important; border-color:#2DD4BF !important; box-shadow:none; }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) { background:rgba(13,148,136,.35) !important; border-radius:10px; }
[data-testid="stSidebar"] [data-baseweb="select"] > div, [data-testid="stSidebar"] [data-baseweb="input"] > div { background:#F7FAFC !important; }
[data-testid="stSidebar"] [data-baseweb="select"] *, [data-testid="stSidebar"] [data-baseweb="input"] *, [data-testid="stSidebar"] input { color:#153451 !important; }
[data-testid="stSidebar"] [data-baseweb="tag"] { background:var(--cf-blue) !important; }
[data-testid="stSidebar"] [data-baseweb="tag"] * { color:#fff !important; }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] { background:rgba(255,255,255,.07) !important; border:1px dashed rgba(255,255,255,.4) !important; }
.cf-user { display:flex; align-items:center; gap:10px; padding:10px 12px; border-radius:14px; background:rgba(255,255,255,.07);
  border:1px solid rgba(255,255,255,.14); margin-bottom:8px; }
.cf-avatar { flex:0 0 34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center;
  background:var(--cf-primary); font-weight:700; color:#fff !important; }
.cf-user-meta { min-width:0; }
.cf-user-label { font-size:.68rem; letter-spacing:.08em; text-transform:uppercase; opacity:.65; }
.cf-user-email { font-size:.82rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

/* ---------- page title bar ---------- */
.cf-titlebar { display:flex; align-items:flex-end; justify-content:space-between; gap:16px; flex-wrap:wrap;
  margin:.1rem 0 1rem; padding-bottom:.9rem; border-bottom:1px solid var(--cf-border); }
.cf-titlebar h1 { margin:0; padding:0; font-size:clamp(1.6rem,3vw,2.2rem); font-weight:800; letter-spacing:-.03em; color:var(--cf-navy) !important; }
.cf-titlebar h1 span { color:var(--cf-primary); }
.cf-titlebar p { margin:.25rem 0 0; color:var(--cf-muted); font-size:.95rem; max-width:780px; }
.cf-updated { background:#fff; border:1px solid var(--cf-border); border-radius:999px; padding:6px 14px; font-size:.8rem;
  color:var(--cf-muted); box-shadow:0 1px 2px rgba(11,37,48,.04); }
.cf-updated b { color:var(--cf-navy); }

/* ---------- typography, cards, charts ---------- */
h1, h2, h3, h4 { color:var(--cf-navy) !important; letter-spacing:-.02em; overflow-wrap:anywhere; }
p, label, [data-testid="stMarkdownContainer"] { color:var(--cf-ink); }
hr { border-color:var(--cf-border) !important; }
.metric-card, .cf-feature-card, [data-testid="stMetric"], [data-testid="stVerticalBlockBorderWrapper"] {
  border:1px solid var(--cf-border) !important; border-radius:16px !important; background:var(--cf-card) !important;
  box-shadow:0 1px 2px rgba(11,37,48,.04), 0 6px 18px rgba(11,37,48,.05) !important; }
.metric-card { padding:1.05rem 1.15rem; position:relative; overflow:hidden; transition:transform .15s, box-shadow .15s; }
.metric-card:hover { transform:translateY(-2px); box-shadow:0 10px 26px rgba(11,37,48,.10) !important; }
.metric-card:before { content:""; position:absolute; left:0; top:0; right:0; height:3px;
  background:linear-gradient(90deg,#0D9488,#2DD4BF); }
.metric-label, .cf-feature-copy, [data-testid="stMetric"] label { color:var(--cf-muted) !important; font-size:.74rem;
  font-weight:600; letter-spacing:.05em; text-transform:uppercase; }
.metric-value, [data-testid="stMetricValue"] { color:var(--cf-navy) !important; font-weight:800 !important;
  font-size:1.7rem; letter-spacing:-.02em; font-variant-numeric:tabular-nums; }
.cf-feature-title { color:var(--cf-navy) !important; font-weight:700; font-size:1.02rem; margin-bottom:7px; }
.cf-feature-card { padding:1rem 1.1rem; }
.cf-feature-copy { text-transform:none; letter-spacing:0; font-size:.88rem; line-height:1.5; font-weight:400; }
[data-testid="stPlotlyChart"] { background:var(--cf-card) !important; border:1px solid var(--cf-border) !important;
  border-radius:16px !important; padding:6px; box-shadow:0 1px 2px rgba(11,37,48,.04), 0 6px 18px rgba(11,37,48,.05); }
[data-testid="stDataFrame"], [data-testid="stTable"] { border:1px solid var(--cf-border) !important; border-radius:14px !important; overflow:hidden; }
[data-testid="stExpander"] { border:1px solid var(--cf-border) !important; border-radius:14px !important; background:var(--cf-card) !important; }
[data-testid="stCaptionContainer"] { color:var(--cf-muted) !important; }
[data-testid="stAlert"] { border-radius:13px; }

/* ---------- controls ---------- */
.stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button, button[kind="primary"] {
  background:var(--cf-primary) !important; color:#fff !important; border:1px solid var(--cf-primary) !important;
  border-radius:10px !important; font-weight:600 !important; transition:background .15s, box-shadow .15s; }
.stButton button:hover, .stDownloadButton button:hover, [data-testid="stFormSubmitButton"] button:hover {
  background:var(--cf-primary-dark) !important; border-color:var(--cf-primary-dark) !important;
  box-shadow:0 4px 12px rgba(15,118,110,.28); }
[data-baseweb="input"] > div, [data-baseweb="textarea"] > div, [data-baseweb="select"] > div {
  border-color:#CBD5DC !important; background:#fff !important; border-radius:10px !important; }
[data-baseweb="input"] > div:focus-within, [data-baseweb="textarea"] > div:focus-within, [data-baseweb="select"] > div:focus-within {
  border-color:var(--cf-primary) !important; box-shadow:0 0 0 3px rgba(15,118,110,.15) !important; }
[data-baseweb="tab-list"] { background:#E6ECF0 !important; border-radius:12px !important; padding:4px; gap:4px; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display:none !important; }
[data-baseweb="tab"] { color:var(--cf-muted) !important; border-radius:9px !important; font-weight:600; }
[data-baseweb="tab"][aria-selected="true"] { color:var(--cf-primary) !important; background:#fff !important;
  box-shadow:0 1px 4px rgba(11,37,48,.12); }


/* ---------- pastel KPI tiles ---------- */
.metric-card { border-radius:16px !important; box-shadow:none !important; border:0 !important; }
.metric-card:before { display:none !important; }
.metric-card.tone-blue { background:#E9F0FE !important; }
.metric-card.tone-green { background:#E4F5F1 !important; }
.metric-card.tone-amber { background:#FEF3E0 !important; }
.metric-card.tone-lavender { background:#EDE9FE !important; }
.metric-card.tone-lavender .metric-value { color:#5B4FC4 !important; }
[data-testid="stMain"] a { color:#2563EB; }
.metric-card.tone-green .metric-value { color:#0B7A70 !important; }
.metric-card.tone-amber .metric-value { color:#B45309 !important; }
.metric-sub { margin-top:.55rem; background:rgba(255,255,255,.65); border-radius:8px; padding:4px 8px; font-size:.76rem; color:#44525F; }
/* pill toggles (radios in the main area) */
[data-testid="stMain"] [data-testid="stRadio"] [role="radiogroup"] { gap:8px; flex-wrap:wrap; }
[data-testid="stMain"] [data-testid="stRadio"] label { background:#fff; border:1px solid var(--cf-border); border-radius:999px; padding:3px 14px; }
[data-testid="stMain"] [data-testid="stRadio"] label > div:first-child { display:none; }
[data-testid="stMain"] [data-testid="stRadio"] label:has(input:checked) { background:var(--cf-primary); border-color:var(--cf-primary); }
[data-testid="stMain"] [data-testid="stRadio"] label:has(input:checked) * { color:#fff !important; }
/* patient-flow stage cards */
.cf-flow { display:flex; align-items:stretch; overflow-x:auto; padding:6px 2px 12px; }
.cf-stage { flex:1 1 0; min-width:148px; border-radius:18px; padding:16px 12px; text-align:center; border:1px solid;
  display:flex; flex-direction:column; align-items:center; gap:10px; }
.cf-stage.blue { background:#DCEBFD; border-color:#A9CBF5; }
.cf-stage.green { background:#DDF3E8; border-color:#9ED9BB; }
.cf-stage.amber { background:#FDEFD8; border-color:#F0B45F; box-shadow:0 0 0 4px rgba(217,119,6,.10), 0 10px 26px rgba(217,119,6,.18); }
.cf-stage-title { font-size:.76rem; font-weight:800; letter-spacing:.04em; text-transform:uppercase; color:#243447; }
.cf-stage-icon { width:56px; height:56px; border-radius:16px; background:rgba(255,255,255,.72); display:flex;
  align-items:center; justify-content:center; font-size:26px; }
.cf-stage-meta { font-size:.84rem; color:#33475B; line-height:1.4; }
.cf-stage-note { background:#D97706; border-radius:10px; padding:6px 8px; font-size:.75rem; line-height:1.35; }
.cf-stage-note, .cf-stage-note b { color:#fff !important; }
.cf-arrow { flex:0 0 28px; display:flex; align-items:center; justify-content:center; color:#7FA6D6; font-size:20px; }
.cf-arrow.amber { color:#D97706; }
.cf-path-step { border-radius:14px; padding:14px 16px; text-align:center; font-size:1.05rem; font-weight:600; color:var(--cf-navy); }
.cf-path-step.blue { background:#E9F0FE; } .cf-path-step.green { background:#E4F5F1; color:#0B7A70; }
.cf-path-step small { display:block; font-weight:400; font-size:.8rem; color:var(--cf-muted); margin-top:2px; }
.cf-path-arrow { text-align:center; color:var(--cf-primary); font-size:20px; line-height:1.9; }
/* completeness bars */
.cf-bar-row { display:grid; grid-template-columns:minmax(110px,1.2fr) 3fr 62px; gap:12px; align-items:center;
  padding:9px 2px; border-bottom:1px solid #EDF1F4; font-size:.9rem; }
.cf-bar { height:8px; border-radius:99px; background:#E8EDF1; overflow:hidden; }
.cf-bar i { display:block; height:100%; border-radius:99px; background:#2563EB; }
.cf-bar i.warn { background:#D97706; } .cf-bar i.bad { background:#DC2626; }
.cf-bar-pct { text-align:right; color:var(--cf-muted); font-variant-numeric:tabular-nums; }


/* ---------- every st.metric becomes a pastel tile (all pages) ---------- */
[data-testid="stMetric"] { background:#E9F0FE !important; border:0 !important; box-shadow:none !important; padding:.95rem 1.1rem; }
[data-testid="stHorizontalBlock"] > div:nth-child(2n) [data-testid="stMetric"] { background:#E4F5F1 !important; }
[data-testid="stHorizontalBlock"] > div:nth-child(3n) [data-testid="stMetric"] { background:#EDE9FE !important; }
[data-testid="stHorizontalBlock"] > div:nth-child(4n) [data-testid="stMetric"] { background:#FEF3E0 !important; }
[data-testid="stHorizontalBlock"] > div:nth-child(2n) [data-testid="stMetricValue"] { color:#0B7A70 !important; }
[data-testid="stHorizontalBlock"] > div:nth-child(4n) [data-testid="stMetricValue"] { color:#B45309 !important; }
/* rounded teal frame around the app */
.stApp::after { content:""; position:fixed; inset:0; border:6px solid #BFE8DF; border-radius:18px; pointer-events:none; z-index:999990; }

/* ---------- status chips ---------- */
.cf-status { display:flex; flex-wrap:wrap; gap:8px; margin:-.4rem 0 1rem; }
.cf-chip { background:#fff; border:1px solid var(--cf-border); color:var(--cf-ink-soft); border-radius:999px;
  padding:4px 12px; font-size:.78rem; font-weight:500; }
.cf-chip.warn { background:#FEF3E0; border-color:#D97706; color:#92400E; }
.cf-source { color:var(--cf-muted); font-size:.8rem; margin:-.3rem 0 .6rem; }
</style>
""", unsafe_allow_html=True)

# ---------- session timeout, access log and admin role ----------
try:
    _TIMEOUT_MIN = int(st.secrets.get("SESSION_TIMEOUT_MIN", 30))
except Exception:  # noqa: BLE001
    _TIMEOUT_MIN = 30
_last = st.session_state.get("cf_last_active")
if _last and _time.time() - _last > _TIMEOUT_MIN * 60:
    try:
        supabase.auth.sign_out()
    except Exception:  # noqa: BLE001
        pass
    for _k in ("cf_last_active", "cf_logged", "cf_last_page", "cf_sb_client"):
        st.session_state.pop(_k, None)
    st.session_state.careflow_user = None
    st.session_state["cf_timeout_notice"] = _TIMEOUT_MIN
    st.rerun()
st.session_state["cf_last_active"] = _time.time()


def _admin_emails():
    try:
        raw = st.secrets.get("ADMIN_EMAILS", [])
    except Exception:  # noqa: BLE001
        return set()
    if isinstance(raw, str):
        raw = raw.split(",")
    return {str(e).strip().lower() for e in raw if str(e).strip()}


def is_admin():
    return str(st.session_state.careflow_user["email"]).lower() in _admin_emails()


def log_access(event, page=""):
    """Best effort: needs the access_log table from supabase_security.sql; never blocks the app."""
    try:
        supabase.table("access_log").insert({"user_email": str(st.session_state.careflow_user["email"]),
                                             "event": event, "page": page}).execute()
    except Exception:  # noqa: BLE001
        pass


# ======================================================================
# DESIGN: Aurora (lavender glass, top navigation)
# ======================================================================
THEME = "Aurora"  # single design
THEMES = {
    "Aurora": dict(bg="linear-gradient(135deg,#C9C3F4 0%,#DCE4FB 42%,#E8ECFB 68%,#F7DBE6 100%)", panel="rgba(255,255,255,.55)",
                   card="rgba(255,255,255,.92)", ink="#14141F", muted="#5B5B75", accent="#16161D", accent_hover="#34344A",
                   shadow="0 10px 30px rgba(90,80,160,.10)", t_lav="#D8D2F7", t_sky="#DCE8FB", t_pink="#F8DCE6",
                   t_mint="#D9F0E6", t_hero_ink="#2B2170", side="rgba(255,255,255,.55)"),
}
THEME_PALETTES = {"Aurora": ["#7C6FE0", "#7DB3E8", "#E58BA8", "#6FCFB0", "#16161D", "#F5B971", "#9AA3B5", "#C5CBE0"]}
THEME_CSS = r'''
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
:root { --cf-primary:@@accent@@; --cf-primary-dark:@@accent_hover@@; --cf-navy:@@ink@@; --cf-ink:@@ink@@; --cf-muted:@@muted@@;
  --cf-card:@@card@@; --cf-border:rgba(20,20,31,.08); }
html, body, .stApp, .stMarkdown, p, label, h1, h2, h3, h4, button, input, textarea {
  font-family:'Outfit','Inter',system-ui,-apple-system,'Segoe UI',sans-serif !important; }
[data-testid="stAppViewContainer"] { background:@@bg@@ !important; background-attachment:fixed !important; }
.stApp::after { display:none !important; }
[data-testid="stHeader"] { background:transparent !important; backdrop-filter:none !important; }
.block-container { background:@@panel@@; backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px); border-radius:28px;
  margin:3.4rem auto 1.4rem; width:calc(100% - 1.6rem); padding-top:1.5rem !important; border:1px solid rgba(255,255,255,.65);
  box-shadow:0 20px 60px rgba(90,80,160,.12); }
h1, h2, h3, h4 { font-weight:500 !important; letter-spacing:-.02em; color:@@ink@@ !important; }
/* title */
.cf-titlebar { border-bottom:0 !important; padding-bottom:.2rem; margin-bottom:.8rem; }
.cf-titlebar h1 { font-weight:500 !important; font-size:clamp(2.1rem,4.4vw,3.2rem) !important; letter-spacing:-.035em; color:@@ink@@ !important; }
.cf-titlebar h1 span { color:inherit !important; }
.cf-titlebar p { color:@@muted@@; }
.cf-updated, .cf-chip { background:@@card@@; border:0 !important; box-shadow:@@shadow@@; }
.cf-chip.warn { background:#FFE7D6; color:#9A3412; }
/* cards */
.metric-card, .cf-feature-card, [data-testid="stMetric"], [data-testid="stVerticalBlockBorderWrapper"], [data-testid="stPlotlyChart"],
[data-testid="stExpander"], [data-testid="stDataFrame"], [data-testid="stTable"] {
  background:@@card@@ !important; border:0 !important; border-radius:24px !important; box-shadow:@@shadow@@ !important; }
[data-testid="stVerticalBlockBorderWrapper"] { padding:clamp(6px,1vw,14px); }
.metric-card { padding:1.15rem 1.25rem; }
.metric-card.tone-lavender, [data-testid="stHorizontalBlock"] > div:nth-child(3n) [data-testid="stMetric"] { background:@@t_lav@@ !important; }
.metric-card.tone-blue, [data-testid="stHorizontalBlock"] > div:nth-child(2n) [data-testid="stMetric"] { background:@@t_sky@@ !important; }
.metric-card.tone-green { background:@@t_mint@@ !important; }
.metric-card.tone-amber, [data-testid="stHorizontalBlock"] > div:nth-child(4n) [data-testid="stMetric"] { background:@@t_pink@@ !important; }
.metric-card .metric-value, [data-testid="stMetricValue"] { color:@@ink@@ !important; font-weight:500 !important; font-size:2.1rem; }
.metric-card.tone-blue .metric-value, .metric-card.tone-green .metric-value, .metric-card.tone-amber .metric-value { color:@@ink@@ !important; }
.metric-card .metric-label, [data-testid="stMetric"] label { color:@@muted@@ !important; }
.metric-card.tone-lavender .metric-value, .metric-card.tone-lavender .metric-label { color:@@t_hero_ink@@ !important; }
.metric-sub { background:rgba(255,255,255,.7) !important; border-radius:999px !important; padding:4px 12px !important; }
.cf-stage { border-radius:24px; } .cf-path-step { border-radius:20px; }
/* controls: black pills */
.stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button, button[kind="primary"] {
  background:@@accent@@ !important; color:#fff !important; border:0 !important; border-radius:999px !important; padding:.45rem 1.3rem; }
.stButton button:hover, .stDownloadButton button:hover, [data-testid="stFormSubmitButton"] button:hover { background:@@accent_hover@@ !important; box-shadow:none; }
.stButton button *, .stDownloadButton button *, [data-testid="stDownloadButton"] button *, [data-testid="stBaseButton-secondary"] *,
[data-testid="stBaseButton-primary"] *, [data-testid="stFormSubmitButton"] button *, button[kind="primary"] *, button[kind="secondary"] *,
.stButton button p, .stDownloadButton button p { color:#fff !important; }
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button *, [data-testid="stSidebar"] .stDownloadButton button * { color:#fff !important; }
[data-testid="stMain"] [data-testid="stRadio"] label { border:0 !important; background:rgba(255,255,255,.85); }
[data-testid="stMain"] [data-testid="stRadio"] label:has(input:checked) { background:@@accent@@ !important; }
[data-baseweb="tab-list"] { background:rgba(255,255,255,.8) !important; border-radius:999px !important; }
[data-baseweb="tab"] { border-radius:999px !important; }
[data-baseweb="tab"][aria-selected="true"] { background:@@accent@@ !important; color:#fff !important; box-shadow:none; }
[data-baseweb="input"] > div, [data-baseweb="textarea"] > div, [data-baseweb="select"] > div { background:rgba(240,240,246,.9) !important; border-color:transparent !important; border-radius:16px !important; }
[data-baseweb="input"] > div:focus-within, [data-baseweb="select"] > div:focus-within { box-shadow:0 0 0 2px @@accent@@ !important; }
.cf-bar i { background:@@accent@@; }
/* top navigation pills (best effort across Streamlit versions) */
[data-testid="stTopNavLink"], [data-testid="stHeader"] nav a { border-radius:999px !important; }
[data-testid="stTopNavLink"][aria-current="page"], [data-testid="stHeader"] nav a[aria-current="page"] { background:@@accent@@ !important; }
[data-testid="stTopNavLink"][aria-current="page"] *, [data-testid="stHeader"] nav a[aria-current="page"] * { color:#fff !important; }
/* light glass sidebar (filters, data source, account) */
[data-testid="stSidebar"], [data-testid="stSidebar"] > div, [data-testid="stSidebar"] [data-testid="stSidebarContent"],
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"], [data-testid="stSidebar"] [data-testid="stVerticalBlock"],
[data-testid="stSidebar"] [data-testid="stElementContainer"], [data-testid="stSidebar"] [data-testid="stBottom"],
[data-testid="stSidebar"] [data-testid="stExpander"] { background:@@side@@ !important; }
[data-testid="stSidebar"] { border-right:0 !important; backdrop-filter:blur(16px); }
[data-testid="stSidebar"] * { color:@@ink@@ !important; }
[data-testid="stSidebar"] hr { border-color:rgba(20,20,31,.1) !important; }
[data-testid="stSidebarNavLink"][aria-current="page"], [data-testid="stSidebarNav"] a[aria-current="page"] { background:@@accent@@ !important; box-shadow:none; }
[data-testid="stSidebar"] [aria-current="page"], [data-testid="stSidebar"] [aria-current="page"] * { color:#fff !important; }
[data-testid="stSidebarNavLink"]:hover, [data-testid="stSidebarNav"] a:hover { background:rgba(20,20,31,.06) !important; }
[data-testid="stSidebar"] .stButton button { background:@@accent@@ !important; border:0 !important; }
[data-testid="stSidebar"] .stButton button * { color:#fff !important; }
[data-testid="stSidebar"] [data-baseweb="tag"] { background:@@accent@@ !important; }
[data-testid="stSidebar"] [data-baseweb="select"] > div, [data-testid="stSidebar"] [data-baseweb="input"] > div { background:#fff !important; }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] { background:rgba(255,255,255,.7) !important; border:1px dashed rgba(20,20,31,.25) !important; }
.cf-user { background:rgba(255,255,255,.8); border:0; } .cf-avatar { background:@@accent@@; }
'''

_PAPER = "rgba(0,0,0,0)"  # charts sit transparently on the white cards
if THEME in THEMES:
    _css = THEME_CSS
    for _k, _v in THEMES[THEME].items():
        _css = _css.replace(f"@@{_k}@@", _v)
    st.markdown(f"<style>{_css}</style>", unsafe_allow_html=True)
# ---------- motion layer: entrance, count-up, hover lift (matches the demo video) ----------
MOTION_CSS = r'''
@property --cf-n { syntax:'<integer>'; initial-value:0; inherits:false; }
@keyframes cf-panel { from { opacity:0; transform:translateY(16px) scale(.985); } }
@keyframes cf-blur-in { from { opacity:0; filter:blur(14px); transform:translateY(10px); } }
@keyframes cf-rise { from { opacity:0; transform:translateY(16px); } }
@keyframes cf-pop { from { opacity:0; transform:translateY(14px) scale(.94); } }
@keyframes cf-wipe { from { clip-path:inset(0 100% 0 0); } to { clip-path:inset(0 0 0 0); } }
@keyframes cf-grow { from { transform:scaleX(0); } }
@keyframes cf-n { from { --cf-n:0; } }
@keyframes cf-out { 0%,97% { opacity:1; } 100% { opacity:0; } }
@keyframes cf-in { 0%,97% { opacity:0; } 100% { opacity:1; } }
/* page + title */
.block-container { animation:cf-panel .7s cubic-bezier(.2,.8,.2,1) backwards; }
.cf-titlebar h1 { animation:cf-blur-in .9s cubic-bezier(.2,.8,.2,1) .1s backwards; }
.cf-titlebar p, .cf-updated { animation:cf-rise .7s ease .25s backwards; }
/* KPI tiles and stage cards pop in one after another */
.metric-card { animation:cf-pop .6s cubic-bezier(.2,.8,.2,1) backwards; animation-delay:calc(var(--i,0) * 90ms + .15s); }
.cf-stage { animation:cf-pop .6s cubic-bezier(.2,.8,.2,1) backwards; animation-delay:calc(var(--i,0) * 110ms + .2s); }
.cf-path-step { animation:cf-rise .5s cubic-bezier(.2,.8,.2,1) backwards; animation-delay:calc(var(--i,0) * 90ms + .2s); }
.cf-arrow { animation:cf-rise .5s ease .5s backwards; }
/* count-up numbers (plain digits while counting, formatted value at the end) */
.cf-count { position:relative; display:inline-block; counter-reset:cfn var(--cf-n); animation:cf-n 1.3s cubic-bezier(.2,.7,.2,1) .25s backwards; }
.cf-count::before { content:counter(cfn); position:absolute; left:0; top:0; white-space:nowrap; animation:cf-out 1.55s linear .0s both; }
.cf-count-real { animation:cf-in 1.55s linear 0s both; }
/* charts draw in from the left; bars grow */
[data-testid="stPlotlyChart"] .js-plotly-plot { animation:cf-wipe 1.2s cubic-bezier(.2,.7,.2,1) .25s backwards; }
.cf-bar i { transform-origin:left; animation:cf-grow .9s cubic-bezier(.2,.8,.2,1) .3s backwards; }
.cf-stage.red { background:#FDE3E3; border-color:#F2A5A5; box-shadow:0 0 0 4px rgba(220,38,38,.10), 0 10px 26px rgba(220,38,38,.18); }
.cf-stage.red .cf-stage-note { background:#DC2626; } .cf-arrow.red { color:#DC2626; }
/* hover lift */
.metric-card, .cf-stage, .cf-path-step, [data-testid="stMetric"], .cf-chip { transition:transform .25s cubic-bezier(.2,.8,.2,1), box-shadow .25s; }
.metric-card:hover, .cf-stage:hover, .cf-path-step:hover, [data-testid="stMetric"]:hover { transform:translateY(-4px); }
.stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button { transition:transform .15s, background .2s, box-shadow .2s; }
.stButton button:active, .stDownloadButton button:active, [data-testid="stFormSubmitButton"] button:active { transform:scale(.97); }
/* shine on the hero tile, glow on the potential-bottleneck card */
@keyframes cf-shine { 0% { transform:translateX(-130%); } 55%, 100% { transform:translateX(130%); } }
@keyframes cf-glow { 0%, 100% { box-shadow:0 0 0 4px rgba(217,119,6,.10), 0 10px 26px rgba(217,119,6,.18); }
                     50% { box-shadow:0 0 0 9px rgba(217,119,6,.16), 0 14px 34px rgba(217,119,6,.30); } }
.metric-card.tone-lavender::after { content:""; position:absolute; inset:0; pointer-events:none;
  background:linear-gradient(110deg, transparent 35%, rgba(255,255,255,.38) 50%, transparent 65%);
  transform:translateX(-130%); animation:cf-shine 4s ease-in-out 1.4s infinite; }
.cf-stage.amber { animation:cf-pop .6s cubic-bezier(.2,.8,.2,1) backwards, cf-glow 2.8s ease-in-out 1.2s infinite;
  animation-delay:calc(var(--i,0) * 110ms + .2s), 1.2s; }
/* responsive */
@media (max-width: 900px) {
  .block-container { margin:3.2rem .4rem 1rem !important; width:calc(100% - .8rem) !important; border-radius:22px !important;
    padding-left:.9rem !important; padding-right:.9rem !important; }
  .cf-titlebar { align-items:flex-start; }
  .metric-card .metric-value, [data-testid="stMetricValue"] { font-size:1.7rem !important; }
  .cf-flow { scroll-snap-type:x proximity; } .cf-stage { min-width:172px; scroll-snap-align:start; }
  .cf-bar-row { grid-template-columns:1fr 2fr 52px; gap:8px; }
}
@media (max-width: 520px) {
  .cf-titlebar h1 { font-size:1.9rem !important; } .cf-titlebar p { font-size:.88rem; }
  .cf-chip { font-size:.72rem; padding:3px 9px; } .cf-updated { font-size:.74rem; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation:none !important; transition:none !important; }
  .cf-count::before { display:none; }
}
'''
st.markdown(f"<style>{MOTION_CSS}</style>", unsafe_allow_html=True)
_LOGO_FILE = _WORDMARK_AURORA_FILE

# ======================================================================
# THEME + SMALL UI HELPERS
# ======================================================================
# CareFlow patient-journey palette: keep stage meanings consistent across pages.
STAGE_COLORS = core.STAGE_COLORS
PALETTE = ["#2563EB", "#0D9488", "#7C6FE0", "#D97706", "#153451", "#38BDF8", "#64748B", "#94A3B8"]  # action blue, teal, lavender, amber, navy...
if THEME in THEME_PALETTES:
    PALETTE = THEME_PALETTES[THEME]

def activity_stage_color(activity):
    """Visual stage colour for an activity; honours the user's stage mapping. Not clinical triage."""
    return STAGE_COLORS[core.classify_stage(activity, st.session_state.get("cf_stage_map"))]


pio.templates["careflow"] = go.layout.Template(layout=go.Layout(
    colorway=PALETTE, font=dict(color="#14202B", family="Inter, Segoe UI, system-ui, sans-serif"),
    paper_bgcolor=_PAPER, plot_bgcolor=_PAPER,
    margin=dict(l=10, r=10, t=40, b=10),
    xaxis=dict(gridcolor="#E8EDF1", zerolinecolor="#CBD5DC", linecolor="#CBD5DC"),
    yaxis=dict(gridcolor="#E8EDF1", zerolinecolor="#CBD5DC", linecolor="#CBD5DC"),
    hoverlabel=dict(bgcolor="#153451", font=dict(color="#FFFFFF")),
))
pio.templates.default = "careflow"
px.defaults.template = "careflow"
px.defaults.color_continuous_scale = ["#DDF4F1", "#0D9488"]

# Streamlit >= 1.50 replaces use_container_width with width="stretch".
try:
    _ST_VERSION = tuple(int(x) for x in st.__version__.split(".")[:2])
except Exception:
    _ST_VERSION = (0, 0)
WIDE = {"width": "stretch"} if _ST_VERSION >= (1, 50) else {"use_container_width": True}

_chart_ids = itertools.count()  # reset on every script run -> stable, unique chart keys


def table(data, *, csv_name=None, **kw):
    st.dataframe(data, hide_index=True, **WIDE, **kw)
    if csv_name:
        st.download_button("Download CSV", data.to_csv(index=False).encode("utf-8"), csv_name, "text/csv", key=f"dl_{csv_name}")


def chart(build, empty="Not enough data to draw this chart.", height=None):
    """Render a Plotly figure from build(); never lets a bad chart break the page.
    build() returns a figure, or None when there is nothing to draw."""
    try:
        fig = build()
    except Exception as exc:  # noqa: BLE001 - surface any charting problem gracefully
        st.warning("This chart could not be drawn. The rest of the page is unaffected.")
        with st.expander("Technical details"):
            st.code(f"{type(exc).__name__}: {exc}")
        return
    if fig is None:
        st.info(empty)
        return
    if height:
        fig.update_layout(height=height)
    st.plotly_chart(fig, theme=None, key=f"cf_chart_{next(_chart_ids)}",
                    config={"displaylogo": False}, **WIDE)


def status_chips():
    if C.raw.empty:
        return
    chips = [f"{len(C.f):,} of {len(C.raw):,} events", f"{C.n_cases:,} cases", f"Source: {C.source}"]
    if C.active:
        chips.append("Filters: " + C.active)
    html = "".join(f'<span class="cf-chip">{escape(c)}</span>' for c in chips)
    if C.synthetic:
        html += '<span class="cf-chip warn">Departments are synthetic demo labels</span>'
    st.markdown(f'<div class="cf-status">{html}</div>', unsafe_allow_html=True)
    keys = globals().get("FILTER_KEYS") or {}
    removable = []
    if keys.get("depts") and st.session_state.get(keys["depts"]):
        removable.append(("Department", keys["depts"]))
    if keys.get("acts") and st.session_state.get(keys["acts"]):
        removable.append(("Activity", keys["acts"]))
    if keys.get("dates") and "dates" in C.active:
        removable.append(("Dates", keys["dates"]))
    if removable:
        cols = st.columns(len(removable) + 3)
        for col, (label, key) in zip(cols, removable):
            col.button(f"✕ {label}", key=f"cf_rm_{label}", on_click=lambda k=key: st.session_state.pop(k, None))


def page_header(title, subtitle="Turn event-log data into clearer operational insights and pathway visibility.",
                chips=True):
    words = str(title).split()
    head = escape(" ".join(words[:-1]))
    heading = f"{head} <span>{escape(words[-1])}</span>" if len(words) > 1 else f"<span>{escape(str(title))}</span>"
    src = getattr(globals().get("C"), "source", "")
    badge = f'<div class="cf-updated">Source: <b>{escape(str(src))}</b></div>' if src else ""
    st.markdown(f'<div class="cf-titlebar"><div><h1>{heading}</h1><p>{subtitle}</p></div>{badge}</div>',
                unsafe_allow_html=True)
    if chips:
        status_chips()


_COUNT_RE = re.compile(r"\d{1,3}(?:,\d{3})*")


def count_up(value):
    """Whole numbers count up from 0 on load; any other value is shown as-is."""
    v = str(value)
    if _COUNT_RE.fullmatch(v):
        return f'<span class="cf-count" style="--cf-n:{v.replace(",", "")}"><span class="cf-count-real">{v}</span></span>'
    return v


KPI_TONES = ["blue", "green", "lavender", "amber", "blue", "green"]


def kpis(items):
    """Pastel KPI tiles. Items are (label, value) or (label, value, sub-note)."""
    any_sub = any(len(it) > 2 and it[2] for it in items)
    for i, (col, it) in enumerate(zip(st.columns(len(items)), items)):
        sub = (f'<div class="metric-sub">{it[2]}</div>' if len(it) > 2 and it[2]
               else ('<div class="metric-sub" style="visibility:hidden">&nbsp;</div>' if any_sub else ""))
        col.markdown(
            f'<div class="metric-card tone-{KPI_TONES[i % len(KPI_TONES)]}" style="--i:{i}"><div class="metric-label">{it[0]}</div>'
            f'<div class="metric-value">{count_up(it[1])}</div>{sub}</div>',
            unsafe_allow_html=True,
        )


# ---- patient-flow stage helpers: every number is computed from the loaded event log ----
STAGE_META = core.STAGE_META
fmt_dwell = core.fmt_dwell


def stage_of(activity):
    return core.classify_stage(activity, st.session_state.get("cf_stage_map"))


@st.cache_data(show_spinner=False)
def cached_stage_summary(d, case, act, time, overrides_json, targets_json):
    return core.stage_summary(d, case, act, time, json.loads(overrides_json), json.loads(targets_json))


def stage_summary(f):
    if f.empty or not (C.case and C.act):
        return pd.DataFrame()
    cols = [c for c in (C.case, C.act, C.time) if c]
    return cached_stage_summary(f[cols], C.case, C.act, C.time,
                                json.dumps(st.session_state.get("cf_stage_map", {}), sort_keys=True),
                                json.dumps(st.session_state.get("cf_targets", {}), sort_keys=True))


def render_stage_flow(style="flow"):
    g = stage_summary(C.f)
    if g.empty:
        st.info("Map a case ID and an activity column (Field mapping) to see the stage flow.")
        return
    targets = {k: v for k, v in st.session_state.get("cf_targets", {}).items() if v and v > 0}
    present = [(k, l, i) for k, l, i in STAGE_META if k in g.index]
    over = {k for k, _, _ in present if k in targets and pd.notna(g.loc[k, "avg_h"]) and g.loc[k, "avg_h"] > targets[k]}
    longest = None
    if not targets:  # no targets set: only a potential bottleneck can be shown
        cand = g.loc[[k for k, _, _ in present if k != "completed"], "avg_h"].dropna()
        longest = cand.idxmax() if len(cand) >= 2 else None
    parts = []
    for n, (k, label, icon) in enumerate(present):
        r = g.loc[k]
        if style == "list":
            parts.append(f'<div class="cf-path-step {"green" if n % 2 else "blue"}" style="--i:{n}">{escape(label)}'
                         f'<small>{int(r.cases):,} cases · avg time {fmt_dwell(r.avg_h)}</small></div>')
            if n < len(present) - 1:
                parts.append('<div class="cf-path-arrow">↓</div>')
            continue
        tone = "red" if k in over else ("amber" if k == longest else ("green" if k == "completed" else "blue"))
        meta = (f"Cases reaching stage: {int(r.cases):,}" if k == "completed"
                else f"Avg time: {fmt_dwell(r.avg_h)}<br>{int(r.events):,} events")
        meta += f'<br><span style="opacity:.75;font-size:.76rem">e.g. {escape(str(r.names))}</span>'
        if k in targets and pd.notna(r.over_pct):
            meta += f'<br><span style="font-size:.78rem">Target {fmt_dwell(targets[k])} · {r.over_pct:.0f}% of visits over</span>'
        note = ""
        if k in over:
            note = (f'<div class="cf-stage-note"><b>Over target</b><br>Average {fmt_dwell(r.avg_h)} '
                    f'vs {fmt_dwell(targets[k])}</div>')
        elif k == longest:
            note = f'<div class="cf-stage-note"><b>Potential bottleneck</b><br>Longest average: {fmt_dwell(r.avg_h)}</div>'
        parts.append(f'<div class="cf-stage {tone}" style="--i:{n}"><div class="cf-stage-title">{escape(label)}<br>({int(r.cases):,})</div>'
                     f'<div class="cf-stage-icon">{icon}</div><div class="cf-stage-meta">{meta}</div>{note}</div>')
        if n < len(present) - 1:
            nxt = present[n + 1][0]
            parts.append(f'<div class="cf-arrow{" red" if nxt in over else (" amber" if nxt == longest else "")}">➜</div>')
    st.markdown(f'<div class="cf-flow">{"".join(parts)}</div>' if style == "flow" else "".join(parts),
                unsafe_allow_html=True)
    st.caption("Stages come from your mapping, or are inferred from activity names. Average time is the gap to the next "
               "recorded event in the same case. "
               + ("Red marks stages whose average is over the target you set." if targets else
                  "The amber stage has the longest average, a potential bottleneck only; set targets under Stage Mapping & Targets."))


def completeness_bars(f, max_rows=12):
    if f.empty:
        return
    pct = (f.notna().mean() * 100).sort_values()
    rows = []
    for name, p in pct.head(max_rows).items():
        tone = "" if p >= 99 else ("warn" if p >= 90 else "bad")
        rows.append(f'<div class="cf-bar-row"><div>{escape(str(name))}</div><div class="cf-bar">'
                    f'<i class="{tone}" style="width:{p:.1f}%"></i></div><div class="cf-bar-pct">{p:.1f}%</div></div>')
    st.markdown("".join(rows), unsafe_allow_html=True)
    if len(pct) > max_rows:
        st.caption(f"Showing the {max_rows} least complete of {len(pct)} fields.")


def fmt_hours(x):
    return "—" if x is None or pd.isna(x) else f"{x:,.1f} h"


def source_note(text):
    st.markdown(f'<div class="cf-source">Source: {text}</div>', unsafe_allow_html=True)


def footer():
    st.divider()
    st.caption(
        "CareFlow is a clinical process analytics workspace, not a clinical decision-support system. "
        "Department labels are synthetic where indicated. Do not publish identifiable patient or health data "
        "to a public repository."
    )


def guard(fn):
    """Wrap a page so an unexpected error shows a friendly message instead of a crash.
    (st.stop / st.rerun derive from BaseException and pass straight through.)"""
    @wraps(fn)
    def inner():
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            st.error("This page ran into a problem and could not finish loading. "
                     "Other pages are unaffected. Try adjusting the filters, or check Field mapping in the sidebar.")
            with st.expander("Technical details"):
                st.code(f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}")
        footer()
    return inner


def need(**roles):
    """need(**{"case ID": C.case}) -> True if all mapped, else shows guidance."""
    missing = [label for label, col in roles.items() if not col]
    if missing:
        st.info(f"This view needs: {', '.join(missing)}. Assign them under **Field mapping** in the sidebar. "
                f"Detected fields: {', '.join(map(str, C.raw.columns))}")
        return False
    return True


# ======================================================================
# DATA LAYER (cached, with loading states)
# ======================================================================
EVENT_LOG_CANDIDATES = ["careflow_event_log.csv", "event_log_ED_MMA_2026.csv", "sample_event_log.csv"]
PM_OUTPUT_DIRS = ["pm_outputs", "process_mining_outputs", "."]
PM_OUTPUT_KEYS = {"transitions": ["transition", "dfg", "directly_follows"], "variants": ["variant", "pathway"]}
PM_NORMALIZERS = {"transitions": pm.normalize_transitions, "variants": pm.normalize_variants}


@st.cache_data(show_spinner=False)
def _read_csv(path, mtime):
    return pd.read_csv(path)


def load_event_log(uploaded):
    """-> (DataFrame, source label, error message or None)"""
    if uploaded is not None:
        try:
            d = pd.read_csv(uploaded)
            return d, uploaded.name, (None if not d.empty else "The uploaded file has no rows.")
        except Exception as exc:  # noqa: BLE001
            return pd.DataFrame(), uploaded.name, f"Could not read the uploaded file ({type(exc).__name__}: {exc})."
    problems = []
    for name in EVENT_LOG_CANDIDATES:
        p = Path(name)
        if not p.exists():
            continue
        try:
            d = _read_csv(str(p), p.stat().st_mtime)
            if not d.empty:
                return d, name, None
            problems.append(f"{name} is empty")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{name}: {type(exc).__name__}")
    return pd.DataFrame(), "No CSV found", "; ".join(problems) or None


def discover_pm_outputs():
    """Look for process-mining CSV outputs and normalise them. Never raises."""
    found, notes = {}, []
    for folder in PM_OUTPUT_DIRS:
        p = Path(folder)
        if not p.is_dir():
            continue
        for f in sorted(p.glob("*.csv")):
            stem = f.stem.lower()
            for kind, keys in PM_OUTPUT_KEYS.items():
                if kind in found or not any(k in stem for k in keys):
                    continue
                try:
                    norm = PM_NORMALIZERS[kind](_read_csv(str(f), f.stat().st_mtime))
                except Exception as exc:  # noqa: BLE001
                    notes.append(f"{f.name}: could not be read ({type(exc).__name__})")
                    continue
                if norm is None:
                    notes.append(f"{f.name}: columns not recognised as {kind}")
                else:
                    found[kind] = {"file": f.name, "data": norm}
    return found, notes


@st.cache_data(show_spinner="Preparing event log…")
def prepare_log(raw, case, time, dept):
    d = raw.copy()
    if time:
        d[time] = pm.parse_timestamps(d[time])
    synthetic = False
    if not dept:
        d = pm.add_demo_department(d, case or d.columns[0])
        dept, synthetic = "demo_department", True
    return d, dept, synthetic


@st.cache_data(show_spinner="Mining directly-follows transitions…")
def cached_transitions(d, case, act, time):
    return pm.mine_transitions(d, case, act, time)


@st.cache_data(show_spinner="Building pathway variants…")
def cached_variants(d, case, act, time):
    return pm.mine_variants(d, case, act, time)


@st.cache_data(show_spinner="Calculating case durations…")
def cached_durations(d, case, time):
    return pm.case_durations(d, case, time)


def pm_source(kind, label, compute):
    """Use a precomputed process-mining output if one exists and the user opts in; else compute live."""
    pre = C.pm_outputs.get(kind)
    if pre and st.toggle(f"Use precomputed {label} ({pre['file']}) — ignores filters", key=f"use_pre_{kind}"):
        return pre["data"], f"precomputed process-mining output · {pre['file']}"
    return compute(), "computed live from the filtered event log"


@dataclass
class Ctx:
    raw: pd.DataFrame          # prepared, unfiltered
    f: pd.DataFrame            # filtered
    source: str
    case: Optional[str]
    act: Optional[str]
    time: Optional[str]
    dept: Optional[str]
    status: Optional[str]
    staff: Optional[str]
    synthetic: bool
    pm_outputs: dict
    dept_summary: str
    active: str = ""

    @property
    def n_cases(self):
        return int(self.f[self.case].nunique()) if self.case else len(self.f)


C: Ctx  # assigned once data + filters are ready (below)


def top_counts(series, label, top=10):
    return series.fillna("Unknown").astype(str).value_counts().head(top).rename_axis(label).reset_index(name="Events")


def fig_bar_counts(col, label, top=10, height=300):
    if not col:
        return None
    d = top_counts(C.f[col], label, top)
    if d.empty:
        return None
    fig = px.bar(d, x="Events", y=label, orientation="h")
    fig.update_traces(marker_color=PALETTE[0])
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=height, showlegend=False)
    return fig


def fig_donut(col, label, height=300):
    if not col:
        return None
    d = top_counts(C.f[col], label, 6)
    if d.empty:
        return None
    fig = px.pie(d, names=label, values="Events", hole=0.58)
    fig.update_layout(height=height, legend=dict(orientation="h", y=-0.1))
    return fig


FREQ = {"Day": "D", "Week": "W", "Month": "MS"}


def fig_volume(grain, height=300):
    if not C.time:
        return None
    t = C.f.dropna(subset=[C.time])
    if t.empty:
        return None
    s = t.groupby(pd.Grouper(key=C.time, freq=FREQ[grain])).size().reset_index(name="Events")
    fig = px.area(s, x=C.time, y="Events")
    fig.update_traces(line_color=PALETTE[1], fillcolor="rgba(13,148,136,.25)")
    fig.update_layout(height=height, xaxis_title=None)
    return fig


def pick_top(n_total, label, key, default=10, cap=30):
    if n_total <= 3:
        return n_total
    return st.slider(label, 3, min(cap, n_total), min(default, n_total), key=key)


# ======================================================================
# PAGES
# ======================================================================
def attention_lines(median_h, wow, g):
    """Plain-language findings, all calculated from the data in view."""
    lines = [f"**{C.n_cases:,} cases** are in view, with a median elapsed time of **{fmt_hours(median_h)}**."]
    if wow:
        arrow = "▲" if wow["pct"] >= 0 else "▼"
        lines.append(f"New cases in the latest 7 days: **{wow['cur']:,}** ({arrow} {abs(wow['pct']):.0f}% against the 7 days before).")
    targets = {k: v for k, v in st.session_state.get("cf_targets", {}).items() if v and v > 0}
    if g is not None and not g.empty:
        labels = core.STAGE_LABELS
        over = [(k, g.loc[k]) for k in targets if k in g.index and pd.notna(g.loc[k, "avg_h"]) and g.loc[k, "avg_h"] > targets[k]]
        if over:
            for k, r in over:
                extra = f", {r.over_pct:.0f}% of visits over target" if pd.notna(r.over_pct) else ""
                lines.append(f"**Over target:** {labels[k]} averages {fmt_dwell(r.avg_h)} against a target of {fmt_dwell(targets[k])}{extra}.")
        elif targets:
            lines.append("Every stage with a target is within it on average.")
        else:
            cand = g.loc[[k for k in g.index if k != "completed"], "avg_h"].dropna()
            if len(cand) >= 2:
                k = cand.idxmax()
                lines.append(f"Slowest stage by average time: **{labels[k]}** ({fmt_dwell(cand.max())}). "
                             "Set target times under *Stage Mapping & Targets* to flag breaches.")
    comp = core.completeness(C.f)
    low = comp[comp < 90]
    if len(low):
        lines.append("Data gaps: " + ", ".join(f"{escape(str(n))} ({p:.0f}% complete)" for n, p in low.head(3).items()) + ".")
    return lines


def build_report_html(lines, g):
    import html as _h
    rows = "".join(f"<tr><td>{escape(core.STAGE_LABELS.get(k, k))}</td><td>{int(r.cases):,}</td><td>{int(r.events):,}</td>"
                   f"<td>{escape(fmt_dwell(r.avg_h))}</td></tr>" for k, r in g.iterrows()) if g is not None and not g.empty else ""
    items = "".join(f"<li>{escape(_h.unescape(l).replace('**', '').replace('*', ''))}</li>" for l in lines)
    return ("<!doctype html><html><head><meta charset='utf-8'><title>CareFlow summary</title><style>"
            "body{font-family:system-ui,sans-serif;max-width:820px;margin:2rem auto;color:#14141F;line-height:1.5}"
            "table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:6px 8px;text-align:left}"
            f"</style></head><body><h1>CareFlow summary</h1><p>Source: {escape(str(C.source))} · generated {pd.Timestamp.now():%Y-%m-%d %H:%M}</p>"
            f"<h2>What needs attention</h2><ul>{items}</ul><h2>Stage summary</h2><table><tr><th>Stage</th><th>Cases</th>"
            f"<th>Events</th><th>Average time</th></tr>{rows}</table><p style='color:#666;font-size:.85rem'>Stages come from the "
            "stage mapping or are inferred from activity names. Average time is the gap to the next recorded event in the same case."
            "</p></body></html>")


@st.cache_data(show_spinner=False)
def to_csv_bytes(d):
    return d.to_csv(index=False).encode("utf-8")


@guard
def page_dashboard():
    page_header("Executive Dashboard")
    f = C.f
    dur = cached_durations(f, C.case, C.time) if C.case and C.time else pd.DataFrame()
    median_h = dur["Elapsed hours"].median() if not dur.empty else float("nan")
    wow = core.week_over_week(f, C.case, C.time)
    g = stage_summary(f)
    lines = attention_lines(median_h, wow, g)
    with st.container(border=True):
        st.markdown("#### What needs attention")
        st.markdown("\n".join(f"- {ln}" for ln in lines))
    wow_txt = f" · {'▲' if wow['pct'] >= 0 else '▼'} {abs(wow['pct']):.0f}% vs prior 7 days" if wow else ""
    kpis([
        ("Cases / patients", f"{C.n_cases:,}", f"{len(f) / max(C.n_cases, 1):.1f} events per case{wow_txt}"),
        ("Event records", f"{len(f):,}", f"{len(f) / max(len(C.raw), 1):.0%} of loaded log"),
        ("Unique activities", f"{f[C.act].nunique():,}" if C.act else "—",
         f"Most frequent: {escape(str(f[C.act].fillna('Unknown').astype(str).value_counts().index[0]))}" if C.act and len(f) else ""),
        ("Departments", f"{f[C.dept].nunique():,}",
         f"Busiest: {escape(str(f[C.dept].fillna('Unknown').astype(str).value_counts().index[0]))}" if len(f) else ""),
        ("Median elapsed time", fmt_hours(median_h),
         f"90th percentile: {fmt_hours(dur['Elapsed hours'].quantile(0.9))}" if not dur.empty else ""),
    ])
    st.write("")
    with st.container(border=True):
        st.markdown("#### Patient flow analytics")
        render_stage_flow()
    grain = st.radio("Group event volume by", list(FREQ), horizontal=True, key="dash_grain")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Activity distribution**")
        chart(lambda: fig_bar_counts(C.act, "Activity", 8), "No activity column is mapped.")
    with c2:
        st.markdown("**Department workload**")
        chart(lambda: fig_donut(C.dept, "Department"))
    with c3:
        st.markdown("**Event volume over time**")
        chart(lambda: fig_volume(grain), "A parseable timestamp column is needed for this chart.")
    l, r = st.columns([1, 1])
    with l:
        st.markdown("**Case elapsed-time distribution**")
        chart(lambda: None if dur.empty else px.histogram(dur, x="Elapsed hours", nbins=30)
              .update_traces(marker_color=PALETTE[0]).update_layout(height=300),
              "Needs case IDs and parseable timestamps.")
    with r:
        st.markdown("**Event log preview**")
        table(f.head(12))
    with st.container(border=True):
        st.markdown("#### Data completeness by field")
        completeness_bars(f)
    with st.container(border=True):
        st.markdown("#### Export")
        e1, e2, e3 = st.columns(3)
        if g is not None and not g.empty:
            out = g.reset_index().rename(columns={"_stage": "stage"})
            out["stage"] = out["stage"].map(core.STAGE_LABELS)
            e1.download_button("Stage summary (CSV)", to_csv_bytes(out.drop(columns=["names"])), "stage_summary.csv", "text/csv", key="dl_stage")
        e2.download_button("Summary report (HTML)", build_report_html(lines, g).encode("utf-8"), "careflow_summary.html",
                           "text/html", key="dl_report", help="Open in a browser and use Print > Save as PDF.")
        e3.download_button("Filtered event log (CSV)", to_csv_bytes(f), "event_log_filtered.csv", "text/csv", key="dl_log")

@guard
def page_pm_explorer():
    page_header("Process Mining Explorer")
    st.caption("Observed event sequences from the selected event log. This describes recorded workflow; "
               "it does not recommend clinical treatment.")
    if not need(**{"case ID": C.case, "activity": C.act}):
        return
    tab_map, tab_wait, tab_var = st.tabs(["Transition map", "Bottlenecks", "Variants"])

    trans, trans_src = pm_source("transitions", "transitions",
                                 lambda: cached_transitions(C.f, C.case, C.act, C.time))
    with tab_map:
        source_note(trans_src)
        if trans.empty:
            st.info("There are not enough consecutive events within a case to calculate transitions.")
        else:
            n_acts = len(set(trans["From activity"]) | set(trans["To activity"]))
            n = pick_top(n_acts, "Activities shown in the map", "pm_map_n", default=12)

            def heatmap():
                involvement = pd.concat([trans.groupby("From activity")["Transitions"].sum(),
                                         trans.groupby("To activity")["Transitions"].sum()]).groupby(level=0).sum()
                keep = involvement.nlargest(n).index
                sub = trans[trans["From activity"].isin(keep) & trans["To activity"].isin(keep)]
                m = sub.pivot_table(index="From activity", columns="To activity", values="Transitions",
                                    aggfunc="sum", fill_value=0)
                fig = px.imshow(m, aspect="auto", text_auto=True,
                                labels=dict(x="To activity", y="From activity", color="Transitions"))
                fig.update_layout(height=140 + 32 * len(m))
                return fig
            chart(heatmap)
            st.caption("Rows are the activity that happened first; columns are what directly followed it.")
            table(trans.head(200))
            st.download_button("Export transitions CSV", trans.to_csv(index=False).encode("utf-8"),
                               "careflow_transitions.csv", "text/csv")
    with tab_wait:
        source_note(trans_src)
        if "Avg wait (h)" not in trans.columns or trans.empty:
            st.info("Waiting times need a parseable timestamp column (or an output file with an hours-based wait column).")
        else:
            min_n = st.slider("Minimum transitions to include", 1, int(max(trans["Transitions"].max(), 2)), 1,
                              key="pm_wait_min")

            def waits():
                w = trans[trans["Transitions"] >= min_n].nlargest(15, "Avg wait (h)").copy()
                if w.empty:
                    return None
                w["Step"] = w["From activity"] + " → " + w["To activity"]
                fig = px.bar(w, x="Avg wait (h)", y="Step", orientation="h", hover_data=["Transitions"])
                fig.update_traces(marker_color=PALETTE[1])
                fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=140 + 28 * len(w))
                return fig
            chart(waits, "No transitions meet the minimum count.")
            st.caption("Longest average gaps between consecutive recorded events. Long waits can reflect "
                       "documentation delays as well as real queues.")
    with tab_var:
        render_variants(key="pm")


def render_variants(key):
    variants, src = pm_source("variants", "variants", lambda: cached_variants(C.f, C.case, C.act, C.time)[0])
    source_note(src)
    if variants.empty:
        st.info("No complete pathways could be assembled from the current filters.")
        return
    c1, c2 = st.columns([2, 1])
    with c1:
        query = st.text_input("Search pathways by activity name", key=f"{key}_variant_q")
    with c2:
        st.metric("Distinct pathways", f"{len(variants):,}")
    shown = variants
    if query.strip():
        shown = variants[variants["Observed pathway"].str.contains(query.strip(), case=False, regex=False)]
    if shown.empty:
        st.info("No pathway contains that text.")
        return
    n = pick_top(len(shown), "Pathways to chart", f"{key}_variant_n", default=10)
    top = shown.head(n)

    def bar():
        fig = px.bar(top, x="Cases", y="Variant", orientation="h",
                     hover_data=["Observed pathway", "Share of cases (%)", "Steps"])
        fig.update_traces(marker_color=PALETTE[0])
        fig.update_layout(yaxis={"autorange": "reversed"}, height=120 + 30 * len(top))
        return fig
    chart(bar)
    table(shown.head(200))
    st.download_button("Export pathways CSV", shown.to_csv(index=False).encode("utf-8"),
                       "careflow_pathways.csv", "text/csv", key=f"{key}_variant_dl")


# ======================================================================
# GEMINI-POWERED AI WORKFLOW ASSISTANT
# Sends aggregate analytics only; never sends raw event rows or case IDs.
# ======================================================================
def _cf_ai_secret(name, default=None):
    try:
        value = st.secrets.get(name, default)
        return value if value else default
    except Exception:
        return default


def _cf_ai_analytics_context():
    f = C.f
    ctx = {
        "source": str(C.source),
        "events_in_current_view": int(len(f)),
        "cases_in_current_view": int(C.n_cases),
        "mapped_fields": {"case_id": bool(C.case), "activity": bool(C.act),
                           "timestamp": bool(C.time), "department": bool(C.dept),
                           "resource": bool(C.staff)},
        "active_filters": str(getattr(C, "active", "") or "None"),
        "department_scope": str(C.dept_summary),
        "department_labels_are_synthetic": bool(C.synthetic),
    }
    if C.act and not f.empty:
        ctx["top_activities_by_event_count"] = [
            {"activity": str(k), "events": int(v)}
            for k, v in f[C.act].fillna("Unknown").astype(str).value_counts().head(8).items()
        ]
    if C.dept and not f.empty:
        ctx["top_departments_by_event_count"] = [
            {"department": str(k), "events": int(v)}
            for k, v in f[C.dept].fillna("Unknown").astype(str).value_counts().head(8).items()
        ]
    if C.case and C.act and not f.empty:
        try:
            trans = cached_transitions(f, C.case, C.act, C.time)
            if trans is not None and not trans.empty:
                cols = {"From activity", "To activity", "Transitions"}
                if cols.issubset(trans.columns):
                    rows = trans.copy()
                    if "Avg wait (h)" in rows.columns:
                        rows = rows.sort_values("Avg wait (h)", ascending=False, na_position="last")
                        ctx["slowest_observed_transitions"] = [
                            {"from": str(r["From activity"]), "to": str(r["To activity"]),
                             "average_gap_hours": (None if pd.isna(r.get("Avg wait (h)")) else round(float(r["Avg wait (h)"]), 2)),
                             "transition_count": int(r["Transitions"])}
                            for _, r in rows.head(8).iterrows()
                        ]
                    else:
                        ctx["most_frequent_transitions"] = [
                            {"from": str(r["From activity"]), "to": str(r["To activity"]),
                             "transition_count": int(r["Transitions"])}
                            for _, r in rows.nlargest(8, "Transitions").iterrows()
                        ]
        except Exception:
            ctx["transition_analysis"] = "Unavailable for the current field mapping."
        try:
            variants, _ = cached_variants(f, C.case, C.act, C.time)
            if variants is not None and not variants.empty:
                keep = [c for c in ("Observed pathway", "Cases", "Share of cases (%)", "Steps") if c in variants.columns]
                ctx["most_frequent_observed_pathways"] = variants.head(5)[keep].where(pd.notna(variants.head(5)[keep]), None).to_dict("records")
        except Exception:
            ctx["pathway_analysis"] = "Unavailable for the current field mapping."
    if C.staff and not f.empty:
        ctx["resource_event_summary"] = {
            "events_with_resource": int(f[C.staff].notna().sum()),
            "distinct_resource_labels": int(f[C.staff].nunique(dropna=True)),
            "note": "Event counts are not staffing utilization, workload capacity, or time-on-task."
        }
    ctx["interpretation_limits"] = [
        "Timestamp gaps are gaps between recorded events, not verified queue or treatment waiting times.",
        "Event counts do not establish resource utilization or staff capacity.",
        "No simulation or staffing scenario is run by this assistant.",
        "Do not infer patient-level outcomes, clinical causes, or treatment recommendations."
    ]
    return ctx


def _cf_ai_local_answer(question, context):
    q = question.lower()
    if "transition" in q or "wait" in q or "slow" in q or "bottleneck" in q:
        rows = context.get("slowest_observed_transitions", [])
        if rows:
            lines = ["Slowest observed transition gaps in the current filtered data:"]
            for r in rows[:5]:
                gap = r.get("average_gap_hours")
                gap_text = "not available" if gap is None else f"{gap:,.2f} hours"
                lines.append(f"- {r['from']} → {r['to']}: {gap_text} average recorded gap across {r['transition_count']:,} transitions.")
            return "\n".join(lines) + "\n\nThese are recorded-event gaps, not confirmed queue times or proof of a bottleneck cause."
    if "pathway" in q or "frequent" in q:
        rows = context.get("most_frequent_observed_pathways", [])
        if rows:
            return "Most frequent observed pathways in the current view:\n" + "\n".join(
                f"- {r.get('Observed pathway', 'Pathway')}: {r.get('Cases', '—')} cases"
                + (f" ({r.get('Share of cases (%)')}%)" if r.get('Share of cases (%)') is not None else "")
                for r in rows)
    if "resource" in q or "utilization" in q or "staff" in q:
        r = context.get("resource_event_summary")
        if r:
            return (f"The current view has {r['events_with_resource']:,} events with a mapped resource and "
                    f"{r['distinct_resource_labels']:,} distinct resource labels. This does not measure utilization, "
                    "capacity, or time-on-task; those require roster, availability, and duration data.")
        return "No resource/staff field is mapped. Use Field mapping to assign one before reviewing resource event counts."
    return (f"The current filtered view contains {context['events_in_current_view']:,} event records across "
            f"{context['cases_in_current_view']:,} cases. Data source: {context['source']}. "
            "I can summarize recorded transitions, frequent pathways, and mapped resource event counts. "
            "For detailed interpretation, configure GEMINI_API_KEY in Streamlit Secrets. "
            "I cannot calculate hypothetical staffing simulations from the observed event log alone.")


def _cf_ai_gemini_answer(question, context, history=None):
    """Call Gemini generateContent through REST; no extra package dependency."""
    import urllib.error
    import urllib.request

    api_key = _cf_ai_secret("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in Streamlit Secrets.")
    model = str(_cf_ai_secret("GEMINI_MODEL", "gemini-3.8-flash")).strip()
    system_text = (
        "You are CareFlow's operational analytics assistant for hospital management. "
        "Answer only from the aggregate analytics JSON supplied below and the conversation. "
        "Never invent metrics, causal explanations, staffing outcomes, simulation results, or missing fields. "
        "Clearly distinguish recorded timestamp gaps from actual queue/wait times and event counts from utilization. "
        "If asked to simulate increasing doctors or compare hypothetical scenarios, explain that no simulation engine "
        "or staffing model is connected and list the extra inputs needed. Do not give diagnosis, triage, or treatment advice. "
        "Do not request or expose patient identifiers. Be concise and state when data is insufficient."
    )
    system_instruction = system_text + "\n\nCURRENT AGGREGATE CAREFLOW ANALYTICS:\n" + json.dumps(context, ensure_ascii=False, default=str)
    parts = []
    for item in (history or [])[-8:]:
        role = "model" if item.get("role") == "assistant" else "user"
        parts.append({"role": role, "parts": [{"text": str(item.get("content", ""))[:3000]}]})
    parts.append({"role": "user", "parts": [{"text": question[:3000]}]})
    payload = {"systemInstruction": {"parts": [{"text": system_instruction}]},
               "contents": parts, "generationConfig": {"temperature": 0.2, "maxOutputTokens": 900}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={
        "Content-Type": "application/json", "x-goog-api-key": api_key
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"Gemini API returned HTTP {exc.code}: {detail}") from exc
    candidates = result.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no answer. Check model availability or safety settings.")
    answer = "\n".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []) if p.get("text"))
    if not answer.strip():
        raise RuntimeError("Gemini returned an empty text response.")
    return answer.strip()


@guard
def page_ai_assistant():
    """Mobile-friendly CareFlow AI chat, styled to match the supplied reference."""
    context = _cf_ai_analytics_context()
    api_ready = bool(_cf_ai_secret("GEMINI_API_KEY"))

    st.markdown("""
    <style>
    .cf-ai-shell { background:#F8FAFC; border:1px solid #DCE3E9; border-radius:24px;
      overflow:hidden; box-shadow:0 8px 24px rgba(15,35,55,.06); margin:.25rem 0 1rem; }
    .cf-ai-head { display:flex; align-items:center; gap:14px; padding:20px 22px 17px;
      background:#fff; border-bottom:1px solid #DCE3E9; }
    .cf-ai-avatar { width:54px; height:54px; flex:0 0 54px; border-radius:50%; display:flex;
      align-items:center; justify-content:center; background:#F3E8FF; color:#9333EA; font-size:27px; }
    .cf-ai-title { color:#14202B; font-size:clamp(1.15rem,3vw,1.55rem); font-weight:800; line-height:1.25; }
    .cf-ai-status { color:#15945B; font-weight:650; font-size:.9rem; margin-top:4px; }
    .cf-ai-body { padding:22px; }
    .cf-ai-welcome { background:#fff; border:1px solid #E0E5EB; border-radius:20px;
      box-shadow:0 2px 5px rgba(15,35,55,.08); padding:20px; color:#4B5563;
      font-size:1rem; line-height:1.65; margin:0 0 16px; }
    .cf-ai-welcome strong { color:#263445; }
    div[data-testid="stChatMessage"] { background:#fff; border:1px solid #E0E5EB;
      border-radius:18px; padding:12px 14px; box-shadow:0 2px 5px rgba(15,35,55,.05); }
    div[data-testid="stChatInput"] { background:#fff; border-radius:14px; }
    .cf-ai-footnote { color:#64748B; font-size:.78rem; line-height:1.5; padding:4px 2px 10px; }
    @media(max-width:700px) {
      .cf-ai-head { padding:17px 15px; gap:11px; }
      .cf-ai-body { padding:15px; }
      .cf-ai-welcome { padding:17px; font-size:.96rem; }
      .cf-ai-avatar { width:48px; height:48px; flex-basis:48px; }
    }
    </style>
    <div class="cf-ai-shell">
      <div class="cf-ai-head">
        <div class="cf-ai-avatar">🤖</div>
        <div style="min-width:0">
          <div class="cf-ai-title">CareFlow AI Assistant</div>
          <div class="cf-ai-status">● Connected to Dataset</div>
        </div>
      </div>
      <div class="cf-ai-body">
        <div class="cf-ai-welcome">Hello! I'm the <strong>CareFlow AI Assistant</strong>. I can help you understand the current event log and its operational analytics.<br><br>Here are some things you can ask me:</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Connection and data scope are shown clearly without implying that Gemini is configured.
    if not api_ready:
        st.caption("Local analytics mode is active. Add GEMINI_API_KEY in Streamlit Secrets to enable Gemini responses.")
    suggestions = [
        "What are the major workflow bottlenecks?",
        "Summarize the workflow performance.",
        "Which transition has the highest elapsed time?",
        "Show the five slowest observed transitions.",
        "Which patient pathway is most frequent?",
        "Explain the resource utilization results and their limitations.",
    ]
    for i, prompt in enumerate(suggestions):
        if st.button(prompt, key=f"cf_gemini_suggest_{i}", use_container_width=True):
            st.session_state["cf_ai_pending_question"] = prompt

    if "cf_ai_history" not in st.session_state:
        st.session_state["cf_ai_history"] = []
    for item in st.session_state["cf_ai_history"]:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])

    question = st.chat_input("Ask about transitions, pathways, bottlenecks or resources…")
    question = question or st.session_state.pop("cf_ai_pending_question", None)
    if question:
        st.session_state["cf_ai_history"].append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Analyzing the current CareFlow data…"):
                try:
                    answer = _cf_ai_gemini_answer(question, context, st.session_state["cf_ai_history"][:-1])
                    st.caption("Powered by Google Gemini · aggregate analytics context")
                except Exception as exc:
                    answer = _cf_ai_local_answer(question, context)
                    st.warning(f"Gemini is unavailable; showing the local analytics fallback. Details: {str(exc)[:350]}")
                st.markdown(answer)
        st.session_state["cf_ai_history"].append({"role": "assistant", "content": answer})

    left, right = st.columns([1, 1])
    with left:
        if st.button("Clear conversation", key="cf_ai_clear", use_container_width=True):
            st.session_state["cf_ai_history"] = []
            st.session_state.pop("cf_ai_pending_question", None)
            st.rerun()
    with right:
        st.caption("Dataset: current filtered event log")
    st.markdown('<div class="cf-ai-footnote">Privacy: only aggregate counts, pathway summaries and transition summaries are sent to Gemini. Raw event rows and case IDs are not included. Obtain hospital privacy/security approval before using an external AI service with real hospital data. This assistant does not provide clinical advice.</div>', unsafe_allow_html=True)


@guard
def page_patient_flow():
    page_header("Patient Flow")
    if not need(**{"case ID": C.case, "activity": C.act}):
        return
    with st.container(border=True):
        st.markdown("#### Explore the patient pathway")
        render_stage_flow("list")

    # Patient journey Sankey: aggregated directly-follows transitions from the
    # currently filtered event log. No patient identifiers are displayed.
    with st.container(border=True):
        st.markdown("#### Patient Journey Map")
        st.caption("Aggregated movement between recorded activities. Link width represents observed transition frequency.")
        if len(C.f) < 2:
            st.info("At least two recorded events are needed to build a journey map.")
        else:
            journey = cached_transitions(C.f, C.case, C.act, C.time)
            if journey.empty:
                st.info("No consecutive activity transitions were found in the current data.")
            else:
                max_links = min(40, len(journey))
                default_links = min(20, max_links)
                link_limit = st.slider(
                    "Transitions to display", min_value=1, max_value=max_links,
                    value=default_links, key="patient_flow_sankey_limit"
                )
                shown = journey.head(link_limit).copy()
                labels = list(dict.fromkeys(
                    shown["From activity"].astype(str).tolist()
                    + shown["To activity"].astype(str).tolist()
                ))
                node_index = {label: i for i, label in enumerate(labels)}
                node_colors = [activity_stage_color(label) for label in labels]
                fig = go.Figure(data=[go.Sankey(
                    arrangement="snap",
                    node=dict(
                        pad=18, thickness=18, line=dict(color="rgba(100,116,139,.35)", width=0.5),
                        label=labels, color=node_colors,
                        hovertemplate="%{label}<extra></extra>"
                    ),
                    link=dict(
                        source=[node_index[x] for x in shown["From activity"].astype(str)],
                        target=[node_index[x] for x in shown["To activity"].astype(str)],
                        value=shown["Transitions"].astype(float).tolist(),
                        customdata=shown["Transitions"].tolist(),
                        hovertemplate="%{source.label} → %{target.label}<br>Observed transitions: %{value:,}<extra></extra>"
                    )
                )])
                fig.update_layout(height=520, margin=dict(l=10, r=10, t=20, b=10), font=dict(size=12))
                chart(lambda: fig)
                st.caption("This is an operational summary of recorded event sequences, not a prescribed clinical pathway. "
                           "Activity colors are inferred from labels and should be checked in Stage Mapping.")
    # Bottleneck detection: rank observed consecutive-activity waits from the
    # filtered event log. These are operational intervals, not clinical targets.
    with st.container(border=True):
        st.markdown("#### Bottleneck Detection")
        st.caption("Ranks transitions by observed waiting time between consecutive recorded activities. Results depend on timestamp quality and the current filters.")
        if not C.time:
            st.info("Map a timestamp column in Stage Mapping to analyse waiting times.")
        else:
            waits = cached_transitions(C.f, C.case, C.act, C.time)
            if waits.empty or not {"Avg wait (h)", "Median wait (h)"}.issubset(waits.columns):
                st.info("There are not enough consecutive events with usable timestamps to calculate transition waiting times.")
            else:
                waits = waits.copy()
                waits["Avg wait (h)"] = pd.to_numeric(waits["Avg wait (h)"], errors="coerce")
                waits["Median wait (h)"] = pd.to_numeric(waits["Median wait (h)"], errors="coerce")
                # Negative intervals generally indicate timestamp/order problems;
                # exclude them rather than presenting them as meaningful waits.
                invalid_waits = int((waits["Avg wait (h)"] < 0).sum())
                waits = waits[
                    waits["Avg wait (h)"].ge(0)
                    & waits["Median wait (h)"].ge(0)
                ].dropna(subset=["Avg wait (h)", "Median wait (h)"])
                if waits.empty:
                    st.warning("No non-negative transition waiting times are available. Check timestamp mapping and event ordering.")
                else:
                    waits = waits.sort_values(
                        ["Median wait (h)", "Avg wait (h)", "Transitions"],
                        ascending=[False, False, False],
                        ignore_index=True,
                    )
                    metric_col = st.selectbox(
                        "Rank bottlenecks by",
                        ["Median wait (h)", "Avg wait (h)"],
                        format_func=lambda x: "Median waiting time" if x.startswith("Median") else "Average waiting time",
                        key="bottleneck_rank_metric",
                    )
                    top_n = min(15, len(waits))
                    bottleneck_limit = st.slider(
                        "Transitions to show", min_value=1, max_value=top_n,
                        value=min(10, top_n), key="bottleneck_limit",
                    )
                    ranked = waits.sort_values(metric_col, ascending=False).head(bottleneck_limit)
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Transitions analysed", f"{len(waits):,}")
                    m2.metric("Longest median wait", fmt_hours(waits["Median wait (h)"].max()))
                    m3.metric("Transitions with recorded events", f"{int(waits['Transitions'].sum()):,}")
                    bottleneck_fig = px.bar(
                        ranked.sort_values(metric_col, ascending=True),
                        x=metric_col,
                        y=ranked.sort_values(metric_col, ascending=True).apply(
                            lambda r: f"{r['From activity']} → {r['To activity']}", axis=1
                        ),
                        orientation="h",
                        labels={metric_col: "Observed waiting time (hours)", "y": "Activity transition"},
                        hover_data=["Transitions", "Avg wait (h)", "Median wait (h)"],
                    )
                    bottleneck_fig.update_layout(
                        height=max(360, 42 * len(ranked)),
                        margin=dict(l=10, r=20, t=20, b=10),
                        yaxis_title=None,
                    )
                    chart(lambda: bottleneck_fig)
                    display_cols = ["From activity", "To activity", "Transitions", "Avg wait (h)", "Median wait (h)"]
                    table(waits[display_cols].head(bottleneck_limit).round(2))
                    if invalid_waits:
                        st.warning(f"Excluded {invalid_waits:,} transitions with negative average waiting time. Review timestamp mapping or event ordering.")
                    st.caption("A longer observed interval is a signal for operational review, not proof of a care delay or poor clinical performance. No thresholds or hospital targets are assumed.")

    tab_case, tab_time = st.tabs(["Case timeline", "Elapsed time"])
    with tab_case:
        ids = C.f[C.case].dropna().astype(str).unique()
        if len(ids) == 0:
            st.info("No cases in the current filters.")
        else:
            if len(ids) > 5000:
                st.caption("Showing the first 5,000 cases; narrow the filters to reach others.")
            choice = st.selectbox("Select a case", ids[:5000], key="flow_case")
            ev = C.f[C.f[C.case].astype(str) == choice].copy()
            if C.time:
                ev = ev.sort_values(C.time, kind="stable")
            ev["Step"] = range(1, len(ev) + 1)
            ev[C.act] = ev[C.act].fillna("Unknown activity").astype(str)

            def timeline():
                use_time = bool(C.time) and ev[C.time].notna().any()
                fig = px.line(ev, x=C.time if use_time else "Step", y=C.act, markers=True, hover_data=["Step"])
                # Color each recorded activity by its mapped patient-journey stage.
                marker_colors = [activity_stage_color(a) for a in ev[C.act]]
                fig.update_traces(line=dict(color="#94A3B8", width=2),
                                  marker=dict(size=10, color=marker_colors,
                                              line=dict(color="#FFFFFF", width=1)))
                fig.update_yaxes(categoryorder="array", categoryarray=list(dict.fromkeys(ev[C.act])),
                                 autorange="reversed", title=None)
                fig.update_layout(height=140 + 34 * ev[C.act].nunique())
                return fig
            chart(timeline)
            legend_cols = st.columns(3)
            legend_items = [("Admission / registration", STAGE_COLORS["admission"]),
                            ("Assessment / diagnostics", STAGE_COLORS["diagnostics"]),
                            ("Treatment", STAGE_COLORS["treatment"]),
                            ("Discharge / completed", STAGE_COLORS["completed"]),
                            ("Transfer / departure", STAGE_COLORS["transfer"]),
                            ("Waiting / delay", STAGE_COLORS["waiting"]),
                            ("Exception / attention", STAGE_COLORS["attention"])]
            for i, (label, color) in enumerate(legend_items):
                with legend_cols[i % 3]:
                    st.markdown(f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{color};margin-right:7px"></span>{escape(label)}', unsafe_allow_html=True)
            st.caption("Colors are inferred from recorded activity names for navigation only; verify mappings for your event log. They do not indicate clinical severity or outcomes.")
            st.caption("Events are ordered by timestamp when available, otherwise by file order.")
            table(ev.drop(columns=["Step"]))
    with tab_time:
        if not need(**{"timestamp": C.time}):
            return
        dur = cached_durations(C.f, C.case, C.time)
        if dur.empty:
            st.info("No cases with usable timestamps.")
            return
        a, b, c = st.columns(3)
        a.metric("Cases with timestamps", f"{len(dur):,}")
        b.metric("Median elapsed", fmt_hours(dur["Elapsed hours"].median()))
        c.metric("90th percentile", fmt_hours(dur["Elapsed hours"].quantile(0.9)))
        chart(lambda: px.histogram(dur, x="Elapsed hours", nbins=30).update_traces(marker_color=PALETTE[0]))
        st.caption("Elapsed time is the span between first and last recorded event, not necessarily length of stay.")
        st.markdown("**Longest observed cases**")
        table(dur.nlargest(20, "Elapsed hours").round({"Elapsed hours": 2}))


@guard
def page_pathways():
    page_header("Clinical Pathways")
    if not need(**{"case ID": C.case, "activity": C.act}):
        return
    render_variants(key="cp")
    st.caption("These are observed sequences from the supplied event log, not clinical recommendations.")


@guard
def page_comparison():
    page_header("Pathway Comparison")
    st.caption("Descriptive comparison of observed pathways. Always computed from the filtered event log.")
    if not need(**{"case ID": C.case, "activity": C.act}):
        return
    variants, seq = cached_variants(C.f, C.case, C.act, C.time)
    if variants.empty:
        st.info("No complete pathways could be assembled from the current filters.")
        return
    head = variants.head(50)
    labels = {v: f"{v} · {n} cases · {p[:70]}"
              for v, n, p in zip(head["Variant"], head["Cases"], head["Observed pathway"])}
    picked = st.multiselect("Pathways to compare (up to 5)", list(labels), default=list(labels)[:3],
                            format_func=labels.get, max_selections=5, key="cmp_pick")
    if len(picked) < 2:
        st.info("Select at least two pathways.")
        return
    sel = variants[variants["Variant"].isin(picked)].copy()
    if C.time:
        dur = cached_durations(C.f, C.case, C.time).merge(seq.rename("Observed pathway"), left_on=C.case, right_index=True)
        med = dur.groupby("Observed pathway")["Elapsed hours"].median().round(1).rename("Median elapsed (h)")
        sel = sel.merge(med, on="Observed pathway", how="left")
    c1, c2 = st.columns(2)
    with c1:
        chart(lambda: px.bar(sel, x="Variant", y="Cases", hover_data=["Observed pathway"]).update_traces(marker_color=PALETTE[0]),
              height=320)
    with c2:
        chart(lambda: px.bar(sel, x="Variant", y="Median elapsed (h)", hover_data=["Observed pathway"])
              .update_traces(marker_color=PALETTE[1]) if "Median elapsed (h)" in sel else None,
              "Median elapsed time needs a parseable timestamp column.", height=320)
    table(sel)
    if len(picked) == 2:
        a, b = (set(sel.loc[sel["Variant"] == v, "Observed pathway"].iloc[0].split(" → ")) for v in picked)
        d1, d2 = st.columns(2)
        d1.markdown(f"**Only in {picked[0]}:** " + (", ".join(sorted(a - b)) or "—"))
        d2.markdown(f"**Only in {picked[1]}:** " + (", ".join(sorted(b - a)) or "—"))


@guard
def page_beds():
    page_header("Bed & Discharge Management")
    st.caption("Operational indicators appear only when the event log contains suitable fields. No bed availability is invented.")
    raw = C.raw
    bed = pm.find_col(raw, ["bed status", "bed availability", "bed id", "bed number", "bed occupied"])
    disch = pm.find_col(raw, ["discharge", "discharged at", "discharge date", "discharge time"])
    adm = pm.find_col(raw, ["admission", "admitted at", "admission date", "admission time"])
    a, b, c = st.columns(3)
    a.metric("Cases in current filter", f"{C.n_cases:,}")
    b.metric("Admission field", "Available" if adm else "Not detected")
    c.metric("Discharge field", "Available" if disch else "Not detected")
    if bed:
        counts = top_counts(C.f[bed], "Recorded value", 30).rename(columns={"Events": "Records"})
        chart(lambda: px.bar(counts, x="Recorded value", y="Records", title="Recorded bed-related values"))
    else:
        st.info("No bed/occupancy field was detected, so occupancy and available-bed counts cannot be calculated.")
    if adm or disch:
        cols = [c for c in [C.case, adm, disch, C.dept, C.status] if c]
        table(C.f[cols].drop_duplicates().head(500))
    else:
        st.info("Add verified admission/discharge timestamps to the source data to enable discharge-delay analysis.")
    st.warning("This is an analytics view, not a live bed-management system. Confirm all operational figures "
               "against the hospital's authoritative system.")


@guard
def page_coordination():
    page_header("Care coordination")
    st.write("Department-level overview based on the available fields.")
    if C.synthetic:
        st.warning("Departments here are synthetic demo labels, not source data.")
    d = top_counts(C.f[C.dept], "Department", 50).rename(columns={"Events": "Event records"})
    kpis([
        ("Departments", f"{C.f[C.dept].nunique():,}"),
        ("Event records", f"{len(C.f):,}"),
        ("Busiest department", escape(str(d.iloc[0]["Department"])) if len(d) else "—",
         f"{int(d.iloc[0]['Event records']):,} events" if len(d) else ""),
    ])
    st.write("")
    table(d, csv_name="departments.csv")
    chart(lambda: px.bar(d, x="Department", y="Event records").update_traces(marker_color=PALETTE[0]))


_TEAM_HINTS = ("zone", "unit", "ward", "service", "consult", "department", "triage", "disposition", "team", "clinic")
_TEAM_SKIP = ("month", "day", "age", "timestamp", "time", "date")


def _team_columns():
    """Low-cardinality fields that can stand in for care units / services when no staff column exists."""
    cols = []
    for col in C.f.columns:
        name = str(col).lower()
        if col in (C.case, C.time, C.act) or any(name == k or name.endswith("_" + k) for k in _TEAM_SKIP):
            continue
        n = C.f[col].nunique(dropna=True)
        if 2 <= n <= 40:
            cols.append(col)
    cols.sort(key=lambda c: (not any(h in str(c).lower() for h in _TEAM_HINTS), str(c)))
    return cols


@guard
def page_teams():
    page_header("Care Teams")
    if C.f.empty:
        st.info("No events to show.")
        return

    if C.staff:
        w = C.f.groupby([C.dept, C.staff]).size().reset_index(name="Event records")
        table(w.sort_values("Event records", ascending=False))
        top = w.nlargest(30, "Event records")
        chart(lambda: px.bar(top, x=C.staff, y="Event records", color=C.dept, barmode="group"))
        st.caption("Showing the 30 busiest staff/department combinations. Verify the staff mapping before relying on it.")
        return

    st.caption("This event log has no staff or resource column, so teams are shown by care unit and service "
               "fields instead. These describe where and for whom work happened, not individual staff. "
               "Map a real staff column under **Field mapping** to see per-staff workload.")
    cols = _team_columns()
    if not cols:
        st.info("No suitable grouping fields were found. Fields available: " + ", ".join(map(str, C.raw.columns)))
        return

    col = st.selectbox("Group workload by", cols, key="teams_group",
                       format_func=lambda c: str(c).replace("_", " ").capitalize()
                       + (" (demo labels)" if C.synthetic and c == C.dept else ""))
    d = C.f.assign(_grp=C.f[col].fillna("Unknown").astype(str))
    agg = {"Events": ("_grp", "size")}
    if C.case:
        agg["Cases"] = (C.case, "nunique")
    summary = d.groupby("_grp").agg(**agg).reset_index().rename(columns={"_grp": str(col)})
    summary["Share of events (%)"] = (summary["Events"] / summary["Events"].sum() * 100).round(1)
    summary = summary.sort_values("Events", ascending=False)

    kpis([("Groups", f"{len(summary):,}"),
          ("Events", f"{int(summary['Events'].sum()):,}"),
          ("Busiest group", str(summary.iloc[0][str(col)])[:28]),
          ("Busiest share", f"{summary.iloc[0]['Share of events (%)']:.1f}%")])
    st.write("")

    n = pick_top(len(summary), "Groups to chart", "teams_n", default=15, cap=40)
    top = summary.head(n)

    def bar():
        fig = px.bar(top, x="Events", y=str(col), orientation="h",
                     hover_data=[c for c in ("Cases", "Share of events (%)") if c in top.columns])
        fig.update_traces(marker_color=PALETTE[0])
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=120 + 30 * len(top))
        return fig
    chart(bar)

    if C.act:
        st.markdown("**Activity mix by group**")
        keep = summary.head(12)[str(col)].tolist()
        m = (d[d["_grp"].isin(keep)].assign(_act=lambda x: x[C.act].fillna("Unknown activity").astype(str))
             .pivot_table(index="_grp", columns="_act", values=C.act, aggfunc="size", fill_value=0))
        chart(lambda: None if m.empty else px.imshow(
            m, aspect="auto", text_auto=True, labels=dict(x="Activity", y=str(col), color="Events"))
            .update_layout(height=140 + 32 * len(m)), "Not enough data for this view.")
        st.caption("Shows the 12 busiest groups. Darker cells mean more recorded events of that activity.")

    table(summary.head(200))
    st.download_button("Export team workload CSV", summary.to_csv(index=False).encode("utf-8"),
                       "careflow_team_workload.csv", "text/csv", key="teams_dl")


@guard
def page_reports():
    page_header("Reports & Outcomes")
    st.write("Generate an overview from the loaded event log.")
    a, b, c = st.columns(3)
    a.metric("Event records", f"{len(C.f):,}")
    b.metric("Cases / patients", f"{C.n_cases:,}")
    c.metric("Activities", f"{C.f[C.act].nunique():,}" if C.act else "Not detected")
    if C.case and C.time:
        dur = cached_durations(C.f, C.case, C.time)
        if not dur.empty:
            o1, o2 = st.columns(2)
            o1.metric("Cases with usable timestamps", f"{len(dur):,}")
            o2.metric("Median observed elapsed time", fmt_hours(dur["Elapsed hours"].median()))
            st.caption("Elapsed time is the span between first and last recorded event, not necessarily length of stay.")
    summary = C.f.describe(include="all").transpose().astype(str).reset_index(names="Field")
    table(summary)
    st.download_button("Download filtered event log CSV", C.f.to_csv(index=False).encode("utf-8"),
                       "careflow_filtered_event_log.csv", "text/csv")


@guard
def page_quality():
    page_header("Data Quality Studio")
    st.caption("Review missing fields, duplicates, timestamp quality and event-log readiness before interpreting analytics.")
    f = C.f
    q = st.columns(4)
    q[0].metric("Rows", f"{len(f):,}")
    q[1].metric("Columns", f"{len(f.columns):,}")
    q[2].metric("Duplicate rows", f"{int(f.duplicated().sum()):,}")
    q[3].metric("Rows with missing values", f"{int(f.isna().any(axis=1).sum()):,}")
    roles = {C.case: "Case ID", C.act: "Activity", C.time: "Timestamp", C.dept: "Department",
             C.status: "Status", C.staff: "Staff/resource"}
    rep = pd.DataFrame({
        "Field": f.columns.astype(str),
        "Detected role": [roles.get(c, "Other") for c in f.columns],
        "Missing values": [int(f[c].isna().sum()) for c in f.columns],
        "Missing %": [round(float(f[c].isna().mean() * 100), 2) for c in f.columns],
        "Unique values": [int(f[c].nunique(dropna=True)) for c in f.columns],
    })
    table(rep)
    if C.time:
        raw_t = C.raw[C.time]
        t1, t2 = st.columns(2)
        t1.metric("Missing / unparseable timestamps", f"{int(raw_t.isna().sum()):,}")
        t2.metric("Timestamp parse success", f"{100 * raw_t.notna().mean():.1f}%" if len(raw_t) else "N/A")
    else:
        st.warning("No timestamp column mapped. Time-based ordering and elapsed-time analysis are unavailable.")
    if C.case and C.act:
        st.caption("Process-mining readiness: case and activity columns are mapped. Confirm that case IDs are "
                   "pseudonymised and events are correctly ordered before operational use.")
    st.download_button("Download data-quality report", rep.to_csv(index=False).encode("utf-8"),
                       "careflow_data_quality_report.csv", "text/csv")


@guard
def page_dictionary():
    page_header("Data Dictionary")
    st.caption("Columns in the loaded event log and the process-mining role each was mapped to.")
    role_names = {C.case: "Case / encounter identifier", C.act: "Activity / event", C.time: "Timestamp",
                  C.status: "Status / outcome", C.staff: "Staff / resource",
                  C.dept: "Synthetic demo department (not source data)" if C.synthetic else "Department / unit"}
    d = pd.DataFrame([{
        "Source field": str(c), "Detected role": role_names.get(c, "Unmapped"), "Data type": str(C.raw[c].dtype),
        "Example value": str(C.raw[c].dropna().iloc[0])[:120] if C.raw[c].notna().any() else "(all values missing)",
    } for c in C.raw.columns])
    table(d)
    st.download_button("Export data dictionary", d.to_csv(index=False).encode("utf-8"), "careflow_data_dictionary.csv", "text/csv")
    st.info("Role detection is based on column names. Review or override it under Field mapping in the sidebar.")


@guard
def page_insights():
    page_header("Insights & Benchmarks")
    st.caption("Descriptive insights from the loaded event log, not external hospital benchmarks or clinical recommendations.")
    f = C.f
    a, b, c = st.columns(3)
    a.metric("Records in view", f"{len(f):,}")
    b.metric("Distinct cases", f"{C.n_cases:,}" if C.case else "Not detected")
    c.metric("Missing-value cells", f"{int(f.isna().sum().sum()):,}")
    l, r = st.columns(2)
    with l:
        st.markdown("#### Data completeness by field")
        comp = pd.DataFrame({"Field": f.columns.astype(str),
                             "Completeness (%)": [round(float(f[c].notna().mean() * 100), 1) for c in f.columns]})
        chart(lambda: px.bar(comp.sort_values("Completeness (%)").head(18), x="Completeness (%)", y="Field",
                             orientation="h", range_x=[0, 100], color="Completeness (%)"))
    with r:
        st.markdown("#### Event volume by activity")
        chart(lambda: fig_bar_counts(C.act, "Activity", 12, height=420), "No activity column is mapped.")
    if C.case:
        st.markdown("#### Events per case")
        per_case = f.groupby(C.case).size().rename("Events per case").reset_index()
        chart(lambda: px.histogram(per_case, x="Events per case", nbins=25).update_traces(marker_color=PALETTE[0]))
        table(per_case["Events per case"].describe().round(2).rename_axis("Statistic").reset_index())
    st.info("Validate definitions and clinical context with qualified staff before operational use.")


@guard
def page_governance():
    page_header("Security & Governance")
    f = C.f
    a, b, c = st.columns(3)
    a.metric("Rows", f"{len(f):,}")
    b.metric("Columns", f"{len(f.columns):,}")
    c.metric("Rows with any missing data", f"{int(f.isna().any(axis=1).sum()):,}")
    for label, col in [("case identifier", C.case), ("activity", C.act), ("timestamp", C.time)]:
        (st.info if col else st.warning)(
            f"Detected {label} field: {col}" if col else f"No {label} column mapped. Use Field mapping in the sidebar.")
    st.markdown("#### Data-handling checklist")
    st.markdown(
        "- Use pseudonymised case IDs; avoid names, MRNs and free-text clinical notes in the event log.\n"
        "- Do not commit identifiable patient data or secrets to a public repository.\n"
        "- Uploaded files stay in this browser session only.\n"
        "- Tasks, profiles and reminders are session-only until backed by a protected, audited database."
    )


@guard
def page_tasks():
    page_header("Task & Escalation Center", chips=False)
    st.caption("Track follow-up work in this active session. Tasks are not yet saved to a shared database or hospital system.")
    if "careflow_tasks" not in st.session_state:
        st.session_state.careflow_tasks = [
            {"Task":"Review pathway deviation", "Owner":"Pathway Lead", "Priority":"High", "Status":"Open", "Due date":"Not set"},
            {"Task":"Validate event-log timestamps", "Owner":"Data Quality Team", "Priority":"Medium", "Status":"In progress", "Due date":"Not set"},
        ]
    with st.form("careflow_add_task_form", clear_on_submit=True):
        st.markdown("#### Create a task")
        c1, c2 = st.columns(2)
        with c1:
            task_title = st.text_input("Task title")
            task_owner = st.text_input("Assigned owner / team")
            task_due = st.date_input("Due date")
        with c2:
            task_priority = st.selectbox("Priority", ["High", "Medium", "Low"])
            task_status = st.selectbox("Status", ["Open", "In progress", "Blocked", "Done"])
        add_task = st.form_submit_button("Add task", use_container_width=True)
    if add_task:
        if task_title.strip():
            st.session_state.careflow_tasks.append({"Task":task_title.strip(), "Owner":task_owner.strip() or "Unassigned", "Priority":task_priority, "Status":task_status, "Due date":str(task_due)})
            st.success("Task added for this session.")
        else:
            st.error("Enter a task title first.")
    tasks_df = pd.DataFrame(st.session_state.careflow_tasks)
    if not tasks_df.empty:
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Total tasks", len(tasks_df))
        m2.metric("Open", int((tasks_df["Status"] == "Open").sum()))
        m3.metric("In progress", int((tasks_df["Status"] == "In progress").sum()))
        m4.metric("High priority", int((tasks_df["Priority"] == "High").sum()))
        st.dataframe(tasks_df, use_container_width=True, hide_index=True)
        st.download_button("Export tasks CSV", tasks_df.to_csv(index=False).encode("utf-8"), "careflow_tasks.csv", "text/csv")
    st.warning("For real hospital use, connect tasks to a protected database with role-based permissions and an audit trail before relying on them operationally.")


@guard
def page_notifications():
    page_header("Notifications Center", chips=False)
    st.caption("Session-level reminders and app notices. These are not connected to a live hospital alerting system.")
    if "careflow_notifications" not in st.session_state:
        st.session_state.careflow_notifications = [
            {"Type": "Data quality", "Title": "Review event-log quality", "Details": "Check missing fields and timestamp parsing in Data Quality Studio.", "Status": "Unread"},
            {"Type": "Security", "Title": "Protect sensitive information", "Details": "Avoid committing identifiable patient data or secrets to a public repository.", "Status": "Unread"},
        ]
    with st.form("careflow_add_notification_form", clear_on_submit=True):
        n1, n2 = st.columns(2)
        with n1:
            notification_title = st.text_input("Reminder title")
            notification_type = st.selectbox("Category", ["General", "Data quality", "Security", "Reporting", "Task follow-up"])
        with n2:
            notification_details = st.text_area("Reminder details")
            notification_status = st.selectbox("Initial status", ["Unread", "Read"])
        add_notification = st.form_submit_button("Add reminder", use_container_width=True)
    if add_notification:
        if notification_title.strip():
            st.session_state.careflow_notifications.insert(0, {"Type": notification_type, "Title": notification_title.strip(), "Details": notification_details.strip(), "Status": notification_status})
            st.success("Reminder added for this session.")
        else:
            st.error("Enter a reminder title.")
    notices_df = pd.DataFrame(st.session_state.careflow_notifications)
    if not notices_df.empty:
        unread = int((notices_df["Status"] == "Unread").sum())
        st.metric("Unread reminders", unread)
        st.dataframe(notices_df, use_container_width=True, hide_index=True)
        if st.button("Mark all reminders as read", use_container_width=True):
            for notice in st.session_state.careflow_notifications:
                notice["Status"] = "Read"
            st.rerun()
        st.download_button("Export reminders", notices_df.to_csv(index=False).encode("utf-8"), "careflow_reminders.csv", "text/csv")
    st.warning("Reminders are session-only. They are not sent as email, SMS, push notifications, or clinical alerts.")


@guard
def page_saved():
    page_header("Saved Workspace", chips=False)
    st.caption("Save a named snapshot of the current dataset and filters. Saved views are temporary and session-only.")
    if "careflow_saved_views" not in st.session_state:
        st.session_state.careflow_saved_views = []
    with st.form("careflow_saved_workspace_form", clear_on_submit=True):
        view_name = st.text_input("Workspace name", placeholder="e.g. Monthly pathway review")
        view_notes = st.text_area("Notes", placeholder="What are you reviewing?")
        save_view = st.form_submit_button("Save current workspace", use_container_width=True)
    if save_view:
        if view_name.strip():
            st.session_state.careflow_saved_views.insert(0, {"Name":view_name.strip(),"Page":st.session_state.get("careflow_page", ""),"Data source":C.source,"Rows in current view":int(len(C.f)),"Department filter":str(C.dept_summary),"Active filters":C.active or "None","Notes":view_notes.strip()})
            st.success("Workspace saved for this session.")
        else:
            st.error("Enter a workspace name first.")
    if st.session_state.careflow_saved_views:
        views_df = pd.DataFrame(st.session_state.careflow_saved_views)
        st.dataframe(views_df, use_container_width=True, hide_index=True)
        st.download_button("Export saved workspaces", views_df.to_csv(index=False).encode("utf-8"), "careflow_saved_workspaces.csv", "text/csv")
        if st.button("Clear saved workspaces"):
            st.session_state.careflow_saved_views = []
            st.rerun()
    else:
        st.markdown('<div class="cf-feature-card"><div class="cf-feature-title">Your analysis workspace, organized</div><div class="cf-feature-copy">Save a named snapshot of the dataset and filters you are reviewing. For now, saved views exist only during the current session.</div></div>', unsafe_allow_html=True)


@guard
def page_prefs():
    page_header("Display Preferences", chips=False)
    st.caption("Personalize your review experience. Settings apply only to the active session.")
    if "careflow_display_preferences" not in st.session_state:
        st.session_state.careflow_display_preferences = {"density":"Comfortable","chart_labels":True,"compact_tables":False}
    prefs = st.session_state.careflow_display_preferences
    with st.form("careflow_display_preferences_form"):
        density = st.radio("Layout density", ["Comfortable","Compact"], horizontal=True, index=0 if prefs["density"] == "Comfortable" else 1)
        chart_labels = st.checkbox("Show chart labels where supported", value=prefs["chart_labels"])
        compact_tables = st.checkbox("Prefer compact table views", value=prefs["compact_tables"])
        save_prefs = st.form_submit_button("Save preferences", use_container_width=True)
    if save_prefs:
        st.session_state.careflow_display_preferences = {"density":density,"chart_labels":chart_labels,"compact_tables":compact_tables}
        st.success("Preferences saved for this session.")
    p1,p2,p3 = st.columns(3)
    p1.markdown('<div class="cf-feature-card"><div class="cf-feature-title">Comfortable reading</div><div class="cf-feature-copy">Balanced spacing for longer review sessions.</div></div>', unsafe_allow_html=True)
    p2.markdown('<div class="cf-feature-card"><div class="cf-feature-title">Clear visual hierarchy</div><div class="cf-feature-copy">Consistent headings, cards, and chart containers.</div></div>', unsafe_allow_html=True)
    p3.markdown('<div class="cf-feature-card"><div class="cf-feature-title">Responsive workspace</div><div class="cf-feature-copy">Designed for desktop and smaller screens.</div></div>', unsafe_allow_html=True)
    st.info("Persistent preferences require secure user-specific storage.")


@guard
def page_help():
    page_header("Help Center", chips=False)
    st.caption("Guidance for using the analytics workspace and troubleshooting common issues.")
    q1,q2,q3 = st.columns(3)
    q1.metric("Help topics", "6")
    q2.metric("Support channel", "Form")
    q3.metric("Service status", "App session")
    with st.expander("How do I load my actual event log?", expanded=True):
        st.write("Place the approved CSV file beside app.py in the repository using one of the configured filenames: careflow_event_log.csv, event_log_ED_MMA_2026.csv, or sample_event_log.csv. Do not commit identifiable patient data to a public repository. You can also upload a CSV under Data source in the sidebar (kept in this browser session only), and place process-mining output CSVs in a pm_outputs/ folder.")
    with st.expander("Why are department names marked as synthetic?"):
        st.write("If the source event log has no department field, CareFlow creates demo labels for visualization. These are not real department assignments and should not be used for operational decisions.")
    with st.expander("Why is a chart or metric missing?"):
        st.write("CareFlow detects columns by name. Ensure your event log includes appropriate case/encounter ID, activity/event, and timestamp columns. Rename source columns clearly if detection fails.")
    with st.expander("How do I troubleshoot login problems?"):
        st.write("Confirm SUPABASE_URL and SUPABASE_KEY are correctly configured in Streamlit Cloud Secrets, and check whether email verification is enabled in Supabase. Never share passwords or secret keys in support requests.")
    with st.expander("Are tasks, profiles, and support requests permanently saved?"):
        st.write("Not by this version of the app. Some entries are stored only in the active Streamlit session. Configure secure database tables, access controls, retention, and audit logging before using them as persistent hospital records.")
    with st.expander("Can CareFlow provide clinical recommendations?"):
        st.write("No. Current features summarize observed event-log patterns. They are not a diagnostic, triage, or treatment recommendation system.")
    st.markdown("#### Contact support")
    with st.form("careflow_support_form", clear_on_submit=True):
        support_topic = st.selectbox("Topic", ["Login / account", "Data loading", "Charts / reports", "Task management", "Security / privacy", "Other"])
        support_email = st.text_input("Reply email (optional)", value=st.session_state.careflow_user.get("email", ""))
        support_message = st.text_area("Describe the issue (do not include patient-identifying information)")
        send_support = st.form_submit_button("Submit support request", use_container_width=True)
    if send_support:
        if support_message.strip():
            if "careflow_support_requests" not in st.session_state:
                st.session_state.careflow_support_requests = []
            st.session_state.careflow_support_requests.append({"Topic":support_topic, "Email":support_email.strip(), "Message":support_message.strip()})
            st.success("Support request captured for this session. It has not been emailed or sent to a support team.")
        else:
            st.error("Please describe the issue before submitting.")


@guard
def page_profile():
    page_header("Profile", chips=False)
    st.caption("Choose the profile that matches how you use CareFlow. Profile details are currently saved only for this browser session.")

    user = st.session_state.careflow_user
    email = user.get("email", "")
    profile_type = st.radio(
        "Profile type",
        ["Client / Patient", "Doctor / Clinician"],
        horizontal=True,
        key="careflow_profile_type",
        help="This selects the profile form only; it does not grant or restrict system permissions.",
    )

    if profile_type == "Client / Patient":
        st.markdown("### 👤 Client profile")
        st.info("Only enter information needed for your account. Do not enter medical record numbers or sensitive clinical details in this demo profile.")
        with st.form("client_profile_form"):
            c1, c2 = st.columns(2)
            with c1:
                client_name = st.text_input("Full name")
                client_age = st.number_input("Age", min_value=0, max_value=120, value=18)
                client_gender = st.selectbox("Gender", ["Prefer not to say", "Female", "Male", "Other"])
            with c2:
                client_phone = st.text_input("Contact number (optional)")
                client_city = st.text_input("City / Location (optional)")
                client_preferred_contact = st.selectbox("Preferred contact method", ["Email", "Phone", "No preference"])
            st.text_input("Account email", value=email, disabled=True)
            client_notes = st.text_area("Accessibility or communication preference (optional)", placeholder="Avoid sharing diagnosis, patient IDs, or other sensitive health details.")
            client_submitted = st.form_submit_button("Save client profile", use_container_width=True)
        if client_submitted:
            st.session_state["careflow_client_profile"] = {
                "Name": client_name.strip(), "Age": client_age, "Gender": client_gender,
                "Contact number": client_phone.strip(), "City": client_city.strip(),
                "Preferred contact": client_preferred_contact, "Email": email,
                "Communication preference": client_notes.strip(),
            }
            st.success("Client profile saved for this session.")
            st.warning("This profile is not permanently stored or shared with a care team. Do not use it as a clinical record.")
        saved_client = st.session_state.get("careflow_client_profile")
        if saved_client:
            with st.expander("View saved client profile"):
                st.json(saved_client)

    else:
        st.markdown("### 🩺 Doctor / clinician profile")
        with st.form("doctor_profile_form"):
            st.markdown("#### Personal information")
            col1, col2 = st.columns(2)
            with col1:
                doctor_name = st.text_input("Doctor / clinician name")
                doctor_gender = st.selectbox("Gender", ["Prefer not to say", "Female", "Male", "Other"])
                doctor_phone = st.text_input("Contact number")
            with col2:
                doctor_department = st.selectbox("Department", ["Emergency", "General Medicine", "Cardiology", "Neurology", "Paediatrics", "Orthopaedics", "Surgery", "Radiology", "Other"])
                doctor_designation = st.selectbox("Designation", ["Doctor", "Resident Doctor", "Consultant", "Senior Consultant", "Department Head", "Nurse", "Care Coordinator", "Analyst", "Other"])
                doctor_hospital = st.text_input("Hospital / healthcare facility")
            st.text_input("Account email", value=email, disabled=True)
            st.markdown("#### Professional information")
            col3, col4 = st.columns(2)
            with col3:
                doctor_qualification = st.text_input("Qualification")
                doctor_specialization = st.text_input("Specialization")
            with col4:
                doctor_experience = st.number_input("Years of experience", min_value=0, max_value=70, value=0)
                doctor_location = st.text_input("City / Location")
            doctor_bio = st.text_area("Professional bio (optional)")
            doctor_submitted = st.form_submit_button("Save clinician profile", use_container_width=True)
        if doctor_submitted:
            st.session_state["careflow_doctor_profile"] = {
                "Name": doctor_name.strip(), "Gender": doctor_gender, "Contact number": doctor_phone.strip(),
                "Department": doctor_department, "Designation": doctor_designation,
                "Hospital": doctor_hospital.strip(), "Email": email,
                "Qualification": doctor_qualification.strip(), "Specialization": doctor_specialization.strip(),
                "Experience years": doctor_experience, "Location": doctor_location.strip(), "Bio": doctor_bio.strip(),
            }
            st.success("Clinician profile saved for this session.")
            st.warning("This is a profile form, not professional credential verification. Details are not permanently stored yet.")
        saved_doctor = st.session_state.get("careflow_doctor_profile")
        if saved_doctor:
            with st.expander("View saved clinician profile"):
                st.json(saved_doctor)


# ======================================================================
# PROCESS DISCOVERY & METRICS  (reads the files written by pipeline/*.py)
# ======================================================================
_APP_DIR = Path(__file__).resolve().parent
PM_DIRS = [Path("pm_outputs"), Path("process_mining_outputs"), Path("."),
           _APP_DIR / "pm_outputs", _APP_DIR]


def _pm_find(name):
    """Locate an output file in pm_outputs/, the repo root, or beside app.py."""
    for d in PM_DIRS:
        p = d / name
        if p.is_file():
            return p
    return None


@st.cache_data(show_spinner=False)
def _pm_file(path, mtime):
    return pd.read_csv(path)


def _pm_read(name):
    """Return a DataFrame for the named output file, or None if missing/unreadable."""
    p = _pm_find(name)
    if p is None:
        return None
    try:
        return _pm_file(str(p), p.stat().st_mtime)
    except Exception:  # noqa: BLE001
        return None


def _fmt_minutes(m):
    if m is None or pd.isna(m):
        return "—"
    return f"{m / 60:,.1f} h" if m >= 120 else f"{m:,.0f} min"


@guard
def page_discovery():
    page_header("Process Discovery & Metrics",
                "Process model and metrics produced by the offline process-mining pipeline.", chips=False)
    st.caption("Observed workflow from recorded events. This describes what happened; it does not recommend "
               "clinical treatment. These results come from files in pm_outputs/, not from the sidebar filters.")

    pathways = _pm_read("pathway_frequencies.csv")
    trans = _pm_read("transition_metrics.csv")
    cases = _pm_read("case_metrics.csv")
    model_png = _pm_find("careflow_process_map.png")

    if pathways is None and trans is None and cases is None and model_png is None:
        st.info("No pipeline outputs found. Run `python pipeline/calculate_metrics.py --input <event_log.csv>` and "
                "`python pipeline/discover_process.py --input <event_log.csv>`, then place the results in a "
                "`pm_outputs/` folder beside app.py.")
        return

    if cases is not None:
        dur = cases["observed_duration_minutes"]
        kpis([
            ("Cases", f"{len(cases):,}"),
            ("Distinct pathways", f"{len(pathways):,}" if pathways is not None else "—"),
            ("Distinct transitions", f"{len(trans):,}" if trans is not None else "—"),
            ("Median case duration", _fmt_minutes(dur.median())),
            ("90th percentile", _fmt_minutes(dur.quantile(0.9))),
        ])
        st.write("")

    tab_model, tab_paths, tab_trans, tab_cases = st.tabs(
        ["Process model", "Pathway frequencies", "Transition metrics", "Case durations"])

    with tab_model:
        if model_png is not None:
            st.image(str(model_png), caption="Petri net discovered with the Inductive Miner (PM4Py). "
                     "Black boxes are silent transitions that allow a step to be skipped or the flow to split/join.",
                     **WIDE)
            st.download_button("Download process map (PNG)", model_png.read_bytes(),
                               "careflow_process_map.png", "image/png")
            st.caption("The Inductive Miner favours a model that replays every recorded case. As a result the "
                       "model is permissive: it allows many activity orders that rarely or never occur. Use the "
                       "Pathway frequencies tab to see which sequences actually dominate.")
        else:
            st.info("careflow_process_map.png was not found in pm_outputs/.")

    with tab_paths:
        if pathways is None:
            st.info("pathway_frequencies.csv was not found in pm_outputs/.")
        else:
            top10 = pathways.head(10)["case_percent"].sum()
            a, b = st.columns(2)
            a.metric("Most common pathway", f"{pathways.iloc[0]['case_percent']:.1f}% of cases")
            b.metric("Top 10 pathways cover", f"{top10:.1f}% of cases")
            q = st.text_input("Search pathways by activity name", key="disc_path_q")
            shown = pathways
            if q.strip():
                shown = pathways[pathways["pathway"].str.contains(q.strip(), case=False, regex=False)]
            if shown.empty:
                st.info("No pathway contains that text.")
            else:
                n = pick_top(len(shown), "Pathways to chart", "disc_path_n", default=10)
                top = shown.head(n).copy()
                top["Variant"] = [f"V{i}" for i in top.index + 1]

                def bar():
                    fig = px.bar(top, x="case_count", y="Variant", orientation="h",
                                 hover_data=["pathway", "case_percent"],
                                 labels={"case_count": "Cases", "case_percent": "% of cases"})
                    fig.update_traces(marker_color=PALETTE[0])
                    fig.update_layout(yaxis={"autorange": "reversed"}, height=120 + 30 * len(top))
                    return fig
                chart(bar)
                table(shown.rename(columns={"pathway": "Observed pathway", "case_count": "Cases",
                                            "case_percent": "Share of cases (%)"}).head(200))
                st.download_button("Export pathways CSV", shown.to_csv(index=False).encode("utf-8"),
                                   "careflow_pathway_frequencies.csv", "text/csv", key="disc_path_dl")

    with tab_trans:
        if trans is None:
            st.info("transition_metrics.csv was not found in pm_outputs/.")
        else:
            min_n = st.slider("Minimum transitions to include", 1, int(max(trans["transition_count"].max(), 2)),
                              1, key="disc_trans_min")
            t = trans[trans["transition_count"] >= min_n].copy()
            t["Step"] = t["from_activity"] + " → " + t["to_activity"]

            def waits():
                w = t.dropna(subset=["median_minutes"]).nlargest(15, "median_minutes")
                if w.empty:
                    return None
                fig = px.bar(w, x="median_minutes", y="Step", orientation="h",
                             hover_data=["transition_count", "average_minutes"],
                             labels={"median_minutes": "Median wait (min)"})
                fig.update_traces(marker_color=PALETTE[1])
                fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=140 + 28 * len(w))
                return fig
            st.markdown("**Longest median gaps between consecutive events**")
            chart(waits, "No transitions meet the minimum count.")
            st.caption("Long gaps can reflect documentation delays as well as real queues. "
                       "Negative time intervals are excluded from time statistics.")
            table(t.drop(columns=["Step"]).rename(columns={
                "from_activity": "From", "to_activity": "To", "transition_count": "Transitions",
                "valid_time_count": "Valid timings", "average_minutes": "Avg (min)", "median_minutes": "Median (min)"}))
            st.download_button("Export transitions CSV", t.drop(columns=["Step"]).to_csv(index=False).encode("utf-8"),
                               "careflow_transition_metrics.csv", "text/csv", key="disc_trans_dl")

    with tab_cases:
        if cases is None:
            st.info("case_metrics.csv was not found in pm_outputs/.")
        else:
            dur_h = (cases["observed_duration_minutes"] / 60).rename("Observed duration (h)")
            cap = float(dur_h.quantile(0.99))
            chart(lambda: px.histogram(dur_h[dur_h <= cap].to_frame(), x="Observed duration (h)", nbins=40)
                  .update_traces(marker_color=PALETTE[0]).update_layout(height=320))
            st.caption(f"Duration is first to last recorded event. Chart trimmed at the 99th percentile "
                       f"({cap:,.1f} h) so a few very long cases do not flatten it.")
            ev = cases["event_count"].value_counts().sort_index().rename_axis("Events per case") \
                .reset_index(name="Cases")
            chart(lambda: px.bar(ev, x="Events per case", y="Cases").update_traces(marker_color=PALETTE[1])
                  .update_layout(height=280, xaxis=dict(dtick=1)))
            st.caption("Individual case IDs are intentionally not listed on this page.")
    source_note("pm_outputs/ (generated by pipeline/calculate_metrics.py and pipeline/discover_process.py)")



# ======================================================================
# PREDICTIVE MODEL (parameters are chosen manually by the user)
# ======================================================================
@st.cache_data(show_spinner=False)
def cached_case_table(d, case, act, time):
    """One row per case: first-event fields plus start time, elapsed hours and event counts."""
    d = d.copy()
    d[time] = pd.to_datetime(d[time], errors="coerce")
    d = d.dropna(subset=[case, time]).sort_values([case, time], kind="stable")
    grp = d.groupby(case, sort=False)
    out = d.drop_duplicates(case, keep="first").set_index(case)
    out["__start"] = grp[time].min()
    out["__elapsed_h"] = (grp[time].max() - grp[time].min()).dt.total_seconds() / 3600
    out["__events"] = grp.size()
    if act:
        out["__acts"] = grp[act].nunique()
    return out


def train_case_model(X, elapsed, start, *, task, algo, hp, test_share, seed, split, threshold, log_target, balanced):
    """Fit a scikit-learn pipeline with the exact parameters supplied; returns the model and honest hold-out metrics."""
    import numpy as np
    from sklearn import metrics as skm
    from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
    from sklearn.ensemble import (GradientBoostingClassifier, GradientBoostingRegressor,
                                  RandomForestClassifier, RandomForestRegressor)
    from sklearn.impute import SimpleImputer
    from sklearn.inspection import permutation_importance
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    X = X.copy()
    num_cols = [c for c in X.columns if pd.api.types.is_numeric_dtype(X[c]) and not pd.api.types.is_bool_dtype(X[c])]
    cat_cols = [c for c in X.columns if c not in num_cols]
    for c in cat_cols:
        X[c] = X[c].fillna("Unknown").astype(str)
    reg = task == "reg"
    y = elapsed.astype(float) if reg else (elapsed > threshold).astype(int)

    n = len(X)
    n_test = max(5, int(round(n * test_share)))
    if split == "chrono":
        order = np.argsort(start.values, kind="stable")
    else:
        order = np.random.RandomState(seed).permutation(n)
    test_idx, train_idx = order[-n_test:], order[:-n_test]
    Xtr, Xte, ytr, yte = X.iloc[train_idx], X.iloc[test_idx], y.iloc[train_idx], y.iloc[test_idx]
    if not reg and ytr.nunique() < 2:
        raise ValueError("With this threshold every training case falls in one class. Change the threshold or split method.")

    try:
        ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:  # older scikit-learn
        ohe = OneHotEncoder(handle_unknown="ignore", sparse=False)
    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), num_cols),
        ("cat", ohe, cat_cols)], remainder="drop")

    cw = "balanced" if (balanced and not reg) else None
    depth = hp.get("max_depth") or None
    if algo == "rf":
        est = (RandomForestRegressor(n_estimators=hp["n_estimators"], max_depth=depth, min_samples_leaf=hp["min_samples_leaf"],
                                     random_state=seed, n_jobs=-1) if reg else
               RandomForestClassifier(n_estimators=hp["n_estimators"], max_depth=depth, min_samples_leaf=hp["min_samples_leaf"],
                                      class_weight=cw, random_state=seed, n_jobs=-1))
    elif algo == "gb":
        kw = dict(n_estimators=hp["n_estimators"], learning_rate=hp["learning_rate"], max_depth=hp["max_depth"] or 3, random_state=seed)
        est = GradientBoostingRegressor(**kw) if reg else GradientBoostingClassifier(**kw)
    else:
        est = Ridge(alpha=hp["alpha"]) if reg else LogisticRegression(C=hp["C"], class_weight=cw, max_iter=1000)
    model = Pipeline([("pre", pre), ("est", est)])
    if reg and log_target:
        model = TransformedTargetRegressor(regressor=model, func=np.log1p, inverse_func=np.expm1)
    model.fit(Xtr, ytr)

    pred = model.predict(Xte)
    if reg:
        base = np.full(len(yte), float(ytr.median()))
        m = {"MAE (hours)": skm.mean_absolute_error(yte, pred), "RMSE (hours)": float(np.sqrt(skm.mean_squared_error(yte, pred))),
             "R²": skm.r2_score(yte, pred), "Baseline MAE (always predict median)": skm.mean_absolute_error(yte, base)}
        better = m["MAE (hours)"] < m["Baseline MAE (always predict median)"]
        scoring, extra = "r2", pd.DataFrame({"Actual hours": yte.values, "Predicted hours": pred})
    else:
        proba = model.predict_proba(Xte)[:, 1]
        m = {"Accuracy": skm.accuracy_score(yte, pred), "Precision": skm.precision_score(yte, pred, zero_division=0),
             "Recall": skm.recall_score(yte, pred, zero_division=0), "F1": skm.f1_score(yte, pred, zero_division=0),
             "ROC AUC": skm.roc_auc_score(yte, proba) if yte.nunique() == 2 else float("nan"),
             "Baseline accuracy (always majority class)": max(ytr.mean(), 1 - ytr.mean())}
        better = m["Accuracy"] > m["Baseline accuracy (always majority class)"]
        scoring = "accuracy"
        extra = pd.crosstab(pd.Series(yte.values, name="Actual").map({0: "Not long", 1: "Long"}),
                            pd.Series(pred, name="Predicted").map({0: "Not long", 1: "Long"}))
    tt = pd.DataFrame({"Case": Xte.index.astype(str), "Actual": yte.values, "Predicted": pred})
    if not reg:
        tt["Probability long"] = proba
    sample = Xte.sample(min(len(Xte), 2000), random_state=seed)
    imp = permutation_importance(model, sample, y.loc[sample.index],
                                 n_repeats=5, random_state=seed, scoring=scoring)
    imp_df = (pd.DataFrame({"Feature": X.columns, "Importance": imp.importances_mean})
              .sort_values("Importance", ascending=False))
    opts = {c: sorted(X[c].unique().tolist()) for c in cat_cols}
    nums = {c: (float(X[c].min()), float(X[c].max()), float(X[c].median()), bool(pd.api.types.is_integer_dtype(X[c])))
            for c in num_cols}
    return {"model": model, "features": list(X.columns), "opts": opts, "nums": nums, "metrics": m, "better": bool(better),
            "importance": imp_df, "extra": extra, "test_table": tt, "task": task, "n_train": len(Xtr), "n_test": len(Xte),
            "threshold": threshold, "median_h": float(elapsed.median())}


@(st.fragment if hasattr(st, "fragment") else (lambda fn: fn))
def _predict_panel(res):
    """Runs as a fragment, so pressing Predict does not rerun the whole page."""
    reg = res["task"] == "reg"
    vals = {}
    cols = st.columns(3)
    for i, name in enumerate(res["features"]):
        with cols[i % 3]:
            if name in res["opts"]:
                vals[name] = st.selectbox(name, res["opts"][name], key=f"mi_{name}")
            else:
                lo, hi, med, is_int = res["nums"][name]
                if is_int:
                    vals[name] = st.number_input(name, int(lo), int(max(hi, lo + 1)), int(med), 1, key=f"mi_{name}")
                else:
                    vals[name] = st.number_input(name, float(lo), float(max(hi, lo + 1e-6)), float(med), key=f"mi_{name}")
    if st.button("Predict", key="m_predict", type="primary"):
        row = pd.DataFrame([vals])
        if reg:
            p = float(res["model"].predict(row)[0])
            kpis([("Predicted duration", fmt_hours(max(p, 0))),
                  ("Typical error on test cases", f"± {fmt_hours(res['metrics']['MAE (hours)'])}"),
                  ("Median duration in data", fmt_hours(res["median_h"]))])
        else:
            p = float(res["model"].predict_proba(row)[0][1])
            kpis([(f"Chance of lasting over {res['threshold']:g} hrs", f"{p:.0%}"),
                  ("Test precision", f"{res['metrics']['Precision']:.0%}"),
                  ("Test recall", f"{res['metrics']['Recall']:.0%}")])
    st.caption("Estimates come from patterns in this file only. They support planning and analysis; "
               "they are not clinical guidance and should not replace clinical judgement.")


@guard
def page_model():
    page_header("Predictive Model", "Train a model on this event log with parameters you choose, then try your own inputs.")
    try:
        import sklearn  # noqa: F401
    except ImportError:
        st.error("This page needs scikit-learn. Add `scikit-learn` to requirements.txt and redeploy.")
        return
    if not need(**{"case ID": C.case, "timestamp": C.time}):
        return
    tbl = cached_case_table(C.f, C.case, C.act, C.time)
    if len(tbl) < 30:
        st.warning(f"Only {len(tbl):,} cases with usable timestamps are in view; at least 30 are needed to train and test a model.")
        return

    with st.expander("Arrival forecast for staffing (seasonal average)"):
        fc, bt = core.arrival_forecast(tbl["__start"], 7)
        if fc.empty:
            st.info("Not enough history to forecast arrivals (at least 50 cases with timestamps are needed).")
        else:
            chart(lambda: px.line(fc, x="Time", y="Expected arrivals").update_traces(line_color=PALETTE[0], fill="tozeroy")
                  .update_layout(height=300))
            peak = fc.loc[fc["Expected arrivals"].idxmax()]
            st.markdown(f"Busiest expected hour: **{peak['Time']:%a %d %b, %H:00}** with about **{peak['Expected arrivals']:.1f}** arrivals.")
            if bt:
                better = bt["mae_model"] < bt["mae_naive"]
                st.caption(f"Back-test on the last 7 days: average error {bt['mae_model']:.2f} arrivals per hour, against "
                           f"{bt['mae_naive']:.2f} for 'same hour last week'. "
                           + ("The seasonal average does better." if better else "It does not beat 'same hour last week', so treat it with caution."))
            else:
                st.caption("Less than 3 weeks of history, so no back-test is possible; treat the forecast as indicative.")
            st.caption("The forecast averages arrivals for the same weekday and hour in this log. It cannot know about holidays, outbreaks or staffing changes.")

    with st.container(border=True):
        st.markdown("#### 1 · Choose what to predict and from what")
        c1, c2 = st.columns(2)
        with c1:
            task_label = st.radio("Prediction target", ["Case duration (hours)", "Long case (yes / no)"], key="m_task")
            algo_label = st.radio("Algorithm", ["Random forest", "Gradient boosting", "Linear (Ridge / Logistic)"], key="m_algo")
        with c2:
            multi = st.checkbox("Only cases with 2 or more events", value=True, key="m_multi",
                                help="Single-event cases have a duration of 0 and distort duration models.")
        task = "reg" if task_label.startswith("Case") else "clf"
        algo = {"Random forest": "rf", "Gradient boosting": "gb"}.get(algo_label, "lin")
        data = tbl[tbl["__events"] >= 2] if multi else tbl
        if len(data) < 30:
            st.warning("Fewer than 30 cases remain after this option; untick it or widen the filters.")
            return

        feats = pd.DataFrame(index=data.index)
        feats["Start hour"] = data["__start"].dt.hour
        feats["Start weekday"] = data["__start"].dt.day_name()
        feats["Start month"] = data["__start"].dt.month
        for col in data.columns:
            if str(col).startswith("__") or col in (C.case, C.time) or col in feats.columns:
                continue
            ser = data[col]
            if pd.api.types.is_datetime64_any_dtype(ser):
                continue
            nun = ser.nunique(dropna=True)
            if 2 <= nun <= 50 and nun < 0.5 * len(data):
                feats[col] = ser
        leaky = {"Events in case (only known after the case ends)": data["__events"]}
        if "__acts" in data:
            leaky["Distinct activities (only known after the case ends)"] = data["__acts"]
        default = [c for c in [C.act, "Start hour", "Start weekday", C.dept] if c in feats.columns]
        chosen = st.multiselect("Features known when the case starts", list(feats.columns), default=default, key="m_feats")
        chosen_leaky = st.multiselect("Optional features known only after the case ends (analysis, not early prediction)",
                                      list(leaky), key="m_leaky")
        for k in chosen_leaky:
            feats[k] = leaky[k]
        chosen += chosen_leaky

    with st.form("cf_model_form"):
        st.markdown("#### 2 · Set the training parameters")
        hp = {}
        a, b, c = st.columns(3)
        if algo == "rf":
            hp["n_estimators"] = a.number_input("Number of trees", 10, 500, 200, 10)
            hp["max_depth"] = b.number_input("Max depth (0 = unlimited)", 0, 40, 8)
            hp["min_samples_leaf"] = c.number_input("Min cases per leaf", 1, 100, 5)
        elif algo == "gb":
            hp["n_estimators"] = a.number_input("Boosting rounds", 10, 500, 150, 10)
            hp["learning_rate"] = b.number_input("Learning rate", 0.01, 1.0, 0.10, 0.01)
            hp["max_depth"] = c.number_input("Max tree depth", 1, 10, 3)
        elif task == "reg":
            hp["alpha"] = a.number_input("Regularisation strength (alpha)", 0.001, 1000.0, 1.0, 0.1, format="%.3f")
        else:
            hp["C"] = a.number_input("Inverse regularisation (C)", 0.001, 1000.0, 1.0, 0.1, format="%.3f")
        d1, d2, d3 = st.columns(3)
        test_pct = d1.slider("Hold-out test share (%)", 10, 50, 25, 5)
        split_label = d2.radio("Split method", ["Random", "Chronological (test = most recent cases)"])
        seed = d3.number_input("Random seed", 0, 99999, 42)
        e1, e2 = st.columns(2)
        threshold, log_target, balanced = 0.0, False, False
        if task == "reg":
            log_target = e1.checkbox("Train on a log scale (helps long-tailed durations)", value=True)
        else:
            med = float(data["__elapsed_h"].median())
            threshold = e1.number_input("A case is 'long' if it lasts more than (hours)", 0.01, 100000.0,
                                        max(round(med, 1), 0.1), 0.5)
            balanced = e2.checkbox("Balance class weights", value=True)
        go_train = st.form_submit_button("Train model", type="primary", **WIDE)

    if go_train:
        if not chosen:
            st.error("Select at least one feature.")
        else:
            with st.spinner("Training…"):
                try:
                    res = train_case_model(
                        feats[chosen], data["__elapsed_h"], data["__start"], task=task, algo=algo, hp=hp,
                        test_share=test_pct / 100, seed=int(seed), split="chrono" if split_label.startswith("Chrono") else "random",
                        threshold=float(threshold), log_target=log_target, balanced=balanced)
                    res.update(params={"Algorithm": algo_label, **hp, "Test share": f"{test_pct}%", "Split": split_label.split(" (")[0],
                                       "Seed": int(seed)}, fingerprint=(C.source, len(C.f), multi),
                                settings={"target": task_label, "algorithm": algo_label, "features": chosen,
                                          "parameters": {k: (float(v) if isinstance(v, float) else int(v)) for k, v in hp.items()},
                                          "test_share_pct": int(test_pct), "split": split_label, "seed": int(seed),
                                          "threshold_hours": float(threshold), "log_target": bool(log_target),
                                          "balanced": bool(balanced), "multi_event_cases_only": bool(multi), "trained_on": str(C.source)})
                    st.session_state["cf_model"] = res
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Training failed: {exc}")

    res = st.session_state.get("cf_model")
    if not res:
        st.info("Set the parameters above and press **Train model**. Nothing is trained until you do.")
        return
    if res["fingerprint"] != (C.source, len(C.f), multi):
        st.warning("The data or filters changed since this model was trained. Retrain to refresh the results.")
    reg = res["task"] == "reg"
    with st.container(border=True):
        st.markdown("#### 3 · Hold-out results")
        st.caption(f"Trained on {res['n_train']:,} cases and tested on {res['n_test']:,} cases the model never saw. "
                   + ", ".join(f"{k}: {v}" for k, v in res["params"].items()))
        kpis([(k, (f"{v:,.2f}" if reg or k == "ROC AUC" else f"{v:.1%}") if pd.notna(v) else "n/a")
              for k, v in res["metrics"].items() if not k.startswith("Baseline")] +
             [(k, f"{v:,.2f}" if reg else f"{v:.1%}") for k, v in res["metrics"].items() if k.startswith("Baseline")][:1])
        (st.success if res["better"] else st.warning)(
            "The model beats the simple baseline on unseen cases." if res["better"] else
            "The model does not beat the simple baseline on unseen cases, so it adds little. Try other features or parameters.")
        with st.expander("How to read these results"):
            st.markdown(
                "- **Hold-out cases** were never used for training, so these numbers show how the model does on new cases.\n"
                "- **Baseline** is the simplest possible guess. A useful model must beat it.\n"
                "- **Feature importance** shows how much the score drops when a feature is shuffled; it shows what the model "
                "relies on, not what causes an outcome.\n"
                "- Small data sets give unstable results. Change the seed: if the numbers swing, trust them less.")
        d1, d2 = st.columns(2)
        d1.download_button("Download test predictions (CSV)", res["test_table"].to_csv(index=False).encode("utf-8"),
                           "model_test_predictions.csv", "text/csv", key="m_dl_pred")
        d2.download_button("Download model settings (JSON)", json.dumps(res["settings"], indent=2).encode("utf-8"),
                           "model_settings.json", "application/json", key="m_dl_set")
        l, r = st.columns(2)
        with l:
            st.markdown("**What drives the prediction** (drop in score when a feature is shuffled)")
            chart(lambda: px.bar(res["importance"].head(12), x="Importance", y="Feature", orientation="h")
                  .update_traces(marker_color=PALETTE[0]).update_layout(yaxis={"categoryorder": "total ascending"}, height=320))
        with r:
            if reg:
                st.markdown("**Actual vs predicted duration (test cases)**")
                chart(lambda: px.scatter(res["extra"], x="Actual hours", y="Predicted hours", opacity=.55)
                      .update_traces(marker_color=PALETTE[1]).update_layout(height=320))
            else:
                st.markdown("**Confusion matrix (test cases)**")
                table(res["extra"].reset_index())

    with st.container(border=True):
        st.markdown("#### 4 · Try your own inputs")
        _predict_panel(res)


# ======================================================================
# NAVIGATION (requires Streamlit >= 1.37 for st.navigation + Material icons)
# ======================================================================
@guard
def page_stage_mapping():
    page_header("Stage Mapping & Targets", "Tell CareFlow which stage each activity belongs to, then set target times so breaches are flagged.")
    if not need(**{"activity column": C.act}):
        return
    labels = core.STAGE_LABELS
    rev = {v: k for k, v in labels.items()}
    ov = st.session_state.setdefault("cf_stage_map", {})
    st.session_state.setdefault("cf_stage_snapshot", dict(ov))
    ver = st.session_state.setdefault("cf_map_ver", 0)
    acts = C.raw[C.act].fillna("Unknown activity").astype(str).value_counts()
    auto = {a: core.classify_stage(a) for a in acts.index}
    snap = st.session_state["cf_stage_snapshot"]
    base = pd.DataFrame({"Activity": acts.index, "Events": acts.values,
                         "Stage": [labels[snap.get(a, auto[a])] for a in acts.index]})
    with st.container(border=True):
        st.markdown("#### 1 · Map activities to stages")
        st.caption("Pick a stage for each activity. Anything you change overrides the automatic guess everywhere in the app.")
        edited = st.data_editor(base, hide_index=True, disabled=["Activity", "Events"], key=f"cf_stage_editor_{ver}",
                                column_config={"Stage": st.column_config.SelectboxColumn("Stage", options=list(rev), required=True)},
                                **WIDE)
        new = {a: rev[sg] for a, sg in zip(edited["Activity"], edited["Stage"]) if rev[sg] != auto[a]}
        st.session_state["cf_stage_map"] = new
        b1, b2, b3 = st.columns(3)
        if b1.button("Reset to automatic mapping", key="cf_map_reset"):
            st.session_state.update(cf_stage_map={}, cf_stage_snapshot={}, cf_map_ver=ver + 1)
            st.rerun()
        b2.download_button("Save mapping & targets (JSON)",
                           json.dumps({"stage_map": new, "targets": st.session_state.get("cf_targets", {})}, indent=2).encode(),
                           "careflow_stage_config.json", "application/json", key="cf_map_dl")
        up = b3.file_uploader("Load saved JSON", type="json", key=f"cf_map_up_{ver}", label_visibility="collapsed")
        if up is not None:
            try:
                cfg = json.load(up)
                good = {a: k for a, k in cfg.get("stage_map", {}).items() if k in labels}
                tg = {k: float(v) for k, v in cfg.get("targets", {}).items() if k in labels and float(v) > 0}
                st.session_state.update(cf_stage_map=good, cf_stage_snapshot=dict(good), cf_targets=tg, cf_map_ver=ver + 1)
                st.rerun()
            except Exception:  # noqa: BLE001
                st.error("That file is not a valid CareFlow stage configuration.")
    g = stage_summary(C.f)
    present = [(k, l) for k, l, _ in core.STAGE_META if not g.empty and k in g.index and k != "completed"]
    with st.container(border=True):
        st.markdown("#### 2 · Set target times")
        st.caption("Target average time in each stage, in hours (0 means no target). Use your own service standards.")
        tg = dict(st.session_state.get("cf_targets", {}))
        cols = st.columns(3)
        for i, (k, label) in enumerate(present):
            tg[k] = cols[i % 3].number_input(f"{label} (hours)", 0.0, 1000.0, float(tg.get(k, 0.0)), 0.25, key=f"cf_tg_{k}")
        st.session_state["cf_targets"] = {k: v for k, v in tg.items() if v and v > 0}
    with st.container(border=True):
        st.markdown("#### 3 · Preview")
        render_stage_flow()
    st.caption("Mapping and targets last for this browser session. Download the JSON to keep them and load it next time.")


@guard
def page_access_log():
    page_header("Access Log", "Sign-ins and page views recorded for your organisation (administrators only).", chips=False)
    if not is_admin():
        st.warning("This page is only available to administrators (ADMIN_EMAILS in the app secrets).")
        return
    try:
        rows = supabase.table("access_log").select("*").order("created_at", desc=True).limit(500).execute().data
    except Exception as exc:  # noqa: BLE001
        st.error("Could not read the access log. Run supabase_security.sql in Supabase and add your email to app_admins.")
        st.caption(str(exc)[:200])
        return
    if not rows:
        st.info("No entries yet.")
        return
    df = pd.DataFrame(rows)
    kpis([("Entries shown", f"{len(df):,}"), ("People", f"{df['user_email'].nunique():,}"),
          ("Sign-ins", f"{(df['event'] == 'login').sum():,}")])
    st.write("")
    table(df, csv_name="access_log.csv")


def _page(fn, title, icon, slug, default=False):
    return st.Page(fn, title=title, icon=f":material/{icon}:", url_path=None if default else slug, default=default)


NAV = {
    "Analytics": [
        _page(page_dashboard, "Executive Dashboard", "dashboard", "dashboard", default=True),
        _page(page_pm_explorer, "Process Mining Explorer", "account_tree", "process-mining"),
        _page(page_ai_assistant, "AI Workflow Assistant", "smart_toy", "ai-assistant"),
        _page(page_patient_flow, "Patient Flow", "timeline", "patient-flow"),
        _page(page_pathways, "Clinical Pathways", "route", "clinical-pathways"),
        _page(page_comparison, "Pathway Comparison", "compare_arrows", "pathway-comparison"),
        _page(page_model, "Predictive Model", "model_training", "predictive-model"),
        _page(page_discovery, "Process Discovery & Metrics", "schema", "process-discovery"),
    ],
    "Operations": [
        _page(page_beds, "Bed & Discharge Management", "bed", "beds-discharge"),
        _page(page_tasks, "Task & Escalation Center", "task_alt", "tasks"),
        _page(page_coordination, "Care coordination", "hub", "care-coordination"),
        _page(page_teams, "Care Teams", "groups", "care-teams"),
        _page(page_notifications, "Notifications Center", "notifications", "notifications"),
    ],
    "Data & Governance": [
        _page(page_reports, "Reports & Outcomes", "summarize", "reports"),
        _page(page_quality, "Data Quality Studio", "fact_check", "data-quality"),
        _page(page_stage_mapping, "Stage Mapping & Targets", "alt_route", "stage-mapping"),
        _page(page_dictionary, "Data Dictionary", "menu_book", "data-dictionary"),
        _page(page_insights, "Insights & Benchmarks", "insights", "insights"),
        _page(page_governance, "Security & Governance", "shield", "governance"),
    ],
    "Workspace": [
        _page(page_saved, "Saved Workspace", "bookmark", "saved-workspace"),
        _page(page_prefs, "Display Preferences", "tune", "preferences"),
        _page(page_help, "Help Center", "help", "help"),
        _page(page_profile, "Profile", "person", "profile"),
    ],
}
if is_admin():
    NAV["Data & Governance"].append(_page(page_access_log, "Access Log", "history", "access-log"))
# Pages that work without an event log (session-only forms and help).
SESSION_PAGES = {"Process Discovery & Metrics", "Task & Escalation Center", "Notifications Center", "Saved Workspace",
                 "Display Preferences", "Help Center", "Profile", "Access Log"}

try:  # sidebar brand: wordmark expanded, mark only when collapsed
    st.logo(str(_LOGO_FILE), icon_image=str(_MARK_FILE), size="large")
except TypeError:
    try:
        st.logo(str(_LOGO_FILE), icon_image=str(_MARK_FILE))
    except Exception:  # noqa: BLE001
        pass
except Exception:  # noqa: BLE001
    pass


_TOP_NAV = _ST_VERSION >= (1, 46)  # top navigation needs Streamlit 1.46+
try:
    pg = st.navigation(NAV, position="top" if _TOP_NAV else "sidebar")
except TypeError:  # older Streamlit without top navigation
    pg = st.navigation(NAV)
st.session_state["careflow_page"] = pg.title
if not st.session_state.get("cf_logged"):
    st.session_state["cf_logged"] = True
    log_access("login")
if st.session_state.get("cf_last_page") != pg.title:
    st.session_state["cf_last_page"] = pg.title
    log_access("page_view", pg.title)


def render_account():
    with st.sidebar:
        st.divider()
        email = str(st.session_state.careflow_user["email"])
        st.markdown(
            f'<div class="cf-user"><div class="cf-avatar">{escape(email[:1].upper())}</div>'
            f'<div class="cf-user-meta"><div class="cf-user-label">Signed in</div>'
            f'<div class="cf-user-email">{escape(email)}</div></div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Log out", key="cf_logout", **WIDE):
            try:
                supabase.auth.sign_out()
            except Exception:  # noqa: BLE001
                pass
            st.session_state.careflow_user = None
            st.rerun()


# ======================================================================
# LOAD DATA -> MAP FIELDS -> FILTER -> CONTEXT
# ======================================================================
data_box = st.sidebar.expander("Data source", expanded=False)
with data_box:
    uploaded = st.file_uploader("Upload event log (CSV)", type="csv", key="cf_upload",
                                help="Replaces the repository file for this browser session only.")
    st.caption("Uploads are not stored. Avoid identifiable patient data on a public deployment.")

with st.spinner("Loading event log…"):
    raw, source_name, load_error = load_event_log(uploaded)
    pm_outputs, pm_notes = discover_pm_outputs()

with data_box:
    st.caption(f"Active file: **{source_name}**")
    if pm_outputs:
        st.caption("Process-mining outputs found: " + ", ".join(f"{k} ({v['file']})" for k, v in pm_outputs.items()))
    else:
        st.caption("No process-mining output files found (looked in pm_outputs/). Results are computed live.")
    for note in pm_notes:
        st.warning(note)

block = None  # (severity, message) when data pages cannot render
if raw.empty:
    C = Ctx(raw=pd.DataFrame(), f=pd.DataFrame(), source=source_name, case=None, act=None, time=None, dept=None,
            status=None, staff=None, synthetic=False, pm_outputs={}, dept_summary="—")
    block = ("error", load_error or "No event-log CSV was found.")
else:
    auto = pm.detect_roles(raw)
    LABELS = {"case": "Case / patient ID", "activity": "Activity", "time": "Timestamp",
              "dept": "Department", "status": "Status", "staff": "Staff / resource"}
    opts = [None] + list(raw.columns)
    chosen = {}
    with st.sidebar.expander("Field mapping", expanded=False):
        st.caption("Auto-detected from column names. Override anything that was missed or wrong.")
        for role, label in LABELS.items():
            chosen[role] = st.selectbox(label, opts, index=opts.index(auto[role]) if auto[role] in opts else 0,
                                        key=f"map_{role}_{source_name}",
                                        format_func=lambda c: "(none)" if c is None else str(c))
        picked = [c for c in chosen.values() if c is not None]
        if len(set(picked)) != len(picked):
            st.warning("Each column should be used for only one role.")

    df, dept_col, synthetic = prepare_log(raw, chosen["case"], chosen["time"], chosen["dept"])
    case_c, act_c, time_c = chosen["case"], chosen["activity"], chosen["time"]

    # ---- global filters (apply to every analytics page) ----
    fkeys = {n: f"flt_{n}_{source_name}" for n in ("depts", "acts", "dates", "whole")}
    FILTER_KEYS = fkeys

    def reset_filters():
        for k in fkeys.values():
            st.session_state.pop(k, None)

    sel_depts, sel_acts, whole, date_range = [], [], True, None
    with st.sidebar:
        st.markdown("### Filters")
        sel_depts = st.multiselect(
            "Department (demo labels)" if synthetic else "Department",
            sorted(df[dept_col].dropna().astype(str).unique()), key=fkeys["depts"], placeholder="All departments")
        if act_c:
            sel_acts = st.multiselect(
                "Activity", sorted(df[act_c].fillna("Unknown activity").astype(str).unique()),
                key=fkeys["acts"], placeholder="All activities")
            if sel_acts and case_c:
                whole = st.checkbox("Keep whole cases that include these activities", value=True, key=fkeys["whole"])
        if time_c and df[time_c].notna().any():
            lo, hi = df[time_c].min().date(), df[time_c].max().date()
            date_range = st.date_input("Event dates", value=(lo, hi), min_value=lo, max_value=hi, key=fkeys["dates"])
            date_range = tuple(date_range) if isinstance(date_range, (tuple, list)) else None
        st.button("Reset filters", on_click=reset_filters, key="cf_reset_filters", **WIDE)

    f = pm.apply_filters(df, case=case_c, act=act_c, time=time_c, dept=dept_col, depts=sel_depts, acts=sel_acts,
                         date_range=date_range, keep_whole_cases=whole)
    active = []
    if sel_depts:
        active.append("department")
    if sel_acts:
        active.append(f"{len(sel_acts)} activit{'y' if len(sel_acts) == 1 else 'ies'}")
    if date_range and len(date_range) == 2 and time_c:
        full = df[time_c].dropna()
        if not full.empty and (pd.Timestamp(date_range[0]) > full.min().normalize()
                               or pd.Timestamp(date_range[1]) < full.max().normalize()):
            active.append("dates")

    C = Ctx(raw=df, f=f, source=source_name, case=case_c, act=act_c, time=time_c, dept=dept_col,
            status=chosen["status"], staff=chosen["staff"], synthetic=synthetic, pm_outputs=pm_outputs,
            dept_summary=", ".join(sel_depts) or "All departments", active=", ".join(active))
    if f.empty:
        block = ("warning", "No events match the current filters. Widen the selection or press **Reset filters** in the sidebar.")

render_account()

# ======================================================================
# RENDER
# ======================================================================
if block and pg.title not in SESSION_PAGES:
    page_header(pg.title, chips=False)
    (st.error if block[0] == "error" else st.warning)(block[1])
    if block[0] == "error":
        st.markdown(
            "**To get started**\n\n"
            "- Upload a CSV under **Data source** in the sidebar, or\n"
            "- Place `careflow_event_log.csv`, `event_log_ED_MMA_2026.csv` or `sample_event_log.csv` beside `app.py`.\n\n"
            "The file needs a case/patient ID, an activity and (ideally) a timestamp column."
        )
    footer()
else:
    pg.run()
