-- =============================================================================
-- BCSE302P Database Systems - Library Management System
-- Triggers: Business Integrity & Automated Audit Logging
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Audit Logs Schema & Sequence (if not already created)
-- -----------------------------------------------------------------------------
DECLARE
    v_table_exists NUMBER;
    v_seq_exists   NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_seq_exists FROM user_sequences WHERE sequence_name = 'AUDIT_LOGS_SEQ';
    IF v_seq_exists = 0 THEN
        EXECUTE IMMEDIATE 'CREATE SEQUENCE audit_logs_seq START WITH 1 INCREMENT BY 1 NOCACHE';
    END IF;

    SELECT COUNT(*) INTO v_table_exists FROM user_tables WHERE table_name = 'AUDIT_LOGS';
    IF v_table_exists = 0 THEN
        EXECUTE IMMEDIATE 'CREATE TABLE audit_logs (
            log_id        NUMBER PRIMARY KEY,
            member_id     NUMBER,
            book_id       NUMBER,
            action_type   VARCHAR2(50) NOT NULL,
            log_timestamp DATE DEFAULT SYSDATE,
            details       VARCHAR2(255),
            CONSTRAINT fk_audit_member FOREIGN KEY (member_id) REFERENCES library_members(member_id) ON DELETE SET NULL,
            CONSTRAINT fk_audit_book FOREIGN KEY (book_id) REFERENCES library_books(book_id) ON DELETE SET NULL
        )';
    END IF;
END;
/

-- -----------------------------------------------------------------------------
-- 2. Trigger: trg_after_book_borrow
--    Fires AFTER INSERT on library_loans.
--    - Enforces availability check; raises ORA-20001 if out of stock.
--    - Automatically decrements available_copies in library_books.
--    - Audits the borrowing transaction into audit_logs.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TRIGGER trg_after_book_borrow
AFTER INSERT ON library_loans
FOR EACH ROW
DECLARE
    v_available_copies NUMBER;
BEGIN
    -- Query current stock for the requested book
    SELECT available_copies
    INTO v_available_copies
    FROM library_books
    WHERE book_id = :NEW.book_id
    FOR UPDATE;

    -- Raise application error if book is out of stock prior to insertion
    IF v_available_copies < 1 THEN
        RAISE_APPLICATION_ERROR(-20001, 'Book is currently out of stock');
    END IF;

    -- Automatically decrement available copies in BOOKS table
    UPDATE library_books
    SET available_copies = available_copies - 1
    WHERE book_id = :NEW.book_id;

    -- Log borrowing event into AUDIT_LOGS
    INSERT INTO audit_logs (
        log_id,
        member_id,
        book_id,
        action_type,
        log_timestamp,
        details
    )
    VALUES (
        audit_logs_seq.NEXTVAL,
        :NEW.member_id,
        :NEW.book_id,
        'BOOK_BORROWED',
        SYSDATE,
        'Loan ID: ' || :NEW.loan_id || ' created for Member ' || :NEW.member_id || 
        '. Due: ' || TO_CHAR(:NEW.due_date, 'YYYY-MM-DD')
    );
END trg_after_book_borrow;
/

-- -----------------------------------------------------------------------------
-- 3. Trigger: trg_after_book_return
--    Fires AFTER UPDATE of return_date on library_loans.
--    - Automatically increments available_copies in library_books.
--    - Automatically executes fine calculation logic if return_date > due_date.
--    - Audits the return transaction into audit_logs.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TRIGGER trg_after_book_return
AFTER UPDATE OF return_date ON library_loans
FOR EACH ROW
WHEN (NEW.return_date IS NOT NULL AND OLD.return_date IS NULL)
DECLARE
    v_fine NUMBER := 0;
    v_days_late NUMBER := 0;
BEGIN
    -- Automatically increment available copies in BOOKS table
    UPDATE library_books
    SET available_copies = available_copies + 1
    WHERE book_id = :NEW.book_id;

    -- Calculate fine if overdue (due_date < return_date)
    IF :NEW.return_date > :NEW.due_date THEN
        v_days_late := TRUNC(:NEW.return_date) - TRUNC(:NEW.due_date);
        v_fine := calculate_fine(:NEW.due_date, :NEW.return_date);
    END IF;

    -- Log return event into AUDIT_LOGS
    INSERT INTO audit_logs (
        log_id,
        member_id,
        book_id,
        action_type,
        log_timestamp,
        details
    )
    VALUES (
        audit_logs_seq.NEXTVAL,
        :NEW.member_id,
        :NEW.book_id,
        'BOOK_RETURNED',
        SYSDATE,
        'Loan ID: ' || :NEW.loan_id || ' returned. ' ||
        CASE 
            WHEN v_days_late > 0 THEN 'Overdue by ' || v_days_late || ' day(s). Fine: $' || TO_CHAR(v_fine, 'FM990.00')
            ELSE 'Returned on time. Fine: $0.00'
        END
    );
END trg_after_book_return;
/
