-- =============================================================================
-- BCSE302P Database Systems - Library Management System
-- Stored Procedures, Functions, and Cursors
-- =============================================================================

-- =============================================================================
-- SECTION 1: FUNCTIONS
-- =============================================================================

-- 1. Check Available Copies of a Book
CREATE OR REPLACE FUNCTION get_available_copies (
    p_book_id IN NUMBER
)
RETURN NUMBER
IS
    v_available_copies NUMBER;
BEGIN
    SELECT available_copies
    INTO v_available_copies
    FROM library_books
    WHERE book_id = p_book_id;

    RETURN v_available_copies;
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        RETURN -1;
END get_available_copies;
/

-- 2. Calculate Fine for Overdue Returns ($5/day past due date)
CREATE OR REPLACE FUNCTION calculate_fine (
    p_due_date    IN DATE,
    p_return_date IN DATE
)
RETURN NUMBER
IS
    v_days_late NUMBER;
    v_fine      NUMBER;
BEGIN
    IF p_return_date IS NULL OR p_return_date <= p_due_date THEN
        RETURN 0;
    END IF;

    v_days_late := TRUNC(p_return_date) - TRUNC(p_due_date);
    v_fine      := v_days_late * 5;

    RETURN v_fine;
END calculate_fine;
/

-- 3. Count Active Loans for a Member
CREATE OR REPLACE FUNCTION count_member_loans (
    p_member_id IN NUMBER
)
RETURN NUMBER
IS
    v_loan_count NUMBER;
BEGIN
    SELECT COUNT(*)
    INTO v_loan_count
    FROM library_loans
    WHERE member_id = p_member_id
      AND return_date IS NULL;

    RETURN v_loan_count;
END count_member_loans;
/

-- =============================================================================
-- SECTION 2: STORED PROCEDURES
-- =============================================================================

-- 1. Borrow Book Procedure
-- Automatically leverages trg_after_book_borrow for stock decrement and audit.
CREATE OR REPLACE PROCEDURE borrow_book (
    p_member_id IN NUMBER,
    p_book_id   IN NUMBER
)
IS
    v_member_count     NUMBER;
    v_book_count       NUMBER;
    v_available_copies NUMBER;
BEGIN
    -- Validate Member Existence
    SELECT COUNT(*)
    INTO v_member_count
    FROM library_members
    WHERE member_id = p_member_id;

    IF v_member_count = 0 THEN
        RAISE_APPLICATION_ERROR(-20001, 'Member does not exist.');
    END IF;

    -- Validate Book Existence
    SELECT COUNT(*)
    INTO v_book_count
    FROM library_books
    WHERE book_id = p_book_id;

    IF v_book_count = 0 THEN
        RAISE_APPLICATION_ERROR(-20002, 'Book does not exist.');
    END IF;

    -- Validate Stock Availability
    SELECT available_copies
    INTO v_available_copies
    FROM library_books
    WHERE book_id = p_book_id;

    IF v_available_copies <= 0 THEN
        RAISE_APPLICATION_ERROR(-20003, 'No copies of this book are available.');
    END IF;

    -- Insert Loan Record (Fires trg_after_book_borrow automatically)
    INSERT INTO library_loans (
        loan_id,
        book_id,
        member_id,
        borrow_date,
        due_date
    )
    VALUES (
        library_loans_seq.NEXTVAL,
        p_book_id,
        p_member_id,
        SYSDATE,
        SYSDATE + 14
    );

    COMMIT;

    DBMS_OUTPUT.PUT_LINE('Book borrowed successfully.');
    DBMS_OUTPUT.PUT_LINE('Due date: ' || TO_CHAR(SYSDATE + 14, 'DD-MON-YYYY'));
END borrow_book;
/

-- 2. Return Book Procedure
-- Automatically leverages trg_after_book_return for stock increment and audit.
CREATE OR REPLACE PROCEDURE return_book (
    p_loan_id IN NUMBER
)
IS
    v_book_id     NUMBER;
    v_return_date DATE;
    v_due_date    DATE;
    v_fine        NUMBER;
