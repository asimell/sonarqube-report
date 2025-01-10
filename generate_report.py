import sys
import argparse
import requests
from datetime import datetime
import math

def create_args() -> argparse.ArgumentParser:
    args = argparse.ArgumentParser()
    args.add_argument("--project-id", help="SonarQube Project ID")
    args.add_argument("--token", help="SonarQube API Token")
    args.add_argument("--host", help="SonarQube Host", default="http://localhost:9000")
    return args

def fetch_issues(host: str, project_id: str, token: str) -> dict:
    p = 1
    total_pages = 1
    issues = {}
    headers = {"Authorization": f"Basic {token}"}
    while p <= total_pages:
        url = f"{host}/api/issues/search?componentKeys={project_id}&ps=500&p={p}"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"Failed to fetch issues: {resp.text}")
            sys.exit(1)
        data = resp.json()
        for issue in data["issues"]:
            issues[issue["key"]] = {
                "component": issue["component"],
                "message": issue["message"],
                "severity": issue["severity"],
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

    return issues

def format_issues(issues: dict, document: str) -> None:
    severities = ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]
    amounts = {severity: 0 for severity in severities}
    table = "<table><tr><th>Component</th><th>Message</th><th>Severity</th><th>Type</th><th>Lines</th><th>Rule</th><th>Effort</th></tr>"
    for severity in severities:
        for key, issue in issues.items():
            if issue["severity"] == severity:
                amounts[severity] += 1
                table += f"<tr><td class='small'>{issue['component']}</td><td>{issue['message']}</td><td>{issue['severity']}</td><td>{issue['type']}</td><td>Lines: {issue['startline']}-{issue['endline']}\nOffset: {issue['startoffset']}-{issue['endoffset']}</td><td>{issue['rule']}</td><td>{issue['effort']}</td></tr>"
    table += "</table>"
    severity_table = "<table class='small'><tr><th>Severity</th><th>Amount</th></tr>"
    for severity in severities:
        severity_table += f"<tr><td>{severity}</td><td>{amounts[severity]}</td></tr>"
    document = document.replace("${ISSUES}", table)
    document = document.replace("${SUMMARY}", severity_table)
    with open("report.html", "w") as f:
        f.write(document)

if __name__ == "__main__":
    args = create_args().parse_args()
    data = fetch_issues(args.host, args.project_id, args.token)
    with open("report_template.html") as f:
        document = f.read()

    document = document.replace("${DATE}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    format_issues(data, document)
