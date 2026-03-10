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


def render_candidate_help(title: str, score_label: str, reasons_label: str) -> None:
    with st.popover("!"):
        st.markdown(f"**{title} 읽는 법**")
        if "Knee" in title:
            st.markdown("- `symbol` > 종목코드")
            st.markdown("- `name` > 종목명")
            st.markdown("- `close` > 전일 종가")
            st.markdown("- `pct_change` > 전일대비등락률")
            st.markdown("- `knee_score` > 평가점수")
            st.markdown("- `knee_grade` > 평가등급")
            st.markdown("- `vol_ratio_20` > 거래량")
            st.markdown("- `knee_reasons` > 평가근거")
        else:
            st.markdown("- `symbol` > 종목코드")
            st.markdown("- `name` > 종목명")
            st.markdown("- `close` > 전일 종가")
            st.markdown("- `pct_change` > 전일대비등락률")
            st.markdown("- `shoulder_score` > 평가점수")
            st.markdown("- `shoulder_grade` > 평가등급")
            st.markdown("- `vol_ratio_20` > 거래량")
            st.markdown("- `shoulder_reasons` > 평가근거")

        if "Knee" in title:
            st.markdown("**해석 예시**")
            st.markdown("- `pct_change`가 플러스이고 `close`가 올라오는데 `vol_ratio_20`도 높으면, 단순 기술적 반등보다 실제 매수세가 붙는 반등으로 볼 수 있습니다.")
            st.markdown("- `knee_score`가 높고 `grade`가 `Strong`면, 저점권 접근, 반등, 거래량, 모멘텀 개선 같은 조건이 많이 겹친 상태입니다.")
            st.markdown("- `knee_reasons`에 `최근 20일 저점권`, `종가 반등`, `MACD 개선`이 같이 있으면, 하락 흐름이 약해지면서 반전 시도가 나오는 상황으로 해석할 수 있습니다.")
            st.markdown("- `close`는 후보가 잡힌 기준 가격이므로, 이후 이 가격대 위에서 버티는지 보는 기준점으로 쓰면 됩니다.")
        else:
            st.markdown("**해석 예시**")
            st.markdown("- `pct_change`가 마이너스로 꺾이고 `vol_ratio_20`도 높으면, 단순 쉬어가는 흐름보다 매도 물량이 강하게 나오는지 의심해볼 수 있습니다.")
            st.markdown("- `shoulder_score`가 높고 `grade`가 `Strong`면, 고점권 접근, 약세 전환, 거래량 이상, 모멘텀 둔화 조건이 많이 겹친 상태입니다.")
            st.markdown("- `shoulder_reasons`에 `고점권`, `종가 약세`, `MACD 둔화`가 같이 있으면, 상승 힘이 식으면서 꺾이기 시작하는 구간으로 볼 수 있습니다.")
            st.markdown("- `close`는 약세 후보가 포착된 기준 가격이므로, 이후 이 가격 아래로 더 밀리는지 볼 때 기준점이 됩니다.")


def render_validation_help() -> None:
    with st.popover("!"):
        st.markdown("**Validation 읽는 법**")
        st.markdown("- 이 표는 과거에 나온 신호가 이후 며칠 뒤 실제로 맞았는지 확인하는 영역입니다.")
        st.markdown("- `ret_1d`, `ret_3d`, `ret_5d`, `ret_10d`는 신호 발생 후 각각 1일, 3일, 5일, 10일 뒤 수익률입니다.")
        st.markdown("- `knee_success`는 5일 안에 `+3%` 이상 상승했는지 뜻합니다.")
        st.markdown("- `shoulder_success`는 5일 안에 `-3%` 이하 하락했는지 뜻합니다.")
        st.markdown("- 무릎 후보는 수익률이 플러스인지, 어깨 후보는 수익률이 마이너스인지 보면 먼저 빠르게 해석할 수 있습니다.")


def load_latest_signals(signal_dir: str) -> tuple[pd.DataFrame, str | None]:
    files = sorted(Path(signal_dir).glob("*_signals.csv"))
    if not files:
        return pd.DataFrame(), None
    latest = files[-1]
    return pd.read_csv(latest, dtype={"symbol": str}), latest.stem.replace("_signals", "")


def prepare_history_for_chart(history: pd.DataFrame) -> pd.DataFrame:
    frame = history.copy()
    frame["date"] = pd.to_datetime(frame["date"].astype(str), format="%Y%m%d", errors="coerce")
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return frame


def format_candidate_view(frame: pd.DataFrame, score_column: str, reasons_column: str) -> pd.DataFrame:
    view = frame[
        ["symbol", "name", "close", "pct_change", score_column, f"{score_column.split('_')[0]}_grade", "vol_ratio_20", reasons_column]
    ].copy()
    view["close"] = pd.to_numeric(view["close"], errors="coerce").map(lambda v: f"{int(v):,}" if pd.notna(v) else "")
    view = view.rename(
        columns={
            "symbol": "종목코드",
            "name": "종목명",
            "close": "전일 종가",
            "pct_change": "전일대비등락률",
            score_column: "평가점수",
            f"{score_column.split('_')[0]}_grade": "평가등급",
            "vol_ratio_20": "거래량",
            reasons_column: "평가근거",
        }
    )
    return view


