# handlers/email_handler.py
"""
Toplu mail gönderim handler'ı
/toplumaile
/dosyalarıgöster
Input ve Output'taki tüm dosyaları ZIP yapar
ZIP'i PERSONAL_EMAIL'e gönderir
Input dosyasının ilk 6 karakterini ZIP ismi olarak kullanır
Dosya durumunu gösteren yardımcı komut
Reply keyboard desteği
Bu şekilde iki aşamalı işleminiz tamamlanmış olur!
"""
import zipfile
import tempfile
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from config import config
from utils.mailer import send_email_with_attachment
from utils.logger import logger

router = Router()

@router.message(Command("toplumaile", "toplumail", "tmail"))
async def cmd_toplu_mail(message: Message):
    """Input ve Output dosyalarını ZIP yapıp PERSONAL_EMAIL'e gönderir"""
    try:
        await message.answer("📧 Input ve Output dosyaları ZIP yapılıp mail gönderiliyor...")
        
        # Input ve Output klasörlerini kontrol et
        if not any(config.INPUT_DIR.iterdir()) and not any(config.OUTPUT_DIR.iterdir()):
            await message.answer("❌ Input veya Output klasörü boş. Önce /process komutu ile işlem yapın.")
            return
        
        # ZIP oluştur
        zip_path = await create_input_output_zip()
        
        if not zip_path:
            await message.answer("❌ ZIP dosyası oluşturulamadı.")
            return
        
        # Mail gönder
        success = await send_zip_email(zip_path)
        
        # Geçici ZIP'i sil
        zip_path.unlink(missing_ok=True)
        
        if success:
            await message.answer(
                f"✅ Input ve Output dosyaları başarıyla ZIP yapılıp gönderildi!\n"
                f"📧 Alıcı: {config.PERSONAL_EMAIL}"
            )
        else:
            await message.answer(f"❌ Mail gönderilemedi: {config.PERSONAL_EMAIL}")
            
    except Exception as e:
        logger.error(f"Toplu mail hatası: {e}")
        await message.answer("❌ İşlem sırasında hata oluştu.")

async def create_input_output_zip() -> Path:
    """Input ve Output klasörlerindeki dosyaları ZIP yapar"""
    try:
        # ZIP dosyası için isim oluştur (input dosyasından)
        input_files = list(config.INPUT_DIR.glob("*.xlsx"))
        zip_name = "output_files"
        
        if input_files:
            # İlk input dosyasının ilk 6 karakterini al
            first_input = input_files[0]
            zip_name = first_input.stem[:6] if first_input.stem else "output_files"
        
        # Geçici ZIP dosyası
        zip_path = Path(tempfile.gettempdir()) / f"{zip_name}_toplu.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Input dosyalarını ekle
            for file_path in config.INPUT_DIR.glob("*"):
                if file_path.is_file():
                    zipf.write(file_path, f"input/{file_path.name}")
            
            # Output dosyalarını ekle
            for file_path in config.OUTPUT_DIR.glob("*"):
                if file_path.is_file():
                    zipf.write(file_path, f"output/{file_path.name}")
        
        return zip_path
        
    except Exception as e:
        logger.error(f"ZIP oluşturma hatası: {e}")
        return None

async def send_zip_email(zip_path: Path) -> bool:
    """ZIP dosyasını mail olarak gönderir"""
    if not config.PERSONAL_EMAIL:
        logger.error("PERSONAL_EMAIL tanımlı değil")
        return False
    
    try:
        subject = "📊 Excel İşleme - Tüm Dosyalar"
        body = (
            "Merhaba,\n\n"
            "Excel işleme sonucu oluşan tüm input ve output dosyaları ektedir.\n\n"
            "İyi çalışmalar,\nData_listesi_Hıdır"
        )
        
        success = await send_email_with_attachment(
            [config.PERSONAL_EMAIL],
            subject,
            body,
            zip_path
        )
        
        return success
        
    except Exception as e:
        logger.error(f"ZIP mail gönderme hatası: {e}")
        return False

@router.message(Command("dosyalarıgöster", "dosyalar"))
async def cmd_dosyalari_goster(message: Message):
    """Input ve Output'taki dosyaları listeler"""
    try:
        input_files = list(config.INPUT_DIR.glob("*"))
        output_files = list(config.OUTPUT_DIR.glob("*"))
        
        response = ["📁 **DOSYA DURUMU**"]
        
        if input_files:
            response.append("\n📥 **Input Dosyaları:**")
            for file in input_files[:10]:  # İlk 10 dosya
                size = file.stat().st_size / 1024  # KB
                response.append(f"• {file.name} ({size:.1f} KB)")
            if len(input_files) > 10:
                response.append(f"• ... ve {len(input_files) - 10} dosya daha")
        else:
            response.append("\n📥 **Input:** Boş")
        
        if output_files:
            response.append("\n📤 **Output Dosyaları:**")
            for file in output_files[:10]:  # İlk 10 dosya
                size = file.stat().st_size / 1024  # KB
                response.append(f"• {file.name} ({size:.1f} KB)")
            if len(output_files) > 10:
                response.append(f"• ... ve {len(output_files) - 10} dosya daha")
        else:
            response.append("\n📤 **Output:** Boş")
        
        response.append(f"\n📧 **Toplu Mail Alıcısı:** {config.PERSONAL_EMAIL}")
        response.append("\n🔗 **Komutlar:** /toplumaile - /dosyalarıgöster")
        
        await message.answer("\n".join(response))
        
    except Exception as e:
        logger.error(f"Dosya listeleme hatası: {e}")
        await message.answer("❌ Dosya listesi alınamadı.")