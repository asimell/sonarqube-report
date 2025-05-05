# SonarQube Report

## Overview

The `generate_report.py` script is used to generate a report from SonarQube analysis results of the
issues of a given project.

## Instructions

### Prerequisites

- Python 3.x installed
- Required Python packages (`pip install -r requirements.txt`)
  - You can also use the included `Pipfile` to launch a `pipenv` environment.

Using a virtual environment is recommended.

### Running the Script

Example usage:

```sh
$ token="squ_example1234example4321"
$ python generate_report.py --project-id <your_project_id> --token $token --host <host> --include-issue-details
<your_project_id>
1 projects analyzed.
Report generated successfully
```

### Parameters

- `--project-id`: SonarQube Project ID. Supports a list of project ids separated by a space or a file where each project is on its own line.
- `--token`: SonarQube API Token base64 encoded
- `--host`: SonarQube Host (default: `http://localhost:9000`)
- `--include-issue-details`: Whether to include a detailed table of all the fetched issues or provide just the overall results (default: `false`)
- `--anonymous`: Whether to replace the repository names with `Project <number>` and parse the full paths of the
    component and leave just the filename. (default: `false`)
- `--impact-severities`: Whether to use issue impact severity types (`BLOCKER`, `HIGH`, `MEDIUM`, `LOW`, `INFO`) rather than issue severities
    (`BLOCKER`, `CRITICAL`, `MAJOR`, `MINOR`, `INFO`)
- `--impact-qualities`: Whether to use issue impact software qualities (`SECURITY`, `RELIABILITY`, `MAINTAINABILITY`) rather than issue types
    (`CODE_SMELL`, `BUG`, `VULNERABILITY`)
- `--branch`: SonarQube branch to analyze (default: `main`)

## Output

The script will generate a report HTML file of SonarQube findings. The HTML file can then be saved as a PDF from the browser by printing it
and saving as PDF.

If you print with portrait orientation, the rightmost columns in the tables might end up a bit funky. Therefore, for best results, it's recommended
to print in landscape orientation. If that doesn't fully do the trick, try saving with a slightly lowered scaling (e.g. 90%).
