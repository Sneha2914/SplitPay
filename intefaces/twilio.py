from flask import Flask
from flask import request
from twilio.rest import Client
import os, uuid

from twilio.twiml.messaging_response import MessagingResponse

from services.expense_service import save_expense, check_expense_entered, save_expense_split, \
    get_expense_from_group_and_title, delete_expense_using_id_and_title, get_expense_titles_amounts
from services.group_service import create_group_in_db, check_group_in_db, get_group_participants, add_participant
from services.user_service import get_user_by_phone, get_user_by_name, create_user_in_db

ACCOUNT_ID = os.environ.get('TWILIO_ACCOUNT')
TWILIO_TOKEN = os.environ.get('TWILIO_TOKEN')

app = Flask(__name__)
client = Client(ACCOUNT_ID, TWILIO_TOKEN)
TWILIO_NUMBER = 'whatsapp:+14155238886'

user_sessions = {}
user_group_state = {}
user_expense_state = {}
group_data = {}
expense_data = {}
user_login_state = {}


def reset_global_variables():
    user_sessions.clear()
    user_group_state.clear()
    user_expense_state.clear()
    group_data.clear()
    expense_data.clear()
    user_login_state.clear()


@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    from_number = request.values.get("From")
    body = request.values.get("Body").strip()
    # print("number: ", from_number, "body: ", body)
    from_number = from_number[-10:]
    print(from_number, body)
    check = create_user(from_number, body)
    # return create_user(from_number, body)
    return check


def create_user(from_number, body):
    if from_number in user_login_state:
        user_id, display_name = create_user_in_db(uuid.uuid4(), from_number, body)
        user_login_state.pop(from_number)
        resp = MessagingResponse()
        print(resp, user_id, display_name)
        resp.message(f"Your username will be *{display_name}*. Use this username to add expenses as a participant.")
        print(resp)
        return str(resp)
    else:
        user_id, display_name = get_user_by_phone(from_number)
        if display_name is None:
            user_login_state[from_number] = 'LOGIN'
            resp = MessagingResponse()
            resp.message("🆕 Seems like a new user. Please enter your name: ")
            return str(resp)
        else:
            return create_group(body, user_id)


def create_group(body, user_id):
    print("create group")

    resp = MessagingResponse()

    # Handle new /create command
    if body.lower().startswith("/create-group"):
        reset_global_variables()
        user_group_state[user_id] = "ASK_GROUP_NAME"
        group_data[user_id] = {}
        resp.message("🆕 Creating a new group.\nPlease enter the group name:")
        return str(resp)

    # Continue conversation if user is already in a state
    if user_id in user_group_state:
        state = user_group_state[user_id]

        if state == "ASK_GROUP_NAME":
            group_data[user_id]["name"] = body
            user_group_state[user_id] = "ASK_PARTICIPANTS"
            resp.message("Great! Now enter participants (separate names with commas):")

        elif state == "ASK_PARTICIPANTS":
            participants = [p.strip() for p in body.split(",") if p.strip()]
            group_data[user_id]["participants"] = participants

            # Confirm group creation
            group_name = group_data[user_id]["name"]
            resp.message(
                f"✅ Group created!\n\n"
                f"Name: {group_name}\n"
                f"Participants: {', '.join(participants)}"
            )

            # add group in group table
            group_id = check_group_in_db(group_name)

            if group_id != -1:
                group_participants = get_group_participants(group_id)
                participants_names = []
                for participant in group_participants:
                    participants_names.append(participant[1])
                resp.message(f"❗You already have a group with name *{group_name}* with participants {', '.join(participants_names)}")
            else:
                print("group not found")
                participants_not_present = []
                for participant in participants:
                    user_id = get_user_by_name(participant)
                    if user_id == -1:
                        participants_not_present.append(participant)

                if len(participants_not_present) > 0:
                    resp.message(f"❗ {', '.join(participants_not_present)} does not exist. Please check the username. Group is not created.")
                else:
                    group_id = create_group_in_db(uuid.uuid4(), group_name, user_id)
                    for participant in participants:
                        participant_id = get_user_by_name(participant)
                        add_participant(group_id, participant_id)
                    resp.message(f"✅ Group is created with name *{group_name}* with participants {', '.join(participants)}")

                    # Clear state (or save to DB here)
                    user_group_state.pop(user_id)
                    group_data.pop(user_id)
        else:
            resp.message("❓ I didn’t understand. Type /create group to start again.")
    else:
        return add_expense(user_id, body)

    return str(resp)


