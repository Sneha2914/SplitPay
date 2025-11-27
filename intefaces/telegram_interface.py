from telegram import Update, ChatMemberOwner
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, ConversationHandler
from agents.langchain_agent import interpret_message

from services.group_service import check_group_in_db_using_id, create_group_in_db, update_group_name, \
    get_group_participants, add_participant
from services.user_service import get_user_by_id, create_user_in_db, get_user_by_name
from services.expense_service import get_expense_from_group_and_title_and_payer, get_all_expense_of_user, \
    delete_expense_using_id, get_expense_summary_by_group_title_payer, get_expense_splits_by_expense_id, save_expense, \
    save_expense_user_id, save_expense_split_user_id


ASK_AMOUNT, ASK_PARTICIPANTS, ASK_CONFIRMATION = range(3)


def check_group(chat, owner_id):
    group_id = chat.id
    group_name = chat.title

    group_name_from_db = check_group_in_db_using_id(group_id)

    if group_name_from_db == -1:
        group_id_from_db = create_group_in_db(group_id, group_name, owner_id)
    elif group_name_from_db != group_name:
        group_id_from_db = update_group_name(group_id, group_name_from_db, group_name)
    else:
        return True, group_name

    if str(group_id) != group_id_from_db:
        return False, None

    return False, group_name


def check_user(admin):
    user = get_user_by_id(admin.user.id)

    if user == -1:
        create_user_in_db(admin.user.id, None, admin.user.first_name.strip().capitalize())

    return None


def check_group_participants(group_id, admins):
    participants = get_group_participants(group_id)
    participants_ids = [participant[0] for participant in participants]

    for admin in admins:
        user_id = admin.user.id
        if user_id not in participants_ids:
            add_participant(group_id, user_id)


def process_expense(parsed_message):
    payer = parsed_message.get("payer") or "NA"
    title = parsed_message.get("title") or "NA"
    amount = float(parsed_message.get("amount") or 0)
    participants = [p.strip().capitalize() for p in parsed_message.get("participants", "").split(",") if p.strip()]
    participants_split = parsed_message.get('split')  # ast.literal_eval(f"[{parsed_message.get('split')}]")
    split_type = parsed_message.get("split_type")

    return payer, title, amount, participants, participants_split, split_type


async def check_parsed_message(update, context):
    if ((context.user_data["title"] == "NA") or
            (context.user_data["amount"] <= 0) or (len(context.user_data["split"]) == 0)):
        await update.message.reply_text(f"The message sent is not formatted correct. "
                                        f"Difficult for bot to extract Title/ Amount/ Participants "
                                        f"in the expense. Please update the message.")
        return
    else:
        participants_split = "\n".join(f"{item['participant']}'s share: "
                                       f"{item['share']}" for item in context.user_data['split'])
        total = 0.0
        for item in context.user_data['split']:
            total += item['share']
        if float(total) == float(context.user_data['amount']):
            await update.message.reply_text(f"<b>Verify the expense:</b> \n \n"
                                            f"{context.user_data['payer']} paid ₹{context.user_data['amount']} "
                                            f"for {context.user_data['title']} \n"
                                            f"{participants_split} \n \n"
                                            f"Please type <b>yes</b> to add the expense else <b>no</b>.",
                                            parse_mode="HTML")
        else:
            await update.message.reply_text(f"<b>Verify the expense:</b> \n \n"
                                            f"{context.user_data['payer']} paid ₹{context.user_data['amount']} "
                                            f"for {context.user_data['title']} \n"
                                            f"{participants_split} \n \n"
                                            f"Expense share doesn't seem correct. Please type correct split.",
                                            parse_mode="HTML")
            return
    return ASK_CONFIRMATION


def verify_participants(participants):

    for user_name in participants:
        user = get_user_by_name(user_name)
        if user == -1:
            return False

    return True


