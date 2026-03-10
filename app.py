from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.knee_shoulder.config import load_config
from src.knee_shoulder.storage import load_existing_history, load_validation_history


st.set_page_config(page_title="Knee Shoulder Monitor", layout="wide")
st.title("Knee/Shoulder Stock Monitor")
st.caption("Daily close-based reversal monitoring dashboard for Korean stocks.")

config = load_config()
paths = config["paths"]


def load_latest_signals(signal_dir: str) -> tuple[pd.DataFrame, str | None]:
    files = sorted(Path(signal_dir).glob("*_signals.csv"))
    if not files:
        return pd.DataFrame(), None
    latest = files[-1]
    return pd.read_csv(latest, dtype={"symbol": str}), latest.stem.replace("_signals", "")


signals_df, signal_date = load_latest_signals(paths["signal_dir"])
validation_df = load_validation_history(Path(paths["validation_file"]))

if signals_df.empty:
    st.warning("No signal file found yet. Run `python3 run_daily.py` first.")
    st.stop()

header_cols = st.columns(4)
analysis_date = signal_date or "-"
run_at = signals_df["run_at"].iloc[0] if "run_at" in signals_df.columns and not signals_df.empty else "-"
header_cols[0].metric("Analysis Date", analysis_date)
header_cols[1].metric("Knee Strong", int((signals_df["knee_grade"] == "Strong").sum()))
header_cols[2].metric("Shoulder Strong", int((signals_df["shoulder_grade"] == "Strong").sum()))
header_cols[3].metric("Run At", run_at)

knee_view = signals_df[signals_df["knee_score"] >= config["runtime"]["signal_threshold"]].copy()
shoulder_view = signals_df[signals_df["shoulder_score"] >= config["runtime"]["signal_threshold"]].copy()

st.subheader("Knee Candidates")
st.dataframe(
    knee_view[["symbol", "name", "close", "pct_change", "knee_score", "knee_grade", "vol_ratio_20", "knee_reasons"]],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Shoulder Candidates")
st.dataframe(
    shoulder_view[["symbol", "name", "close", "pct_change", "shoulder_score", "shoulder_grade", "vol_ratio_20", "shoulder_reasons"]],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Symbol Detail")
st.caption("아래 차트는 선택한 종목 1개만 보여줍니다. 기본값은 후보 리스트의 첫 번째 종목입니다.")
symbol = st.selectbox("Symbol", signals_df["symbol"] + " | " + signals_df["name"])
selected_symbol = symbol.split(" | ", 1)[0]
selected_row = signals_df[signals_df["symbol"] == selected_symbol].iloc[0]
history = load_existing_history(Path(paths["raw_dir"]) / f"{selected_symbol}.csv")

if not history.empty:
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=history["date"], y=history["close"], mode="lines", name="Close"))
    if "ma_20" in history.columns:
        figure.add_trace(go.Scatter(x=history["date"], y=history["ma_20"], mode="lines", name="MA20"))
    figure.update_layout(
        height=420,
        margin=dict(l=20, r=20, t=20, b=20),
    )
    st.plotly_chart(figure, use_container_width=True)

detail_cols = st.columns(2)
detail_cols[0].write(
    {
        "knee_score": int(selected_row["knee_score"]),
        "knee_grade": selected_row["knee_grade"],
        "knee_reasons": selected_row["knee_reasons"],
        "knee_confirmed": bool(selected_row["knee_confirmed"]),
    }
)
detail_cols[1].write(
    {
        "shoulder_score": int(selected_row["shoulder_score"]),
        "shoulder_grade": selected_row["shoulder_grade"],
        "shoulder_reasons": selected_row["shoulder_reasons"],
        "shoulder_confirmed": bool(selected_row["shoulder_confirmed"]),
    }
)

st.subheader("Validation")
if not validation_df.empty:
    symbol_validation = validation_df[validation_df["symbol"] == selected_symbol]
    st.dataframe(symbol_validation, use_container_width=True, hide_index=True)
else:
    st.info("Validation data will appear after enough forward days have accumulated.")
