from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.knee_shoulder.config import load_config
from src.knee_shoulder.storage import load_existing_history, load_validation_history


st.set_page_config(page_title="Knee Shoulder Monitor", page_icon="🌻", layout="wide")
st.title("Knee/Shoulder Stock Monitor")
st.caption("Daily close-based reversal monitoring dashboard for Korean stocks.")

config = load_config()
paths = config["paths"]
CANDIDATE_DISPLAY_MIN_SCORE = 50
CANDIDATE_TABLE_HEIGHT = 245


def render_candidate_help(title: str, score_label: str, reasons_label: str) -> None:
    with st.popover("!"):
        st.markdown(f"**{title} 읽는 법**")
        if "Knee" in title:
            st.markdown("- `symbol` > 종목코드")
            st.markdown("- `name` > 종목명")
            st.markdown("- `close` > 전일 종가. 매수 후보가 잡힌 기준 가격입니다. 이후 이 가격 위에서 버티는지 보는 기준점입니다.")
            st.markdown("- `pct_change` > 전일대비등락률. 플러스면 당일 반등 힘이 붙었는지, 너무 급등했는지도 같이 봅니다.")
            st.markdown("- `knee_score` > 평가점수. 높을수록 매수 후보 조건이 많이 겹친 상태입니다.")
            st.markdown("- `knee_grade` > 평가등급. `Strong`는 우선 확인할 강한 매수 후보, `Watch`는 관찰할 매수 후보입니다.")
            st.markdown("- `vol_ratio_20` > 거래량. 1보다 크면 평소보다 거래가 많이 붙은 날입니다. 반등과 함께 높으면 의미가 커집니다.")
            st.markdown("- `knee_reasons` > 평가근거. 왜 이 종목이 매수 후보로 잡혔는지 핵심 이유를 보여줍니다.")
        else:
            st.markdown("- `symbol` > 종목코드")
            st.markdown("- `name` > 종목명")
            st.markdown("- `close` > 전일 종가. 매도 후보가 포착된 기준 가격입니다. 이후 이 가격 아래로 더 밀리는지 보는 기준점입니다.")
            st.markdown("- `pct_change` > 전일대비등락률. 마이너스로 꺾였는지, 고점권에서 약세 전환이 시작됐는지 볼 때 중요합니다.")
            st.markdown("- `shoulder_score` > 평가점수. 높을수록 매도 후보 조건이 많이 겹친 상태입니다.")
            st.markdown("- `shoulder_grade` > 평가등급. `Strong`는 우선 경계할 강한 매도 후보, `Watch`는 관찰할 후보입니다.")
            st.markdown("- `vol_ratio_20` > 거래량. 꺾이는 날 이 값이 높으면 단순 눌림보다 실제 매도 물량이 나왔는지 의심해볼 수 있습니다.")
            st.markdown("- `shoulder_reasons` > 평가근거. 왜 이 종목이 매도 후보로 잡혔는지 핵심 이유를 보여줍니다.")

        if "Knee" in title:
            st.markdown("**해석 예시**")
            st.markdown("- `pct_change`가 플러스이고 `vol_ratio_20`도 높으면, 그냥 잠깐 튄 반등보다 실제 매수세가 붙는 매수 후보로 해석할 수 있습니다.")
            st.markdown("- `knee_score`가 70 이상으로 높고 `Strong`면, 여러 매수 조건이 한 번에 나온 상태라 우선순위를 높게 둘 수 있습니다.")
            st.markdown("- `knee_reasons`에 `최근 20일 저점권`, `종가 반등`, `MACD 개선`이 함께 있으면, 하락 흐름이 약해지며 매수 시도가 나오는 상황으로 해석합니다.")
            st.markdown("- `close`는 이후 손절선이나 추세 유지 여부를 볼 때 기준 가격으로 사용할 수 있습니다.")
        else:
            st.markdown("**해석 예시**")
            st.markdown("- `pct_change`가 마이너스로 꺾이고 `vol_ratio_20`도 높으면, 단순 쉬어감보다 매도 물량이 강하게 나온 것으로 해석할 수 있습니다.")
            st.markdown("- `shoulder_score`가 70 이상으로 높고 `Strong`면, 고점권 약세 전환 조건이 많이 겹친 상태입니다.")
            st.markdown("- `shoulder_reasons`에 `고점권`, `종가 약세`, `MACD 둔화`가 함께 있으면, 상승 힘이 식으면서 꺾이기 시작하는 구간으로 볼 수 있습니다.")
            st.markdown("- `close`는 이후 추가 하락 여부를 볼 때 기준 가격으로 사용할 수 있습니다.")


def render_validation_help() -> None:
    with st.popover("!"):
        st.markdown("**예측평가 읽는 법**")
        st.markdown("- 이 표는 오늘 후보가 아니라, **직전 거래일에 포착된 후보가 오늘 기준으로 어떻게 됐는지** 보는 영역입니다.")
        st.markdown("- `평가일` > 해당 신호를 평가한 기준 날짜입니다.")
        st.markdown("- `매수점수` > 무릎 후보 점수입니다. 높을수록 매수 후보 근거가 많이 겹친 상태입니다.")
        st.markdown("- `매도점수` > 어깨 후보 점수입니다. 높을수록 매도 후보 근거가 많이 겹친 상태입니다.")
        st.markdown("- `수익률(1일)`, `수익률(3일)`, `수익률(5일)`, `수익률(10일)` > 평가일 이후 각각 1일, 3일, 5일, 10일 뒤 수익률입니다.")
        st.markdown("- `매수 성공여부` > 5일 안에 `+3%` 이상 상승했는지 뜻합니다.")
        st.markdown("- `매도 성공여부` > 5일 안에 `-3%` 이하 하락했는지 뜻합니다.")
        st.markdown("- 해석할 때는 매수 후보는 수익률이 플러스인지, 매도 후보는 수익률이 마이너스인지 먼저 보면 됩니다.")


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


