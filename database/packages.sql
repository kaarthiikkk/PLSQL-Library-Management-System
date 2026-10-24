-- =============================================================================
-- BCSE302P Database Systems - Library Management System
-- Package Specification & Body: library_pkg
-- =============================================================================

CREATE OR REPLACE PACKAGE library_pkg AS

    PROCEDURE borrow_book(
        p_member_id IN NUMBER,
        p_book_id   IN NUMBER
    );

    PROCEDURE return_book(
        p_loan_id IN NUMBER
    );

    FUNCTION get_available_copies(
        p_book_id IN NUMBER
    ) RETURN NUMBER;

    FUNCTION calculate_fine(
        p_due_date    IN DATE,
        p_return_date IN DATE
    ) RETURN NUMBER;

    FUNCTION count_member_loans(
        p_member_id IN NUMBER
    ) RETURN NUMBER;

    PROCEDURE display_borrowed_books;

    PROCEDURE display_overdue_books;

END library_pkg;
/

CREATE OR REPLACE PACKAGE BODY library_pkg AS

    -- -------------------------------------------------------------------------
    -- Procedure: borrow_book
    -- Validates preconditions and inserts loan record.
    -- trg_after_book_borrow handles stock decrement and audit log creation.
    -- -------------------------------------------------------------------------
    PROCEDURE borrow_book(
        p_member_id IN NUMBER,
        p_book_id   IN NUMBER
    )
    IS
        v_member_count     NUMBER;
        v_book_count       NUMBER;
        v_available_copies NUMBER;
    BEGIN
        -- Member existence validation
        SELECT COUNT(*)
        INTO v_member_count
        FROM library_members
        WHERE member_id = p_member_id;

        IF v_member_count = 0 THEN
            RAISE_APPLICATION_ERROR(-20001, 'Member does not exist.');
        END IF;

        -- Book existence validation
        SELECT COUNT(*)
        INTO v_book_count
        FROM library_books
        WHERE book_id = p_book_id;

        IF v_book_count = 0 THEN
            RAISE_APPLICATION_ERROR(-20002, 'Book does not exist.');
        END IF;

        -- Stock validation
        SELECT available_copies
        INTO v_available_copies
        FROM library_books
        WHERE book_id = p_book_id;

        IF v_available_copies <= 0 THEN
            RAISE_APPLICATION_ERROR(-20003, 'No copies of this book are available.');
        END IF;

        -- Insert loan record (triggers trg_after_book_borrow)
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

        DBMS_OUTPUT.PUT_LINE('Package: Book borrowed successfully.');
        DBMS_OUTPUT.PUT_LINE('Due date: ' || TO_CHAR(SYSDATE + 14, 'DD-MON-YYYY'));
    END borrow_book;

    -- -------------------------------------------------------------------------
    -- Procedure: return_book
    -- Updates return_date and fine_amount.
    -- trg_after_book_return handles stock increment and audit log creation.
    -- -------------------------------------------------------------------------
    PROCEDURE return_book(
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

        UPDATE library_loans
        SET return_date = SYSDATE,
            fine_amount = v_fine
        WHERE loan_id = p_loan_id;

        COMMIT;

        DBMS_OUTPUT.PUT_LINE('Package: Book returned successfully.');
        DBMS_OUTPUT.PUT_LINE('Fine assessed: $' || TO_CHAR(v_fine, 'FM990.00'));
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE_APPLICATION_ERROR(-20005, 'Loan does not exist.');
    END return_book;

    -- -------------------------------------------------------------------------
    -- Function: get_available_copies
    -- -------------------------------------------------------------------------
    FUNCTION get_available_copies(
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

    -- -------------------------------------------------------------------------
    -- Function: calculate_fine
    -- -------------------------------------------------------------------------
    FUNCTION calculate_fine(
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

    -- -------------------------------------------------------------------------
    -- Function: count_member_loans
    -- -------------------------------------------------------------------------
    FUNCTION count_member_loans(
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

    -- -------------------------------------------------------------------------
    -- Procedure: display_borrowed_books (Cursor Implementation)
    -- -------------------------------------------------------------------------
    PROCEDURE display_borrowed_books
    IS
        CURSOR cur_borrowed IS
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
        DBMS_OUTPUT.PUT_LINE('================ PACKAGE: BORROWED BOOKS ================');
        FOR rec IN cur_borrowed LOOP
            DBMS_OUTPUT.PUT_LINE('Loan ID: ' || rec.loan_id || ' | Book: ' || rec.title ||
                                 ' | Member: ' || rec.member_name ||
                                 ' | Due: ' || TO_CHAR(rec.due_date, 'DD-MON-YYYY'));
        END LOOP;
    END display_borrowed_books;

    -- -------------------------------------------------------------------------
    -- Procedure: display_overdue_books (Cursor Implementation)
    -- -------------------------------------------------------------------------
    PROCEDURE display_overdue_books
    IS
        CURSOR cur_overdue IS
            SELECT
                l.loan_id,
                b.title,
                m.first_name || ' ' || m.last_name AS member_name,
                l.due_date,
                TRUNC(SYSDATE) - TRUNC(l.due_date) AS days_overdue,
                calculate_fine(l.due_date, SYSDATE) AS fine
            FROM library_loans l
            JOIN library_books b ON l.book_id = b.book_id
            JOIN library_members m ON l.member_id = m.member_id
            WHERE l.return_date IS NULL
              AND l.due_date < SYSDATE
            ORDER BY l.due_date ASC;
    BEGIN
        DBMS_OUTPUT.PUT_LINE('================ PACKAGE: OVERDUE BOOKS ================');
        FOR rec IN cur_overdue LOOP
            DBMS_OUTPUT.PUT_LINE('Loan ID: ' || rec.loan_id || ' | Book: ' || rec.title ||
                                 ' | Days Overdue: ' || rec.days_overdue ||
                                 ' | Fine: $' || TO_CHAR(rec.fine, 'FM990.00'));
        END LOOP;
    END display_overdue_books;

END library_pkg;
/
