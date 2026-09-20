import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.colors as pcolors
import json
from snowflake.snowpark.context import get_active_session
import _snowflake
from typing import Any, Dict, List, Optional
import yaml



session = get_active_session()

PALE_COLORS = [
    "#A8DADC",
    "#BDE0FE",
    "#CDB4DB",
    "#FFC8DD",
    "#D8F3DC",
    "#FFF1B6",
    "#FFD6A5",
    "#CDEAC0"
]

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
 page_title="IBP Rejection Analytics",
 page_icon="📊",
 layout="wide"
    
)

st.title("📊 IBP Rejection Analytics Dashboard")

st.markdown(
"""
Monitor rejected records across Locations, Products and Validation Categories.
""")


session = get_active_session()

# Initialize session state chat memory exclusively for the Cortex Analyst tab
if "analyst_chat_history" not in st.session_state:
    st.session_state.analyst_chat_history = []

# =====================================================
# DATA LOAD
# =====================================================
@st.cache_data(ttl=300)

def load_data():
    query = """
    SELECT
    ID,
    CREATED_AT::DATE AS REJECTION_DATE,
    COALESCE(RECORD_DATA:LOCID::VARCHAR,RECORD_DATA:WERKS_IBP::VARCHAR) AS LOCATION_ID,
    RECORD_DATA:PRDID::VARCHAR AS PRODUCT_ID,
    REJECT_REASON,
    ACTUAL_SOURCE,
    MODEL_NAME,
    SOURCE_TABLE
    FROM DBT_STAGING.REJECTED_DATA_LOG
    """
    df = session.sql(query).to_pandas()
    
    columns_to_fill = [
        "LOCATION_ID",
        "PRODUCT_ID",
        "ACTUAL_SOURCE",
        "MODEL_NAME"
    ]
    df[columns_to_fill] = df[columns_to_fill].fillna("UNKNOWN")
 
    conditions = [
     df["REJECT_REASON"].str.contains("location_product", case=False, na=False),
     (df["REJECT_REASON"].str.contains("WHERE clause", case=False, na=False)) & (~df["REJECT_REASON"].str.contains("location_product", case=False, na=False)),
     df["REJECT_REASON"].str.contains("lookup", case=False, na=False),
     df["REJECT_REASON"].str.contains("duplicate", case=False, na=False),
     df["REJECT_REASON"].str.contains("null", case=False, na=False)
    ]
    
    categories = [
     "Missing Location-Product Mapping",
     "Business Rule Validation Failure",
     "Lookup Validation Failure",
     "Duplicate Record",
     "Missing Mandatory Data"
    ]
    
    df["REJECTION_CATEGORY"] = np.select(conditions, categories, default="Other Validation Failure")
    return df

df_original = load_data()

# =====================================================
# CUSTOM UI
# =====================================================

# st.markdown("""
# <style>

# .main{
#     background:#f6f8fc;
# }

# div[data-testid="metric-container"]{
#     background:white;
#     border-radius:12px;
#     padding:15px;
#     border:1px solid #e8ecf4;
#     box-shadow:0px 2px 6px rgba(0,0,0,0.07);
# }

# .stTabs [data-baseweb="tab"]{
#     font-size:16px;
#     font-weight:600;
# }

# </style>
# """, unsafe_allow_html=True)

# =====================================================
# SEARCH PANEL
# =====================================================

st.sidebar.header("🔍 Search Filters")

# Compact instructions using smaller text
st.sidebar.caption(
    "💡 **Tip:** You can search multiple comma-separated IDs.<br>"
    "*Example Locations:* `LOC01, LOC02`<br>"
    "*Example Products:* `PRD01, PRD02`",
    unsafe_allow_html=True
)

# 1. Callback function that forces the state keys to empty string values
def clear_search_filters():
    st.session_state["loc_search_key"] = ""
    st.session_state["prd_search_key"] = ""
    st.session_state["current_tab"] = "📍 Locations"
    # st.session_state["search_executed"] = False

def handle_search_change():
    if (
        not st.session_state.loc_search_key.strip()
        and not st.session_state.prd_search_key.strip()
    ):
        st.session_state.search_executed = False

# 2. Text boxes tied directly to the state keys
location_search = st.sidebar.text_input(
    "Location ID(s)",
    placeholder="e.g., LOC01, LOC02",
    key="loc_search_key",
    on_change=handle_search_change
)

