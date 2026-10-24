-- =============================================================================
-- BCSE302P Database Systems - Library Management System
-- Schema Definition: Tables, Constraints, Sequences, and Seed Data
-- =============================================================================

-- Drop existing tables and sequences if needed (safe cleanup)
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE audit_logs CASCADE CONSTRAINTS';
EXCEPTION WHEN OTHERS THEN NULL;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE library_loans CASCADE CONSTRAINTS';
EXCEPTION WHEN OTHERS THEN NULL;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE library_books CASCADE CONSTRAINTS';
EXCEPTION WHEN OTHERS THEN NULL;
END;
/


BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE library_members CASCADE CONSTRAINTS';
EXCEPTION WHEN OTHERS THEN NULL;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'DROP SEQUENCE library_loans_seq';
EXCEPTION WHEN OTHERS THEN NULL;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'DROP SEQUENCE audit_logs_seq';
EXCEPTION WHEN OTHERS THEN NULL;
END;
/

-- -----------------------------------------------------------------------------
-- 1. Sequences
-- -----------------------------------------------------------------------------
CREATE SEQUENCE library_loans_seq START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE audit_logs_seq START WITH 1 INCREMENT BY 1 NOCACHE;

-- -----------------------------------------------------------------------------
-- 2. Tables
-- -----------------------------------------------------------------------------
CREATE TABLE library_books (
    book_id          NUMBER PRIMARY KEY,
    title            VARCHAR2(100) NOT NULL,
    author           VARCHAR2(100) NOT NULL,
    category         VARCHAR2(50),
    total_copies     NUMBER DEFAULT 1,
    available_copies NUMBER DEFAULT 1,
    CONSTRAINT chk_copies_nonnegative CHECK (available_copies >= 0)
);

CREATE TABLE library_members (
    member_id      NUMBER PRIMARY KEY,
    first_name     VARCHAR2(50) NOT NULL,
    last_name      VARCHAR2(50) NOT NULL,
    student_number VARCHAR2(20) UNIQUE,
    email          VARCHAR2(100)
);

CREATE TABLE library_loans (
    loan_id     NUMBER PRIMARY KEY,
    book_id     NUMBER NOT NULL,
    member_id   NUMBER NOT NULL,
    borrow_date DATE DEFAULT SYSDATE,
    due_date    DATE,
    return_date DATE,
    fine_amount NUMBER(10,2) DEFAULT 0,
    CONSTRAINT fk_loan_book FOREIGN KEY (book_id) REFERENCES library_books(book_id),
    CONSTRAINT fk_loan_member FOREIGN KEY (member_id) REFERENCES library_members(member_id)
);

CREATE TABLE audit_logs (
    log_id        NUMBER PRIMARY KEY,
    member_id     NUMBER,
    book_id       NUMBER,
    action_type   VARCHAR2(50) NOT NULL,
    log_timestamp DATE DEFAULT SYSDATE,
    details       VARCHAR2(255),
    CONSTRAINT fk_audit_member FOREIGN KEY (member_id) REFERENCES library_members(member_id) ON DELETE SET NULL,
    CONSTRAINT fk_audit_book FOREIGN KEY (book_id) REFERENCES library_books(book_id) ON DELETE SET NULL
);

-- -----------------------------------------------------------------------------
-- 3. Seed Data
-- -----------------------------------------------------------------------------
INSERT INTO library_books (book_id, title, author, category, total_copies, available_copies)
VALUES (1, 'Clean Code', 'Robert C. Martin', 'Programming', 3, 3);

INSERT INTO library_books (book_id, title, author, category, total_copies, available_copies)
VALUES (2, 'Introduction to Algorithms', 'Thomas H. Cormen', 'Algorithms', 2, 2);

INSERT INTO library_books (book_id, title, author, category, total_copies, available_copies)
VALUES (3, 'Database Systems', 'Raghu Ramakrishnan', 'Database', 4, 4);

INSERT INTO library_books (book_id, title, author, category, total_copies, available_copies)
VALUES (4, 'Python Crash Course', 'Eric Matthes', 'Programming', 3, 3);

INSERT INTO library_members (member_id, first_name, last_name, student_number, email)
VALUES (1, 'John', 'Mokoena', '223100001', 'john@example.com');

INSERT INTO library_members (member_id, first_name, last_name, student_number, email)
VALUES (2, 'Sarah', 'Dlamini', '223100002', 'sarah@example.com');

INSERT INTO library_members (member_id, first_name, last_name, student_number, email)
VALUES (3, 'Thabo', 'Nkosi', '224100003', 'thabo@example.com');

COMMIT;
