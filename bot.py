import os
import io
import json
import logging

from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler

# === НАСТРОЙКИ ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")

# === Google API ===
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service():
    creds = None
    if 'GOOGLE_TOKEN_JSON' in os.environ:
        try:
            creds_json = json.loads(os.environ['GOOGLE_TOKEN_JSON'])
            creds = Credentials.from_authorized_user_info(creds_json, SCOPES)
        except Exception as e:
            raise Exception(f"Не удалось распарсить GOOGLE_TOKEN_JSON: {e}")

    if not creds or not creds.valid:
        raise Exception("Нет действительного токена. Проверь GOOGLE_TOKEN_JSON.")

    return build('drive', 'v3', credentials=creds)

# Инициализация Google Drive
drive_service = get_drive_service()

# === Telegram logic ===
logging.basicConfig(level=logging.INFO)
photo_buffer = {}

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    bio = io.BytesIO()
    await file.download_to_memory(out=bio)
    bio.seek(0)
    photo_buffer[user_id] = bio
    await update.message.reply_text("Фото получено! Теперь отправь мне имя для файла.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in photo_buffer:
        await update.message.reply_text("Сначала пришли фото.")
        return

    file_name = update.message.text.strip() + ".jpg"
    media = photo_buffer.pop(user_id)
    media.seek(0)

    file_metadata = {
        'name': file_name,
        'parents': [GDRIVE_FOLDER_ID]
    }
    media_body = MediaIoBaseUpload(media, mimetype='image/jpeg', resumable=False)

    drive_service.files().create(
        body=file_metadata,
        media_body=media_body,
        fields='id'
    ).execute()

    await update.message.reply_text(f"✅ Фото загружено на Google Drive как: {file_name}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь фото, а потом отдельным сообщением — имя файла.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()