product_search = st.sidebar.text_input(
    "Product ID(s)",
    placeholder="e.g., PRD01, PRD02",
    key="prd_search_key",
    on_change=handle_search_change
)



# Arrange Search and Reset buttons side-by-side
btn_col1, btn_col2 = st.sidebar.columns(2)

with btn_col1:
    search_clicked = st.button("🔍 Search",
                               use_container_width=True,
                               on_click=lambda: st.session_state.update
                               ({"current_tab": "📍 Locations"})
                              )   

with btn_col2:
    # 3. Use 'on_click' callback instead of an 'if' block assignment
    # This guarantees the backend states clear cleanly during the rerun cycle
    st.button(
        "🔄 Reset", 
        on_click=clear_search_filters, 
        use_container_width=True
    )

# 4. Extract comma-separated values safely
location_values = [
    x.strip().upper()
    for x in location_search.split(",")
    if x.strip()
]

product_values = [
    x.strip().upper()
    for x in product_search.split(",")
    if x.strip()
]


#debug the session_state
# st.write("search_executed =", st.session_state.get("search_executed"))
# st.write("location_values =", location_values)
# st.write("product_values =", product_values)

# st.write("loc:", repr(location_search))
# st.write("prd:", repr(product_search))

# =====================================================
# DATA FILTERING LOGIC
# =====================================================
df = df_original.copy()

if location_values:
    df = df[
        df["LOCATION_ID"]
        .astype(str)
        .str.upper()
        .isin(location_values)
    ]

if product_values:
    df = df[
        df["PRODUCT_ID"]
        .astype(str)
        .str.upper()
        .isin(product_values)
    ]

# =====================================================
# KPI CARDS
# =====================================================

c1, c2, c3 = st.columns(3)

with c1:
    st.metric(
        "🚨 Total Rejections",
        f"{len(df):,}"
    )

with c2:
    st.metric(
        "📍 Impacted Locations",
        df["LOCATION_ID"].nunique()
    )

with c3:
    st.metric(
        "📦 Impacted Products",
        df["PRODUCT_ID"].nunique()
    )

st.divider()


# with st.expander("✨ Cortex Analyst", expanded=True):

# ========================================
# SEARCH CRITERIA
# ========================================

def has_search_criteria():
    return bool(location_values or product_values)

def show_search_message():
    st.info(
        "Please enter one or more Location ID(s) or Product ID(s) and click Search."
    )


# =====================================================
# LOCATION TAB
# =====================================================
def locations_tab(df):
    
    st.subheader("📍 Location Rejections")

    if not has_search_criteria():
        show_search_message()
        return
    
    location_df = (
        df.groupby("LOCATION_ID")
        .size()
        .reset_index(name="TOTAL_REJECTIONS")
        .sort_values(
            "TOTAL_REJECTIONS",
            ascending=True
        )
        )
    if location_df.empty:
        st.warning("No matching locations found.")
    else:
         # Get the top 10 locations to keep the horizontal chart clean
         top_10_locations = location_df.tail(10) # tail because data is sorted ascending
         fig = px.bar(
             top_10_locations,
             y="LOCATION_ID",
             x="TOTAL_REJECTIONS",
             orientation="h",
             # 1. Map color to the rejection counts for the fade effect
             color="TOTAL_REJECTIONS", 
             text="TOTAL_REJECTIONS",
             color_continuous_scale=["#E9D8FD", "#4A154B"]
         )
         
         fig.update_layout(
             # Hides the color legend bar on the right to save horizontal space
             coloraxis_showscale=False,
                 xaxis={
                     'tickformat': 'd',  # Forces numbers to format as integers only (no 1.5, 2.5)
                     'nticks': 10        # Limits the axis to a maximum of 10 clean, spaced-out labels
                     },
             # 2. Configures the Y-Axis for horizontal bar sorting and clean labels
             yaxis={
                 'type': 'category',     
                 'categoryorder': 'total ascending' # Highest rejections stay at the top
             }
         )
         
         fig.update_traces(textposition='auto') #auto inside outside none
         
         st.plotly_chart(
             fig,
             use_container_width=True
         )
         
         # Displays the clean data table below just like the products tab
         # st.markdown("### 📋 Total Rejected Locations List")
         # st.dataframe(
         #     location_df.sort_values("TOTAL_REJECTIONS", ascending=False)[["LOCATION_ID", "TOTAL_REJECTIONS"]],
         #     hide_index=True,
         #     use_container_width=True
         # )

