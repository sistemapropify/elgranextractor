# Solución: Checkpoint de Seguridad de Facebook (Error 190, Subcódigo 459)

## Diagnóstico Completo

El token de Meta Ads **NO está vencido**, pero Facebook ha bloqueado el acceso por razones de seguridad. Los detalles son:

- **Token**: Válido (token del sistema sin expiración)
- **Permisos**: Completo (ads_management, ads_read, business_management, public_profile)
- **Error**: `You cannot access the app till you log in to www.facebook.com and follow the instructions given.`
- **Código**: 190, Subcódigo 459
- **Checkpoint URL**: `https://www.facebook.com`
- **Tipo**: OAuthException

## Causa del Problema

Facebook ha detectado actividad inusual o requiere verificación adicional por:

1. **Modo de desarrollo**: La aplicación está en modo "Development" y necesita revisión
2. **Checkpoint de seguridad**: Facebook sospecha de actividad inusual en la cuenta
3. **Permisos pendientes**: Algunos permisos requieren revisión manual
4. **Verificación de identidad**: El usuario necesita confirmar su identidad

## Pasos para Resolver

### Paso 1: Iniciar Sesión en Facebook
1. Ve a [facebook.com](https://www.facebook.com)
2. Inicia sesión con la cuenta personal que autorizó la aplicación "propifai Aps"
   - Esta es la cuenta asociada al User ID: `122161553204905389`

### Paso 2: Visitar el Checkpoint URL
1. Ve directamente a: `https://www.facebook.com`
2. Facebook debería mostrarte automáticamente un mensaje de verificación
3. Si no aparece, intenta:
   - [Facebook Account Quality](https://www.facebook.com/accountquality/)
   - [Facebook Support Inbox](https://www.facebook.com/support)

### Paso 3: Completar la Verificación
Sigue las instrucciones que Facebook te proporcione, que pueden incluir:
- Confirmar tu identidad con una foto
- Verificar tu número de teléfono
- Confirmar tu dirección de correo electrónico
- Revisar la actividad reciente de la cuenta

### Paso 4: Verificar el Estado de la Aplicación
1. Ve a [Facebook for Developers](https://developers.facebook.com/apps/)
2. Selecciona la aplicación `1492510719113702` (propifai Aps)
3. Verifica que la aplicación esté en modo "Live" (no "Development")
4. Si está en modo Development, cambia a Live (requiere revisión de Facebook)

### Paso 5: Probar la Conexión Nuevamente
Después de completar la verificación:
```bash
cd webapp
py test_meta_token.py
```

## Solución Alternativa si Persiste el Error

### Opción A: Crear una Nueva Aplicación
1. Crea una nueva aplicación en [Facebook for Developers](https://developers.facebook.com/apps/)
2. Configúrala como "Business" desde el inicio
3. Solicita revisión inmediata para los permisos de ads
4. Genera un nuevo token

### Opción B: Usar un System User Token
1. Ve a Business Settings > System Users
2. Crea un nuevo System User
3. Genera un token sin expiración
4. Asigna permisos a la cuenta de ads

### Opción C: Contactar Soporte de Facebook
1. Ve a [Facebook Business Support](https://business.facebook.com/business/help)
2. Explica el error 190, subcódigo 459
3. Proporciona el App ID y User ID

## Prevención Futura

1. **Mantén la aplicación en modo Live** una vez aprobada
2. **Usa tokens del sistema** (System User Tokens) que son más estables
3. **Monitorea los errores 190** con alertas
4. **Renueva tokens proactivamente** cada 60 días (aunque este no expira)

## Estado Actual de la Aplicación

- ✅ App ID: 1492510719113702
- ✅ App Name: propifai Aps  
- ✅ User ID: 122161553204905389
- ✅ Token Type: Sistema (sin expiración)
- ✅ Permisos: Completos
- ❌ Estado: Bloqueado por checkpoint de seguridad
- ❌ Acceso API: Denegado (Error 190)

## Tiempo Estimado de Resolución

- **Checkpoint simple**: 5-30 minutos
- **Revisión de aplicación**: 1-7 días
- **Crear nueva app**: 1-2 horas

## Contacto de Emergencia

Si el problema persiste después de seguir estos pasos, contacta:
- Facebook Business Support: https://business.facebook.com/business/help
- Meta for Developers: https://developers.facebook.com/support/

---

**Nota**: Este es un problema común con las aplicaciones de Facebook. Una vez resuelto el checkpoint, el token funcionará normalmente sin necesidad de regenerarlo.