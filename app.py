#!/usr/bin/env python3
"""
BCSE302P Database Systems - Library Management System
Lightweight Full-Stack Web Dashboard (app.py)
Embedded Single-File Solution with Glassmorphism Dark UI,
Oracle PL/SQL Driver Support & High-Fidelity SQLite Simulation Fallback.
"""

import os
import sys
import datetime
import sqlite3
import subprocess
from flask import Flask, request, redirect, url_for, flash, render_template_string, jsonify

app = Flask(__name__)
app.secret_key = "bcse302p-oracle-plsql-library-management-system-secret-key"

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library_web.db")

# -----------------------------------------------------------------------------
# Database Setup & Oracle Driver Detection
# -----------------------------------------------------------------------------
ORACLE_USER = os.environ.get("ORACLE_USER")
ORACLE_PASS = os.environ.get("ORACLE_PASSWORD")
ORACLE_DSN = os.environ.get("ORACLE_DSN")

USE_ORACLE = False
if ORACLE_USER and ORACLE_PASS and ORACLE_DSN:
    try:
        import oracledb
        USE_ORACLE = True
    except ImportError:
        USE_ORACLE = False

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(force=False):
    if force and os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except Exception:
            pass

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS library_books (
        book_id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        category TEXT,
        total_copies INTEGER DEFAULT 1,
        available_copies INTEGER DEFAULT 1 CHECK (available_copies >= 0)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS library_members (
        member_id INTEGER PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        student_number TEXT UNIQUE,
        email TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS library_loans (
        loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL,
        member_id INTEGER NOT NULL,
        borrow_date DATE DEFAULT (DATE('now')),
        due_date DATE,
        return_date DATE,
        fine_amount REAL DEFAULT 0.0,
        FOREIGN KEY (book_id) REFERENCES library_books(book_id),
        FOREIGN KEY (member_id) REFERENCES library_members(member_id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER,
        book_id INTEGER,
        action_type TEXT NOT NULL,
        log_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        details TEXT,
        FOREIGN KEY (member_id) REFERENCES library_members(member_id),
        FOREIGN KEY (book_id) REFERENCES library_books(book_id)
    );
    """)

    # Drop existing triggers if re-init to ensure fresh definitions
    cur.execute("DROP TRIGGER IF EXISTS trg_after_book_borrow;")
    cur.execute("DROP TRIGGER IF EXISTS trg_after_book_return;")

    # Production-grade Trigger 1: trg_after_book_borrow
    cur.execute("""
    CREATE TRIGGER trg_after_book_borrow
    AFTER INSERT ON library_loans
    FOR EACH ROW
    BEGIN
        UPDATE library_books
        SET available_copies = available_copies - 1
        WHERE book_id = NEW.book_id;

        INSERT INTO audit_logs (member_id, book_id, action_type, log_timestamp, details)
        VALUES (
            NEW.member_id,
            NEW.book_id,
            'BOOK_BORROWED',
            CURRENT_TIMESTAMP,
            'Loan ID: ' || NEW.loan_id || ' created. Due: ' || NEW.due_date
        );
    END;
    """)

    # Production-grade Trigger 2: trg_after_book_return
    cur.execute("""
    CREATE TRIGGER trg_after_book_return
    AFTER UPDATE OF return_date ON library_loans
    FOR EACH ROW
    WHEN NEW.return_date IS NOT NULL AND OLD.return_date IS NULL
    BEGIN
        UPDATE library_books
        SET available_copies = available_copies + 1
        WHERE book_id = NEW.book_id;

        INSERT INTO audit_logs (member_id, book_id, action_type, log_timestamp, details)
        VALUES (
            NEW.member_id,
            NEW.book_id,
            'BOOK_RETURNED',
            CURRENT_TIMESTAMP,
            'Loan ID: ' || NEW.loan_id || ' returned. Fine assessed: $' || printf('%.2f', NEW.fine_amount)
        );
    END;
    """)

    # Insert initial seed data if table is empty
    cur.execute("SELECT COUNT(*) FROM library_books")
    if cur.fetchone()[0] == 0:
        books_data = [
            (1, 'Clean Code', 'Robert C. Martin', 'Programming', 3, 3),
            (2, 'Introduction to Algorithms', 'Thomas H. Cormen', 'Algorithms', 2, 2),
            (3, 'Database Systems', 'Raghu Ramakrishnan', 'Database', 4, 4),
            (4, 'Python Crash Course', 'Eric Matthes', 'Programming', 3, 3)
        ]
        cur.executemany("INSERT INTO library_books VALUES (?, ?, ?, ?, ?, ?)", books_data)

    cur.execute("SELECT COUNT(*) FROM library_members")
    if cur.fetchone()[0] == 0:
        members_data = [
            (1, 'John', 'Mokoena', '223100001', 'john@example.com'),
            (2, 'Sarah', 'Dlamini', '223100002', 'sarah@example.com'),
            (3, 'Thabo', 'Nkosi', '224100003', 'thabo@example.com')
        ]
        cur.executemany("INSERT INTO library_members VALUES (?, ?, ?, ?, ?)", members_data)

    conn.commit()
    conn.close()

# -----------------------------------------------------------------------------
# PL/SQL Emulation Business Logic Layer
# -----------------------------------------------------------------------------
def calculate_fine(due_date_str, return_date_str):
    if not return_date_str or not due_date_str:
        return 0.0
    try:
        d_due = datetime.datetime.strptime(due_date_str, "%Y-%m-%d").date()
        d_ret = datetime.datetime.strptime(return_date_str, "%Y-%m-%d").date()
        if d_ret <= d_due:
            return 0.0
        days_late = (d_ret - d_due).days
        return float(days_late * 5.0)
    except Exception:
        return 0.0

def plsql_borrow_book(member_id, book_id, borrow_date_str=None):
    conn = get_db()
    cur = conn.cursor()

    # Precondition 1: Validate Member
    cur.execute("SELECT first_name, last_name FROM library_members WHERE member_id = ?", (member_id,))
    member = cur.fetchone()
    if not member:
        conn.close()
        raise Exception("ORA-20001: Member does not exist in library database.")

    # Precondition 2: Validate Book
    cur.execute("SELECT title, available_copies FROM library_books WHERE book_id = ?", (book_id,))
    book = cur.fetchone()
    if not book:
        conn.close()
        raise Exception("ORA-20002: Book does not exist in catalog.")

    # Precondition 3: Validate Stock (Enforced by Trigger trg_after_book_borrow)
    if book["available_copies"] < 1:
        conn.close()
        raise Exception("ORA-20001: Book is currently out of stock (available copies < 1).")

    if not borrow_date_str:
        borrow_date = datetime.date.today()
    else:
        try:
            borrow_date = datetime.datetime.strptime(borrow_date_str, "%Y-%m-%d").date()
        except ValueError:
            borrow_date = datetime.date.today()

    due_date = borrow_date + datetime.timedelta(days=14)

    # Insert into library_loans -> Fires trg_after_book_borrow
    cur.execute("""
        INSERT INTO library_loans (book_id, member_id, borrow_date, due_date)
        VALUES (?, ?, ?, ?)
    """, (book_id, member_id, borrow_date.strftime("%Y-%m-%d"), due_date.strftime("%Y-%m-%d")))

    loan_id = cur.lastrowid
    conn.commit()
    conn.close()
    return loan_id, due_date.strftime("%Y-%m-%d"), book["title"], f"{member['first_name']} {member['last_name']}"

def plsql_return_book(loan_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT l.loan_id, l.book_id, l.due_date, l.return_date, b.title
        FROM library_loans l
        JOIN library_books b ON l.book_id = b.book_id
        WHERE l.loan_id = ?
    """, (loan_id,))
    loan = cur.fetchone()

    if not loan:
        conn.close()
        raise Exception("ORA-20005: Loan record does not exist.")

    if loan["return_date"] is not None:
        conn.close()
        raise Exception("ORA-20004: This book has already been returned.")

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    fine = calculate_fine(loan["due_date"], today_str)

    # Update return date -> Fires trg_after_book_return
    cur.execute("""
        UPDATE library_loans
        SET return_date = ?, fine_amount = ?
        WHERE loan_id = ?
    """, (today_str, fine, loan_id))

    conn.commit()
    conn.close()
    return loan["title"], fine

# Initialize database on startup
init_db()

# -----------------------------------------------------------------------------
# Embedded HTML & CSS Template
# -----------------------------------------------------------------------------
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oracle PL/SQL Library Management System | BCSE302P</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #090d16;
            --bg-surface: rgba(17, 24, 39, 0.75);
            --bg-surface-elevated: rgba(30, 41, 59, 0.85);
            --border-color: rgba(255, 255, 255, 0.09);
            --border-focus: rgba(99, 102, 241, 0.6);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-indigo: #6366f1;
            --accent-violet: #8b5cf6;
            --accent-cyan: #06b6d4;
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
            --accent-rose: #f43f5e;
            --font-main: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-mono: 'Fira Code', monospace;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: var(--font-main);
            background-color: var(--bg-base);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.5;
            background-image: 
                radial-gradient(circle at 15% 10%, rgba(99, 102, 241, 0.15) 0%, transparent 45%),
                radial-gradient(circle at 85% 90%, rgba(6, 182, 212, 0.12) 0%, transparent 45%),
                radial-gradient(circle at 50% 50%, rgba(139, 92, 246, 0.05) 0%, transparent 60%);
            background-attachment: fixed;
            padding-bottom: 60px;
        }

        .container {
            max-width: 1380px;
            margin: 0 auto;
            padding: 24px 20px;
        }

        /* Header Bar */
        header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 20px 28px;
            background: var(--bg-surface);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            margin-bottom: 28px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
        }

        .brand-section {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .brand-icon {
            width: 48px;
            height: 48px;
            border-radius: 14px;
            background: linear-gradient(135deg, var(--accent-indigo), var(--accent-violet));
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 20px rgba(99, 102, 241, 0.5);
            font-size: 24px;
        }

        .brand-text h1 {
            font-size: 1.35rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            background: linear-gradient(to right, #ffffff, #cbd5e1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .brand-text p {
            font-size: 0.825rem;
            color: var(--text-secondary);
            font-weight: 500;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .badge-pill {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            border-radius: 30px;
            font-size: 0.8rem;
            font-weight: 600;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #34d399;
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: #34d399;
            box-shadow: 0 0 8px #34d399;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.7); }
            70% { transform: scale(1.1); box-shadow: 0 0 0 8px rgba(52, 211, 153, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(52, 211, 153, 0); }
        }

        .btn-header {
            padding: 8px 16px;
            border-radius: 10px;
            font-size: 0.825rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            border: 1px solid var(--border-color);
            background: var(--bg-surface-elevated);
            color: var(--text-primary);
        }

        .btn-header:hover {
            background: rgba(255, 255, 255, 0.1);
            transform: translateY(-1px);
        }

        /* Flash Alerts */
        .alerts-wrapper {
            margin-bottom: 24px;
        }

        .alert {
            padding: 14px 20px;
            border-radius: 14px;
            margin-bottom: 12px;
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            animation: slideDown 0.3s ease;
        }

        .alert-success {
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.4);
            color: #6ee7b7;
        }

        .alert-error {
            background: rgba(244, 63, 94, 0.15);
            border: 1px solid rgba(244, 63, 94, 0.4);
            color: #fda4af;
        }

        @keyframes slideDown {
            from { opacity: 0; transform: translateY(-8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Metric Grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }

        .metric-card {
            background: var(--bg-surface);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 18px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
        }

        .metric-card:hover {
            transform: translateY(-3px);
            border-color: rgba(99, 102, 241, 0.4);
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.3);
        }

        .metric-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .metric-label {
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
        }

        .metric-icon {
            width: 36px;
            height: 36px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
        }

        .metric-value {
            font-size: 2rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            color: #ffffff;
        }

        .metric-subtext {
            font-size: 0.75rem;
            color: var(--text-secondary);
        }

        /* Main Content Layout */
        .dashboard-content {
            display: grid;
            grid-template-columns: 360px 1fr;
            gap: 24px;
        }

        @media (max-width: 1080px) {
            .dashboard-content {
                grid-template-columns: 1fr;
            }
        }

        /* Card Styles */
        .glass-card {
            background: var(--bg-surface);
            backdrop-filter: blur(14px);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 24px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
            margin-bottom: 24px;
        }

        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            padding-bottom: 14px;
            border-bottom: 1px solid var(--border-color);
        }

        .card-title {
            font-size: 1.1rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .card-title-icon {
            color: var(--accent-indigo);
        }

        /* Form Controls */
        .form-group {
            margin-bottom: 18px;
        }

        label {
            display: block;
            font-size: 0.825rem;
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }

        input, select {
            width: 100%;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 12px 14px;
            color: var(--text-primary);
            font-family: var(--font-main);
            font-size: 0.9rem;
            outline: none;
            transition: all 0.2s ease;
        }

        input:focus, select:focus {
            border-color: var(--border-focus);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
            background: rgba(15, 23, 42, 0.95);
        }

        .input-hint {
            font-size: 0.72rem;
            color: var(--text-muted);
            margin-top: 5px;
        }

        .btn-primary {
            width: 100%;
            background: linear-gradient(135deg, var(--accent-indigo), var(--accent-violet));
            color: #ffffff;
            border: none;
            border-radius: 12px;
            padding: 14px;
            font-size: 0.95rem;
            font-weight: 700;
            font-family: var(--font-main);
            cursor: pointer;
            transition: all 0.25s ease;
            box-shadow: 0 4px 16px rgba(99, 102, 241, 0.35);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 22px rgba(99, 102, 241, 0.55);
        }

        .btn-primary:active {
            transform: translateY(0);
        }

        /* Tables & Lists */
        .table-responsive {
            overflow-x: auto;
            border-radius: 14px;
            border: 1px solid var(--border-color);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
            text-align: left;
        }

        thead {
            background: rgba(15, 23, 42, 0.9);
        }

        th {
            padding: 14px 16px;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            font-size: 0.725rem;
            letter-spacing: 0.05em;
            border-bottom: 1px solid var(--border-color);
        }

        td {
            padding: 14px 16px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            color: var(--text-secondary);
        }

        tbody tr {
            transition: background 0.15s ease;
        }

        tbody tr:hover {
            background: rgba(255, 255, 255, 0.03);
            color: var(--text-primary);
        }

        .table-title {
            color: var(--text-primary);
            font-weight: 600;
        }

        .stock-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .stock-in {
            background: rgba(16, 185, 129, 0.12);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.25);
        }

        .stock-out {
            background: rgba(244, 63, 94, 0.12);
            color: #fb7185;
            border: 1px solid rgba(244, 63, 94, 0.25);
        }

        .action-tag {
            font-family: var(--font-mono);
            font-size: 0.75rem;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 600;
        }

        .tag-borrow {
            background: rgba(6, 182, 212, 0.15);
            color: #22d3ee;
            border: 1px solid rgba(6, 182, 212, 0.3);
        }

        .tag-return {
            background: rgba(139, 92, 246, 0.15);
            color: #a78bfa;
            border: 1px solid rgba(139, 92, 246, 0.3);
        }

        .tag-overdue {
            background: rgba(244, 63, 94, 0.15);
            color: #fb7185;
            border: 1px solid rgba(244, 63, 94, 0.3);
        }

        .tag-active {
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .btn-table {
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 0.75rem;
            font-weight: 600;
            border: 1px solid var(--border-color);
            background: var(--bg-surface-elevated);
            color: var(--text-primary);
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .btn-table:hover {
            background: var(--accent-indigo);
            border-color: var(--accent-indigo);
            color: #ffffff;
            transform: translateY(-1px);
        }

        .btn-return {
            background: rgba(245, 158, 11, 0.15);
            border-color: rgba(245, 158, 11, 0.3);
            color: #fbbf24;
        }

        .btn-return:hover {
            background: #d97706;
            border-color: #d97706;
            color: #ffffff;
        }

        /* Cursors & Verification Drawer */
        .verification-console {
            background: #050811;
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 16px;
            font-family: var(--font-mono);
            font-size: 0.8rem;
            color: #a5f3fc;
            max-height: 280px;
            overflow-y: auto;
            white-space: pre-wrap;
            line-height: 1.45;
        }

        /* Search input */
        .table-search {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 12px;
        }

        .table-search input {
            max-width: 260px;
            padding: 8px 12px;
            font-size: 0.8rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="brand-section">
                <div class="brand-icon">📚</div>
                <div class="brand-text">
                    <h1>Library Management System</h1>
                    <p>BCSE302P Database Systems | Oracle PL/SQL Full-Stack Project</p>
                </div>
            </div>
            <div class="header-actions">
                <div class="badge-pill">
                    <div class="pulse-dot"></div>
                    <span>{{ 'Oracle DB (Live)' if use_oracle else 'PL/SQL Engine (Emulated)' }}</span>
                </div>
                <form action="/seed_overdue" method="POST" style="display:inline;">
                    <button type="submit" class="btn-header" title="Inject an overdue loan to test fines and cursor">
                        ⚡ Add Overdue Loan
                    </button>
                </form>
                <form action="/reset_db" method="POST" style="display:inline;" onsubmit="return confirm('Reset library database to default seed state?');">
                    <button type="submit" class="btn-header" title="Reset all tables and logs">
                        🔄 Reset DB
                    </button>
                </form>
            </div>
        </header>

        <!-- Flash Messages -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="alerts-wrapper">
                    {% for category, message in messages %}
                        <div class="alert {{ 'alert-success' if category == 'success' else 'alert-error' }}">
                            <span><strong>{{ '✔ SUCCESS: ' if category == 'success' else '✖ PL/SQL ERROR: ' }}</strong>{{ message }}</span>
                        </div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <!-- Metrics Dashboard -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-top">
                    <span class="metric-label">Catalog Titles</span>
                    <div class="metric-icon" style="background: rgba(99, 102, 241, 0.15); color: #818cf8;">📖</div>
                </div>
                <div class="metric-value">{{ stats.total_books }}</div>
                <div class="metric-subtext">{{ stats.total_copies }} total physical copies</div>
            </div>

            <div class="metric-card">
                <div class="metric-top">
                    <span class="metric-label">Available Copies</span>
                    <div class="metric-icon" style="background: rgba(16, 185, 129, 0.15); color: #34d399;">📗</div>
                </div>
                <div class="metric-value">{{ stats.available_copies }}</div>
                <div class="metric-subtext">Immediate checkout ready</div>
            </div>

            <div class="metric-card">
                <div class="metric-top">
                    <span class="metric-label">Active Loans</span>
                    <div class="metric-icon" style="background: rgba(6, 182, 212, 0.15); color: #22d3ee;">🔖</div>
                </div>
                <div class="metric-value">{{ stats.active_loans }}</div>
                <div class="metric-subtext">{{ stats.overdue_loans }} overdue loans pending</div>
            </div>

            <div class="metric-card">
                <div class="metric-top">
                    <span class="metric-label">Audit Events</span>
                    <div class="metric-icon" style="background: rgba(139, 92, 246, 0.15); color: #a78bfa;">⚡</div>
                </div>
                <div class="metric-value">{{ stats.total_audits }}</div>
                <div class="metric-subtext">Automated trigger audit trail</div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="dashboard-content">
            <!-- Sidebar: Borrow Book Form -->
            <aside>
                <div class="glass-card">
                    <div class="card-header">
                        <h2 class="card-title">
                            <span class="card-title-icon">✍</span> Borrow a Book
                        </h2>
                    </div>
                    <form action="/borrow" method="POST">
                        <div class="form-group">
                            <label for="member_id">Select Library Member</label>
                            <select id="member_id" name="member_id" required>
                                {% for member in members %}
                                    <option value="{{ member.member_id }}">
                                        #{{ member.member_id }} - {{ member.first_name }} {{ member.last_name }} ({{ member.student_number }})
                                    </option>
                                {% endfor %}
                            </select>
                            <div class="input-hint">Validates member via PL/SQL precondition</div>
                        </div>

                        <div class="form-group">
                            <label for="book_id">Select Book Title</label>
                            <select id="book_id" name="book_id" required>
                                {% for book in books %}
                                    <option value="{{ book.book_id }}" {{ 'disabled' if book.available_copies < 1 else '' }}>
                                        #{{ book.book_id }} - {{ book.title }} ({{ book.available_copies }} in stock)
                                    </option>
                                {% endfor %}
                            </select>
                            <div class="input-hint">Triggers trg_after_book_borrow on insert</div>
                        </div>

                        <div class="form-group">
                            <label for="borrow_date">Borrow Date</label>
                            <input type="date" id="borrow_date" name="borrow_date" value="{{ today_str }}" required>
                            <div class="input-hint">Due date automatically calculated as +14 days</div>
                        </div>

                        <button type="submit" class="btn-primary" id="btn-submit-borrow">
                            <span>Execute Borrow Procedure</span> ➔
                        </button>
                    </form>
                </div>

                <!-- Database Architecture Card -->
                <div class="glass-card">
                    <div class="card-header">
                        <h2 class="card-title" style="font-size: 0.95rem;">
                            <span class="card-title-icon">🏛</span> Database Architecture
                        </h2>
                    </div>
                    <p style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 12px;">
                        Implements BCSE302P course requirements:
                    </p>
                    <ul style="font-size: 0.775rem; color: var(--text-muted); list-style: none; display: flex; flex-direction: column; gap: 8px;">
                        <li>🔹 <strong>Tables & PK/FK:</strong> 4 normalized relations</li>
                        <li>🔹 <strong>Package:</strong> <code>library_pkg</code></li>
                        <li>🔹 <strong>Triggers:</strong> <code>trg_after_book_borrow</code> & <code>trg_after_book_return</code></li>
                        <li>🔹 <strong>Stored Cursors:</strong> Overdue & Active loan queries</li>
                        <li>🔹 <strong>Audit Trail:</strong> Persistent <code>AUDIT_LOGS</code></li>
                    </ul>
                </div>
            </aside>

            <!-- Main Tables Section -->
            <main>
                <!-- Books Catalog -->
                <div class="glass-card">
                    <div class="card-header">
                        <h2 class="card-title">
                            <span class="card-title-icon">📚</span> Books Catalog & Inventory
                        </h2>
                    </div>
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Title</th>
                                    <th>Author</th>
                                    <th>Category</th>
                                    <th>Total</th>
                                    <th>Available</th>
                                    <th>Status</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for book in books %}
                                    <tr>
                                        <td style="font-family: var(--font-mono); font-weight: 600;">#{{ book.book_id }}</td>
                                        <td class="table-title">{{ book.title }}</td>
                                        <td>{{ book.author }}</td>
                                        <td><span style="font-size: 0.75rem; background: rgba(255,255,255,0.06); padding: 3px 8px; border-radius: 6px;">{{ book.category }}</span></td>
                                        <td>{{ book.total_copies }}</td>
                                        <td style="font-weight: 700; color: #ffffff;">{{ book.available_copies }}</td>
                                        <td>
                                            {% if book.available_copies > 0 %}
                                                <span class="stock-badge stock-in">● In Stock</span>
                                            {% else %}
                                                <span class="stock-badge stock-out">● Out of Stock</span>
                                            {% endif %}
                                        </td>
                                        <td>
                                            <button class="btn-table" onclick="selectBook({{ book.book_id }})" {{ 'disabled' if book.available_copies < 1 else '' }}>
                                                Select
                                            </button>
                                        </td>
                                    </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Active Loans Table -->
                <div class="glass-card">
                    <div class="card-header">
                        <h2 class="card-title">
                            <span class="card-title-icon">⏳</span> Active & Historical Loans
                        </h2>
                    </div>
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th>Loan ID</th>
                                    <th>Book Title</th>
                                    <th>Borrower</th>
                                    <th>Borrow Date</th>
                                    <th>Due Date</th>
                                    <th>Status / Fine</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% if loans %}
                                    {% for loan in loans %}
                                        <tr>
                                            <td style="font-family: var(--font-mono); font-weight: 600;">#{{ loan.loan_id }}</td>
                                            <td class="table-title">{{ loan.title }}</td>
                                            <td>{{ loan.first_name }} {{ loan.last_name }}</td>
                                            <td style="font-family: var(--font-mono); font-size: 0.8rem;">{{ loan.borrow_date }}</td>
                                            <td style="font-family: var(--font-mono); font-size: 0.8rem;">{{ loan.due_date }}</td>
                                            <td>
                                                {% if loan.return_date %}
                                                    <span class="action-tag tag-return">Returned</span>
                                                    {% if loan.fine_amount > 0 %}
                                                        <span style="font-size: 0.75rem; color: #fb7185; font-weight: 600;">(Fine: ${{ "%.2f"|format(loan.fine_amount) }})</span>
                                                    {% endif %}
                                                {% elif loan.is_overdue %}
                                                    <span class="action-tag tag-overdue">Overdue ({{ loan.days_overdue }}d)</span>
                                                    <span style="font-size: 0.75rem; color: #fb7185; font-weight: 600;">Est. Fine: ${{ "%.2f"|format(loan.est_fine) }}</span>
                                                {% else %}
                                                    <span class="action-tag tag-active">Active</span>
                                                {% endif %}
                                            </td>
                                            <td>
                                                {% if not loan.return_date %}
                                                    <form action="/return/{{ loan.loan_id }}" method="POST" style="margin:0;">
                                                        <button type="submit" class="btn-table btn-return" title="Return book and fire trg_after_book_return">
                                                            Return Book
                                                        </button>
                                                    </form>
                                                {% else %}
                                                    <span style="font-size: 0.75rem; color: var(--text-muted);">Completed</span>
                                                {% endif %}
                                            </td>
                                        </tr>
                                    {% endfor %}
                                {% else %}
                                    <tr>
                                        <td colspan="7" style="text-align: center; padding: 24px; color: var(--text-muted);">
                                            No loan records found. Use the form on the left to borrow a book!
                                        </td>
                                    </tr>
                                {% endif %}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Live Trigger Audit Logs -->
                <div class="glass-card">
                    <div class="card-header">
                        <h2 class="card-title">
                            <span class="card-title-icon">⚡</span> Automated Trigger Audit Trail (<code>AUDIT_LOGS</code>)
                        </h2>
                    </div>
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th>Log ID</th>
                                    <th>Event Type</th>
                                    <th>Member ID</th>
                                    <th>Book ID</th>
                                    <th>Details</th>
                                    <th>Timestamp</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% if audit_logs %}
                                    {% for log in audit_logs %}
                                        <tr>
                                            <td style="font-family: var(--font-mono); font-weight: 600;">#{{ log.log_id }}</td>
                                            <td>
                                                {% if log.action_type == 'BOOK_BORROWED' %}
                                                    <span class="action-tag tag-borrow">BOOK_BORROWED</span>
                                                {% elif log.action_type == 'BOOK_RETURNED' %}
                                                    <span class="action-tag tag-return">BOOK_RETURNED</span>
                                                {% else %}
                                                    <span class="action-tag">{{ log.action_type }}</span>
                                                {% endif %}
                                            </td>
                                            <td style="font-family: var(--font-mono);">#{{ log.member_id }}</td>
                                            <td style="font-family: var(--font-mono);">#{{ log.book_id }}</td>
                                            <td>{{ log.details }}</td>
                                            <td style="font-family: var(--font-mono); font-size: 0.775rem;">{{ log.log_timestamp }}</td>
                                        </tr>
                                    {% endfor %}
                                {% else %}
                                    <tr>
                                        <td colspan="6" style="text-align: center; padding: 24px; color: var(--text-muted);">
                                            No audit events recorded yet. Borrow or return a book to fire automated trigger logging!
                                        </td>
                                    </tr>
                                {% endif %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </main>
        </div>
    </div>

    <script>
        function selectBook(bookId) {
            const selectEl = document.getElementById('book_id');
            if (selectEl) {
                selectEl.value = bookId;
                selectEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                selectEl.focus();
            }
        }
    </script>
</body>
</html>
"""

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db()
    cur = conn.cursor()

    # Books
    cur.execute("SELECT * FROM library_books ORDER BY book_id ASC")
    books = [dict(row) for row in cur.fetchall()]

    # Members
    cur.execute("SELECT * FROM library_members ORDER BY member_id ASC")
    members = [dict(row) for row in cur.fetchall()]

    # Loans
    cur.execute("""
        SELECT 
            l.loan_id, l.book_id, l.member_id, l.borrow_date, l.due_date, l.return_date, l.fine_amount,
            b.title, m.first_name, m.last_name
        FROM library_loans l
        JOIN library_books b ON l.book_id = b.book_id
        JOIN library_members m ON l.member_id = m.member_id
        ORDER BY l.loan_id DESC
    """)
    raw_loans = [dict(row) for row in cur.fetchall()]

    today = datetime.date.today()
    today_str = today.strftime("%Y-%m-%d")
    loans = []
    overdue_count = 0
    active_count = 0

    for loan in raw_loans:
        d_due = datetime.datetime.strptime(loan["due_date"], "%Y-%m-%d").date() if loan["due_date"] else today
        is_overdue = False
        days_overdue = 0
        est_fine = 0.0

        if loan["return_date"] is None:
            active_count += 1
            if today > d_due:
                is_overdue = True
                days_overdue = (today - d_due).days
                est_fine = days_overdue * 5.0
                overdue_count += 1
        
        loan["is_overdue"] = is_overdue
        loan["days_overdue"] = days_overdue
        loan["est_fine"] = est_fine
        loans.append(loan)

    # Audit Logs
    cur.execute("SELECT * FROM audit_logs ORDER BY log_id DESC LIMIT 50")
    audit_logs = [dict(row) for row in cur.fetchall()]

    # Statistics
    cur.execute("SELECT COUNT(*), SUM(total_copies), SUM(available_copies) FROM library_books")
    total_books, total_copies, avail_copies = cur.fetchone()
    total_books = total_books or 0
    total_copies = total_copies or 0
    avail_copies = avail_copies or 0

    cur.execute("SELECT COUNT(*) FROM audit_logs")
    total_audits = cur.fetchone()[0]

    conn.close()

    stats = {
        "total_books": total_books,
        "total_copies": total_copies,
        "available_copies": avail_copies,
        "active_loans": active_count,
        "overdue_loans": overdue_count,
        "total_audits": total_audits
    }

    return render_template_string(
        DASHBOARD_HTML,
        books=books,
        members=members,
        loans=loans,
        audit_logs=audit_logs,
        stats=stats,
        today_str=today_str,
        use_oracle=USE_ORACLE
    )

@app.route("/borrow", methods=["POST"])
def borrow():
    try:
        member_id = int(request.form.get("member_id"))
        book_id = int(request.form.get("book_id"))
        borrow_date_str = request.form.get("borrow_date")

        loan_id, due_date, book_title, member_name = plsql_borrow_book(member_id, book_id, borrow_date_str)
        flash(f"Book '{book_title}' successfully borrowed by {member_name} (Loan ID: {loan_id}, Due Date: {due_date}). Trigger 'trg_after_book_borrow' decremented inventory and logged transaction.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("index"), code=303)

@app.route("/return/<int:loan_id>", methods=["POST"])
def return_book_route(loan_id):
    try:
        book_title, fine = plsql_return_book(loan_id)
        if fine > 0:
            flash(f"Book '{book_title}' successfully returned. Late fine assessed: ${fine:.2f}. Trigger 'trg_after_book_return' incremented available stock and recorded audit entry.", "success")
        else:
            flash(f"Book '{book_title}' returned on time ($0.00 fine). Trigger 'trg_after_book_return' incremented stock and updated audit log.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("index"), code=303)

@app.route("/seed_overdue", methods=["POST"])
def seed_overdue():
    try:
        conn = get_db()
        cur = conn.cursor()
        # Seed an overdue loan from 20 days ago (due 6 days ago)
        borrow_date = (datetime.date.today() - datetime.timedelta(days=20)).strftime("%Y-%m-%d")
        due_date = (datetime.date.today() - datetime.timedelta(days=6)).strftime("%Y-%m-%d")
        
        # Check stock for book 4
        cur.execute("SELECT available_copies FROM library_books WHERE book_id = 4")
        row = cur.fetchone()
        if row and row[0] > 0:
            cur.execute("""
                INSERT INTO library_loans (book_id, member_id, borrow_date, due_date)
                VALUES (4, 3, ?, ?)
            """, (borrow_date, due_date))
            conn.commit()
            flash("Demonstration overdue loan added for Member #3 and Book #4 (Overdue by 6 days). Accruing $30.00 fine.", "success")
        else:
            flash("Book #4 is currently out of stock; cannot inject loan.", "error")
        conn.close()
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("index"), code=303)

@app.route("/reset_db", methods=["POST"])
def reset_db_route():
    try:
        init_db(force=True)
        flash("Library database successfully restored to default seed state.", "success")
    except Exception as e:
        flash(f"Error resetting database: {e}", "error")
    return redirect(url_for("index"), code=303)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    try:
        print(f"[*] Starting Library Management System Web Server on http://127.0.0.1:{port}")
        app.run(host="127.0.0.1", port=port, debug=False)
    except OSError as e:
        if "Address already in use" in str(e) or getattr(e, "errno", None) == 48:
            alt_port = 5001 if port == 5000 else port + 1
            print(f"[!] Port {port} is currently in use. Automatically falling back to http://127.0.0.1:{alt_port}")
            app.run(host="127.0.0.1", port=alt_port, debug=False)
        else:
            raise e
