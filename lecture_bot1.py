import json
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# ---------- CONFIG ----------
BOT_TOKEN = "8360019615:AAGzb73i7spmYtFu6o9UUat047weUDrHEIE"
GROUP_ID = "@phaaarr"  # group username or numeric ID
ADMIN_IDS = [7317816083]  # Telegram numeric ID
DATA_FILE = "lectures.json"
# ----------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure data file exists and initialize with stats
if not Path(DATA_FILE).exists():
    initial_data = {
        "_stats": {"total_forwards": 0},
        # Initializing with the new nested structure
        "Phytochemistry": {"thread_id": None, "document_lectures": {}, "media_lectures": {}},
        "Microbiology": {"thread_id": None, "document_lectures": {}, "media_lectures": {}},
        "Pharmacology": {"thread_id": None, "document_lectures": {}, "media_lectures": {}},
        "Pharmaceutics": {"thread_id": None, "document_lectures": {}, "media_lectures": {}},
        "Analytical Chemistry": {"thread_id": None, "document_lectures": {}, "media_lectures": {}},
        "Medicinal Chemistry": {"thread_id": None, "document_lectures": {}, "media_lectures": {}}
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(initial_data, f, ensure_ascii=False, indent=2)

def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Helper function to filter subjects (excluding internal keys like _stats)
def get_subjects(data):
    return {k: v for k, v in data.items() if not k.startswith('_')}

# Helper function to send or edit the main admin menu
async def send_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message_id=None):
    keyboard = [
        [InlineKeyboardButton("📊 Show Usage Stats", callback_data="admin|show_usage")],
        [InlineKeyboardButton("📚 Manage Subjects", callback_data="admin|manage_subjects")],
    ]
    text = "⚙️ *Admin Settings Menu*"

    if message_id:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=message_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

# ---------- LLM/QUIZ GENERATION (MOCK/SIMULATION) ----------

def generate_mock_quiz_payload(title: str):
    """
    Simulates the structured JSON output from a Gemini API call.
    (Implementation details are inside the file but outside this snippet for brevity)
    """
    
    # Placeholder for the actual JSON response we'd parse from the API
    mock_response = [
        {
            "question": f"Which is the main type of receptor introduced in '{title.split(' ')[0]}...'?",
            "options": ["G-Protein Coupled", "Ion Channel", "Enzyme-linked", "Intracellular"],
            "correctAnswer": "G-Protein Coupled"
        },
        {
            "question": "What is the primary function of a ligand?",
            "options": ["To break down cell walls", "To bind to a receptor", "To generate ATP", "To synthesize DNA"],
            "correctAnswer": "To bind to a receptor"
        },
        {
            "question": "How many questions are in this generated quiz?",
            "options": ["3", "5", "7", "10"],
            "correctAnswer": "5"
        },
        {
            "question": "Is this feature using an LLM to provide a valuable study aid?",
            "options": ["Yes, it is.", "No, it's just a file bot.", "Maybe", "I don't know"],
            "correctAnswer": "Yes, it is."
        },
        {
            "question": "What is the primary content type of the lecture (Document or Media)?",
            "options": ["Document", "Media", "Both", "None"],
            "correctAnswer": "Document" if "document" in title.lower() else "Media"
        }
    ]
    
    return mock_response

