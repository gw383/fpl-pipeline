import streamlit as st


def metric_card(title, value, rank):
    st.html(
        f"""
        <div style="
            background:white;
            border-radius:12px;
            padding:14px 18px;
            height:95px;
            position:relative;
            box-shadow:0 1px 4px rgba(0,0,0,0.08);
        ">

            <div style="
                font-size:14px;
                color:#666;
            ">
                {title}
            </div>

            <div style="
                font-size:30px;
                font-weight:700;
                margin-top:8px;
                color:#222;
            ">
                {value}
            </div>

            <div style="
                position:absolute;
                top:12px;
                right:12px;
                background:#ececec;
                color:#555;
                padding:4px 10px;
                border-radius:999px;
                font-size:13px;
                font-weight:600;
            ">
                #{rank}
            </div>
        </div>
        """)
