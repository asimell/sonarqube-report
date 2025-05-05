import sys
import argparse
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import math
import html
from pathlib import Path

from logging import Logger

logger = Logger(__name__)

TEMPLATES = Path("templates")

ISSUE_SEVERITIES = ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]
IMPACT_SEVERITIES = ["BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"]
CONVERT_TO_GRADES = ["reliability_rating", "security_rating", "sqale_rating"]
PERCENTAGE_METRICS = ["security_hotspots_reviewed", "line_coverage"]
ISSUE_TYPES = ["CODE_SMELL", "BUG", "VULNERABILITY"]
IMPACT_TYPES = ["SECURITY", "RELIABILITY", "MAINTAINABILITY"]

def create_args() -> argparse.ArgumentParser:
    args = argparse.ArgumentParser()
    args.add_argument("--project-id", "-p", help="SonarQube Project ID", nargs="+")
    args.add_argument("--token", help="SonarQube API Token")
    args.add_argument("--host", help="SonarQube Host", default="http://localhost:9000")
    args.add_argument("--include-issue-details", help="Include issue details in the report", action="store_true")
    args.add_argument("--anonymous", help="Anonymize project names", action="store_true")
    args.add_argument("--impact-severities", help="Use impact severities instead of issue severities", action="store_true")
    args.add_argument("--impact-qualities", help="Use impact qualities instead of issue types", action="store_true")
    args.add_argument("--branch", help="Branch to analyze", default="main")
    return args

def _get(url: str, token: str) -> {dict}:
    resp = requests.get(url, auth=HTTPBasicAuth(token, ""))
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

def fetch_issues(host: str, project_id: str, token: str, anonymous: bool, impact_details: bool, impact_qualities: bool, branch: str) -> {dict, int, int}:
    p = 1
    total_pages = 1
    issues = {}
    file_counter = 1    # For anonymizing file names
    file_names = {}
    while p <= total_pages:
        url = f"{host}/api/issues/search?componentKeys={project_id}&ps=500&p={p}&statuses=OPEN,CONFIRMED,REOPENED&branch={branch}"
        data = _get(url, token)
        for issue in data["issues"]:
            component = issue["component"]
            if anonymous:
                if component not in file_names:
                    file_ending = component.split(".")[-1]
                    file_names[component] = f"file_{file_counter}.{file_ending}"
                    file_counter += 1
                component = file_names[component]
            severity = issue["impacts"][0]["severity"] if impact_details else issue["severity"]
            issue_type = issue["impacts"][0]["softwareQuality"] if impact_qualities else issue["type"]

            issue_entry = {
                "component": component,
                "message": html.escape(issue["message"]),
                "severity": severity,
                "type": issue_type,
                "rule": issue["rule"],
                "effort": issue["effort"]
            }

            if "textRange" in issue:
                issue_entry.update({
                    "startline": issue["textRange"]["startLine"],
                    "endline": issue["textRange"]["endLine"],
                    "startoffset": issue["textRange"]["startOffset"],
                    "endoffset": issue["textRange"]["endOffset"],
                })

            issues[issue["key"]] = issue_entry

        total_pages = math.ceil(data["total"] / data["ps"])
        p += 1
    project_issues = {"issues": issues}
    try:    # Some API version may not have this data
        debt = data["debtTotal"]
    except KeyError:
        debt = data["effortTotal"]
    return project_issues, data["effortTotal"], debt

def fetch_metrics(host: str, project_id: str, token: str) -> {dict}:
    url = f"{host}/api/measures/component?component={project_id}&metricKeys=ncloc,security_hotspots,reliability_rating,security_rating,sqale_rating,security_hotspots_reviewed,sqale_index,vulnerabilities,complexity&additionalFields=metrics"
    data = _get(url, token)
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
    for t in TYPES:
        severity_table += f"<th>{t}</th>"
    severity_table += "<th>Total</th></tr>"
    abs_total = 0
    for severity in SEVERITIES:
        severity_table += f"<tr><td>{severity}</td>"
        total = 0
        for t in range(len(TYPES)):
            severity_table += f"<td>{amounts[severity][t]}</td>"
            total += amounts[severity][t]
        abs_total += total
        severity_table += f"<td><strong>{total}</strong></td></tr>"

    severity_table += "<tr><td><strong>Total</strong></td>"
    for t in TYPES:
        severity_table += f"<td><strong>{sum([amounts[severity][TYPES.index(t)] for severity in SEVERITIES])}</strong></td>"


    severity_table += f"<td><strong>{abs_total}</strong></td></tr></table>"
    return severity_table

