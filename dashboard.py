import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import func
from database import SessionLocal, engine, Base
from models import RawReview, ExtractedTheme, ValidatedInsight
from mcp_server.google_client import GoogleWorkspaceClient

# Ensure DB is created
Base.metadata.create_all(bind=engine)

st.set_page_config(page_title="Blinkit Review Analyzer", page_icon="🛍️", layout="wide")

st.title("🛍️ Blinkit Review Analyzer Dashboard")
st.markdown("Analyze raw reviews, visualize extracted themes, and validate problem statements.")

# Initialize DB session
@st.cache_resource
def get_db_session():
    return SessionLocal()

db = get_db_session()

# --- Tabs ---
tab1, tab2, tab3 = st.tabs(["📊 Themes & Insights", "📝 Validation Workspace", "🗃️ Raw Reviews"])

# --- TAB 1: Themes & Insights ---
with tab1:
    st.header("Extracted Themes Analysis")
    
    # Fetch themes aggregated
    themes_query = db.query(
        ExtractedTheme.theme_tag,
        func.count(ExtractedTheme.id).label('review_count'),
        func.avg(ExtractedTheme.sentiment_score).label('avg_sentiment')
    ).group_by(ExtractedTheme.theme_tag).all()
    
    if not themes_query:
        st.info("No themes extracted yet. Run the NLP ingestion pipeline.")
    else:
        # Process into DataFrame
        data = []
        for t in themes_query:
            # Source diversity
            review_ids = db.query(ExtractedTheme.review_id).filter(ExtractedTheme.theme_tag == t.theme_tag).subquery()
            sources = db.query(RawReview.source).filter(RawReview.id.in_(review_ids)).distinct().all()
            source_count = len(sources)
            
            data.append({
                "Theme": t.theme_tag,
                "Mentions": t.review_count,
                "Source Diversity": source_count,
                "Ranking Score": t.review_count * source_count,
                "Avg Sentiment": round(t.avg_sentiment, 2) if t.avg_sentiment else 0.0
            })
            
        df_themes = pd.DataFrame(data).sort_values("Ranking Score", ascending=False)
        
        # Display Metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Unique Themes", len(df_themes))
        col2.metric("Most Frequent Theme", df_themes.iloc[0]["Theme"] if len(df_themes) > 0 else "N/A")
        col3.metric("Lowest Sentiment Theme", df_themes.sort_values("Avg Sentiment").iloc[0]["Theme"] if len(df_themes) > 0 else "N/A")
        
        st.divider()
        
        # Visualizations
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.subheader("Theme Frequency")
            fig1 = px.bar(df_themes.head(10), x="Mentions", y="Theme", orientation='h', 
                          title="Top 10 Themes by Mentions", color="Avg Sentiment", color_continuous_scale="RdYlGn")
            fig1.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_chart2:
            st.subheader("Theme Ranking Score (Frequency × Sources)")
            fig2 = px.bar(df_themes.head(10), x="Theme", y="Ranking Score", 
                          title="Top 10 Themes by Priority Score", color="Source Diversity", color_continuous_scale="Blues")
            st.plotly_chart(fig2, use_container_width=True)
            
        st.subheader("Detailed Theme Data")
        st.dataframe(df_themes, use_container_width=True)


