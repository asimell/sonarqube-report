import sys
import argparse
import requests
from datetime import datetime
import math
import html
import json

# TODO: Per project metrics: security hotspots (incl. categories), issue categories

SEVERITIES = ["BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"]
CONVERT_TO_GRADES = ["reliability_rating", "security_rating", "sqale_rating"]
PERCENTAGE_METRICS = ["security_hotspots_reviewed", "line_coverage"]
ISSUE_TYPES = ["CODE_SMELL", "BUG", "VULNERABILITY"]

def create_args() -> argparse.ArgumentParser:
    args = argparse.ArgumentParser()
    args.add_argument("--project-id", "-p", help="SonarQube Project ID", nargs="+")
    args.add_argument("--token", help="SonarQube API Token")
    args.add_argument("--host", help="SonarQube Host", default="http://localhost:9000")
    args.add_argument("--include-issue-details", help="Include issue details in the report", action="store_true")
    args.add_argument("--anonymous", help="Anonymize project names", action="store_true")
    return args

def _get(url: str, token: str) -> {dict}:
    headers = {"Authorization": f"Basic {token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"Failed to fetch data: {resp.text}")
        sys.exit(1)
    return resp.json()

def _convert_to_grade(rating: str) -> str:
    return chr(ord("A") + int(float(rating)) - 1)

def _get_metric_name_from_key(key: str, metrics: list) -> str:
    for metric in metrics:
        if metric["key"] == key:
            return metric["name"]
    return key

def _convert_to_readable_time(minutes: int) -> str:
    if minutes >= 60:
        return str(minutes // 60) + "h " + str(minutes % 60) + "min"
    return str(minutes) + "min"

############################################
# DATA FETCHING
############################################

def fetch_issues(host: str, project_id: str, token: str, anonymous: bool) -> {dict, int, int}:
    p = 1
    total_pages = 1
    issues = {}
    while p <= total_pages:
        url = f"{host}/api/issues/search?componentKeys={project_id}&ps=500&p={p}&statuses=OPEN,CONFIRMED,REOPENED&branch=main"
        data = _get(url, token)
        for issue in data["issues"]:
            if anonymous:
                issue["component"] = issue["component"].split(":", maxsplit=1)[1].split("/")[-1]
            issues[issue["key"]] = {
                "component": issue["component"],
                "message": html.escape(issue["message"]),
                "severity": issue["impacts"][0]["severity"],
                "type": issue["type"],
                "startline": issue["textRange"]["startLine"],
                "endline": issue["textRange"]["endLine"],
                "startoffset": issue["textRange"]["startOffset"],
                "endoffset": issue["textRange"]["endOffset"],
                "rule": issue["rule"],
                "effort": issue["effort"]
            }
        total_pages = math.ceil(data["total"] / data["ps"])
        p += 1
    project_issues = {"issues": issues}
    return project_issues, data["effortTotal"], data["debtTotal"]

def fetch_metrics(host: str, project_id: str, token: str) -> {dict}:
    url = f"{host}/api/measures/component?component={project_id}&metricKeys=ncloc,security_hotspots,reliability_rating,security_rating,sqale_rating,security_hotspots_reviewed,sqale_index,vulnerabilities&additionalFields=metrics"
    data = _get(url, token)
    with open("data.json", "w") as f:
        f.write(json.dumps(data))
    metrics = {}
    for metric in data["component"]["measures"]:
        name = _get_metric_name_from_key(metric["metric"], data["metrics"])
        if metric["metric"] in CONVERT_TO_GRADES:
            metrics[name] = _convert_to_grade(metric["value"])
        elif metric["metric"] in PERCENTAGE_METRICS:
            metrics[name] = f"{metric['value']}%"
        elif metric["metric"] == "sqale_index": # technical debt
            metrics[name] = _convert_to_readable_time(int(metric["value"]))
        else:
            metrics[name] = metric["value"]
    return {"metrics": metrics}


############################################
# HTML FORMATTING
############################################

def _format_severity_summary(amounts: dict) -> str:
    severity_table = "<table class='small severities'><tr><th></th>"
    for t in ISSUE_TYPES:
        severity_table += f"<th>{t}</th>"
    severity_table += "<th>Total</th></tr>"
    abs_total = 0
    for severity in SEVERITIES:
        severity_table += f"<tr><td>{severity}</td>"
        total = 0
        for t in range(len(ISSUE_TYPES)):
            severity_table += f"<td>{amounts[severity][t]}</td>"
            total += amounts[severity][t]
        abs_total += total
        severity_table += f"<td><strong>{total}</strong></td></tr>"

    severity_table += "<tr><td><strong>Total</strong></td>"
    for t in ISSUE_TYPES:
        severity_table += f"<td><strong>{sum([amounts[severity][ISSUE_TYPES.index(t)] for severity in SEVERITIES])}</strong></td>"


    severity_table += f"<td><strong>{abs_total}</strong></td></tr></table>"
    return severity_table

def _format_issue_table(issues: dict) -> {str, dict}:
    table = "<table><tr><th>Component</th><th>Message</th><th>Severity</th><th>Type</th><th>Lines</th><th>Rule</th><th>Effort</th></tr>"
    amounts = {severity: [0 for _ in ISSUE_TYPES] for severity in SEVERITIES}
    for severity in SEVERITIES:
        for _, issue in issues.items():
            if issue["severity"] == severity:
                amounts[severity][ISSUE_TYPES.index(issue["type"])] += 1
                table += f"<tr><td class='small'>{issue['component']}</td><td>{issue['message']}</td><td>{issue['severity']}</td><td>{issue['type']}</td><td>Lines: {issue['startline']}-{issue['endline']}\nOffset: {issue['startoffset']}-{issue['endoffset']}</td><td>{issue['rule']}</td><td>{issue['effort']}</td></tr>"
    table += "</table>"
    return table, amounts

def _format_measure_table(metrics: dict) -> str:
    table = "<table><tr><th>Metric</th><th>Value</th></tr>"
    for metric, value in metrics.items():
        table += f"<tr><td>{metric}</td><td>{value}</td></tr>"
    table += "</table>"
    return table

def format_issues(issues: dict, project_id: str, include_issue_details: bool) -> {str, dict}:
    with open("issues_table_template.html") as f:
        document = f.read()

    table, amounts = _format_issue_table(issues["issues"])
    severity_table = _format_severity_summary(amounts)
    measure_table = _format_measure_table(issues["metrics"])

    document = document.replace("${PROJECT_ID}", project_id)
    document = document.replace("${SEVERITIES}", severity_table)
    document = document.replace("${MEASURES}", measure_table)
    if not include_issue_details:
        table = ""
    document = document.replace("${ISSUES}", table)
    return document, amounts

def format_overall(total_effort: int, total_debt: int, total_amounts: dict) -> str:
    with open("overall_data_template.html") as f:
        document = f.read()
    severity_table = _format_severity_summary(total_amounts)

    effort = _convert_to_readable_time(total_effort)
    debt = _convert_to_readable_time(total_debt)
    totals = {"Total Effort": effort, "Total Debt": debt}
    total_table = _format_measure_table(totals)
    document = document.replace("${SEVERITIES}", severity_table)
    document = document.replace("${TOTAL_AMOUNTS}", total_table)

    return document


if __name__ == "__main__":
    args = create_args().parse_args()

    issues_data = ""
    total_effort = 0
    total_debt = 0
    total_amounts = {severity: [0 for _ in ISSUE_TYPES] for severity in SEVERITIES}

    project_counter = 1 # For anonymizing project names
    for project_key in args.project_id:
        print(project_key)
        data, effort, debt = fetch_issues(args.host, project_key, args.token, args.anonymous)
        data.update(fetch_metrics(args.host, project_key, args.token))

        # Formatting data
        if args.anonymous:
            project_key = f"Project {project_counter}"
            print(f"==> {project_key}")
            project_counter += 1
        t, amounts = format_issues(data, project_key, args.include_issue_details)
        total_effort += effort
        total_debt += debt
        for severity in SEVERITIES:
            for x in range (len(ISSUE_TYPES)):
                total_amounts[severity][x] += amounts[severity][x]
        issues_data += t

    overall= format_overall(total_effort, total_debt, total_amounts)

    with open("report_template.html") as f:
        document = f.read()
    document = document.replace("${DATE}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    document = document.replace("${OVERALL}", overall)
    document = document.replace("${CONTENTS}", issues_data)

    with open("report.html", "w") as f:
        f.write(document)
