import streamlit as st
import plotly.graph_objects as go
import time
from analysis import ProSignalAnalyzer
from utils.data_fetcher import fetch_data, get_dhaka_time

st.set_page_config(page_title="Pro Signal AI", page_icon="⚡", layout="wide")

# CSS দিয়ে UI স্টাইলিং প্রফেশনাল করা
st.markdown("""
    <style>
    .metric-card {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
    }
    .stButton>button {
        background-color: #00FFA3;
        color: #0E1117;
        font-weight: bold;
        border-radius: 8px;
        border: none;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Pro Signal Analyzer AI (v2.1)")
st.caption(f"Last Refreshed: {get_dhaka_time()}")

# サイドバー (Sidebar Controls)
st.sidebar.header("⚙️ কন্ট্রোল প্যানেল")
pair = st.sidebar.selectbox("ট্রেডিং পেয়ার সিলেক্ট করুন:", ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"])
timeframe = st.sidebar.selectbox("টাইমফ্রেম:", ["1m", "5m", "15m", "1h", "4h"])
auto_refresh = st.sidebar.checkbox("অটো-রিফ্রেশ (৩০ সেকেন্ড)", value=True)

analyzer = ProSignalAnalyzer()

# ডেটা ফেচ ও এনালাইসিস
with st.spinner("মার্কেট ডেটা অ্যানালাইস করা হচ্ছে..."):
    df = fetch_data(pair, timeframe=timeframe, limit=100)

if not df.empty:
    signal_data = analyzer.generate_signal(df, pair=pair, timeframe=timeframe)
    
    # টপ মেট্রিক গার্ড
    col1, col2, col3, col4 = st.columns(4)
    
    sig = signal_data['signal']
    sig_color = "#00FFA3" if sig == "BUY" else "#FF4D4D" if sig == "SELL" else "#E6EDF3"
    
    col1.markdown(f"<div class='metric-card'><h4>সিগন্যাল</h4><h2 style='color:{sig_color};'>{sig}</h2></div>", unsafe_allow_html=True)
    col2.markdown(f"<div class='metric-card'><h4>কনফিডেন্স</h4><h2>{signal_data['confidence']}%</h2></div>", unsafe_allow_html=True)
    col3.markdown(f"<div class='metric-card'><h4>বর্তমান প্রাইস</h4><h2>${signal_data['price']}</h2></div>", unsafe_allow_html=True)
    col4.markdown(f"<div class='metric-card'><h4>মার্কেট অবস্থা</h4><h2>{signal_data['regime']}</h2></div>", unsafe_allow_html=True)

    st.markdown("---")

    # লেআউট - ক্যান্ডেলস্টিক চার্ট + বিশ্লেষণ রিজনস
    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.subheader("📈 লাইভ ক্যান্ডেলস্টিক চার্ট")
        fig = go.Figure(data=[go.Candlestick(
            x=df['Timestamp'],
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            increasing_line_color='#00FFA3', 
            decreasing_line_color='#FF4D4D'
        )])
        fig.update_layout(
            template="plotly_dark",
            margin=dict(l=20, r=20, t=20, b=20),
            height=400,
            paper_bgcolor="#161B22",
            plot_bgcolor="#161B22"
        )
        st.plotly_chart(fig, use_container_width=True)

    with right_col:
        st.subheader("🧠 সিগন্যালের কারণসমূহ")
        for reason in signal_data['reasons']:
            st.info(f"✔ {reason}")

else:
    st.error("ডেটা ফেচ করা সম্ভব হয়নি। ইন্টারনেটের কানেকশন চেক করুন।")

if auto_refresh:
    time.sleep(30)
    st.rerun()
