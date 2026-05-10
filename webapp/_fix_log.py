from whatsapp_extractor.models import ExtractorLog, ArchivoExtraccionWhatsApp  
log11 = ExtractorLog.objects.get(id=11)  
print(f"Antes: estado={repr(log11.estado)}")  
log11.estado = 'running'  
log11.save(update_fields=['estado'])  
print(f"Despues: estado={repr(log11.estado)}")  
a = ArchivoExtraccionWhatsApp.objects.get(id=10)  
a.procesado = False  
a.save(update_fields=['procesado'])  
print(f"Archivo 10: procesado={a.procesado}")  
