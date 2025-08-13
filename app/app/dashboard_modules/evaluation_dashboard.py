import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from datetime import datetime, timedelta
import os
import subprocess
import sys


def display_evaluation_dashboard():
    """Display the AI evaluation dashboard"""

    st.header("🧪 AI Evaluation Dashboard")
    st.caption("Real-time monitoring of your bot's AI evaluation results")

    # Database path
    db_path = "evaluation_results.sqlite"

    # Check if database exists
    if not os.path.exists(db_path):
        st.info("🔍 **No evaluation data found**")
        st.markdown("""
        **To start testing your bot:**
        1. Run `python run_evaluation.py` from the terminal
        2. Choose your test size (100 to 10,000 conversations)
        3. Results will appear here in real-time
        """)

        # Quick start buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 Start Quick Test (100)", type="primary"):
                st.info("Starting evaluation system...")
                try:
                    subprocess.Popen([
                        sys.executable, "run_evaluation.py"
                    ], cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                    st.success(
                        "✅ Evaluation system started! Check your terminal.")
                except Exception as e:
                    st.error(f"❌ Error starting evaluation: {e}")

        with col2:
            if st.button("📊 View Analysis Tools"):
                st.info("Analysis tools available via command line:")
                st.code("python analyze_results.py")

        return

    # Load data
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(
            "SELECT * FROM evaluations ORDER BY created_at DESC",
            conn
        )
        conn.close()

        if df.empty:
            st.warning("📭 Database exists but no evaluation data found")
            return

        # Parse JSON data
        df['evaluation_json'] = df['evaluation_data'].apply(
            lambda x: json.loads(x) if x else {}
        )

        # Convert timestamp
        df['created_at'] = pd.to_datetime(df['created_at'])

    except Exception as e:
        st.error(f"❌ Error loading evaluation data: {e}")
        return

    # Main metrics
    st.subheader("📊 Key Metrics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_tests = len(df)
        st.metric("Total Tests", f"{total_tests:,}")

    with col2:
        success_rate = df['webhook_success'].mean() * 100
        st.metric("Success Rate", f"{success_rate:.1f}%")

    with col3:
        avg_score = df['overall_score'].mean()
        st.metric("Average Score", f"{avg_score:.1f}/10")

    with col4:
        avg_response_time = df['webhook_response_time'].mean()
        st.metric("Avg Response Time", f"{avg_response_time:.1f}s")

    # Test run selector
    st.subheader("🔬 Test Run Analysis")

    test_runs = df['test_run_id'].unique()
    if len(test_runs) > 1:
        selected_run = st.selectbox(
            "Select Test Run:",
            ["All Runs"] + list(test_runs),
            index=0
        )

        if selected_run != "All Runs":
            df_filtered = df[df['test_run_id'] == selected_run]
            st.info(
                f"📊 Showing {len(df_filtered):,} tests from {selected_run}")
        else:
            df_filtered = df
    else:
        df_filtered = df
        st.info(f"📊 Showing all {len(df_filtered):,} tests")

    # Charts
    st.subheader("📈 Performance Charts")

    # Score distribution
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.write("**Overall Score Distribution**")
        fig_hist = px.histogram(
            df_filtered,
            x='overall_score',
            nbins=20,
            title="Overall Score Distribution",
            labels={'overall_score': 'Overall Score',
                    'count': 'Number of Tests'}
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_chart2:
        st.write("**Fresh Vegan Score Distribution**")
        fig_vegan = px.histogram(
            df_filtered,
            x='fresh_vegan_score',
            nbins=10,
            title="Fresh Vegan Detection Score",
            labels={'fresh_vegan_score': 'Vegan Score',
                    'count': 'Number of Tests'}
        )
        st.plotly_chart(fig_vegan, use_container_width=True)

    # Strategy distribution
    st.subheader("🎯 A/B Strategy Distribution")

    strategy_counts = df_filtered['recommended_strategy'].value_counts()

    col_strategy1, col_strategy2 = st.columns(2)

    with col_strategy1:
        fig_pie = px.pie(
            values=strategy_counts.values,
            names=[f"Group {s}" for s in strategy_counts.index],
            title="Recommended A/B Strategy Distribution"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_strategy2:
        # Strategy performance comparison
        strategy_performance = df_filtered.groupby('recommended_strategy')[
            'overall_score'].mean()

        fig_bar = px.bar(
            x=[f"Group {s}" for s in strategy_performance.index],
            y=strategy_performance.values,
            title="Performance by Strategy Group",
            labels={'y': 'Average Score', 'x': 'Strategy Group'}
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # Scenario analysis
    st.subheader("🎭 Scenario Performance")

    scenario_stats = df_filtered.groupby('scenario_type').agg({
        'overall_score': ['mean', 'count'],
        'fresh_vegan_score': 'mean',
        'webhook_success': 'mean'
    }).round(2)

    scenario_stats.columns = ['Avg Score',
                              'Count', 'Vegan Score', 'Success Rate']
    st.dataframe(scenario_stats, use_container_width=True)

    # Time series (if data spans multiple days)
    if df_filtered['created_at'].dt.date.nunique() > 1:
        st.subheader("📅 Performance Over Time")

        # Daily performance
        daily_stats = df_filtered.groupby(df_filtered['created_at'].dt.date).agg({
            'overall_score': 'mean',
            'webhook_success': 'mean',
            'test_run_id': 'count'
        }).reset_index()

        daily_stats.columns = ['Date', 'Avg Score',
                               'Success Rate', 'Test Count']

        fig_time = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Average Score Over Time',
                            'Test Volume Over Time'),
            specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
        )

        # Average score
        fig_time.add_trace(
            go.Scatter(x=daily_stats['Date'], y=daily_stats['Avg Score'],
                       mode='lines+markers', name='Average Score'),
            row=1, col=1
        )

        # Test count
        fig_time.add_trace(
            go.Bar(x=daily_stats['Date'], y=daily_stats['Test Count'],
                   name='Test Count'),
            row=2, col=1
        )

        fig_time.update_layout(height=400)
        st.plotly_chart(fig_time, use_container_width=True)

    # Recent results
    st.subheader("🕐 Recent Test Results")

    recent_tests = df_filtered.head(20)[['created_at', 'ig_username', 'scenario_type',
                                         'overall_score', 'recommended_strategy',
                                         'webhook_success']].copy()

    recent_tests['created_at'] = recent_tests['created_at'].dt.strftime(
        '%Y-%m-%d %H:%M')
    recent_tests.columns = ['Time', 'Username',
                            'Scenario', 'Score', 'Strategy', 'Success']

    st.dataframe(recent_tests, use_container_width=True)

    # Export options
    st.subheader("📤 Export Options")

    col_export1, col_export2 = st.columns(2)

    with col_export1:
        if st.button("📄 Generate Report"):
            try:
                # Run the analyzer
                subprocess.run([sys.executable, "analyze_results.py"],
                               cwd=os.path.dirname(os.path.dirname(
                                   os.path.dirname(__file__))),
                               check=True)
                st.success("✅ Report generated! Check your files.")
            except Exception as e:
                st.error(f"❌ Error generating report: {e}")

    with col_export2:
        # CSV download
        csv_data = df_filtered.to_csv(index=False)
        st.download_button(
            label="💾 Download CSV",
            data=csv_data,
            file_name=f"evaluation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

    # Live monitoring
    st.subheader("🔄 Live Monitoring")

    col_live1, col_live2 = st.columns(2)

    with col_live1:
        if st.button("🔄 Refresh Data"):
            st.rerun()

    with col_live2:
        auto_refresh = st.checkbox("🔄 Auto-refresh (30s)")
        if auto_refresh:
            time.sleep(30)
            st.rerun()

    # System status
    st.subheader("⚙️ System Status")

    # Check if evaluation system is running
    webhook_url = "https://1c3f-118-208-224-170.ngrok-free.app/webhook/manychat"

    col_status1, col_status2 = st.columns(2)

    with col_status1:
        # Check last test time
        last_test = df['created_at'].max()
        time_since_last = datetime.now() - last_test.to_pydatetime()

        if time_since_last.total_seconds() < 300:  # 5 minutes
            st.success(f"✅ Recent activity ({time_since_last.seconds}s ago)")
        else:
            st.info(
                f"⏸️ Last test: {time_since_last.days}d {time_since_last.seconds//3600}h ago")

    with col_status2:
        # Test webhook connectivity
        if st.button("🔗 Test Webhook"):
            try:
                import requests
                response = requests.get(webhook_url.replace('/webhook/manychat', '/health'),
                                        timeout=5)
                if response.status_code == 200:
                    st.success("✅ Webhook responsive")
                else:
                    st.warning(f"⚠️ Webhook returned {response.status_code}")
            except Exception as e:
                st.error(f"❌ Webhook not reachable: {e}")

    # Quick actions
    st.subheader("🚀 Quick Actions")

    col_action1, col_action2, col_action3 = st.columns(3)

    with col_action1:
        if st.button("🧪 Run 100 Tests", type="primary"):
            st.info("Starting 100-test evaluation...")
            try:
                subprocess.Popen([sys.executable, "run_evaluation.py"],
                                 cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                st.success("✅ Started! Check terminal for progress.")
            except Exception as e:
                st.error(f"❌ Error: {e}")

    with col_action2:
        if st.button("📊 Full Analysis"):
            st.info("Opening analysis tools...")
            try:
                subprocess.Popen([sys.executable, "analyze_results.py"],
                                 cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                st.success("✅ Analysis tools opened!")
            except Exception as e:
                st.error(f"❌ Error: {e}")

    with col_action3:
        if st.button("🧹 Clear Data"):
            if st.button("⚠️ Confirm Clear"):
                try:
                    os.remove(db_path)
                    st.success("✅ Evaluation data cleared!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error clearing data: {e}")

    # Footer info
    st.divider()
    st.caption(
        f"📊 Dashboard showing {len(df_filtered):,} tests from {len(test_runs)} test runs")
    st.caption(f"💾 Data source: {db_path}")

# Main function for testing


def main():
    st.set_page_config(page_title="AI Evaluation Dashboard", layout="wide")
    display_evaluation_dashboard()


if __name__ == "__main__":
    main()