# =====================================================
# PRODUCT TAB
# =====================================================

def products_tab(df):
    
    st.subheader("📦 Product Rejections")

    if not has_search_criteria():
        show_search_message()
        return

    product_df = (
        df.groupby(["PRODUCT_ID", "MODEL_NAME", "ACTUAL_SOURCE","LOCATION_ID"])
        .size()
        .reset_index(name="TOTAL_REJECTIONS")
        .sort_values(
            "TOTAL_REJECTIONS",
            ascending=False
        )
    )

    product_df_chart = (
        df.groupby(["PRODUCT_ID"])
        .size()
        .reset_index(name="TOTAL_REJECTIONS")
        .sort_values(
            "TOTAL_REJECTIONS",
            ascending=False
        )
    )

    
    sorted_df = product_df.sort_values(by="TOTAL_REJECTIONS", ascending=False)
    top_10_products = sorted_df.head(10)
    
    if product_df.empty:
        st.warning("No matching products found.")
        return

    top_20_products = product_df_chart.head(20)
    
    fig = px.bar(
        top_20_products,
        x="PRODUCT_ID",
        y="TOTAL_REJECTIONS",
        color="TOTAL_REJECTIONS",
        text="TOTAL_REJECTIONS",
        color_continuous_scale=["#E8A7A1", "#5C0601"]
    )
    fig.update_layout(
    coloraxis_showscale=False,  # Optional: Hides the color legend bar on the right
    coloraxis_cmin=product_df["TOTAL_REJECTIONS"].min() - 1, 
        xaxis={
            'type': 'category',     # Treats product IDs cleanly as labels
            'categoryorder': 'total descending'
        },
        yaxis={
            'tickformat': 'd',  # Forces numbers to format as integers only (no 1.5, 2.5)
            'nticks': 10        # Limits the axis to a maximum of 10 clean, spaced-out labels
            }
    )
    
        # Tabs
    chart_tab, data_tab = st.tabs(
        [
            "Chart",
            "Data",
        ]
    )

    with chart_tab:
        fig.update_traces(textposition='auto')
        st.plotly_chart(fig, use_container_width=True)
        
    with data_tab:
        st.markdown("<p style='font-size:16px; font-weight:600; margin-bottom:15px;'>📋 Top 10 Rejected Products Details</p>",
                    unsafe_allow_html=True)
        st.dataframe(
        top_10_products[["PRODUCT_ID", "LOCATION_ID", "MODEL_NAME", "ACTUAL_SOURCE", "TOTAL_REJECTIONS"]],
        hide_index=True,
        use_container_width=True
            )
            
