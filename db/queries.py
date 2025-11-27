# User queries
GET_USER_BY_PHONE = "SELECT user_id, display_name FROM users WHERE phone_number = %s;"
GET_USER_BY_NAME = "SELECT user_id FROM users WHERE LOWER(display_name) = LOWER(%s);"
GET_USER_BY_ID = "SELECT display_name FROM users WHERE LOWER(user_id) = LOWER(%s);"
INSERT_USER = "INSERT INTO users (user_id, phone_number, display_name) VALUES (%s, %s, %s) RETURNING user_id;"

# Group queries
GET_GROUP_BY_NAME = "SELECT group_id FROM groups WHERE LOWER(group_name) = LOWER(%s);"
GET_GROUP_BY_ID = "SELECT group_name FROM groups WHERE LOWER(group_id) = LOWER(%s);"
INSERT_GROUP = "INSERT INTO groups (group_id, group_name, created_by) VALUES (%s, %s, %s) RETURNING group_id;"
ADD_PARTICIPANT = "INSERT INTO group_participants (group_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;"
GET_PARTICIPANTS = """
SELECT u.user_id, u.display_name
FROM users u
JOIN group_participants gp ON u.user_id = gp.user_id
WHERE gp.group_id = %s;
"""
UPDATE_GROUP_NAME = """
UPDATE groups
SET group_name = %s
WHERE group_id = %s AND LOWER(group_name) = LOWER(%s)
RETURNING group_id, group_name;
"""

# Expense queries
INSERT_EXPENSE = """
INSERT INTO expenses (group_id, title, amount, paid_by) 
VALUES (%s, %s, %s, %s) RETURNING expense_id;
"""

INSERT_SPLIT = """
INSERT INTO expense_splits (expense_id, user_id, share_amount) 
VALUES (%s, %s, %s) RETURNING split_id;
"""

GET_EXPENSES_BY_GROUP_AND_USER = """
SELECT e.title, e.amount, u.display_name AS paid_by
FROM expenses e
JOIN users u ON e.paid_by = u.user_id
WHERE e.group_id = %s;
"""

GET_EXPENSE_BY_GROUP_AND_TITLE = """
SELECT expense_id FROM expenses WHERE group_id = %s AND LOWER(title) = LOWER(%s);
"""

GET_EXPENSE_BY_GROUP_AND_TITLE_AND_PAYER = """
SELECT expense_id FROM expenses WHERE group_id = %s AND LOWER(title) = LOWER(%s) AND paid_by = %s;
"""

GET_EXPENSE_SUMMARY_GIVEN_GROUP_TITLE_PAYER = """
SELECT * FROM expenses WHERE group_id = %s AND LOWER(title) = LOWER(%s) AND paid_by = %s;
"""

DELETE_EXPENSE = """
DELETE FROM expenses WHERE group_id = %s AND LOWER(title) = LOWER(%s);
"""

DELETE_EXPENSE_BY_ID = """
DELETE FROM expenses WHERE expense_id = %s;
"""

GET_EXPENSES_BY_GROUP = """
SELECT title, amount
FROM expenses
WHERE group_id = %s
ORDER BY created_at DESC;
"""

GET_EXPENSES_BY_PAYER = """
SELECT title
FROM expenses
WHERE paid_by = %s
ORDER BY created_at DESC;
"""

GET_EXPENSE_SHARE_BY_EXPENSE_ID = """
SELECT user_id, share_amount 
FROM expense_splits
WHERE expense_id = %s;
"""