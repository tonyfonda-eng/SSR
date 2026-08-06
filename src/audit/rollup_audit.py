import os
import csv
import datetime

def generate_rollup(days, label):
    filepath = "docs/daily_metrics.csv"
    if not os.path.exists(filepath):
        print("No daily metrics found.")
        return
        
    end_date = datetime.datetime.now(datetime.timezone.utc)
    start_date = end_date - datetime.timedelta(days=days)
    
    rows = []
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row_date = datetime.datetime.strptime(row['Date'], "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
                if start_date <= row_date <= end_date:
                    rows.append(row)
            except:
                pass
                
    if not rows:
        print(f"No data in the last {days} days.")
        return
        
    num_days = len(rows)
    
    # Calculate averages and sums
    def get_sum(key):
        return sum(float(r.get(key, 0)) for r in rows if r.get(key))
        
    def get_avg(key):
        return get_sum(key) / num_days if num_days > 0 else 0
        
    total_raw = get_sum("Raw_Scanned")
    total_unique = get_sum("Unique_Articles")
    total_alerts = get_sum("Alerts_Dispatched")
    avg_conf = get_avg("Confidence_Score")
    avg_acq = get_avg("Acquisition_Health")
    avg_pipe = get_avg("Pipeline_Health")
    total_cost = get_sum("AI_Total_Cost")
    total_ai_calls = get_sum("AI_Total_Calls")
    total_stops = get_sum("Emergency_Stops")
    
    # Generate Markdown
    md = []
    md.append(f"# SSR {label} Roll-up Report")
    md.append(f"**Period**: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({num_days} days of data)")
    md.append("")
    md.append("## Executive Summary")
    md.append(f"- **Total Raw Articles Scanned**: {total_raw:,.0f}")
    md.append(f"- **Total Unique Articles Processed**: {total_unique:,.0f}")
    md.append(f"- **Total Alerts Dispatched**: {total_alerts:,.0f}")
    md.append(f"- **Total AI Cost**: ${total_cost:,.2f}")
    md.append(f"- **Total AI API Calls**: {total_ai_calls:,.0f}")
    md.append(f"- **Total Emergency Stops**: {total_stops:,.0f}")
    md.append("")
    md.append("## Average Health Scores")
    md.append(f"- **Confidence Score**: {avg_conf:.1f}%")
    md.append(f"- **Acquisition Health**: {avg_acq:.1f}/100")
    md.append(f"- **Pipeline Health**: {avg_pipe:.1f}/100")
    md.append("")
    
    out_dir = f"docs/{label.lower()}_audit"
    os.makedirs(out_dir, exist_ok=True)
    if label == "Weekly":
        filename = f"{end_date.strftime('%Y-W%W')}.md"
    else:
        filename = f"{end_date.strftime('%Y-%m')}.md"
        
    out_path = os.path.join(out_dir, filename)
    with open(out_path, 'w') as f:
        f.write("\n".join(md))
        
    print(f"Generated {label} Roll-up: {out_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "monthly":
        generate_rollup(30, "Monthly")
    else:
        generate_rollup(7, "Weekly")
