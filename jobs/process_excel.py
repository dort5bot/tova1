# jobs/process_excel.py - GÜNCELLENMİŞ VERSİYON
"""
ZIP içinde klasör ayrımı olmadan, tüm input ve output Excel dosyalarının aynı klasörde (düz olarak) bir arada

"""
import asyncio
from pathlib import Path
from typing import Dict, Any
import zipfile
import tempfile

from utils.excel_cleaner import clean_excel_headers
from utils.excel_splitter import split_excel_by_groups
from utils.mailer import send_email_with_attachment
from utils.group_manager import group_manager
from utils.logger import logger
from config import config

from datetime import datetime, timedelta


async def process_excel_task(input_path: Path, user_id: int) -> Dict[str, Any]:
    """Excel işleme görevini yürütür - TOPLU MAIL OTOMATİK EKLENDİ"""
    cleaning_result = None
    try:
        logger.info(f"Excel işleme başlatıldı: {input_path.name}, Kullanıcı: {user_id}")

        # 1. Excel dosyasını temizle ve düzenle
        cleaning_result = clean_excel_headers(str(input_path))
        if not cleaning_result["success"]:
            error_msg = f"Excel temizleme hatası: {cleaning_result.get('error', 'Bilinmeyen hata')}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        logger.info(f"Excel temizlendi: {cleaning_result['row_count']} satır")

        # 2. Dosyayı gruplara ayır
        splitting_result = split_excel_by_groups(
            cleaning_result["temp_path"],
            cleaning_result["headers"]
        )
        
        if not splitting_result["success"]:
            error_msg = f"Excel ayırma hatası: {splitting_result.get('error', 'Bilinmeyen hata')}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        logger.info(f"Excel gruplara ayrıldı: {splitting_result['total_rows']} satır, {len(splitting_result['output_files'])} grup")

        # 3. E-postaları gönder (async olarak) - GRUP MAILLERİ
        email_tasks = []
        output_files = splitting_result["output_files"]
        email_results = []
        
        for group_id, file_info in output_files.items():
            group_info = group_manager.get_group_info(group_id)
            recipients = group_info.get("email_recipients", [])
            
            if recipients and file_info["row_count"] > 0:
                subject = f"{group_info.get('group_name', group_id)} Raporu - {file_info['filename']}"
                body = (
                    f"Merhaba,\n\n"
                    f"{group_info.get('group_name', group_id)} grubu için {file_info['row_count']} satırlık rapor ekte gönderilmiştir.\n\n"
                    f"İyi çalışmalar,\nData_listesi_Hıdır"
                )
                
                # Her alıcı için ayrı mail gönderimi
                for recipient in recipients:
                    if recipient.strip():  # Boş email adreslerini atla
                        task = send_email_with_attachment(
                            [recipient.strip()], subject, body, file_info["path"]
                        )
                        email_tasks.append((task, group_id, recipient, file_info["path"].name))
        
        # Tüm mail görevlerini paralel çalıştır
        if email_tasks:
            logger.info(f"{len(email_tasks)} mail görevi başlatılıyor...")
            
            tasks = [task[0] for task in email_tasks]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Sonuçları işle
            for i, result in enumerate(results):
                task_info = email_tasks[i]
                group_id, recipient, filename = task_info[1], task_info[2], task_info[3]
                
                if isinstance(result, Exception):
                    logger.error(f"Mail gönderim hatası - Grup: {group_id}, Alıcı: {recipient}, Dosya: {filename}, Hata: {result}")
                    email_results.append({
                        "success": False,
                        "group_id": group_id,
                        "recipient": recipient,
                        "error": str(result)
                    })
                else:
                    logger.info(f"Mail gönderildi - Grup: {group_id}, Alıcı: {recipient}, Dosya: {filename}")
                    email_results.append({
                        "success": True,
                        "group_id": group_id,
                        "recipient": recipient
                    })

        # 4. OTOMATİK TOPLU MAIL GÖNDERİMİ - YENİ EKLENDİ
        toplu_mail_success = False
        if config.PERSONAL_EMAIL:
            toplu_mail_success = await send_automatic_bulk_email(input_path, output_files)
            if toplu_mail_success:
                logger.info(f"✅ Otomatik toplu mail gönderildi: {config.PERSONAL_EMAIL}")
            else:
                logger.error(f"❌ Otomatik toplu mail gönderilemedi: {config.PERSONAL_EMAIL}")

        # 5. Geçici dosyaları temizle
        try:
            if cleaning_result and "temp_path" in cleaning_result:
                temp_path = Path(cleaning_result["temp_path"])
                if temp_path.exists():
                    temp_path.unlink()
                    logger.info(f"Geçici dosya silindi: {temp_path.name}")
        except Exception as e:
            logger.warning(f"Geçici dosya silinemedi: {e}")
        
        return {
            "success": True,
            "output_files": output_files,
            "total_rows": splitting_result["total_rows"],
            "matched_rows": splitting_result["matched_rows"],
            "email_results": email_results,
            "bulk_email_sent": toplu_mail_success,  # YENİ EKLENDİ
            "bulk_email_recipient": config.PERSONAL_EMAIL if toplu_mail_success else None,  # YENİ EKLENDİ
            "user_id": user_id
        }
        
    except Exception as e:
        logger.error(f"İşlem görevi hatası: {e}", exc_info=True)
        
        # Hata durumunda geçici dosyaları temizle
        try:
            if cleaning_result and "temp_path" in cleaning_result:
                temp_path = Path(cleaning_result["temp_path"])
                if temp_path.exists():
                    temp_path.unlink()
        except:
            pass
            
        return {"success": False, "error": str(e)}

async def send_automatic_bulk_email(input_path: Path, output_files: Dict) -> bool:
    """Input ve Output dosyalarını ZIP yapıp PERSONAL_EMAIL'e gönderir"""
    if not config.PERSONAL_EMAIL:
        logger.error("PERSONAL_EMAIL tanımlı değil")
        return False
    
    try:
        # UTC+3 saatini al
        now_utc3 = datetime.utcnow() + timedelta(hours=3)
        time_str = now_utc3.strftime("%H%M")  # Saat ve dakika
        
        # ZIP dosyası için isim oluştur
        zip_name = f"{time_str}_{input_path.stem[:9]}" if input_path.stem else f"{time_str}_output_files"
        
        
        # Geçici ZIP dosyası
        zip_path = Path(tempfile.gettempdir()) / f"{zip_name}_rap.zip"
        

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Input dosyasını klasör olmadan ekle
            if input_path.exists():
                zipf.write(input_path, input_path.name)
            
            # Output dosyalarını klasör olmadan ekle
            for file_info in output_files.values():
                file_path = file_info["path"]
                if file_path.exists():
                    zipf.write(file_path, file_info['filename'])

        
        # Mail gönder
        subject = "📊 Data raporu - Ektedir. Saat-dosya adı, gelen(input) ve gönderilen(output)"
        body = (
            "Merhaba,\n\n"
            "Excel işleme sonucu oluşan tüm input(gelen) ve output(gönderilen) dosyaları ektedir.\n\n"
            "Bu mail otomatik olarak gönderilmiştir.\n\n"
            "İyi çalışmalar,\nData_listesi_Hıdır"
        )
        
        success = await send_email_with_attachment(
            [config.PERSONAL_EMAIL],
            subject,
            body,
            zip_path
        )
        
        # Geçici ZIP'i sil
        zip_path.unlink(missing_ok=True)
        
        return success
        
    except Exception as e:
        logger.error(f"Otomatik toplu mail hatası: {e}")
        return False