async def conv_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_name = update.message.from_user.first_name
    sender_id = update.message.from_user.id
    user_text = f"{sender_name} wrote this message. It will be either about add_expense, delete_expense, " \
                f"expenses_history, expense_summary, debt_summary, credit_summary. {update.message.text}"
    chat = await context.bot.get_chat(update.message.chat_id)
    admins = await chat.get_administrators()
    members = await chat.get_member_count()

    if len(admins) != members:
        await update.message.reply_text(f"All group members are not admin. Make sure everyone is assigned admin role.")
        return

    owner = update.message.from_user.id
    for admin in admins:
        check_user(admin)
        if isinstance(admin, ChatMemberOwner):
            owner = admin.user.id

    group_present, group_name = check_group(chat, owner)

    if group_name is None:
        await update.message.reply_text(f"There is trouble fetching your SplitPay group. Try again later!")
        return
    else:
        if not group_present:
            await update.message.reply_text(f"SplitPay group <b>{group_name}</b> is created.", parse_mode="HTML")

    check_group_participants(chat.id, admins)

    try:
        parsed_message = interpret_message(user_text)
        print(parsed_message)
        intent = parsed_message.get("intent")
        if intent == "add_expense":
            payer, title, amount, participants, split, split_type = process_expense(parsed_message)
            valid_participants = verify_participants(participants)
            if not valid_participants:
                await update.message.reply_text(f"The expense participants extracted are "
                                                f"<b>{', '.join(participants)}</b> \n\n"
                                                f"Few of these names are not matching with the "
                                                f"first names of the group members",
                                                parse_mode="HTML")
                return
            context.user_data["user_text"] = user_text
            context.user_data["payer"] = sender_name.strip().capitalize()
            context.user_data["payer_id"] = sender_id
            context.user_data["title"] = title.strip().capitalize()
            context.user_data["amount"] = amount
            context.user_data["split"] = split
            next_step = await check_parsed_message(update, context)
            return next_step
        elif intent == "delete_expense":
            payer, title, amount, participants, split, split_type = process_expense(parsed_message)
            if title == "NA":
                await update.message.reply_text(f"Please provide the title of the expense needs to be deleted.",
                                                parse_mode="HTML")
                return
            else:
                expense_id = get_expense_from_group_and_title_and_payer(chat.id, title, sender_id)
                if expense_id == -1:
                    await update.message.reply_text(f"No expense with title {title} added by you in this group")
                    return
                else:
                    delete_expense_using_id(expense_id)
                    await update.message.reply_text(f"Expense {title} added by you in this group is deleted now.")
                    return
        elif intent == "expenses_history":
            expenses = get_all_expense_of_user(sender_id)
            await update.message.reply_text(f"List of all expenses you added in this group. \n\n"
                                            f"<b>{', '.join(expense[0] for expense in expenses)}</b> \n\n"
                                            f"You can request summary of any expense. Write message accordingly.",
                                            parse_mode="HTML")
            return
        elif intent == "expense_summary":
            title = parsed_message.get('title')
            if title == "NA":
                await update.message.reply_text(f"Please provide the title of the expense for the summary.",
                                                parse_mode="HTML")
                return
            else:
                expense = get_expense_summary_by_group_title_payer(chat.id, title, sender_id)
                if expense == -1:
                    await update.message.reply_text(f"No expense with title <b><s>{title}</s></b> "
                                                    f"added by you in this group", parse_mode="HTML")
                    return
                else:
                    expense_shares = get_expense_splits_by_expense_id(expense['expense_id'])
                    expense_share_msg_list = []
                    for share in expense_shares:
                        user_id = share[0]
                        user_name = str(get_user_by_id(user_id))
                        expense_share_msg_list.append(f"{user_name.capitalize()}'s share: {share[1]}")
                    expense_share_msg = "\n".join(expense_share_msg_list)
                    await update.message.reply_text(f"<b>{expense['title']}</b> expense summary: \n\n"
                                                    f"Title: {expense['title']} \n"
                                                    f"Amount: {expense['amount']} \n"
                                                    f"{expense_share_msg}",
                                                    parse_mode="HTML")
                    return
        elif intent == "debt_summary":

            print("debt summary")
        elif intent == "credit_summary":
            print("credit summary")
        else:
            print("nothing")


    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


async def handle_confirmation(update, context):
    user_text = update.message.text
    sender_id = str(update.message.from_user.id)
    group_id = str(update.message.chat_id)
    sender_name = update.message.from_user.first_name
    parsed_message = interpret_message(user_text)
    intent = parsed_message.get("intent")
    if intent == "NA":
        if str.lower(user_text) == "yes":
            expense_data = {sender_id: {}}
            expense_data[sender_id]['amount'] = context.user_data['amount']
            expense_data[sender_id]['title'] = context.user_data['title']
            expense_data[sender_id]['group'] = group_id
            expense_data[sender_id]['paid_by'] = sender_id
            expense_id = save_expense_user_id(expense_data, sender_id)
            for item in context.user_data['split']:
                user_name = item['participant']
                share = item['share']
                user_id = get_user_by_name(user_name)
                save_expense_split_user_id(expense_id, user_id, share)

            await update.message.reply_text(f"Expense <b>{context.user_data['title']}</b> is added.",
                                            parse_mode="HTML")
        else:
            await update.message.reply_text(f"Expense title <b>{context.user_data['title']}</b> is discarded.",
                                            parse_mode="HTML")
        return ConversationHandler.END
    else:
        new_text = f"{sender_name}'s original message was {context.user_data['user_text']}. " \
                   f"His follow up message after asking confirmation was {user_text}"
        parsed_message = interpret_message(new_text)
        payer, title, amount, participants, split, split_type = process_expense(parsed_message)
        if len(participants) > 0:
            valid_participants = verify_participants(participants)
            if not valid_participants:
                await update.message.reply_text(f"The expense participants extracted are "
                                                f"<b>{', '.join(participants)}</b> \n\n"
                                                f"Few of these names are not matching with the "
                                                f"first names of the group members",
                                                parse_mode="HTML")
                return
        if title != "NA":
            context.user_data["title"] = title.strip().capitalize()
        if amount > 0:
            context.user_data["amount"] = amount
        if len(split) > 0:
            context.user_data["split"] = split
        context.user_data['user_text'] = new_text
        return check_parsed_message(update, context)


def main():
    TOKEN = "8414898971:AAE0rDjK9an0EUxQzRgV2DUTwzRYUQeoNxM"
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, conv_message)],
        states={
            ASK_CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation)]
        },
        fallbacks=[MessageHandler(filters.TEXT & ~filters.COMMAND, conv_message)],
    )
    app.add_handler(conv_handler)

    print("🤖 LangChain SplitBot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
