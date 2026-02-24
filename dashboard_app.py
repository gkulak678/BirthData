import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide")
st.title("Provisional Natality Data Dashboard")
st.subheader("Birth Analysis by State and Gender")


def _normalize_col_name(name):
    name = str(name).strip().lower().replace(" ", "_")
    while "__" in name:
        name = name.replace("__", "_")
    return name


def _canonical_key(name):
    normalized = _normalize_col_name(name)
    return "".join(ch for ch in normalized if ch.isalnum())


def _match_required_fields(columns):
    logical_fields = [
        "state_of_residence",
        "month",
        "month_code",
        "year_code",
        "sex_of_infant",
        "births",
    ]

    alias_map = {
        "state_of_residence": {
            "stateofresidence",
            "stateresidence",
            "residencestate",
            "state",
        },
        "month": {"month"},
        "month_code": {"monthcode"},
        "year_code": {"yearcode"},
        "sex_of_infant": {
            "sexofinfant",
            "infantsex",
            "sex",
            "gender",
            "infantgender",
        },
        "births": {
            "births",
            "birthcount",
            "birthcounts",
            "numberofbirths",
            "livebirths",
            "totalbirths",
        },
    }

    canonical_to_cols = {}
    for col in columns:
        ck = _canonical_key(col)
        canonical_to_cols.setdefault(ck, []).append(col)

    matched = {}
    for field in logical_fields:
        if field in columns:
            matched[field] = field
            continue

        target_ck = _canonical_key(field)
        candidates = []

        if target_ck in canonical_to_cols:
            candidates.extend(canonical_to_cols[target_ck])

        for alias_ck in alias_map.get(field, set()):
            if alias_ck in canonical_to_cols:
                candidates.extend(canonical_to_cols[alias_ck])

        deduped = []
        seen = set()
        for c in candidates:
            if c not in seen:
                deduped.append(c)
                seen.add(c)

        if len(deduped) == 1:
            matched[field] = deduped[0]

    missing = [f for f in logical_fields if f not in matched]
    return matched, missing


@st.cache_data(show_spinner=False)
def load_data():
    try:
        df = pd.read_csv("Provisional_Natality_2025_CDC.csv")
    except FileNotFoundError:
        return None, "file_not_found", None, None
    except Exception as e:
        return None, "read_error", str(e), None

    df.columns = [_normalize_col_name(c) for c in df.columns]

    matched, missing = _match_required_fields(list(df.columns))
    if missing:
        return df, "missing_columns", missing, matched

    rename_to_logical = {actual: logical for logical, actual in matched.items()}
    df = df.rename(columns=rename_to_logical)

    df["births"] = pd.to_numeric(df["births"], errors="coerce")
    df = df.dropna(subset=["births"]).copy()

    for col in ["state_of_residence", "month", "sex_of_infant"]:
        df[col] = df[col].astype(str).str.strip()

    df["month_code"] = pd.to_numeric(df["month_code"], errors="coerce")
    df["year_code"] = pd.to_numeric(df["year_code"], errors="coerce")

    return df, "ok", None, matched


df, status, detail, matched = load_data()

if status == "file_not_found":
    st.error("Dataset file not found in repository.")
    st.stop()

if status == "read_error":
    st.error(f"Error reading dataset: {detail}")
    st.stop()

if status == "missing_columns":
    st.error("Missing required logical fields: " + ", ".join(detail))
    st.write(df.columns)
    st.stop()

state_options = sorted(
    [
        x
        for x in df["state_of_residence"].dropna().unique().tolist()
        if str(x).strip() != ""
    ]
)
gender_options = sorted(
    [
        x
        for x in df["sex_of_infant"].dropna().unique().tolist()
        if str(x).strip() != ""
    ]
)

month_df = df[["month", "month_code"]].dropna(subset=["month"]).drop_duplicates().copy()
month_df["month_code_sort"] = pd.to_numeric(month_df["month_code"], errors="coerce")
month_df = month_df.sort_values(by=["month_code_sort", "month"], na_position="last")
month_options = month_df["month"].astype(str).tolist()

selected_months = st.sidebar.multiselect("Month", ["All"] + month_options, default=["All"])
selected_genders = st.sidebar.multiselect("Gender", ["All"] + gender_options, default=["All"])
selected_states = st.sidebar.multiselect("State", ["All"] + state_options, default=["All"])

filtered_df = df.copy()

if "All" not in selected_months:
    filtered_df = filtered_df[filtered_df["month"].isin(selected_months)]

if "All" not in selected_genders:
    filtered_df = filtered_df[filtered_df["sex_of_infant"].isin(selected_genders)]

if "All" not in selected_states:
    filtered_df = filtered_df[filtered_df["state_of_residence"].isin(selected_states)]

if filtered_df.empty:
    st.warning("No data available for the selected filters.")
    st.dataframe(
        filtered_df.reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
    )
    st.stop()

agg_df = (
    filtered_df.groupby(["state_of_residence", "sex_of_infant"], as_index=False)["births"]
    .sum()
    .sort_values("state_of_residence")
)

fig = px.bar(
    agg_df,
    x="state_of_residence",
    y="births",
    color="sex_of_infant",
    title="Total Births by State and Gender",
    template="plotly_white",
)

fig.update_layout(
    legend_title_text="Gender",
    xaxis_title="State of Residence",
    yaxis_title="Births",
    paper_bgcolor="white",
    plot_bgcolor="white",
)

st.plotly_chart(fig, use_container_width=True, config={"responsive": True})

display_cols = [
    c
    for c in [
        "state_of_residence",
        "month",
        "month_code",
        "year_code",
        "sex_of_infant",
        "births",
    ]
    if c in filtered_df.columns
]
table_df = filtered_df[display_cols].sort_values(
    by=[c for c in ["state_of_residence", "month_code", "sex_of_infant"] if c in filtered_df.columns]
).reset_index(drop=True)

st.dataframe(table_df, use_container_width=True, hide_index=True)
