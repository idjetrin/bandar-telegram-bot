import os
import json
import logging
import re
import google.generativeai as genai
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

MEMORY_FILE = "memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_memory(memory_data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory_data, f, indent=4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! Saya Bot Bandarmologi AI.\n\n"
        "Silakan kirim teks Broker Summary (hasil konversi).\n"
        "Pastikan ada Kode Saham dan Tanggal di dalam teksnya.\n"
        "Saya akan menganalisis dan membandingkannya dengan data sebelumnya."
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teks_user = update.message.text.strip()
    msg = await update.message.reply_text("📝 Teks diterima! AI sedang membaca data...")
    
    try:
        # --- 1. CARI KODE SAHAM ---
        kode_saham = "TIDAK_DIKETAHUI"
        match_saham = re.search(r'(?:Kode Saham\s*:\s*|SUMMARY\s*-\s*)([A-Z]{4})', teks_user.upper())
        if match_saham:
            kode_saham = match_saham.group(1)
        else:
            kata_umum = ["DATA", "BROKER", "SUMMARY", "BUY", "SELL", "INFO", "HARGA", "NET", "AVG", "TAMPILAN"]
            for kata in teks_user.upper().split():
                if len(kata) == 4 and kata.isalpha() and kata not in kata_umum:
                    kode_saham = kata
                    break

        # --- 2. CARI TANGGAL ---
        tanggal_str = "TANGGAL_TIDAK_DITEMUKAN"
        # Cari pola tanggal: 22-10-2026, 22 Oct 26, 2026-10-22, atau Rentang Tanggal: 16-22 Oct
        match_tgl = re.search(r'(\d{1,2}[-/\s][A-Za-z]{3}[-/\s]\d{2,4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}\s*-\s*\d{1,2}\s+[A-Za-z]{3})', teks_user)
        if match_tgl:
            tanggal_str = match_tgl.group(1)

        # --- 3. AMBIL MEMORI ---
        memory = load_memory()
        riwayat_saham = memory.get(kode_saham, [])
        
        # Format memori untuk dikirim ke Gemini
        konteks_memori = "Belum ada riwayat."
        if riwayat_saham:
            # Ambil 5 riwayat terakhir
            riwayat_terakhir = riwayat_saham[-5:]
            konteks_memori = json.dumps(riwayat_terakhir, indent=2)

        # --- 4. PROMPT ANALISIS ---
        prompt_analisis = f"""
        Kamu adalah analis bandarmologi saham IDX.
        Saya punya data teks Broker Summary untuk saham {kode_saham}.
        Data ini memiliki Tanggal: {tanggal_str}.
        
        DATA HARI INI:
        {teks_user}
        
        RIWAYAT SAHAM {kode_saham} SEBELUMNYA (Data dari tanggal lain):
        {konteks_memori}
        
        Tugasmu:
        1. Baca dengan teliti TANGGAL pada data hari ini dan TANGGAL pada data riwayat.
        2. Bandingkan data hari ini dengan riwayat secara KRONOLOGIS (masa lalu ke masa depan). Jangan sampai terbalik!
        3. Apakah ada broker yang konsisten net buy/sell dari waktu ke waktu?
        4. Beri kesimpulan tren: akumulasi, distribusi, atau netral.
        5. Apa yang perlu dikonfirmasi besok?
        Jawab ringkas, bahasa Indonesia, maksimal 8 kalimat. Jangan beri rekomendasi beli/jual.
        """
        
        resp_analisis = model.generate_content(prompt_analisis)
        hasil_akhir = resp_analisis.text

        # --- 5. SIMPAN KE MEMORI ---
        if kode_saham not in memory:
            memory[kode_saham] = []
        
        memory[kode_saham].append({
            "tanggal_data": tanggal_str,
            "waktu_diterima": str(update.message.date),
            "data_teks": teks_user,
            "analisis": hasil_akhir
        })
        save_memory(memory)

        # --- 6. KIRIM HASIL ---
        await msg.delete()
        await update.message.reply_text(f"*Saham: {kode_saham} | Tanggal: {tanggal_str}*\n\n{hasil_akhir}", parse_mode='Markdown')

    except Exception as e:
        await msg.edit_text(f"❌ Waduh, terjadi error:\n{str(e)}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    # Handler untuk menerima TEKS
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot AI Teks + Memori Tanggal berjalan... (Tekan Ctrl+C untuk berhenti)")
    app.run_polling()

if __name__ == "__main__":
    main()