# --- TAB 2: Validation Workspace ---
with tab2:
    st.header("Validate & Export Problem Statements")
    st.markdown("Review extracted themes and formalize them into validated insights.")
    
    if not themes_query:
        st.warning("No themes available for validation.")
    else:
        # Select theme to validate
        selected_theme = st.selectbox("Select a Theme to Validate", [t.theme_tag for t in themes_query])
        
        # Show sample quotes for selected theme
        st.subheader(f"Evidence for '{selected_theme}'")
        quotes = db.query(ExtractedTheme.sentence_extract).filter(ExtractedTheme.theme_tag == selected_theme).limit(5).all()
        for i, q in enumerate(quotes):
            st.markdown(f"> *\"{q[0]}\"*")
            
        st.divider()
        
        # Validation Form
        st.subheader("Formalize Insight")
        existing_validation = db.query(ValidatedInsight).filter(ValidatedInsight.theme_tag == selected_theme).first()
        
        with st.form("validation_form"):
            val_status = st.selectbox(
                "Validation Status", 
                ["Draft", "Confirmed via Interviews", "Partially Confirmed", "Rejected"],
                index=["Draft", "Confirmed via Interviews", "Partially Confirmed", "Rejected"].index(existing_validation.validation_status) if existing_validation else 0
            )
            insight_stmt = st.text_area(
                "Problem Statement", 
                value=existing_validation.insight_statement if existing_validation else f"Users are experiencing issues with {selected_theme}...",
                height=100
            )
            quotes_input = st.text_area(
                "Interview Quotes (One per line)", 
                value="\n".join(existing_validation.interview_quotes) if existing_validation and existing_validation.interview_quotes else ""
            )
            
            submitted = st.form_submit_button("Save Validation")
            if submitted:
                quotes_list = [q.strip() for q in quotes_input.split("\n") if q.strip()]
                if not existing_validation:
                    new_val = ValidatedInsight(
                        theme_tag=selected_theme,
                        insight_statement=insight_stmt,
                        validation_status=val_status,
                        interview_quotes=quotes_list
                    )
                    db.add(new_val)
                else:
                    existing_validation.insight_statement = insight_stmt
                    existing_validation.validation_status = val_status
                    existing_validation.interview_quotes = quotes_list
                db.commit()
                st.success("Validation saved successfully!")

        st.divider()
        st.subheader("Export to Google Docs")
        st.markdown("Push all validated insights to your Google Doc.")
        
        doc_id = st.text_input("Google Doc ID", value="1UD5zLCvLz6p8bNprxneDPai2Y366nuPcZR1qelGzWKA")
        week_tag = st.text_input("Week Tag", value="2026-W32")
        
        if st.button("Export Insights to Google Doc", type="primary"):
            insights = db.query(ValidatedInsight).all()
            if not insights:
                st.error("No validated insights found to export.")
            else:
                with st.spinner("Exporting to Google Docs..."):
                    try:
                        markdown_content = f"# Blinkit Validated Research Insights - {week_tag}\n\n"
                        for insight in insights:
                            markdown_content += f"### Theme: {insight.theme_tag}\n"
                            markdown_content += f"**Status**: {insight.validation_status}\n\n"
                            markdown_content += f"> {insight.insight_statement}\n\n"
                            if insight.interview_quotes:
                                markdown_content += "**Primary Research Quotes:**\n"
                                for quote in insight.interview_quotes:
                                    markdown_content += f"- {quote}\n"
                            markdown_content += "\n"
                            
                        client = GoogleWorkspaceClient()
                        doc_url = client.append_markdown_to_doc(
                            doc_id=doc_id,
                            title=f"Blinkit - Research Export [{week_tag}]",
                            markdown_content=markdown_content
                        )
                        st.success(f"Export successful! [Open Google Doc]({doc_url})")
                    except Exception as e:
                        st.error(f"Failed to export: {str(e)}")


# --- TAB 3: Raw Reviews ---
with tab3:
    st.header("Raw Review Database")
    
    # Filters
    col1, col2 = st.columns(2)
    source_filter = col1.selectbox("Filter by Source", ["All", "App Store", "Play Store", "Twitter", "Reddit"])
    search_query = col2.text_input("Search Reviews")
    
    query = db.query(RawReview)
    if source_filter != "All":
        query = query.filter(RawReview.source == source_filter)
    if search_query:
        query = query.filter(RawReview.content.ilike(f"%{search_query}%"))
        
    reviews = query.order_by(RawReview.timestamp.desc()).limit(100).all()
    
    if not reviews:
        st.info("No reviews found.")
    else:
        df_reviews = pd.DataFrame([{
            "Date": r.timestamp,
            "Source": r.source,
            "Rating": r.rating,
            "Content": r.content
        } for r in reviews])
        
        st.dataframe(df_reviews, use_container_width=True, hide_index=True)
