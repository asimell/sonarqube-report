import sys
import argparse
import requests
from datetime import datetime
import math
import html
SEVERITIES = ["BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"]

def create_args() -> argparse.ArgumentParser:
    args = argparse.ArgumentParser()
    args.add_argument("--project-id", "-p", help="SonarQube Project ID", nargs="+")
    args.add_argument("--token", help="SonarQube API Token")
    args.add_argument("--host", help="SonarQube Host", default="http://localhost:9000")
    return args

def fetch_issues(host: str, project_id: str, token: str) -> {dict, int, int}:
    p = 1
    total_pages = 1
    issues = {}
    headers = {"Authorization": f"Basic {token}"}
    while p <= total_pages:
        url = f"{host}/api/issues/search?componentKeys={project_id}&ps=500&p={p}&statuses=OPEN,CONFIRMED,REOPENED&branch=main"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"Failed to fetch issues: {resp.text}")
            sys.exit(1)
        data = resp.json()
        for issue in data["issues"]:
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

    return issues, data["effortTotal"], data["debtTotal"]

def format_issues(issues: dict, project_id: str) -> {str, dict}:
    with open("issues_table_template.html") as f:
        document = f.read()
    amounts = {severity: 0 for severity in SEVERITIES}
    table = "<table><tr><th>Component</th><th>Message</th><th>Severity</th><th>Type</th><th>Lines</th><th>Rule</th><th>Effort</th></tr>"
    for severity in SEVERITIES:
        for _, issue in issues.items():
            if issue["severity"] == severity:
                amounts[severity] += 1
                table += f"<tr><td class='small'>{issue['component']}</td><td>{issue['message']}</td><td>{issue['severity']}</td><td>{issue['type']}</td><td>Lines: {issue['startline']}-{issue['endline']}\nOffset: {issue['startoffset']}-{issue['endoffset']}</td><td>{issue['rule']}</td><td>{issue['effort']}</td></tr>"
    table += "</table>"
    severity_table = "<table class='small severities'><tr><th>Severity</th><th>Amount</th></tr>"
    for severity in SEVERITIES:
        severity_table += f"<tr><td>{severity}</td><td>{amounts[severity]}</td></tr>"
    severity_table += "<tr><td><strong>Total</strong></td><td><strong>{}</strong></td></tr>".format(sum(amounts.values()))
    severity_table += "</table>"
    document = document.replace("${PROJECT_ID}", project_id)
    document = document.replace("${ISSUES}", table)
    document = document.replace("${SUMMARY}", severity_table)
    return document, amounts

def format_overall(total_effort: int, total_debt: int, total_amounts: dict) -> str:
    with open("overall_data_template.html") as f:
        document = f.read()
    severity_table = "<table class='small severities'><tr><th>Severity</th><th>Amount</th></tr>"
    for severity in SEVERITIES:
        severity_table += f"<tr><td>{severity}</td><td>{total_amounts[severity]}</td></tr>"
    severity_table += "<tr><td><strong>Total</strong></td><td><strong>{}</strong></td></tr>".format(sum(total_amounts.values()))
    severity_table += "</table>"

    effort = str(total_effort // 60) + "h " + str(total_effort % 60) + "min"
    debt = str(total_debt // 60) + "h " + str(total_debt % 60) + "min"
    total_table = "<table class='small total'><tr><th>Total Effort</th><th>Total Debt</th></tr>"
    total_table += f"<tr><td>{effort}</td><td>{debt}</td></tr> </table>"
    document = document.replace("${SEVERITIES}", severity_table)
    document = document.replace("${TOTAL_AMOUNTS}", total_table)

    return document


if __name__ == "__main__":
    args = create_args().parse_args()

    issues_data = ""
    total_effort = 0
    total_debt = 0
    total_amounts = {severity: 0 for severity in SEVERITIES}

    for project_key in args.project_id:
        print(project_key)
        data, effort, debt = fetch_issues(args.host, project_key, args.token)
        t, amounts = format_issues(data, project_key)
        total_effort += effort
        total_debt += debt
        for severity in SEVERITIES:
            total_amounts[severity] += amounts[severity]
        issues_data += t

    overall= format_overall(total_effort, total_debt, total_amounts)

    with open("report_template.html") as f:
        document = f.read()
    document = document.replace("${DATE}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    document = document.replace("${OVERALL}", overall)
    document = document.replace("${CONTENTS}", issues_data)

    with open("report.html", "w") as f:
        f.write(document)
