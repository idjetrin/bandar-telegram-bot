import os
import io
import json
import logging
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 1. Load API Key
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 2. Konfigurasi Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.8-flash') 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- FITUR MEMORY ---
MEMORY_FILE = "memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_memory(memory_data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory_data, f, indent=4)

# --- PROMPT ---
PROMPT_ANALIS = """
Kamu adalah analis bandarmologi saham IDX berpengalaman.
Tolong baca gambar tabel Broker Summary ini (data Buy di kiri, Sell di kanan).

RIWAYAT ANALISIS SEBELUMNYA (Jika ada, gunakan ini untuk melihat konsistensi):
{memory_context}

Tugasmu:
1. Identifikasi broker akumulator dominan dan distributor dominan hari ini.
2. Bandingkan dengan riwayat sebelumnya (jika ada). Apakah ada broker yang konsisten net buy/net sell?
3. Cek divergence: harga vs net buy — apakah ada ketidaksesuaian menarik.
4. Beri kesimpulan awal: indikasi akumulasi, distribusi, atau netral.
5. Sebutkan apa yang perlu dikonfirmasi besok.
Jawab ringkas, bahasa Indonesia, maksimal 8 kalimat. Jangan memberi rekomendasi beli/jual.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! Saya Bot Bandarmologi AI dengan Fitur Memori.\n\n"
        "Kirimkan screenshot tabel Broker Summary, dan saya akan menganalisisnya. "
        "Saya akan mengingat analisis ini untuk besok."
    )

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📸 Foto diterima! AI sedang membaca tabel dan menganalisis...")
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        
        img = Image.open(io.BytesIO(image_bytes))
        img.thumbnail((1200, 1200))
        
        compressed_buffer = io.BytesIO()
        img.save(compressed_buffer, format="JPEG")
        compressed_bytes = compressed_buffer.getvalue()
        
        # Ambil memori (riwayat terakhir, maksimal 5)
        memory = load_memory()
        # Kita asumsikan kuncinya adalah tanggal atau ID chat. Untuk simpelnya, kita pakai list global dulu.
        history_list = memory.get("history", [])
        
        # Ambil 3 riwayat terakhir untuk konteks
        recent_history = history_list[-3:] 
        memory_context = json.dumps(recent_history, indent=2) if recent_history else "Belum ada riwayat."
        
        # Masukkan memori ke prompt
        final_prompt = PROMPT_ANALIS.replace("{memory_context}", memory_context)

        # Kirim ke Gemini
        response = model.generate_content([
            final_prompt,
            {'mime_type': 'image/jpeg', 'data': compressed_bytes}
        ])
        
        # Simpan hasil analisis ke memori
        # (Kita simpan ringkasannya saja agar file tidak terlalu besar)
        history_list.append({
            "waktu": str(update.message.date),
            "analisis": response.text
        })
        memory["history"] = history_list
        save_memory(memory)
        
        await msg.delete()
        await update.message.reply_text(response.text, parse_mode='Markdown')

    except Exception as e:
        await msg.edit_text(f"❌ Waduh, terjadi error:\n{str(e)}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    print("Bot AI + Memory sedang berjalan... (Tekan Ctrl+C untuk berhenti)")
    app.run_polling()

if __name__ == "__main__":
    main()