def add_expense(user_id, body):
    print("add expense")

    resp = MessagingResponse()

    # Start command
    if body.lower().startswith("/add-expense"):
        reset_global_variables()
        user_expense_state[user_id] = "ASK_GROUP"
        expense_data[user_id] = {}
        resp.message("📌 Adding new expense.\nEnter group name:")
        return str(resp)

    # Continue if user is mid-conversation
    if user_id in user_expense_state:
        state = user_expense_state[user_id]

        if state == "ASK_GROUP":
            group_id = check_group_in_db(body)
            if group_id == -1:
                resp.message(f"❗Group with name *{body}* does not exist. Please enter valid name.")
                return str(resp)
            expense_data[user_id]["group"] = group_id
            user_expense_state[user_id] = "ASK_TITLE"
            resp.message("Enter expense title:")

        elif state == "ASK_TITLE":
            # Check no same title exist in db
            expense_id = get_expense_from_group_and_title(expense_data[user_id]['group'], body)
            if expense_id != -1:
                resp.message('The expense title already exits in the group. Use some other title.')
            else:
                expense_data[user_id]["title"] = body
                user_expense_state[user_id] = "ASK_AMOUNT"
                resp.message("Enter expense amount (₹):")

        elif state == "ASK_AMOUNT":
            if body.isdigit():
                expense_data[user_id]["amount"] = int(body)
                user_expense_state[user_id] = "PAID_BY"
                resp.message("Who paid the expense? Enter his username:")
            else:
                resp.message("❌ Please enter a valid number for amount.")

        elif state == "PAID_BY":
            expense_data[user_id]['paid_by'] = body
            user_expense_state[user_id] = "ASK_SPLIT_TYPE"
            resp.message("How do you want to split? (ratio / percentage / amount)")

        elif state == "ASK_SPLIT_TYPE":
            split_type = body.lower()
            if split_type not in ["ratio", "percentage", "amount"]:
                resp.message("❌ Invalid choice. Please reply with 'ratio', 'percentage', or 'amount'.")
            else:
                expense_data[user_id]["split_type"] = split_type
                user_expense_state[user_id] = "ASK_SPLIT_PARTICIPANTS"
                # Example: Pretend we already know participants from DB
                group_participants = get_group_participants(expense_data[user_id]["group"])
                participants_names = []
                for participant in group_participants:
                    participants_names.append(participant[1])
                expense_data[user_id]["participants"] = participants_names
                expense_data[user_id]["splits"] = {}
                expense_data[user_id]["current_index"] = 0
                resp.message(f"Enter {split_type} for {participants_names[0]}:")

        elif state == "ASK_SPLIT_PARTICIPANTS":

            idx = expense_data[user_id]["current_index"]
            participant = expense_data[user_id]["participants"][idx]

            # Store split value
            expense_data[user_id]["splits"][participant] = int(body)

            print(expense_data[user_id]["splits"][participant])
            if idx + 1 < len(expense_data[user_id]["participants"]):
                expense_data[user_id]["current_index"] += 1
                next_participant = expense_data[user_id]["participants"][expense_data[user_id]["current_index"]]
                resp.message(f"Enter {expense_data[user_id]['split_type']} for {next_participant}:")
            else:
                valid_split, reason = check_expense_entered(expense_data, user_id)
                print(valid_split, reason)
                if not valid_split:
                    if reason == 'amount':
                        resp.message("❗The split entered does not match the amount given. "
                                     "Re-enter the splits correctly.")
                    elif reason == 'percentage':
                        resp.message("❗The percentage split entered does not sum up to 100. "
                                     "Re-enter the splits correctly.")
                    expense_data[user_id]["splits"] = {}
                    expense_data[user_id]["current_index"] = 0
                    resp.message(f"Enter {expense_data[user_id]['split_type']} for {expense_data[user_id]['participants'][0]}:")
                    user_expense_state[user_id] = "ASK_SPLIT_PARTICIPANTS"
                else:
                    expense_id = save_expense(expense_data, user_id)
                    if expense_data[user_id]['split_type'] == 'ratio':
                        divider = 0
                        for participant in expense_data[user_id]['participants']:
                            divider += expense_data[user_id]['splits'][participant]
                        for participant in expense_data[user_id]['participants']:
                            expense_data[user_id]['splits'][participant] = (expense_data[user_id]['splits'][
                                                                                participant] / divider) * \
                                                                           expense_data[user_id]['amount']
                    elif expense_data[user_id]['split_type'] == 'percentage':
                        for participant in expense_data[user_id]['participants']:
                            expense_data[user_id]['splits'][participant] = (expense_data[user_id]['splits'][
                                                                                participant] / 100) * \
                                                                           expense_data[user_id]['amount']
                    save_expense_split(expense_data, user_id, expense_id)
                    group = expense_data[user_id]["group"]
                    title = expense_data[user_id]["title"]
                    amount = expense_data[user_id]["amount"]
                    splits = expense_data[user_id]["splits"]

                    summary = f"✅ Expense added!\n\nGroup: {group}\nTitle: " \
                              f"{title}\nAmount: ₹{amount}\nSplit:\n"
                    for p, v in splits.items():
                        summary += f"- {p}: {v}\n"

                    resp.message(summary)

                    user_expense_state.pop(user_id)
                    expense_data.pop(user_id)

        else:
            resp.message("❓ Unknown step. Type /add expense to start again.")

    else:
        return remove_expense(user_id, body)

    return str(resp)


