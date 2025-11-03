# Troubleshooting

This guide provides advice on how to troubleshoot common issues with the donation import process.

## General Approach

The application provides several layers of feedback to help you diagnose problems. The recommended approach to troubleshooting is to follow these steps in order:

1.  **Check the Console Output:** The application provides real-time feedback in the console as it runs. If a critical error occurs, it will often be displayed here first. This is the best place to look for immediate information about what might be going wrong.

2.  **Examine the Fail File:** If the import completes but some records have failed, look for the `_fail.csv` file in the `output` directory you specified in your configuration. This file will contain the exact rows that failed to import, along with a specific error message in the `NB Error Message` column. This can help you identify issues with specific data in your source file.

3.  **Review the Log File:** For the most detailed information about an import job, you should inspect the log file. A new log file is created for each job and is located in the `logs` directory. The log contains a timestamped record of every step in the import process, from configuration and API initialization to the processing of each individual row. Search for "ERROR" or "FAILED" to quickly find the relevant entries.

    **Tip:** If console output is too verbose, you can run with `--log-level ERROR` to see only error messages, or `--log-level NOTICE` to see important milestones without detailed processing information.

4.  **Inspect the Job File:** The JSON job file, located in the `jobs` directory, provides a high-level summary of the import. It contains the overall status of the job, the final counts of successful and failed records, and the names of the log, success, and fail files. This can be a useful starting point to get an overview of a specific import run and to find the names of the associated files.

## Common Issues

-   **Configuration Errors:** If the application fails to start, double-check your configuration file (e.g., `local.yaml`) for any syntax errors or incorrect paths.
-   **Authentication Errors:** If you see errors related to OAuth or authentication, ensure that your `NB_CLIENT_ID`, `NB_CLIENT_SECRET`, and `NB_SLUG` environment variables are correct and that your NationBuilder user has the necessary permissions.
-   **File Not Found Errors:** If the application reports that it cannot find your CSV file, make sure that the `file` path in your `cli_import` configuration is correct and that the file exists in the specified `cli_source` directory.
-   **Data Format Errors:** If you are seeing a large number of failures in your import, it's likely that your CSV file does not match the expected format. Please refer to the [Data Formats](data_formats.md) guide for the list of required fields.