# =====================================================
# CATEGORY TAB
# =====================================================
def categories_tab(df):

    if not has_search_criteria():
        show_search_message()
        return

    st.subheader("🗂️ Rejection Categories")

    category_df = (
        df.groupby(
            ["REJECTION_CATEGORY", "MODEL_NAME", "ACTUAL_SOURCE"]
        )
        .size()
        .reset_index(name="TOTAL_REJECTIONS")
        .sort_values("TOTAL_REJECTIONS", ascending=False)
    )

    if category_df.empty:
        st.warning("No rejection category data found.")
        return

    # Calculate percentages
    total_sum = category_df["TOTAL_REJECTIONS"].sum()
    category_df["PERCENTAGE"] = (
        category_df["TOTAL_REJECTIONS"] / total_sum * 100
    )

    # Color function
    def assign_percentage_color(pct):
        if pct >= 60:
            return "#134E4A"
        elif pct >= 50:
            return "#0F766E"
        elif pct >= 40:
            return "#14B8A6"
        elif pct >= 30:
            return "#2DD4BF"
        elif pct >= 20:
            return "#99F6E4"
        else:
            return "#CCFBF1"

    assigned_colors = [
        assign_percentage_color(p)
        for p in category_df["PERCENTAGE"]
    ]

    # Create pie chart
    fig = px.pie(
        category_df,
        names="REJECTION_CATEGORY",
        values="TOTAL_REJECTIONS",
        hole=0.45,
        color_discrete_sequence=assigned_colors,
    )

    fig.update_traces(textinfo="percent")

    fig.update_layout(
        title="Category Distribution by Volume Share",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.1,
            xanchor="center",
            x=0.5,
        )
    )

    # Tabs
    chart_tab, data_tab = st.tabs(
        [
            "Chart",
            "Data"            
        ]
    )
    with chart_tab:
        st.plotly_chart(fig, use_container_width=True)
        
    with data_tab:
        st.markdown(
            "<p style='font-size:16px; font-weight:600; margin-bottom:15px;'>Category Summary</p>",
            unsafe_allow_html=True)
        
        st.dataframe(
            category_df[
                [
                    "REJECTION_CATEGORY",
                    "MODEL_NAME",
                    "ACTUAL_SOURCE",
                    "TOTAL_REJECTIONS",
                    "PERCENTAGE",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )


# =====================================================
# TREND TAB
# =====================================================

def trend_tab(df):

    if not has_search_criteria():
        show_search_message()
        return
  
    st.subheader("📈 Rejection Trend")

    # -----------------------------------------
    # DETERMINE TREND MODE
    # -----------------------------------------

    trend_mode = None

    if location_values:
        trend_mode = "LOCATION"

    elif product_values:
        trend_mode = "PRODUCT"

    # -----------------------------------------
    # NO SEARCH PROVIDED
    # -----------------------------------------

    if trend_mode is None:

        st.info(
            """
            Please enter Location ID(s) or Product ID(s)
            to view rejection trend.
            """
        )

    # -----------------------------------------
    # DATA AVAILABLE
    # -----------------------------------------

    elif df.empty:

        st.warning(
            "No matching records found."
        )

    else:

        trend_df = df.copy()

        trend_df["REJECTION_DATE"] = pd.to_datetime(
            trend_df["REJECTION_DATE"]
        )

        # Keep only date
        trend_df["TREND_DATE"] = (
            trend_df["REJECTION_DATE"]
            .dt.date
        )

        # =====================================
        # LOCATION TREND
        # =====================================

        if trend_mode == "LOCATION":

            trend_data = (
                trend_df
                .groupby(
                    ["TREND_DATE", "LOCATION_ID"]
                )
                .size()
                .reset_index(
                    name="REJECTED_RECORDS"
                )
                .sort_values(
                    "TREND_DATE"
                )
            )

            if trend_data.empty:

                st.warning(
                    "No trend data available."
                )

            else:

                fig = px.line(
                    trend_data,
                    x="TREND_DATE",
                    y="REJECTED_RECORDS",
                    title="3-Day Rejection Trend",
                    color="LOCATION_ID",
                    markers=True,
                    color_discrete_sequence = [                        
                        "#4E79A7",  # Blue
                        "#F28E2B",  # Orange
                        "#59A14F",  # Green
                        "#E15759",  # Red
                        "#B07AA1",  # Purple
                        "#76B7B2",  # Teal
                        "#EDC948",  # Gold
                        "#9C755F",  # Brown
                        "#FF6F91",  # Pink
                        "#17BECF"   # Cyan
                    ]
                )

                # fig.update_traces(
                #     line_shape="linear",
                #     line_width=4,
                #     marker_size=10
                # )
                fig.update_traces(
                mode="lines+markers",  # Shows lines and clean anchor data dots
                line=dict(shape="linear", width=3), # REQUIREMENT 5: Forces straight lines, not curvy
                marker=dict(size=8)
                    )
                
                fig.update_layout(
                    title="Location-wise Daily Rejection Trend",
                    xaxis_title="Date",
                    yaxis_title="Rejected Records",
                    hovermode="x unified",
                    # plot_bgcolor="white",
                    # paper_bgcolor="white",
                    xaxis={
                        'type': 'date',
                        'tickformat': '%Y-%m-%d',  # REQUIREMENT 5: Displays ONLY date, hides time completely
                        'dtick': 86400000          # Forces exactly 1-day step intervals (value in milliseconds)
                        },
                    # Y-Axis dynamic integer formatting
                    yaxis={
                        'tickformat': 'd',         # Forces whole numbers for rejection counts
                        'nticks': 6                # Clean vertical label spacing
                        }
                    )

                # Tabs
                chart_tab, data_tab = st.tabs(
                    [
                        "Chart",
                        "Data"            
                    ]
                )
                with chart_tab:
                    st.plotly_chart(fig, use_container_width=True)
                    
                with data_tab:
                    st.markdown(
                        "<p style='font-size:16px; font-weight:600; margin-bottom:15px;'>Location-wise Daily Rejection Trend</p>",
                        unsafe_allow_html=True)
                    
                    st.dataframe(
                    trend_data,
                    use_container_width=True,
                    hide_index=True
                )
        # --------------------------------------
        # PRODUCT TREND
        # --------------------------------------

        elif trend_mode == "PRODUCT":

            trend_data = (
                trend_df.groupby(
                    ["TREND_DATE", "PRODUCT_ID"]
                )
                .size()
                .reset_index(
                    name="REJECTED_RECORDS"
                )
            )

            fig = px.line(
                trend_data,
                x="TREND_DATE",
                y="REJECTED_RECORDS",
                color="PRODUCT_ID",
                markers=True,
                color_discrete_sequence=
                px.colors.qualitative.Pastel
            )

            # fig.update_traces(
            #     line_shape="linear",
            #     line_width=4
            # )
            
            fig.update_traces(
            mode="lines+markers",  # Shows lines and clean anchor data dots
            line=dict(shape="linear", width=3), # REQUIREMENT 5: Forces straight lines, not curvy
            marker=dict(size=8)
                    )
            
            fig.update_layout(
                title="Product-wise Rejection Trend",
                xaxis_title="Date",
                yaxis_title="Rejected Records",
                xaxis={
                    'type': 'date',
                    'tickformat': '%Y-%m-%d',  # Displays ONLY date, hides time completely
                    'dtick': 86400000          # Forces exactly 1-day step intervals (value in milliseconds)
                    },
                # Y-Axis dynamic integer formatting
                yaxis={
                    'tickformat': 'd',         # Forces whole numbers for rejection counts
                    'nticks': 6                # Clean vertical label spacing
                    }
            )
            # Tabs
            chart_tab, data_tab = st.tabs(
                [
                    "Chart",
                    "Data"            
                ]
            )
            with chart_tab:
                st.plotly_chart(fig, use_container_width=True)
                
            with data_tab:
                st.markdown(
                    "<p style='font-size:16px; font-weight:600; margin-bottom:15px;'>Product-wise Daily Rejection Trend</p>",
                    unsafe_allow_html=True)
                
                st.dataframe(
                trend_data,
                use_container_width=True,
                hide_index=True
            )
# =====================================================
# CORTEX ANALYST
# =====================================================

def cortex_analyst_tab():

    DATABASE = "DEV"
    SCHEMA = "DBT_STAGING"
    STAGE = "REJECTIONS_STAGE"
    FILE = "REJECTIONS.yaml"

    st.subheader("✨ Cortex Analyst - AI Chat")

    # =====================================================
    # SESSION STATE
    # =====================================================

    if "cortex_messages" not in st.session_state:
        st.session_state.cortex_messages = []
    
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None
    
    if "onboarding_questions" not in st.session_state:
        st.session_state.onboarding_questions = []
    
    if "first_query_done" not in st.session_state:
        st.session_state.first_query_done = False

    # st.write("Current Tab:", st.session_state.current_tab)
    st.write("Messages:", len(st.session_state.cortex_messages))
    # st.write("First Query Done:", st.session_state.first_query_done)
    # st.write("Questions Count:", len(st.session_state.onboarding_questions))
    
    # =====================================================
    # CORTEX API CALL
    # =====================================================

    def send_message(prompt: str) -> Dict[str, Any]:

        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "semantic_model_file": (
                f"@{DATABASE}.{SCHEMA}.{STAGE}/{FILE}"
            )
        }

        resp = _snowflake.send_snow_api_request(
            "POST",
            "/api/v2/cortex/analyst/message",
            {},
            {},
            request_body,
            {},
            30000,
        )

        parsed = json.loads(resp["content"])

        return {
            "message": parsed["message"],
            "request_id": parsed.get("request_id", "")
        }

# =====================================================
# LOAD ONBOARDING QUESTIONS FROM VERIFIED_QUERIES
# =====================================================

    def load_onboarding_questions():
    
        if st.session_state.get("onboarding_questions"):
            return
    
        try:
    
            stage_file = f"@{DATABASE}.{SCHEMA}.{STAGE}/{FILE}"
    
            # Read semantic YAML from stage
            with session.file.get_stream(stage_file) as f:
                yaml_content = f.read().decode("utf-8")
    
            semantic_model = yaml.safe_load(yaml_content)
    
            onboarding_questions = []
    
            # Extract onboarding questions from verified_queries
            for query in semantic_model.get("verified_queries", []):
    
                if query.get("use_as_onboarding_question", False):
    
                    question = query.get("question")
    
                    if question:
                        onboarding_questions.append(question)
    
            # Fallback if none found
            if not onboarding_questions:
    
                onboarding_questions = [
                    "Which locations have the highest rejection count?",
                    "Which products have the most rejections?",
                    "Show rejection trend by month",
                    "Which category has maximum rejections?",
                    "What are the top 10 rejected products?"
                ]
    
            st.session_state.onboarding_questions = onboarding_questions
    
        except Exception as e:
    
            st.error(
                f"Unable to load onboarding questions from semantic model: {e}"
            )
    
            st.session_state.onboarding_questions = [
                "Which locations have the highest rejection count?",
                "Which products have the most rejections?",
                "Show rejection trend by month",
                "Which category has maximum rejections?",
                "What are the top 10 rejected products?"
            ]
    
    
    load_onboarding_questions()
    
    # =====================================================
    # DISPLAY RESPONSE
    # =====================================================
    def detect_chart_type(df):
    
        numeric_cols = (
            df.select_dtypes(include=["number"])
            .columns
            .tolist()
        )
    
        categorical_cols = [
            c for c in df.columns
            if c not in numeric_cols
        ]
    
        has_date = any(
            any(
                keyword in col.lower()
                for keyword in [
                    "date",
                    "day",
                    "month",
                    "year",
                    "trend"
                ]
            )
            for col in df.columns
        )
    
        cols_lower = [c.lower() for c in df.columns]
    
        # Single row -> table
        if len(df) <= 1:
            return "table"
    
        # Rejection Category Distribution
        if (
            "rejection_category" in cols_lower
            and "total_rejections" in cols_lower
            and len(numeric_cols) == 1
            and len(categorical_cols) == 1
        ):
            return "pie"
    
        # Trend data
        if has_date and "total_rejections" in cols_lower and len(numeric_cols) == 1:
            return "line"
    
        # Category + Measure
        if len(categorical_cols) == 1 and len(numeric_cols) == 1:
            return "bar"
    
        # Category + Category + Measure
        if (len(categorical_cols) == 2 
            and len(numeric_cols) == 1 
            and "rejection_category" in [c.lower() for c in df.columns]
           ):
            return "grouped_bar"
    
        return "table"
        
# ============================================================
    def display_content(
        content,
        request_id=None,
        message_index=None
    ):

        if request_id:
            with st.expander("Request ID"):
                st.write(request_id)

        for item in content:

            if item["type"] == "text":

                st.markdown(item["text"])

            elif item["type"] == "suggestions":

                with st.expander(
                    "Suggestions",
                    expanded=True
                ):

                    for idx, suggestion in enumerate(
                        item["suggestions"]
                    ):

                        if st.button(
                            suggestion,
                            key=f"sugg_{message_index}_{idx}"
                        ):
                            st.session_state.pending_prompt = suggestion
                            st.rerun()

            elif item["type"] == "sql":
                
                verified_query = (
                    item.get("confidence", {})
                        .get("verified_query_used")
                    )
                # debug
                # st.write("Verified Query Used:", verified_query)
                
                if verified_query:
                    st.markdown( """
                    <span style="color:#28A745;font-size:0.9rem;">
                    <i><u>Generated based on verified query</u></i>
                     </span>""",unsafe_allow_html=True)
                else:
                    st.markdown( """
                    <span style="color:#29B5E8;font-size:0.9rem;">
                    <i><u>Cortex Analyst generated response</u></i>
                     </span>""",unsafe_allow_html=True)
                
                # cortex generated SQL
                # with st.expander("Generated SQL",expanded=False):
                #     st.code(item["statement"],language="sql")
                    
                with st.expander(
                    "Results",
                    expanded=True
                ):

                    try:

                        result_df = (
                            session.sql(
                                item["statement"]
                            )
                            .to_pandas()
                        )
                        
                        if len(result_df.index) > 0:
                        
                            chart_type = detect_chart_type(result_df)
                        
                            if chart_type == "table":
                        
                                st.dataframe(
                                    result_df,
                                    use_container_width=True
                                )
                        
                            else:
                        
                                data_tab, chart_tab = st.tabs(
                                    [
                                        "Data",
                                        "Chart"
                                    ]
                                )
                        
                                with data_tab:
                        
                                    st.dataframe(
                                        result_df,
                                        use_container_width=True
                                    )
                        
                                with chart_tab:
                        
                                    numeric_cols = (
                                        result_df.select_dtypes(include=["number"])
                                        .columns
                                        .tolist()
                                    )
                        
                                    categorical_cols = [
                                        c
                                        for c in result_df.columns
                                        if c not in numeric_cols
                                    ]
                        
                                    value_col = next(
                                        (
                                            col
                                            for col in result_df.columns
                                            if col.lower() == "total_rejections"
                                        ),
                                        numeric_cols[0] if numeric_cols else None
                                    )
                        
                                    if value_col is None:
                        
                                        st.info(
                                            "No numeric column available for charting."
                                        )
                        
                                    # =====================================
                                    # LINE CHART
                                    # =====================================
                        
                                    elif chart_type == "line":
                        
                                        x_col = result_df.columns[0]
                                        chart_key = f"{request_id}_line"
                        
                                        fig = px.line(
                                            result_df,
                                            x=x_col,
                                            y=value_col,
                                            markers=True
                                        )
                        
                                        fig.update_traces(
                                            mode="lines+markers",
                                            line=dict(width=3),
                                            marker=dict(size=8)
                                        )
                        
                                        fig.update_layout(
                                            xaxis_title=x_col,
                                            yaxis_title=value_col,
                                            hovermode="x unified"
                                        )
                        
                                        st.plotly_chart(
                                            fig,
                                            use_container_width=True,
                                            key=chart_key
                                        )
                                    # =====================================
                                    # PIE / DONUT CHART
                                    # =====================================
                                    
                                    elif chart_type == "pie":
                                        chart_key = f"{request_id}_pie"
                                    
                                        category_col = next(
                                            col
                                            for col in result_df.columns
                                            if col.lower() == "rejection_category"
                                        )
                                    
                                        fig = px.pie(
                                            result_df,
                                            names=category_col,
                                            values=value_col,
                                            hole=0.45,
                                            color_discrete_sequence=[
                                                "#4E79A7",
                                                "#F28E2B",
                                                "#59A14F",
                                                "#E15759",
                                                "#B07AA1",
                                                "#76B7B2",
                                                "#EDC948",
                                                "#FF6F91"
                                            ]
                                        )
                                    
                                        fig.update_traces(
                                            textposition="outside",
                                            textinfo="label+percent",
                                            outsidetextfont=dict(size=12),
                                            marker=dict(line=dict(color="#FFFFFF", width=1))
                                        )
                                    
                                        fig.update_layout(
                                            title=dict(
                                                text="Rejection Category Distribution",
                                                x=0.5
                                            ),
                                            margin=dict(t=100, b=50, l=50, r=200),
                                            legend=dict(
                                                orientation="v",
                                                yanchor="middle",
                                                y=0.5,
                                                xanchor="left",
                                                x=1.02
                                            )
                                        )
                                    
                                        st.plotly_chart(
                                            fig,
                                            use_container_width=True,
                                            chart_key = f"{request_id}_pie"
                                        )
                                    # =====================================
                                    # BAR CHART
                                    # =====================================
                        
                                    elif chart_type == "bar":

                                        chart_key = f"{request_id}_bar"
                        
                                        category_col = categorical_cols[0]
                        
                                        chart_df = (
                                            result_df
                                            .sort_values(
                                                value_col,
                                                ascending=True
                                            )
                                            .tail(20)
                                        )
                        
                                        fig = px.bar(
                                            chart_df,
                                            y=category_col,
                                            x=value_col,
                                            orientation="h",
                                            text=value_col,
                                            color=value_col,
                                            color_continuous_scale=[
                                                "#A8DADC",
                                                "#1D3557"
                                            ]
                                        )
                        
                                        fig.update_layout(
                                            coloraxis_showscale=False,
                                            yaxis={
                                                "categoryorder":
                                                "total ascending"
                                            },
                                            xaxis_title=value_col,
                                            yaxis_title=category_col
                                        )
                        
                                        fig.update_traces(
                                            textposition="outside"
                                        )
                        
                                        st.plotly_chart(
                                            fig,
                                            use_container_width=True,
                                            key=chart_key
                                        )
                        
                                    # =====================================
                                    # GROUPED BAR CHART
                                    # =====================================
                                    elif chart_type == "grouped_bar":
                                        
                                        chart_key = f"{request_id}_grouped_bar"

                                        fig = px.bar(
                                            result_df,
                                            y=categorical_cols[0],
                                            x=value_col,
                                            color=categorical_cols[1],
                                            orientation="h",
                                            barmode="group",
                                            text=value_col,
                                            color_discrete_sequence=[
                                                "#4E79A7",
                                                "#F28E2B",
                                                "#59A14F",
                                                "#E15759",
                                                "#B07AA1",
                                                "#76B7B2",
                                                "#EDC948",
                                                "#FF6F91",
                                                "#17BECF",
                                                "#9C755F"
                                            ]
                                        )
                                    
                                        fig.update_traces(
                                            textposition="outside"
                                        )
                                    
                                        fig.update_layout(
                                            height=max(500, len(result_df) * 60),
                                            bargap=0.35,
                                            bargroupgap=0.15,
                                            xaxis_title=value_col,
                                            yaxis_title=categorical_cols[0],
                                            legend_title=categorical_cols[1]
                                        )
                                        
                                        st.plotly_chart(
                                            fig,
                                            use_container_width=True,
                                            key=chart_key
                                            )
                        
                        else:
                        
                            st.warning(
                                "No data returned."
                            )
                            
                    except Exception as e:
                        st.error(
                            f"Failed to execute SQL: {e}" )

    # =====================================================
    # PROCESS QUERY
    # =====================================================

    def process_message(prompt):
    
        st.session_state.first_query_done = True
    
        st.session_state.cortex_messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        )
    
        try:
    
            response = send_message(prompt)

            # to_print the api response
            # st.json(response)
    
            content = response["message"]["content"]
    
            request_id = response["request_id"]
    
            st.session_state.cortex_messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    "request_id": request_id,
                }
            )
    
        except Exception as e:
    
            st.session_state.cortex_messages.append(
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: {str(e)}"
                        }
                    ]
                }
            )
    