async def quiz_generator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Generating quiz, please wait... 🧠")
    _, subject, content_type, title = query.data.split("|", 3)

    # 1. Call the mock LLM function
    mock_quiz = generate_mock_quiz_payload(title)
    
    # 2. Format the quiz response for Telegram
    quiz_text_parts = [f"🧠 *Quiz for: {title}* (5 Questions)\n"]
    
    for i, q_item in enumerate(mock_quiz):
        quiz_text_parts.append(f"*{i+1}. {q_item['question']}*")
        
        options_text = []
        for j, option in enumerate(q_item['options']):
            prefix = chr(65 + j) # A, B, C, D...
            options_text.append(f"{prefix}) {option}")
        
        # Display the options and the correct answer
        quiz_text_parts.append("\n".join(options_text))
        quiz_text_parts.append(f"  > Correct Answer: *{q_item['correctAnswer']}*")
        quiz_text_parts.append("---")
        
    final_text = "\n".join(quiz_text_parts)
    
    # 3. Send the quiz result to the user
    try:
        back_data = f"lecture|{subject}|{content_type}|{title}"
        keyboard = [[InlineKeyboardButton("⬅️ Back to Lecture Details", callback_data=back_data)]]
        
        await query.edit_message_text(
            final_text, 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Failed to send quiz: {e}")
        await query.edit_message_text("❌ Failed to generate or send the quiz.")

# ---------- BOT COMMANDS (ADMIN) ----------

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    if sender.id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not authorized to use the admin menu.")
        return
    await send_admin_menu(update, context)

# Admin-only: rename a subject
async def rename_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    if sender.id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not an admin for this bot.")
        return

    # Use '|' as delimiter to handle multi-word subject names
    args_text = " ".join(context.args)
    if "|" not in args_text:
        await update.message.reply_text(
            "Usage: `/rename_subject Old Subject Name | New Subject Name`\n\n"
            "*Example:*\n`/rename_subject Phyto Chem | Phytochemistry`",
            parse_mode="Markdown"
        )
        return
        
    parts = args_text.split("|", 1)
    if len(parts) != 2:
        await update.message.reply_text("Usage: `/rename_subject Old Name | New Name` (Requires exactly one '|').", parse_mode="Markdown")
        return
        
    old_name = parts[0].strip()
    new_name = parts[1].strip()
    
    if not old_name or not new_name:
         await update.message.reply_text("❌ Old and New subject names cannot be empty.", parse_mode="Markdown")
         return

    data = load_data()
    
    if old_name not in data or old_name.startswith('_'):
        await update.message.reply_text(f"❌ Subject *{old_name}* not found or is reserved.", parse_mode="Markdown")
        return

    if new_name in data:
        await update.message.reply_text(f"❌ Subject *{new_name}* already exists.", parse_mode="Markdown")
        return

    # Safely move all data from old_name to new_name
    data[new_name] = data.pop(old_name)
    save_data(data)
    
    await update.message.reply_text(
        f"✅ Subject successfully renamed from *{old_name}* to *{new_name}*.",
        parse_mode="Markdown"
    )

# ---------- BOT COMMANDS (USER) ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()
    subjects = get_subjects(data)

    if not subjects:
        await update.message.reply_text("No subjects configured yet. Admins: use /admin or /help.")
        return
        
    keyboard = [[InlineKeyboardButton(subj, callback_data=f"subject|{subj}")] for subj in subjects.keys()]
    await update.message.reply_text(
        f"Hi {user.first_name or 'student'} 👋\nChoose a subject:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*Student usage:*\n"
        "/start - open subject menu\n"
        "/search [query] - search all lectures by title\n\n"
        "*Admin usage (in the group):*\n"
        "Reply to a lecture post with:\n"
        "`/capture SubjectName | Lecture Name`\n"
        "/list - see indexed lectures\n"
        "/admin - access settings menu\n"
        "/rename_subject Old | New - rename a subject"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# User-accessible: search indexed lectures
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = " ".join(context.args).strip()
    if not query_text or len(query_text) < 3:
        await update.message.reply_text("Please provide a search query of at least 3 characters. Example: `/search Receptors`", parse_mode="Markdown")
        return

    data = load_data()
    subjects = get_subjects(data)
    results = []
    
    # Normalize query for comparison
    normalized_query = query_text.lower()

    for subject_name, info in subjects.items():
        # Robustly get document lectures (checking for old 'lectures' key)
        doc_lectures = info.get("document_lectures", info.get("lectures", {}))
        media_lectures = info.get("media_lectures", {})
        
        # Search Documents
        for title, message_id in doc_lectures.items():
            if normalized_query in title.lower():
                # Payload: lecture|subject|content_type|title
                results.append((
                    f"📄 {title} ({subject_name})",
                    f"lecture|{subject_name}|document|{title}"
                ))

        # Search Media
        for title, message_id in media_lectures.items():
            if normalized_query in title.lower():
                # Payload: lecture|subject|content_type|title
                results.append((
                    f"📹 {title} ({subject_name})",
                    f"lecture|{subject_name}|media|{title}"
                ))
                
    if not results:
        await update.message.reply_text(f"🔍 No lectures found matching *{query_text}*.", parse_mode="Markdown")
        return

    # Build keyboard from results
    # Truncate text for button size limit
    keyboard = [[InlineKeyboardButton(
        text if len(text) <= 30 else text[:27]+"...", 
        callback_data=data
    )] for text, data in results]

    await update.message.reply_text(
        f"🔍 Found {len(results)} matches for *{query_text}*:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# Admin-only: capture a lecture
async def capture(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    if sender.id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not an admin for this bot.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to the lecture message in the group when using this command.")
        return

    msg = update.message.reply_to_message
    chat = update.effective_chat
    
    is_correct_chat = False
    if GROUP_ID.startswith('@'):
        if chat.username and chat.username.lower() == GROUP_ID[1:].lower():
            is_correct_chat = True
    else:
        if str(chat.id) == str(GROUP_ID):
            is_correct_chat = True

    if not is_correct_chat:
        logger.warning(f"Capture command blocked in wrong chat. Chat ID: {chat.id}, Username: {chat.username}")
        await update.message.reply_text("This command must be used inside the designated lecture group or its topics.")
        return

    # Argument parsing for subject and custom title
    args_text = " ".join(context.args)
    if not args_text:
        await update.message.reply_text(
            "Usage: `/capture SubjectName | Lecture Name`\n\n"
            "*Example:*\n`/capture Pharmacology | Intro to Receptors`",
            parse_mode="Markdown"
        )
        return

    subject = args_text
    custom_title = None

    if "|" in args_text:
        parts = args_text.split("|", 1)
        subject = parts[0].strip()
        custom_title = parts[1].strip()
    
    if not subject:
         await update.message.reply_text(
            "Usage: `/capture SubjectName | Lecture Name`\n\n"
            "*Error: Subject name cannot be empty.*",
            parse_mode="Markdown"
         )
         return

    data = load_data()
    
    if subject.startswith('_'):
        await update.message.reply_text("Subject name cannot start with an underscore.")
        return

    if subject not in data:
        # Create new subject with the correct nested structure
        data[subject] = {"thread_id": None, "document_lectures": {}, "media_lectures": {}}
    
    # *** MIGRATION/FIX FOR EXISTING SUBJECTS ***
    if 'lectures' in data[subject]: 
        # Move all content from the old 'lectures' key to the new 'document_lectures' key
        data[subject]['document_lectures'] = data[subject].pop('lectures')
    
    # Ensure both keys exist before proceeding
    if 'document_lectures' not in data[subject]:
        data[subject]['document_lectures'] = {}
    if 'media_lectures' not in data[subject]:
        data[subject]['media_lectures'] = {}
    # *** END MIGRATION/FIX ***

    message_id = msg.message_id
    thread_id = getattr(msg, "message_thread_id", None)
    if thread_id and not data[subject].get("thread_id"):
        data[subject]["thread_id"] = thread_id

    # Determine file type
    file_type = "document" # Default to document (PDF, DOCX, etc.)
    if msg.video or msg.animation or msg.audio or msg.voice:
        file_type = "media"
    
    storage_key = "document_lectures" if file_type == "document" else "media_lectures"

    # Determine the title
    title = ""
    if custom_title:
        title = custom_title
    else:
        # Prioritize file names (Document, Video, Audio), then caption, then text
        if msg.document and msg.document.file_name:
            title = msg.document.file_name
        elif msg.video and msg.video.file_name:
            title = msg.video.file_name
        elif msg.audio and msg.audio.file_name:
            title = msg.audio.file_name
        elif msg.caption:
            title = msg.caption.strip()[:200]
        elif msg.text:
            title = msg.text.strip()[:200]
        else:
            title = f"message_{message_id}"

    if title in data[subject][storage_key]:
        title = f"{title} ({message_id})"

    data[subject][storage_key][title] = message_id
    save_data(data)

    await update.message.reply_text(
        f"✅ Saved lecture as *{file_type.upper()}* under *{subject}*:\n`{title}`\nmessage_id: {message_id}\nthread_id: {thread_id or 'None'}",
        parse_mode="Markdown"
    )

# Admin: list indexed lectures
async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    if sender.id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not an admin for this bot.")
        return
    data = load_data()
    subjects = get_subjects(data)

    if not subjects:
        await update.message.reply_text("No subjects/lectures indexed yet.")
        return
        
    lines = []
    for subj, info in subjects.items():
        # Ensure data structure is robust before calculating counts
        docs = info.get("document_lectures", info.get("lectures", {}))
        media = info.get("media_lectures", {})
        
        doc_count = len(docs)
        media_count = len(media)
        
        lines.append(f"*{subj}* (thread_id: {info.get('thread_id')}) - Docs: {doc_count}, Media: {media_count}")
        
        lines.append(f"  *Documents*:")
        for t, mid in docs.items():
            lines.append(f"    • {t} → {mid}")
        lines.append(f"  *Media (Videos/Audio)*:")
        for t, mid in media.items():
            lines.append(f"    • {t} → {mid}")
            
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# Handle buttons
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    payload = query.data

    # --- USER CALLBACKS ---

    if payload.startswith("subject|"):
        subject = payload.split("|", 1)[1]
        if subject not in data:
            await query.edit_message_text("Subject not found.")
            return
        
        info = data[subject]
        
        # Robust check to support subjects created with the old key 'lectures'
        doc_lectures = info.get("document_lectures", info.get("lectures", {}))
        media_lectures = info.get("media_lectures", {})
        
        num_docs = len(doc_lectures)
        num_media = len(media_lectures)

        buttons = []
        
        # New buttons for document vs. media selection
        if num_docs > 0:
            buttons.append([InlineKeyboardButton(f"📄 PDF Lectures ({num_docs})", callback_data=f"type_menu|{subject}|document")])
        if num_media > 0:
            buttons.append([InlineKeyboardButton(f"📹 (Videos/Sound) ({num_media})", callback_data=f"type_menu|{subject}|media")])
        
        if not buttons:
             await query.edit_message_text(
                f"No content indexed for *{subject}* yet.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back")]])
            )
             return

        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])

        await query.edit_message_text(
            f"Select content type for *{subject}*:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if payload == "back":
        subjects = get_subjects(data)
        kb = [[InlineKeyboardButton(s, callback_data=f"subject|{s}")] for s in subjects.keys()]
        await query.edit_message_text("Choose a subject:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if payload.startswith("type_menu|"):
        _, subject, content_type = payload.split("|", 2)
        info = data.get(subject)
        
        # Use the more robust data fetching here too
        if content_type == "document":
            lectures = info.get("document_lectures", info.get("lectures", {}))
            display_name = "PDF Lectures"
        else: # media
            lectures = info.get("media_lectures", {})
            display_name = "Videos/Sound"

        if not lectures:
            await query.edit_message_text(
                f"No {display_name} found for {subject}.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Subject Menu", callback_data=f"subject|{subject}")]])
            )
            return
            
        # New payload format: lecture|subject|content_type|title
        buttons = [
            [InlineKeyboardButton(title if len(title) <= 30 else title[:27]+"...", callback_data=f"lecture|{subject}|{content_type}|{title}")]
            for title in lectures.keys()
        ]
        buttons.append([InlineKeyboardButton("⬅️ Back to Subject Menu", callback_data=f"subject|{subject}")])
        
        await query.edit_message_text(
            f"{display_name} in *{subject}*:", 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if payload.startswith("lecture|"):
        _, subject, content_type, title = payload.split("|", 3)
        info = data.get(subject)
        
        if not info:
            await query.edit_message_text("Subject missing.")
            return
            
        # Use the more robust data fetching here too
        if content_type == "document":
            lecture_data = info.get("document_lectures", info.get("lectures", {}))
        else: # media
            lecture_data = info.get("media_lectures", {})
            
        message_id = lecture_data.get(title)
        
        if not message_id:
            await query.edit_message_text("Lecture not found.")
            return
            
        try:
            # Copy message to user (works even with forwarding disabled)
            await context.bot.copy_message(
                chat_id=query.from_user.id,
                from_chat_id=GROUP_ID,
                message_id=message_id
            )
            
            data = load_data() 
            stats = data.get("_stats", {"total_forwards": 0})
            stats["total_forwards"] = stats.get("total_forwards", 0) + 1
            data["_stats"] = stats
            save_data(data)

            # After sending the file, present quiz option and back button
            back_data = f"type_menu|{subject}|{content_type}"
            quiz_data = f"quiz|{subject}|{content_type}|{title}" # New payload for quiz

            keyboard = [
                [InlineKeyboardButton("🧠 Generate Quiz (LLM)", callback_data=quiz_data)], # NEW BUTTON
                [InlineKeyboardButton("⬅️ Back to Lectures", callback_data=back_data)]
            ]

            await query.edit_message_text(
                f"✅ Sent *{title}* from *{subject}*.\n\n_Tap 'Generate Quiz' for an interactive study aid._", 
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.exception("Copy message failed")
            await query.edit_message_text("Failed to send the lecture. The bot might not have the correct permissions in the source group.")
        return

    # --- LLM QUIZ HANDLER ---
    if payload.startswith("quiz|"):
        await quiz_generator(update, context)
        return
    # --- ADMIN CALLBACKS (admin|action) ---

    if payload.startswith("admin|"):
        _, action, *rest = payload.split("|")
        
        if query.from_user.id not in ADMIN_IDS:
            await query.edit_message_text("❌ Not authorized.")
            return

        data = load_data()
        
        if action == "show_usage":
            stats = data.get("_stats", {"total_forwards": 0})
            count = stats.get("total_forwards", 0)
            text = f"*Global Usage Statistics:*\nTotal Lectures Forwarded: *{count}*"
            keyboard = [[InlineKeyboardButton("⬅️ Admin Menu", callback_data="admin|menu")]]
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        elif action == "manage_subjects":
            subjects = get_subjects(data)
            keyboard = [
                [InlineKeyboardButton(subj, callback_data=f"admin|subject_menu|{subj}")]
                for subj in subjects.keys()
            ]
            keyboard.append([InlineKeyboardButton("⬅️ Admin Menu", callback_data="admin|menu")])
            await query.edit_message_text(
                "*Manage Subjects:*\nSelect a subject to manage.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        elif action == "subject_menu":
            subject = rest[0]
            # Robust check for counts
            num_docs = len(data.get(subject, {}).get("document_lectures", data.get(subject, {}).get("lectures", {})))
            num_media = len(data.get(subject, {}).get("media_lectures", {}))
            num_total = num_docs + num_media
            
            keyboard = [
                [InlineKeyboardButton(f"➡️ Manage Specific Lectures ({num_total})", callback_data=f"admin|manage_lectures|{subject}")],
                [InlineKeyboardButton(f"🗑️ Delete ALL Lectures in '{subject}'", callback_data=f"admin|confirm_delete_lectures|{subject}")],
                [InlineKeyboardButton(f"❌ Delete Entire Subject '{subject}'", callback_data=f"admin|confirm_delete_subject|{subject}")],
                [InlineKeyboardButton("⬅️ Back to Subjects", callback_data="admin|manage_subjects")]
            ]
            await query.edit_message_text(
                f"📚 *Subject: {subject}* (Total Lectures: {num_total})",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
            
        elif action == "manage_lectures":
            subject = rest[0]
            
            # Combine documents and media for a flat deletion list for simplicity
            all_lectures = {}
            # Robustly get document lectures (checking for old 'lectures' key)
            doc_lectures = data.get(subject, {}).get("document_lectures", data.get(subject, {}).get("lectures", {}))
            all_lectures.update({title: {"type": "document", "id": mid} for title, mid in doc_lectures.items()})
            all_lectures.update({title: {"type": "media", "id": mid} for title, mid in data.get(subject, {}).get("media_lectures", {}).items()})

            if not all_lectures:
                await query.edit_message_text("No lectures found to manage.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin|subject_menu|"+subject)]]))
                return
                
            # Payload includes the content type (document or media)
            keyboard = [
                [InlineKeyboardButton(f"🗑️ {title} ({all_lectures[title]['type'].capitalize()})", callback_data=f"admin|confirm_delete_lecture|{subject}|{all_lectures[title]['type']}|{title}")]
                for title in all_lectures.keys()
            ]
            keyboard.append([InlineKeyboardButton("⬅️ Back to Subject Menu", callback_data=f"admin|subject_menu|{subject}")])
            await query.edit_message_text(
                f"*Manage Lectures in {subject}:*\nTap a lecture title to delete it.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        # --- Confirmation & Deletion Actions ---

        elif action == "confirm_delete_subject":
            subject = rest[0]
            keyboard = [
                [InlineKeyboardButton("✅ CONFIRM DELETE SUBJECT", callback_data=f"admin|delete_subject|{subject}")],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"admin|subject_menu|{subject}")]
            ]
            await query.edit_message_text(
                f"🚨 *ARE YOU SURE?* This will permanently delete the entire subject: *{subject}* and all its lectures.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
            
        elif action == "confirm_delete_lectures":
            subject = rest[0]
            keyboard = [
                [InlineKeyboardButton("✅ CONFIRM DELETE ALL LECTURES", callback_data=f"admin|delete_all_lectures|{subject}")],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"admin|subject_menu|{subject}")]
            ]
            await query.edit_message_text(
                f"🚨 *ARE YOU SURE?* This will permanently delete all lectures in *{subject}* (Documents and Media).",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        elif action == "confirm_delete_lecture":
            subject = rest[0]
            content_type = rest[1] # New: get the content type
            title = rest[2]
            keyboard = [
                [InlineKeyboardButton(f"✅ CONFIRM DELETE: {title} ({content_type.capitalize()})", callback_data=f"admin|delete_lecture|{subject}|{content_type}|{title}")],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"admin|manage_lectures|{subject}")]
            ]
            await query.edit_message_text(
                f"🚨 *ARE YOU SURE?* Delete lecture: *{title}* from *{subject}*?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
            
        elif action == "delete_subject":
            subject = rest[0]
            if subject in data:
                del data[subject]
                save_data(data)
                text = f"✅ Subject *{subject}* and all its lectures have been permanently deleted."
            else:
                text = f"Subject *{subject}* not found."
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Subjects", callback_data="admin|manage_subjects")]]))
            return

        elif action == "delete_all_lectures":
            subject = rest[0]
            if subject in data:
                data[subject]["document_lectures"] = {}
                data[subject]["media_lectures"] = {}
                # Also delete the legacy key if it exists
                if 'lectures' in data[subject]:
                     del data[subject]['lectures']
                     
                save_data(data)
                text = f"✅ All lectures (Documents and Media) removed from subject *{subject}*."
            else:
                text = f"Subject *{subject}* not found."
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Subject Menu", callback_data=f"admin|subject_menu|{subject}")]]))
            return

        elif action == "delete_lecture":
            subject = rest[0]
            content_type = rest[1]
            title = rest[2]
            
            text = f"Lecture or Subject not found." # Default failure message
            
            # Determine which key to use for deletion, handling the legacy key if necessary
            if content_type == "document":
                if subject in data and title in data[subject].get("document_lectures", {}):
                    del data[subject]["document_lectures"][title]
                    text = f"✅ Lecture *{title}* ({content_type}) deleted from *{subject}*."
                elif subject in data and 'lectures' in data[subject] and title in data[subject]['lectures']:
                    del data[subject]["lectures"][title]
                    text = f"✅ Lecture *{title}* ({content_type}) deleted from *{subject}*."
            elif content_type == "media":
                if subject in data and title in data[subject].get("media_lectures", {}):
                    del data[subject]["media_lectures"][title]
                    text = f"✅ Lecture *{title}* ({content_type}) deleted from *{subject}*."
            
            save_data(data)
            
            subjects_data = load_data()
            
            # Check if there are any lectures left in the subject before determining back button
            total_lectures_left = len(subjects_data.get(subject, {}).get("document_lectures", {})) + \
                                 len(subjects_data.get(subject, {}).get("media_lectures", {})) + \
                                 len(subjects_data.get(subject, {}).get("lectures", {})) # Check legacy key just in case
            
            if total_lectures_left > 0:
                back_data = f"admin|manage_lectures|{subject}"
                back_label = "⬅️ Back to Lecture List"
            else:
                back_data = f"admin|subject_menu|{subject}"
                back_label = "⬅️ Back to Subject Menu"

            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(back_label, callback_data=back_data)]]))
            return

        elif action == "menu":
            await send_admin_menu(update, context, query.message.message_id)
            return