def remove_expense(sender, incoming_msg):
    print("remove expense")

    resp = MessagingResponse()

    session = user_sessions.get(sender, {"state": None, "data": {}})

    # Command entry point
    if incoming_msg.lower() == "/remove-expense":
        reset_global_variables()
        session["state"] = "ask_group_name"
        session["data"] = {}
        resp.message("Please enter the group name:")

    elif session["state"] == "ask_group_name":
        group_id = check_group_in_db(incoming_msg)
        if group_id == -1:
            resp.message(f"❗Group with name *{incoming_msg}* does not exist. Please enter valid name.")
            return str(resp)
        session["data"]["group_id"] = group_id
        session["data"]["group_name"] = incoming_msg
        session["state"] = "ask_expense_title"
        resp.message("Please enter the expense title you want to remove:")

    elif session["state"] == "ask_expense_title":
        group = session["data"].get("group_id")
        title = incoming_msg

        expense_id = get_expense_from_group_and_title(group, title)

        if expense_id == -1:
            resp.message(f"Expense title *{incoming_msg}* does not exist in the group with name * {session['data'].get('group_name')}*. Enter the correct expense title!")
        else:
            delete_expense_using_id_and_title(group, title)
            resp.message(f"Expense *{incoming_msg}* removed from the group *{session['data'].get('group_name')}*.")

        session = {"state": None, "data": {}}  # reset session

    else:
        return get_all_expenses(sender, incoming_msg)

    user_sessions[sender] = session
    return str(resp)


def get_all_expenses(sender, incoming_msg):
    print("get all expenses")

    resp = MessagingResponse()

    session = user_sessions.get(sender, {"state": None, "data": {}})

    # Command entry point
    if incoming_msg.lower() == "/get-all-expenses":
        reset_global_variables()
        session["state"] = "ask_group_name_get"
        session["data"] = {}
        reply = "Please enter the group name:"

    elif session["state"] == "ask_group_name_get":
        group = incoming_msg.lower()
        group_id = check_group_in_db(group)

        if group_id == -1:
            resp.message(f"❗Group with name *{incoming_msg}* does not exist. Please enter valid name.")
            return str(resp)

        expenses = get_expense_titles_amounts(group_id)

        reply = f"Expenses of group *{incoming_msg}*: \n\n"
        for expense in expenses:
            reply += f"Title: *{expense[0]}* Amount: *{expense[1]}* \n\n"

        session = {"state": None, "data": {}}  # reset session

    else:
        reply = "👋 Hi!\n\n"\
                "Here are the available commands:\n\n"\
                "• *Create a group:* `/create-group`\n"\
                "• *Add an expense:* `/add-expense`\n"\
                "• *Remove an expense:* `/remove-expense`\n " \
                "• *Get all expenses:* `/get-all-expenses`\n"
        print(reply)

    user_sessions[sender] = session
    resp.message(reply)
    return str(resp)