def previous_business_date(date_str: str) -> str | None:
    dt = pd.to_datetime(date_str, format="%Y%m%d", errors="coerce")
    if pd.isna(dt):
        return None
    dt = dt - pd.Timedelta(days=1)
    while dt.weekday() >= 5:
        dt = dt - pd.Timedelta(days=1)
    return dt.strftime("%Y%m%d")


def render_candidate_radio_grid(title: str, options: list[str], key_prefix: str) -> str | None:
    st.markdown(f"**{title}**")
    if not options:
        st.caption("후보 없음")
        return None

    limited = options[:10]
    left_chunk = limited[:5]
    right_chunk = limited[5:10]
    left_col, right_col = st.columns(2)

    with left_col:
        left_selected = st.radio(
            f"{title} 좌측",
            options=left_chunk,
            key=f"{key_prefix}_left",
            label_visibility="collapsed",
        )
    with right_col:
        right_selected = None
        if right_chunk:
            right_selected = st.radio(
                f"{title} 우측",
                options=right_chunk,
                index=None,
                key=f"{key_prefix}_right",
                label_visibility="collapsed",
            )

    if right_selected:
        return right_selected
    if left_selected:
        return left_selected
    return limited[0]


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


def candidate_column_config() -> dict:
    return {
        "종목코드": st.column_config.TextColumn("종목코드", width="small"),
        "종목명": st.column_config.TextColumn("종목명", width="small"),
        "전일 종가": st.column_config.TextColumn("전일 종가", width="small"),
        "전일대비등락률": st.column_config.TextColumn("전일대비등락률", width="small"),
        "평가점수": st.column_config.NumberColumn("평가점수", width="small"),
        "평가등급": st.column_config.TextColumn("평가등급", width="small"),
        "거래량": st.column_config.NumberColumn("거래량", width="small"),
        "평가근거": st.column_config.TextColumn("평가근거", width="large"),
    }


def format_validation_view(frame: pd.DataFrame) -> pd.DataFrame:
    view = frame.copy()
    rename_map = {
        "signal_date": "평가일",
        "symbol": "종목코드",
        "name": "종목명",
        "knee_score": "매수점수",
        "shoulder_score": "매도점수",
        "ret_1d": "수익률(1일)",
        "ret_3d": "수익률(3일)",
        "ret_5d": "수익률(5일)",
        "ret_10d": "수익률(10일)",
        "knee_success": "매수 성공여부",
        "shoulder_success": "매도 성공여부",
    }
    existing_map = {key: value for key, value in rename_map.items() if key in view.columns}
    return view.rename(columns=existing_map)


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

knee_view = signals_df[signals_df["knee_score"] >= CANDIDATE_DISPLAY_MIN_SCORE].copy().sort_values(
    ["knee_score", "pct_change"], ascending=[False, False]
)
shoulder_view = signals_df[signals_df["shoulder_score"] >= CANDIDATE_DISPLAY_MIN_SCORE].copy().sort_values(
    ["shoulder_score", "pct_change"], ascending=[False, True]
)

knee_header_col, knee_help_col = st.columns([20, 1])
with knee_header_col:
    st.subheader("Knee Candidates")
with knee_help_col:
    render_candidate_help("Knee Candidates", "knee_score", "knee_reasons")
st.dataframe(
    format_candidate_view(knee_view, "knee_score", "knee_reasons"),
    use_container_width=True,
    hide_index=True,
    height=CANDIDATE_TABLE_HEIGHT,
    column_config=candidate_column_config(),
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
    height=CANDIDATE_TABLE_HEIGHT,
    column_config=candidate_column_config(),
)

st.subheader("종목 상세")
st.caption("후보 종목만 선택할 수 있습니다. Knee / Shoulder를 나눠서 고르세요.")

knee_options = (knee_view["symbol"] + " | " + knee_view["name"]).tolist()
shoulder_options = (shoulder_view["symbol"] + " | " + shoulder_view["name"]).tolist()

selector_col1, selector_col2 = st.columns(2)
with selector_col1:
    knee_selected = render_candidate_radio_grid("Knee Candidate", knee_options, "knee_candidate_radio")
with selector_col2:
    shoulder_selected = render_candidate_radio_grid("Shoulder Candidate", shoulder_options, "shoulder_candidate_radio")

selected_option = None
if knee_selected:
    selected_option = knee_selected
elif shoulder_selected:
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

validation_header_col, validation_help_col = st.columns([20, 1])
with validation_header_col:
    st.subheader("예측평가")
with validation_help_col:
    render_validation_help()
if not validation_df.empty:
    previous_eval_date = previous_business_date(analysis_date)
    if previous_eval_date:
        daily_validation = validation_df[validation_df["signal_date"].astype(str) == previous_eval_date].copy()
    else:
        daily_validation = pd.DataFrame()

    if daily_validation.empty:
        st.info("직전 거래일 기준으로 아직 표시할 예측평가 데이터가 없습니다.")
    else:
        st.caption(f"직전 거래일 기준 예측평가: {previous_eval_date}")
        st.dataframe(format_validation_view(daily_validation), use_container_width=True, hide_index=True)
else:
    st.info("예측평가 데이터가 아직 없습니다.")

st.markdown(
    """
    <div style="text-align:center; color:#6b7280; font-size:12px; margin-top:48px; padding-bottom:16px;">
        -created by alicia-
    </div>
    """,
    unsafe_allow_html=True,
)
