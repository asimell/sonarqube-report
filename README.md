# SonarQube Report

## Overview

The `generate_report.py` script is used to generate a report from SonarQube analysis results of the
issues of a given project.

## Instructions

### Prerequisites

- Python 3.x installed
- Required Python packages (`pip install -r requirements.txt`)

### Usage

Run the script:

```sh
python generate_report.py --project-id <your_project_id> --token <your_token> --host <host>
```

### Parameters

- `--project-id`: SonarQube Project ID
- `--token`: SonarQube API Token
- `--host`: SonarQube Host (default: `http://localhost:9000`)

## Output

The script will generate a report file in the specified output directory.