# =====================================================
# PROCESS PENDING PROMPT
# =====================================================

    if st.session_state.pending_prompt:
    
        prompt = st.session_state.pending_prompt
    
        st.session_state.pending_prompt = None
    
        with st.spinner("Thinking..."):
            process_message(prompt)
    
        st.rerun()

    # =====================================================
    # CHAT HISTORY
    # =====================================================

    # st.markdown(f"Semantic Model: `{FILE}`")
    
    for idx, message in enumerate(
        st.session_state.cortex_messages
    ):
    
        with st.chat_message(message["role"]):
    
            display_content(
                content=message["content"],
                request_id=message.get("request_id"),
                message_index=idx
            )
    # =====================================================
    # ONBOARDING QUESTIONS
    # ONLY BEFORE FIRST QUERY
    # =====================================================

    if (
        not st.session_state.first_query_done
        and len(st.session_state.onboarding_questions) > 0
    ):
    
        st.markdown("### Suggested Questions")
    
        cols = st.columns(2)
    
        for idx, question in enumerate(
            st.session_state.onboarding_questions
        ):
    
            with cols[idx % 2]:
    
                if st.button(
                    question,
                    key=f"onboard_{idx}",
                    use_container_width=True
                ):
    
                    st.session_state.pending_prompt = question
                    st.rerun()

    # =====================================================
    # INPUT BOX
    # =====================================================
    user_question = st.chat_input(
    "Ask your question about rejection data..."
    )

    if user_question:
    
        with st.spinner("Thinking..."):
            process_message(user_question)
    
        st.rerun()

# =====================================================
# TABS
# =====================================================

if "current_tab" not in st.session_state:
    st.session_state.current_tab = "📍 Locations"

selected_tab = st.segmented_control(
    "",
    [
        "📍 Locations",
        "📦 Products",
        "🗂️ Categories",
        "📈 Trend",
        "✨ Cortex Analyst"
    ],
    key="current_tab"
)
# st.write("Current tab:", st.session_state.get("current_tab"))


TAB_ROUTER = {
    "📍 Locations": lambda: locations_tab(df),
    "📦 Products": lambda: products_tab(df),
    "🗂️ Categories": lambda: categories_tab(df),
    "📈 Trend": lambda: trend_tab(df),
    "✨ Cortex Analyst": cortex_analyst_tab
}

TAB_ROUTER[selected_tab]()