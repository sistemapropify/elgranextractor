# Documentación de la API para Aplicación Móvil

Esta documentación describe los endpoints de la API REST implementados para que la aplicación móvil en Android Studio pueda acceder a los datos de propiedades y buscar comparables.

## Base URL

```
http://tu-servidor.com/api/
```

En desarrollo local:
```
http://localhost:8000/api/
```

## Endpoints Disponibles

### 1. Listar propiedades raw (PropiedadRaw)

**GET** `/propiedades-raw/`

Obtiene una lista paginada de todas las propiedades del modelo PropiedadRaw.

**Parámetros de consulta (opcionales):**
- `tipo_propiedad`: Filtrar por tipo (Casa, Departamento, Terreno, etc.)
- `condicion`: Filtrar por condición (venta, alquiler, etc.)
- `departamento`: Filtrar por departamento
- `precio_min`: Precio mínimo en USD
- `precio_max`: Precio máximo en USD
- `page`: Número de página (paginación)

**Ejemplo de respuesta:**
```json
{
  "count": 1593,
  "next": "http://localhost:8000/api/propiedades-raw/?page=2",
  "previous": null,
  "results": [
    {
      "id": 9433,
      "tipo_propiedad": "Casa",
      "condicion": "alquiler",
      "precio_usd": "429.00",
      "departamento": "Arequipa",
      "provincia": "Islay",
      "distrito": "Mollendo",
      "area_terreno": "240.24",
      "area_construida": null,
      "numero_habitaciones": 2,
      "numero_banos": 1,
      "lat": -17.0270779,
      "lng": -72.01095959999999,
      "precio_m2": null,
      "imagen_url": "https://...",
      "fuente_excel": "excel_corregido",
      "url_propiedad": "https://www.remax.pe/...",
      "coordenadas": "-17.0270779,-72.01095959999999"
    },
    ...
  ]
}
```

### 2. Listar propiedades Propifai (PropifaiProperty)

**GET** `/propiedades-propifai/`

Obtiene una lista paginada de todas las propiedades del modelo PropifaiProperty (base de datos Propifai).

**Parámetros de consulta (opcionales):**
- `tipo_propiedad`: Filtrar por tipo (basado en título)
- `departamento`: Filtrar por departamento
- `precio_min`: Precio mínimo
- `precio_max`: Precio máximo
- `page`: Número de página

**Ejemplo de respuesta:**
```json
{
  "count": 100,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 94,
      "code": "PROP000094",
      "title": "Casa En Characato",
      "price": 115000.0,
      "department": "Arequipa",
      "province": "Arequipa",
      "district": "Characato",
      "built_area": null,
      "land_area": null,
      "bedrooms": 0,
      "bathrooms": 0,
      "lat": -16.404052,
      "lng": -71.539011,
      "precio_m2": null,
      "tipo_propiedad": "Propiedad",
      "coordinates": "-16.404052,-71.539011",
      "imagen_url": "https://propifymedia01.blob.core.windows.net/..."
    },
    ...
  ]
}
```

### 3. Buscar propiedades comparables

**POST** `/comparables/`

Busca propiedades comparables basadas en ubicación geográfica y características similares. Este endpoint replica la funcionalidad de `buscar_comparables` del módulo ACM.

**Cuerpo de la solicitud (JSON):**
```json
{
  "lat": -16.398,
  "lng": -71.535,
  "radio": 1000,
  "tipo_propiedad": "Casa",
  "metros_construccion": 120,
  "metros_terreno": 200,
  "habitaciones": 3,
  "banos": 2
}
```

**Parámetros:**
- `lat` (obligatorio): Latitud del punto de referencia
- `lng` (obligatorio): Longitud del punto de referencia
- `radio` (opcional): Radio de búsqueda en metros (default: 500)
- `tipo_propiedad` (opcional): Tipo de propiedad a filtrar
- `metros_construccion` (opcional): Área construida aproximada (±30%)
- `metros_terreno` (opcional): Área de terreno aproximada (±30%)
- `habitaciones` (opcional): Número exacto de habitaciones
- `banos` (opcional): Número exacto de baños

