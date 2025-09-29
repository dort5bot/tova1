# handlers/reply_handler.py
"""
Reply Keyboard → Kullanıcı dostu arayüz:
Temizle → /clear
Kova → /process
tek → /tek
JSON yap → /js
Komutlar → /dar komutunu ekle, tümünü bu maile atar)
"""

import logging
from aiogram import Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)
router = Router()

class ReplyKeyboardSingleton:
    """
    Singleton sınıfı: sadece bir tane ReplyKeyboard üretir.
    """

    _instance: ReplyKeyboardMarkup | None = None

    @classmethod
    def get_keyboard(cls) -> ReplyKeyboardMarkup:
        """Tekil ReplyKeyboard örneğini döndürür."""
        if cls._instance is None:
            logger.debug("ReplyKeyboard oluşturuluyor...")
            cls._instance = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="oku"), KeyboardButton(text="Temizle"), KeyboardButton(text="Kova"), KeyboardButton(text="TEK")],
                    [KeyboardButton(text="stop"),KeyboardButton(text="JSON yap"), KeyboardButton(text="Komutlar"),KeyboardButton(text="Toplu Mail")],
                ],

                resize_keyboard=True,
                one_time_keyboard=False,
                input_field_placeholder="Bir işlem seçin...",
            )
        return cls._instance


async def show_reply_keyboard(message: Message, title: str) -> None:
    """
    Ortak reply keyboard gösterici.
    """
    keyboard = ReplyKeyboardSingleton.get_keyboard()
    await message.answer(
        f"{title}\n\nSeçeneklerden birini seçin veya Excel dosyası gönderin:",
        reply_markup=keyboard,
    )


# ---------------------------------------------------
# /oku , /klavye /r komutları
# ---------------------------------------------------

# oku
async def send_welcome_message(message: Message):
    await message.answer(
        "📊 Excel İşleme Botuna Hoşgeldiniz!\n\n"
        "1️⃣ Önce **Temizle** butonuna tıkla.\n"
        "2️⃣ Excel dosyasını kontrol et.\n"
        "3️⃣ Dosyada **1. satırda** 'TARİH' ve 'İL' sütunları bulunmalıdır."
    )
    await show_reply_keyboard(message, "📋 Hızlı Erişim Menüsü")

@router.message(Command("oku"))
async def cmd_start_with_keyboard(message: Message) -> None:
    logger.info("oku komutu çalıştı: %s", message.from_user.id)
    await send_welcome_message(message)

@router.message(lambda m: m.text and m.text.lower() == "oku")
async def handle_oku_text(message: Message):
    logger.info("oku butonuna basıldı: %s", message.from_user.id)
    await send_welcome_message(message)



@router.message(Command("r", "klavye"))
async def cmd_reply_keyboard(message: Message) -> None:
    """
    /r veya /klavye komutu → sadece reply keyboard menüsü
    """
    logger.info("Reply keyboard menüsü çağrıldı: %s", message.from_user.id)
    await show_reply_keyboard(message, "📋 Hızlı Erişim Menüsü")


# ---------------------------------------------------
# Tuşların işlemleri
# ---------------------------------------------------


# Temizle
@router.message(lambda m: m.text and m.text == "Temizle")
async def handle_clear(message: Message, state: FSMContext) -> None:
    """
    Reply keyboard → Temizle butonu (/clear)
    """
    logger.info("Temizle komutu çalıştırılıyor: %s", message.from_user.id)
    from handlers.file_handler import clear_all

    await message.answer("🧹 Temizlik başlatılıyor...")
    await clear_all(message)


#  stop
@router.message(lambda m: m.text and m.text == "stop")
async def handle_cancel_button(message: Message, state: FSMContext):
    """Reply keyboard'dan iptal işlemi"""
    current_state = await state.get_state()
    
    if current_state is None:
        await message.answer("ℹ️ iptal edilecek aktif işlem yok.")
        return
    
    await state.clear()
    await message.answer(
        "❌ İşlem iptal edildi.\n"
        "Yeni bir işlem başlatmak için menüden seçim yapabilirsiniz.",
        reply_markup=ReplyKeyboardSingleton.get_keyboard()
    )


# Kova
@router.message(lambda m: m.text and m.text == "Kova")
async def handle_process(message: Message, state: FSMContext) -> None:
    """
    Reply keyboard → İşle butonu (/process)
    """
    logger.info("İşle komutu çalıştırılıyor: %s", message.from_user.id)
    #from handlers.file_handler import clear_all #temizlik
    from handlers.upload_handler import cmd_process
    
    # Sessizce temizlik (kullanıcıya mesaj gönderme)
    #await clear_all(message, silent=True)  # silent parametresi ekle, yoksa ayrı fonksiyon yaz


    await message.answer("⚙️ İşlem başlatılıyor...")
    await cmd_process(message, state)




# TEK
@router.message(lambda m: m.text and m.text == "TEK")
async def handle_tek(message: Message, state: FSMContext):
    """Reply keyboard → TEK butonu (/tek)"""
    from handlers.tek_handler import cmd_tek
    await message.answer("⚙️ TEK işlem başlatılıyor...")
    await cmd_tek(message, state)


# JSON yap
@router.message(lambda m: m.text and m.text == "JSON yap")
async def handle_create_json(message: Message, state: FSMContext) -> None:
    """
    Reply keyboard → JSON oluştur butonu (/js)
    """
    logger.info("JSON oluşturma komutu çalıştırılıyor: %s", message.from_user.id)
    from handlers.json_handler import handle_json_command

    await message.answer("📊 JSON oluşturma başlatılıyor...")
    await handle_json_command(message, state)


# Toplu Mail
@router.message(lambda m: m.text and m.text == "Toplu Mail")
async def handle_toplu_mail(message: Message):
    """Reply keyboard → Toplu Mail butonu (/toplumaile)"""
    from handlers.email_handler import cmd_toplu_mail
    await cmd_toplu_mail(message)
    

# Komutlar
@router.message(lambda m: m.text and m.text == "Komutlar")
async def handle_show_commands(message: Message, state: FSMContext) -> None:
    """
    Reply keyboard → Komut listesi butonu (/dar)
    """
    logger.info("Komut listesi komutu çağrıldı: %s", message.from_user.id)
    from handlers.dar_handler import scan_handlers_for_commands

    scanned = scan_handlers_for_commands()
    lines = [f"{cmd} → {desc}" for cmd, desc in sorted(scanned.items())]
    text = "\n".join(lines) if lines else "❌ Komut bulunamadı."

    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML")