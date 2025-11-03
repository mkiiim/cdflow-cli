# Data Formats

This document outlines the expected CSV data formats for CanadaHelps and PayPal imports.

## General Recommendations

It is highly recommended to use the default CSV export files provided by CanadaHelps and PayPal to ensure compatibility with the importer. The tool is designed to work with the specific column headers and data formats from these exports.

-   **CanadaHelps Export URL:** [https://www.canadahelps.org/en/Admin/MCDonations_DataDownload.aspx](https://www.canadahelps.org/en/Admin/MCDonations_DataDownload.aspx)
-   **PayPal Export URL:** [https://www.paypal.com/reports/dlog](https://www.paypal.com/reports/dlog)

## CanadaHelps

The following fields are required for a successful CanadaHelps import:

-   `DONOR FIRST NAME`
-   `DONOR LAST NAME`
-   `DONOR EMAIL ADDRESS`
-   `AMOUNT`
-   `DONATION DATE`
-   `DONATION TIME`
-   `TRANSACTION NUMBER`

## PayPal

The following fields are required for a successful PayPal import:

-   `Name`
-   `From Email Address`
-   `Gross`
-   `Date`
-   `Time`
-   `Transaction ID`

**Note:** For PayPal imports, either the `Name` or `From Email Address` field must contain a value.
