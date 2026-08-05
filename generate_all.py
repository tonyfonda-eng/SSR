from src.html_generator import *
from src.database import get_latest_workflow_health
metrics = get_latest_workflow_health()
generate_dashboard_html([], "docs/index.html", metrics)
generate_pipeline_health_html("docs/pipeline_health.html", metrics)
generate_decision_analytics_html("docs/decision_analytics.html", metrics)
generate_archive_html("docs/archive.html")
generate_screening_log_html("docs/screening_log.html")
generate_ontology_debug_html("docs/ontology_debug.html")
print("All HTML generated successfully!")