def _format_issue_table(issues: dict) -> {str, dict}:
    table = "<table><tr><th>Component</th><th>Message</th><th>Severity</th><th>Type</th><th>Lines</th><th>Rule</th><th>Effort</th></tr>"
    amounts = {severity: [0 for _ in TYPES] for severity in SEVERITIES}
    # Sort issues by severity first, then by component
    sorted_issues = sorted(issues.items(), key=lambda item: (SEVERITIES.index(item[1]['severity']), item[1]['component']))

    for _, issue in sorted_issues:
        amounts[issue['severity']][TYPES.index(issue["type"])] += 1

        # Check if textRange (key in sonar web api) related keys exist
        if 'startline' in issue:
            lines_info = f"Lines: {issue['startline']}-{issue['endline']}<br>Offset: {issue['startoffset']}-{issue['endoffset']}"
        else:
            lines_info = "N/A"

        table += f"<tr><td class='small'>{issue['component']}</td><td>{issue['message']}</td><td>{issue['severity']}</td><td>{issue['type']}</td><td>{lines_info}</td><td>{issue['rule']}</td><td>{issue['effort']}</td></tr>"

    table += "</table>"
    return table, amounts

def _format_measure_table(metrics: dict) -> str:
    table = "<table><tr><th>Metric</th><th>Value</th></tr>"
    for metric, value in metrics.items():
        table += f"<tr><td>{metric}</td><td>{value}</td></tr>"
    table += "</table>"
    return table

def format_issues(issues: dict, project_id: str, include_issue_details: bool) -> {str, dict}:
    document = TEMPLATES.joinpath("issues_table_template.html").read_text()

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

def format_overall(total_overall: dict, total_severity_amounts: dict) -> str:
    document = TEMPLATES.joinpath("overall_data_template.html").read_text()
    severity_table = _format_severity_summary(total_severity_amounts)

    total_table = _format_measure_table(total_overall)
    document = document.replace("${SEVERITIES}", severity_table)
    document = document.replace("${TOTAL_AMOUNTS}", total_table)

    return document


if __name__ == "__main__":
    args = create_args().parse_args()

    global TYPES
    global SEVERITIES
    SEVERITIES = IMPACT_SEVERITIES if args.impact_severities else ISSUE_SEVERITIES
    TYPES = IMPACT_TYPES if args.impact_qualities else ISSUE_TYPES

    issues_data = ""
    total_effort = 0
    total_debt = 0
    total_hotspots = 0
    total_loc = 0
    total_complexity = 0
    total_severity_amounts = {severity: [0 for _ in TYPES] for severity in SEVERITIES}

    project_counter = 1 # For anonymizing project names

    if Path(args.project_id[0]).exists():
        with open(args.project_id[0]) as f:
            projects = f.read().splitlines()
    else:
        projects = args.project_id

    for project_key in projects:
        logger.info(f"Fetching data for project {project_key}")
        data, effort, debt = fetch_issues(args.host, project_key, args.token, args.anonymous, args.impact_severities, args.impact_qualities, args.branch)
        data.update(fetch_metrics(args.host, project_key, args.token))

        # Formatting data
        if args.anonymous:
            project_key = f"Project {project_counter}"
            logger.info(f"==> {project_key}")
            project_counter += 1
        t, amounts = format_issues(data, project_key, args.include_issue_details)
        total_effort += effort
        total_debt += debt
        total_hotspots += int(data["metrics"]["Security Hotspots"])
        total_loc += int(data["metrics"]["Lines of Code"])
        try:
            total_complexity += int(data["metrics"]["Cyclomatic Complexity"])
        except KeyError:
            pass

        for severity in SEVERITIES:
            for x in range (len(TYPES)):
                total_severity_amounts[severity][x] += amounts[severity][x]
        issues_data += t

    overall_data = {"Total Effort": _convert_to_readable_time(total_effort),
                    "Total Debt": _convert_to_readable_time(total_debt),
                    "Security Hotspots": total_hotspots,
                    "Lines of Code": total_loc,
                    "Cyclomatic Complexity": total_complexity}

    overall= format_overall(overall_data, total_severity_amounts)

    document = TEMPLATES.joinpath("report_template.html").read_text()
    document = document.replace("${DATE}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    document = document.replace("${OVERALL}", overall)
    document = document.replace("${CONTENTS}", issues_data)

    Path("report.html").write_text(document)

    logger.info(f"{len(projects)} projects analyzed.")
    logger.info("Report generated successfully.")