def main():
    if not BOT_TOKEN or not GROUP_ID or not ADMIN_IDS:
        print("ERROR: Set BOT_TOKEN, GROUP_ID, and ADMIN_IDS correctly before running.")
        return

    app = Application.builder().token(BOT_TOKEN).build()
    
    # ----------------------------------------------------
    # NEW: Set Telegram Bot Commands
    # This list defines what shows up in the "/" menu in Telegram
    # ----------------------------------------------------
    commands = [
        # User Commands
        BotCommand("start", "📚 Open lecture subjects menu"),
        BotCommand("search", "🔍 Search all lectures by title"),
        BotCommand("help", "❓ Show all commands (User/Admin)"),
        
        # Admin Commands (Visible to all, but only usable by admins)
        BotCommand("admin", "⚙️ Open admin settings panel"),
        BotCommand("capture", "➕ Index a lecture (MUST reply to a message)"),
        BotCommand("list", "📄 Show detailed list of all indexed content"),
        BotCommand("rename_subject", "✏️ Rename a subject (e.g., Old | New)"),
    ]
    
    # Use the bot instance in the Application to set the commands
    # This is a synchronous call outside of the async handlers
    try:
        app.bot.set_my_commands(commands)
        logger.info("Successfully set bot commands.")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")
    # ----------------------------------------------------

    # User Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_user))
    app.add_handler(CommandHandler("search", search))
    
    # Admin Commands
    app.add_handler(CommandHandler("capture", capture))
    app.add_handler(CommandHandler("list", admin_list))
    app.add_handler(CommandHandler("admin", admin_menu))
    app.add_handler(CommandHandler("rename_subject", rename_subject))
    
    # Callback Handler for buttons (handles quiz| and lecture| etc.)
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Use a MessageHandler for non-command text in private chats to show the menu
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, start))

    app.run_polling()

if __name__ == "__main__":
    main()