BEGIN
    SELECT book_id, return_date, due_date
    INTO v_book_id, v_return_date, v_due_date
    FROM library_loans
    WHERE loan_id = p_loan_id;

    IF v_return_date IS NOT NULL THEN
        RAISE_APPLICATION_ERROR(-20004, 'This book has already been returned.');
    END IF;

    v_fine := calculate_fine(v_due_date, SYSDATE);

    -- Update return date and fine (Fires trg_after_book_return automatically)
    UPDATE library_loans
    SET return_date = SYSDATE,
        fine_amount = v_fine
    WHERE loan_id = p_loan_id;

    COMMIT;

    DBMS_OUTPUT.PUT_LINE('Book returned successfully.');
    DBMS_OUTPUT.PUT_LINE('Fine amount: $' || TO_CHAR(v_fine, 'FM990.00'));
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        RAISE_APPLICATION_ERROR(-20005, 'Loan does not exist.');
END return_book;
/

-- =============================================================================
-- SECTION 3: CURSORS & REPORTING PROCEDURES
-- =============================================================================

-- 1. Display All Active Borrowed Books
CREATE OR REPLACE PROCEDURE display_borrowed_books
IS
    CURSOR borrowed_books_cursor IS
        SELECT
            l.loan_id,
            b.title,
            m.first_name || ' ' || m.last_name AS member_name,
            l.borrow_date,
            l.due_date
        FROM library_loans l
        JOIN library_books b ON l.book_id = b.book_id
        JOIN library_members m ON l.member_id = m.member_id
        WHERE l.return_date IS NULL
        ORDER BY l.borrow_date DESC;
BEGIN
    DBMS_OUTPUT.PUT_LINE('---------------- CURRENT ACTIVE LOANS ----------------');
    FOR loan_record IN borrowed_books_cursor LOOP
        DBMS_OUTPUT.PUT_LINE('Loan ID   : ' || loan_record.loan_id);
        DBMS_OUTPUT.PUT_LINE('Book      : ' || loan_record.title);
        DBMS_OUTPUT.PUT_LINE('Member    : ' || loan_record.member_name);
        DBMS_OUTPUT.PUT_LINE('Borrowed  : ' || TO_CHAR(loan_record.borrow_date, 'DD-MON-YYYY'));
        DBMS_OUTPUT.PUT_LINE('Due Date  : ' || TO_CHAR(loan_record.due_date, 'DD-MON-YYYY'));
        DBMS_OUTPUT.PUT_LINE('------------------------------------------------------');
    END LOOP;
END display_borrowed_books;
/

-- 2. Display Overdue Books with Cursor
CREATE OR REPLACE PROCEDURE display_overdue_books
IS
    CURSOR overdue_cursor IS
        SELECT
            l.loan_id,
            b.title,
            m.first_name || ' ' || m.last_name AS member_name,
            l.borrow_date,
            l.due_date,
            TRUNC(SYSDATE) - TRUNC(l.due_date) AS days_overdue,
            calculate_fine(l.due_date, SYSDATE) AS estimated_fine
        FROM library_loans l
        JOIN library_books b ON l.book_id = b.book_id
        JOIN library_members m ON l.member_id = m.member_id
        WHERE l.return_date IS NULL
          AND l.due_date < SYSDATE
        ORDER BY l.due_date ASC;
BEGIN
    DBMS_OUTPUT.PUT_LINE('---------------- OVERDUE LOANS REPORT ----------------');
    FOR loan_record IN overdue_cursor LOOP
        DBMS_OUTPUT.PUT_LINE('Loan ID      : ' || loan_record.loan_id);
        DBMS_OUTPUT.PUT_LINE('Book         : ' || loan_record.title);
        DBMS_OUTPUT.PUT_LINE('Member       : ' || loan_record.member_name);
        DBMS_OUTPUT.PUT_LINE('Due Date     : ' || TO_CHAR(loan_record.due_date, 'DD-MON-YYYY'));
        DBMS_OUTPUT.PUT_LINE('Days Overdue : ' || loan_record.days_overdue);
        DBMS_OUTPUT.PUT_LINE('Fine Accrued : $' || TO_CHAR(loan_record.estimated_fine, 'FM990.00'));
        DBMS_OUTPUT.PUT_LINE('STATUS       : OVERDUE [ACTION REQUIRED]');
        DBMS_OUTPUT.PUT_LINE('------------------------------------------------------');
    END LOOP;
END display_overdue_books;
/