signals_df, signal_date = load_latest_signals(paths["signal_dir"])
validation_df = load_validation_history(Path(paths["validation_file"]))

if signals_df.empty:
    st.warning("No signal file found yet. Run `python3 run_daily.py` first.")
    st.stop()

header_cols = st.columns(3)
analysis_date = signal_date or "-"
header_cols[0].metric("Analysis Date", analysis_date)
header_cols[1].metric("Knee Strong", int((signals_df["knee_grade"] == "Strong").sum()))
header_cols[2].metric("Shoulder Strong", int((signals_df["shoulder_grade"] == "Strong").sum()))

knee_view = signals_df[signals_df["knee_score"] >= config["runtime"]["signal_threshold"]].copy()
shoulder_view = signals_df[signals_df["shoulder_score"] >= config["runtime"]["signal_threshold"]].copy()

knee_header_col, knee_help_col = st.columns([20, 1])
with knee_header_col:
    st.subheader("Knee Candidates")
with knee_help_col:
    render_candidate_help("Knee Candidates", "knee_score", "knee_reasons")
st.dataframe(
    format_candidate_view(knee_view, "knee_score", "knee_reasons"),
    use_container_width=True,
    hide_index=True,
)

shoulder_header_col, shoulder_help_col = st.columns([20, 1])
with shoulder_header_col:
    st.subheader("Shoulder Candidates")
with shoulder_help_col:
    render_candidate_help("Shoulder Candidates", "shoulder_score", "shoulder_reasons")
st.dataframe(
    format_candidate_view(shoulder_view, "shoulder_score", "shoulder_reasons"),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Symbol Detail")
st.caption("후보 종목만 선택할 수 있습니다. Knee / Shoulder를 나눠서 고르세요.")

knee_options = (knee_view["symbol"] + " | " + knee_view["name"]).tolist()
shoulder_options = (shoulder_view["symbol"] + " | " + shoulder_view["name"]).tolist()

selector_col1, selector_col2 = st.columns(2)
with selector_col1:
    knee_selected = st.radio(
        "Knee Candidate",
        options=knee_options if knee_options else ["후보 없음"],
        key="knee_candidate_radio",
    )
with selector_col2:
    shoulder_selected = st.radio(
        "Shoulder Candidate",
        options=shoulder_options if shoulder_options else ["후보 없음"],
        key="shoulder_candidate_radio",
    )

selected_option = None
if knee_selected != "후보 없음":
    selected_option = knee_selected
elif shoulder_selected != "후보 없음":
    selected_option = shoulder_selected
else:
    st.info("현재 상세 보기로 선택할 후보 종목이 없습니다.")
    st.stop()

selected_symbol = selected_option.split(" | ", 1)[0]
selected_row = signals_df[signals_df["symbol"] == selected_symbol].iloc[0]
history = load_existing_history(Path(paths["raw_dir"]) / f"{selected_symbol}.csv")

if not history.empty:
    history = prepare_history_for_chart(history)
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=history["date"], y=history["close"], mode="lines", name="Close"))
    if "ma_20" in history.columns:
        figure.add_trace(go.Scatter(x=history["date"], y=history["ma_20"], mode="lines", name="MA20"))
    figure.update_layout(
        height=420,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(
            title="Date",
            tickformat="%Y-%m-%d",
            type="date",
        ),
        yaxis=dict(
            title="Close",
            tickformat=",d",
        ),
    )
    st.plotly_chart(figure, use_container_width=True)

detail_cols = st.columns(2)
detail_cols[0].write(
    {
        "close": f"{int(selected_row['close']):,}",
        "knee_score": int(selected_row["knee_score"]),
        "knee_grade": selected_row["knee_grade"],
        "knee_reasons": selected_row["knee_reasons"],
        "knee_confirmed": bool(selected_row["knee_confirmed"]),
    }
)
detail_cols[1].write(
    {
        "close": f"{int(selected_row['close']):,}",
        "shoulder_score": int(selected_row["shoulder_score"]),
        "shoulder_grade": selected_row["shoulder_grade"],
        "shoulder_reasons": selected_row["shoulder_reasons"],
        "shoulder_confirmed": bool(selected_row["shoulder_confirmed"]),
    }
)

validation_header_col, validation_help_col = st.columns([20, 1])
with validation_header_col:
    st.subheader("Validation")
with validation_help_col:
    render_validation_help()
if not validation_df.empty:
    symbol_validation = validation_df[validation_df["symbol"] == selected_symbol]
    st.dataframe(symbol_validation, use_container_width=True, hide_index=True)
else:
    st.info("Validation data will appear after enough forward days have accumulated.")