**Ejemplo de respuesta:**
```json
{
  "status": "ok",
  "total": 15,
  "radio_metros": 1000.0,
  "punto_referencia": {
    "lat": -16.398,
    "lng": -71.535
  },
  "propiedades": [
    {
      "id": 8488,
      "lat": -16.39572763551547,
      "lng": -71.53380767486877,
      "tipo": "Casa",
      "precio": 650000.0,
      "precio_final": null,
      "metros_construccion": 322.5,
      "metros_terreno": 322.5,
      "habitaciones": 7,
      "baños": 7,
      "estado": "En publicación",
      "distrito": "Arequipa",
      "provincia": "Arequipa",
      "departamento": "Arequipa",
      "imagen_url": "https://...",
      "precio_m2": 2015.5,
      "precio_m2_final": null,
      "distancia_metros": 282.88,
      "fuente": "local",
      "es_propify": false
    },
    {
      "id": 94,
      "lat": -16.404052,
      "lng": -71.539011,
      "tipo": "Propiedad",
      "precio": 115000.0,
      "precio_final": 115000.0,
      "metros_construccion": null,
      "metros_terreno": null,
      "habitaciones": 0,
      "baños": 0,
      "estado": "En Publicación",
      "distrito": "Characato",
      "provincia": "Arequipa",
      "departamento": "Arequipa",
      "imagen_url": "https://...",
      "precio_m2": null,
      "precio_m2_final": null,
      "distancia_metros": 797.45,
      "fuente": "propifai",
      "es_propify": true,
      "codigo": "PROP000094",
      "titulo": "Casa En Characato"
    }
  ]
}
```

**Notas:**
- Las propiedades pueden provenir de dos fuentes: `local` (PropiedadRaw) y `propifai` (PropifaiProperty)
- El campo `es_propify` indica si la propiedad es de la base de datos Propifai
- Las propiedades se ordenan por distancia (más cercana primero)
- Se aplican filtros de similitud para metros construidos/terreno (±30%)

## Autenticación

Actualmente los endpoints no requieren autenticación (permission_classes = AllowAny). En producción se recomienda implementar autenticación JWT o API keys.

## Ejemplos de Uso en Android (Kotlin/Java)

### Usando Retrofit (Kotlin)

```kotlin
interface PropiedadesApiService {
    @GET("propiedades-raw/")
    suspend fun getPropiedadesRaw(
        @Query("tipo_propiedad") tipo: String? = null,
        @Query("departamento") departamento: String? = null,
        @Query("page") page: Int = 1
    ): PropiedadesResponse
    
    @POST("comparables/")
    suspend fun buscarComparables(@Body request: ComparablesRequest): ComparablesResponse
}

data class ComparablesRequest(
    val lat: Double,
    val lng: Double,
    val radio: Double = 500.0,
    val tipo_propiedad: String? = null,
    val metros_construccion: Double? = null,
    val metros_terreno: Double? = null,
    val habitaciones: Int? = null,
    val banos: Int? = null
)

// Configuración de Retrofit
val retrofit = Retrofit.Builder()
    .baseUrl("http://tu-servidor.com/api/")
    .addConverterFactory(GsonConverterFactory.create())
    .build()

val service = retrofit.create(PropiedadesApiService::class.java)
```

### Usando Volley (Java)

```java
String url = "http://tu-servidor.com/api/comparables/";
JSONObject jsonBody = new JSONObject();
jsonBody.put("lat", -16.398);
jsonBody.put("lng", -71.535);
jsonBody.put("radio", 1000);
jsonBody.put("tipo_propiedad", "Casa");

JsonObjectRequest request = new JsonObjectRequest(
    Request.Method.POST, url, jsonBody,
    response -> {
        // Procesar respuesta
        Log.d("API", "Respuesta: " + response.toString());
    },
    error -> {
        // Manejar error
        Log.e("API", "Error: " + error.toString());
    }
);

RequestQueue queue = Volley.newRequestQueue(context);
queue.add(request);
```

## Consideraciones para Producción

1. **CORS**: Configurar CORS en el servidor Django para permitir solicitudes desde el dominio de la aplicación móvil.
2. **Rate Limiting**: Implementar límites de tasa para prevenir abuso.
3. **Cache**: Considerar cachear respuestas para mejorar el rendimiento.
4. **SSL**: Usar HTTPS en producción.
5. **Versionado**: Los endpoints actuales están en la versión por defecto. Considerar agregar versionado (`/api/v1/`).

## Soporte

Para problemas o preguntas, contactar al equipo de desarrollo.