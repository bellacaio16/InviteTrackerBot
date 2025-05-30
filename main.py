import logging
import os
import sqlite3
from telegram import Update, ChatInviteLink
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ChatMemberHandler,
)

# === CONFIGURATION FROM ENV VARIABLES ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_GROUP_ID = int(os.getenv("MAIN_GROUP_ID"))
PRIVATE_CHANNEL_LINK = os.getenv("PRIVATE_CHANNEL_LINK")
REFERRAL_THRESHOLD = 3  # Number of invites needed

# === SETUP LOGGING ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === DATABASE SETUP ===
conn = sqlite3.connect("referrals.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        invite_link TEXT,
        referrals INTEGER DEFAULT 0
    )
"""
)
conn.commit()


# === /start COMMAND ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT invite_link FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result:
        invite_link = result[0]
    else:
        # Create a unique invite link with join request enabled and track name
        link: ChatInviteLink = await context.bot.create_chat_invite_link(
            chat_id=MAIN_GROUP_ID,
            creates_join_request=True,
            name=f"ref_{user_id}",
        )
        invite_link = link.invite_link
        cursor.execute(
            "INSERT INTO users (user_id, invite_link) VALUES (?, ?)", (user_id, invite_link)
        )
        conn.commit()

    await update.message.reply_text(
        f"👋 Here's your unique invite link:\n{invite_link}\n\n"
        f"Invite {REFERRAL_THRESHOLD} friends to unlock premium access!"
    )


# === TRACK JOIN REQUESTS ===
async def handle_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_member = update.chat_member

    # Only care about joins in the main group
    if chat_member.chat.id != MAIN_GROUP_ID:
        return

    try:
        inviter_name = chat_member.invite_link.name
        if inviter_name and inviter_name.startswith("ref_"):
            inviter_id = int(inviter_name.split("_")[1])
            cursor.execute("SELECT referrals FROM users WHERE user_id = ?", (inviter_id,))
            result = cursor.fetchone()

            if result:
                referrals = result[0] + 1
                cursor.execute(
                    "UPDATE users SET referrals = ? WHERE user_id = ?", (referrals, inviter_id)
                )
                conn.commit()

                if referrals == REFERRAL_THRESHOLD:
                    await context.bot.send_message(
                        chat_id=inviter_id,
                        text=(
                            f"🎉 Congrats! You’ve invited {REFERRAL_THRESHOLD} people!\n"
                            f"Here’s your private channel access link:\n{PRIVATE_CHANNEL_LINK}"
                        ),
                    )
    except Exception as e:
        logger.error(f"Error in handle_join: {e}")


# === MAIN FUNCTION ===
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(ChatMemberHandler(handle_join, ChatMemberHandler.CHAT_MEMBER))

    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