def check_add_expense(user_id, body):
    print("check add expense")


    while True:
        # Start command
        if body.lower().startswith("/add-expense"):
            reset_global_variables()
            user_expense_state[user_id] = "ASK_GROUP"
            expense_data[user_id] = {}
            body = input("📌 Adding new expense.\nEnter group name:")

        # Continue if user is mid-conversation
        if user_id in user_expense_state:
            state = user_expense_state[user_id]

            if state == "ASK_GROUP":
                group_id = check_group_in_db(body)
                if group_id == -1:
                    body = input(f"❗Group with name *{body}* does not exist. Please enter valid name.")
                else:
                    expense_data[user_id]["group"] = group_id
                    user_expense_state[user_id] = "ASK_TITLE"
                    body = input("Enter expense title:")

            elif state == "ASK_TITLE":
                # Check no same title exist in db
                expense_id = get_expense_from_group_and_title(expense_data[user_id]['group'], body)
                if expense_id != -1:
                    body = input('The expense title already exits in the group. Use some other title.')
                else:
                    expense_data[user_id]["title"] = body
                    user_expense_state[user_id] = "ASK_AMOUNT"
                    body = input("Enter expense amount (₹):")

            elif state == "ASK_AMOUNT":
                if body.isdigit():
                    expense_data[user_id]["amount"] = int(body)
                    user_expense_state[user_id] = "PAID_BY"
                    body = input("Who paid the expense? Enter his username:")
                else:
                    body = input("❌ Please enter a valid number for amount.")

            elif state == "PAID_BY":
                expense_data[user_id]['paid_by'] = body
                user_expense_state[user_id] = "ASK_SPLIT_TYPE"
                body = input("How do you want to split? (ratio / percentage / amount)")

            elif state == "ASK_SPLIT_TYPE":
                split_type = body.lower()
                if split_type not in ["ratio", "percentage", "amount"]:
                    body = input("❌ Invalid choice. Please reply with 'ratio', 'percentage', or 'amount'.")
                else:
                    expense_data[user_id]["split_type"] = split_type
                    user_expense_state[user_id] = "ASK_SPLIT_PARTICIPANTS"
                    # Example: Pretend we already know participants from DB
                    group_participants = get_group_participants(expense_data[user_id]["group"])
                    participants_names = []
                    for participant in group_participants:
                        participants_names.append(participant[1])
                    expense_data[user_id]["participants"] = participants_names
                    expense_data[user_id]["splits"] = {}
                    expense_data[user_id]["current_index"] = 0
                    body = input(f"Enter {split_type} for {participants_names[0]}:")

            elif state == "ASK_SPLIT_PARTICIPANTS":
                # Get current participant

                idx = expense_data[user_id]["current_index"]
                participant = expense_data[user_id]["participants"][idx]

                # Store split value
                expense_data[user_id]["splits"][participant] = int(body)

                print(expense_data[user_id]["splits"][participant])
                # Move to next participant
                if idx + 1 < len(expense_data[user_id]["participants"]):
                    expense_data[user_id]["current_index"] += 1
                    next_participant = expense_data[user_id]["participants"][expense_data[user_id]["current_index"]]
                    body = input(f"Enter {expense_data[user_id]['split_type']} for {next_participant}:")
                else:
                    valid_split, reason = check_expense_entered(expense_data, user_id)
                    print(valid_split, reason)
                    if not valid_split:
                        if reason == 'amount':
                            print("❗The split entered does not match the amount given. Re-enter the splits correctly.")
                        elif reason == 'percentage':
                            print("❗The percentage split entered does not sum up to 100. Re-enter the splits correctly.")
                        expense_data[user_id]["splits"] = {}
                        expense_data[user_id]["current_index"] = 0
                        body = input(f"Enter {expense_data[user_id]['split_type']} for {expense_data[user_id]['participants'][0]}:")
                        user_expense_state[user_id] = "ASK_SPLIT_PARTICIPANTS"
                    else:
                        expense_id = save_expense(expense_data, user_id)
                        if expense_data[user_id]['split_type'] == 'ratio':
                            divider = 0
                            for participant in expense_data[user_id]['participants']:
                                divider += expense_data[user_id]['splits'][participant]
                            for participant in expense_data[user_id]['participants']:
                                expense_data[user_id]['splits'][participant] = (expense_data[user_id]['splits'][participant] / divider) * expense_data[user_id]['amount']
                        elif expense_data[user_id]['split_type'] == 'percentage':
                            for participant in expense_data[user_id]['participants']:
                                expense_data[user_id]['splits'][participant] = (expense_data[user_id]['splits'][participant] / 100) * expense_data[user_id]['amount']

                        save_expense_split(expense_data, user_id, expense_id)
                        # Done, confirm expense
                        group = expense_data[user_id]["group"]
                        title = expense_data[user_id]["title"]
                        amount = expense_data[user_id]["amount"]
                        splits = expense_data[user_id]["splits"]

                        summary = f"✅ Expense added!\n\nGroup: {group}\nTitle: " \
                                  f"{title}\nAmount: ₹{amount}\nSplit:\n"
                        for p, v in splits.items():
                            summary += f"- {p}: {v}\n"

                        body = input(summary)

                        # Reset state
                        user_expense_state.pop(user_id)
                        expense_data.pop(user_id)

            else:
                body = input("❓ Unknown step. Type /add expense to start again.")

        else:
            return remove_expense(user_id, body)

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print_hi('PyCharm')
    # check_create_group("/create-group", 7)
    # check_get_all_expenses(7, '/get-all-expenses')
    # check_remove_expense(7, '/remove-expense')
    check_add_expense(9, "/add-expense")

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
