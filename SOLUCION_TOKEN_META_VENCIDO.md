# Solución: Token de Meta Ads Vencido

## Diagnóstico

El token de acceso de Meta Ads (`META_ACCESS_TOKEN`) en el archivo `.env` está vencido o requiere verificación. El error recibido es:

```
Error 190, Subcódigo 459: "You cannot access the app till you log in to www.facebook.com and follow the instructions given."
```

## Pasos para Renovar el Token

### Paso 1: Acceder al Graph API Explorer
1. Ve a [Graph API Explorer de Facebook](https://developers.facebook.com/tools/explorer/)
2. Inicia sesión con la cuenta de Facebook que tiene acceso a la aplicación de Meta Ads.

### Paso 2: Seleccionar la Aplicación Correcta
1. En la esquina superior derecha, selecciona la aplicación correspondiente a `META_APP_ID: 1492510719113702`
2. Si no aparece, es posible que necesites permisos de administrador.

### Paso 3: Generar un Nuevo Token de Acceso
1. Haz clic en "Generate Access Token"
2. Selecciona los permisos necesarios:
   - `ads_management`
   - `ads_read`
   - `business_management`
   - `public_profile`
3. Sigue las instrucciones de autorización.

### Paso 4: Obtener un Token de Larga Duración
Los tokens generados en el Graph API Explorer son de corta duración (1-2 horas). Para obtener un token de larga duración (60 días):

**Opción A: Usar la App Dashboard**
1. Ve a [Facebook for Developers](https://developers.facebook.com/apps/)
2. Selecciona tu aplicación (`1492510719113702`)
3. Ve a "Settings" > "Basic"
4. Copia el "App ID" y "App Secret"
5. Usa el endpoint de intercambio de tokens:
   ```
   GET /oauth/access_token?grant_type=fb_exchange_token&
   client_id={app-id}&
   client_secret={app-secret}&
   fb_exchange_token={short-lived-token}
   ```

**Opción B: Usar una Herramienta de Línea de Comandos**
```bash
curl -X GET "https://graph.facebook.com/v25.0/oauth/access_token?grant_type=fb_exchange_token&client_id=1492510719113702&client_secret=30d83bb0f1ccae8602ab5a28a604b1f8&fb_exchange_token=TOKEN_CORTO"
```

### Paso 5: Actualizar el Archivo .env
Reemplaza el valor de `META_ACCESS_TOKEN` en `webapp/.env` con el nuevo token:

```env
META_ACCESS_TOKEN=tu_nuevo_token_aqui
```

### Paso 6: Verificar la Conexión
Ejecuta el script de prueba para confirmar que el token funciona:

```bash
cd webapp
py test_meta_token.py
```

## Solución Alternativa: Token del Sistema

Si el token sigue expirando cada 60 días, considera:

1. **Implementar renovación automática** usando el endpoint de refresh token
2. **Usar un token del sistema** (System User Token) que no expire:
   - Ve a Business Settings > System Users
   - Crea un System User y genera un token sin expiración
   - Asigna los permisos necesarios a la cuenta de ads

## Notas Importantes

1. **Seguridad**: Nunca compartas el `META_APP_SECRET` o tokens en repositorios públicos.
2. **Backup**: Guarda una copia del token anterior por si necesitas revertir.
3. **Monitoreo**: Configura alertas para detectar cuando el token esté próximo a expirar.

## Referencias

- [Documentación de Errores de Facebook API](https://developers.facebook.com/docs/graph-api/using-graph-api/error-handling)
- [Guía de Tokens de Acceso](https://developers.facebook.com/docs/facebook-login/access-tokens)
- [Permisos de Marketing API](https://developers.facebook.com/docs/marketing-api/access)

## Estado Actual

- ✅ Token actual: VENCIDO (necesita renovación)
- ✅ App ID: 1492510719113702
- ✅ App Secret: 30d83bb0f1ccae8602ab5a28a604b1f8
- ✅ Ad Account ID: act_1231317231543949
- ❌ Conexión API: Fallida (Error 190)

## Contacto

Si necesitas asistencia adicional con la configuración de Meta Ads API, consulta con el administrador de la cuenta de Facebook Business.