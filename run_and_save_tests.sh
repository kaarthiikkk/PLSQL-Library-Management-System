#!/usr/bin/env bash
# =============================================================================
# BCSE302P Database Systems - Automated Test Verification Runner
# Runs the SQL test suite, verifies exit code, and logs persistent summaries
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/test_outputs"
SUMMARY_LOG="${OUTPUT_DIR}/execution_summary.log"

mkdir -p "${OUTPUT_DIR}"

echo "================================================================================"
echo " Starting Library Management System Test Execution..."
echo " Target: test_outputs/verification_results.txt & test_outputs/execution_summary.log"
echo "================================================================================"

# If sqlplus is available and ORACLE_USER is configured, run via SQL*Plus
if command -v sqlplus >/dev/null 2>&1 && [ -n "${ORACLE_USER}" ]; then
    echo "[INFO] Running via SQL*Plus against Oracle Database..."
    sqlplus -s "${ORACLE_USER}/${ORACLE_PASSWORD}@${ORACLE_DSN}" @"${SCRIPT_DIR}/database/run_tests.sql" > "${SUMMARY_LOG}" 2>&1
    STATUS=$?
else
    echo "[INFO] Running via Python PL/SQL Verification Engine..."
    python3 "${SCRIPT_DIR}/verify.py" 2>&1 | tee "${SUMMARY_LOG}"
    STATUS=$?
fi

if [ $STATUS -eq 0 ]; then
    echo ""
    echo "================================================================================"
    echo " [SUCCESS] All Test Cases Passed Successfully!"
    echo " Verification results: ${OUTPUT_DIR}/verification_results.txt"
    echo " Execution log       : ${SUMMARY_LOG}"
    echo "================================================================================"
else
    echo ""
    echo " [ERROR] Tests failed with status code ${STATUS}" >&2
    exit $STATUS
fi
