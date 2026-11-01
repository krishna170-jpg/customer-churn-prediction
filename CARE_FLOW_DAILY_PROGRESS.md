# CareFlow --- Development Progress

**Date:** 1 November 2026\
**Project:** CareFlow: Clinical Pathway Process Mining

## Work completed

-   Continued development of the Patient Flow experience.
-   Added an experimental Patient Journey Sankey view to visualize
    observed transitions between recorded activities.
-   Added an experimental Bottleneck Detection view to rank observed
    transitions by waiting time.
-   Kept the existing CareFlow support modules (`careflow_core.py` and
    `careflow_pm.py`) as dependencies of the test app.

## Validation status

-   Python syntax compilation passed for the experimental app versions.
-   Full Streamlit runtime testing has not yet been confirmed.
-   Authentication, dashboard navigation, data-source integration, and
    all existing pages still need regression testing before merging into
    the deployed application.

## Data and interpretation notes

-   Visualizations should be calculated from the available event log.
-   Do not present demo or synthetic values as real hospital
    measurements.
-   Observed transition waiting time is not automatically a clinical
    delay or a length-of-stay measure.
-   Activity-stage colors may be inferred and should be reviewed in
    Stage Mapping.

## Test files

-   `app_careflow_sankey_test.py` --- experimental Patient Journey
    Sankey version.
-   `app_careflow_bottleneck_test.py` --- experimental Bottleneck
    Detection version.

These are test copies, not confirmed production releases. Keep the
current deployed `app.py` unchanged until local testing is complete.

## Next steps

1.  Run the test app locally with the existing support modules and
    requirements.
2.  Verify login, logout, dashboard, navigation, filters, and existing
    analytics pages.
3.  Check Sankey transitions and bottleneck waiting-time calculations
    against the event log.
4.  Fix runtime issues and review data labels.
5.  Only then merge the tested changes into `app.py` and deploy.

------------------------------------------------------------------------

*Development note: This document records progress and validation status;
it does not certify the application for clinical use.*
