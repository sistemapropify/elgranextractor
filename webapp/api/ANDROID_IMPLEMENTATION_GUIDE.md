# Guía de Implementación para Android Studio

Esta guía proporciona todo lo necesario para implementar los endpoints de la API en tu aplicación Android.

## 📋 Contenido
1. [Dependencias Gradle](#dependencias-gradle)
2. [Modelos de Datos (Kotlin)](#modelos-de-datos-kotlin)
3. [Servicio API con Retrofit](#servicio-api-con-retrofit)
4. [ViewModel y Repositorio](#viewmodel-y-repositorio)
5. [Ejemplos de Uso](#ejemplos-de-uso)
6. [Configuración de Red](#configuración-de-red)
7. [Manejo de Errores](#manejo-de-errores)
8. [Ejemplo Completo de Activity](#ejemplo-completo-de-activity)

---

## 1. Dependencias Gradle

Agrega estas dependencias en tu archivo `build.gradle` (Module: app):

```gradle
dependencies {
    // Retrofit para llamadas HTTP
    implementation 'com.squareup.retrofit2:retrofit:2.9.0'
    implementation 'com.squareup.retrofit2:converter-gson:2.9.0'
    
    // Coroutines para operaciones asíncronas
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3'
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3'
    
    // ViewModel y LiveData
    implementation 'androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0'
    implementation 'androidx.lifecycle:lifecycle-livedata-ktx:2.7.0'
    implementation 'androidx.lifecycle:lifecycle-runtime-ktx:2.7.0'
    
    // Interceptor para logging de HTTP
    implementation 'com.squareup.okhttp3:logging-interceptor:4.12.0'
    
    // Glide para cargar imágenes
    implementation 'com.github.bumptech.glide:glide:4.16.0'
}
```

## 2. Modelos de Datos (Kotlin)

Crea estos archivos en `app/src/main/java/com/tuapp/models/`:

### Propiedad.kt
```kotlin
package com.tuapp.models

import com.google.gson.annotations.SerializedName

data class Propiedad(
    @SerializedName("id") val id: Long,
    @SerializedName("tipo") val tipo: String?,
    @SerializedName("precio") val precio: Double?,
    @SerializedName("precio_final") val precioFinal: Double?,
    @SerializedName("metros_construccion") val metrosConstruccion: Double?,
    @SerializedName("metros_terreno") val metrosTerreno: Double?,
    @SerializedName("habitaciones") val habitaciones: Int?,
    @SerializedName("baños") val banos: Int?,
    @SerializedName("estado") val estado: String?,
    @SerializedName("distrito") val distrito: String?,
    @SerializedName("provincia") val provincia: String?,
    @SerializedName("departamento") val departamento: String?,
    @SerializedName("imagen_url") val imagenUrl: String?,
    @SerializedName("precio_m2") val precioM2: Double?,
    @SerializedName("precio_m2_final") val precioM2Final: Double?,
    @SerializedName("distancia_metros") val distanciaMetros: Double?,
    @SerializedName("fuente") val fuente: String?,
    @SerializedName("es_propify") val esPropify: Boolean?,
    @SerializedName("lat") val lat: Double?,
    @SerializedName("lng") val lng: Double?,
    @SerializedName("codigo") val codigo: String?,
    @SerializedName("titulo") val titulo: String?
)

data class PropiedadRaw(
    @SerializedName("id") val id: Long,
    @SerializedName("tipo_propiedad") val tipoPropiedad: String?,
    @SerializedName("condicion") val condicion: String?,
    @SerializedName("precio_usd") val precioUsd: String?,
    @SerializedName("departamento") val departamento: String?,
    @SerializedName("provincia") val provincia: String?,
    @SerializedName("distrito") val distrito: String?,
    @SerializedName("area_terreno") val areaTerreno: String?,
    @SerializedName("area_construida") val areaConstruida: String?,
    @SerializedName("numero_habitaciones") val numeroHabitaciones: Int?,
    @SerializedName("numero_banos") val numeroBanos: Int?,
    @SerializedName("lat") val lat: Double?,
    @SerializedName("lng") val lng: Double?,
    @SerializedName("precio_m2") val precioM2: Double?,
    @SerializedName("imagen_url") val imagenUrl: String?,
    @SerializedName("url_propiedad") val urlPropiedad: String?
)

data class PropifaiProperty(
    @SerializedName("id") val id: Long,
    @SerializedName("code") val code: String?,
    @SerializedName("title") val title: String?,
    @SerializedName("price") val price: Double?,
    @SerializedName("department") val department: String?,
    @SerializedName("province") val province: String?,
    @SerializedName("district") val district: String?,
    @SerializedName("built_area") val builtArea: Double?,
    @SerializedName("land_area") val landArea: Double?,
    @SerializedName("bedrooms") val bedrooms: Int?,
    @SerializedName("bathrooms") val bathrooms: Int?,
    @SerializedName("lat") val lat: Double?,
    @SerializedName("lng") val lng: Double?,
    @SerializedName("precio_m2") val precioM2: Double?,
    @SerializedName("tipo_propiedad") val tipoPropiedad: String?,
    @SerializedName("imagen_url") val imagenUrl: String?
)

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

data class ComparablesResponse(
    val status: String,
    val total: Int,
    val radio_metros: Double,
    val punto_referencia: PuntoReferencia,
    val propiedades: List<Propiedad>
)

data class PuntoReferencia(
    val lat: Double,
    val lng: Double
)

data class PropiedadesResponse(
    val count: Int,
    val next: String?,
    val previous: String?,
    val results: List<PropiedadRaw>
)

data class PropifaiResponse(
    val count: Int,
    val next: String?,
    val previous: String?,
    val results: List<PropifaiProperty>
)
```

## 3. Servicio API con Retrofit

Crea `app/src/main/java/com/tuapp/api/ApiService.kt`:

```kotlin
package com.tuapp.api

import com.tuapp.models.*
import retrofit2.Response
import retrofit2.http.*

interface ApiService {
    
    // Obtener propiedades raw
    @GET("propiedades-raw/")
    suspend fun getPropiedadesRaw(
        @Query("tipo_propiedad") tipoPropiedad: String? = null,
        @Query("condicion") condicion: String? = null,
        @Query("departamento") departamento: String? = null,
        @Query("precio_min") precioMin: Double? = null,
        @Query("precio_max") precioMax: Double? = null,
        @Query("page") page: Int = 1
    ): Response<PropiedadesResponse>
    
    // Obtener propiedades Propifai
    @GET("propiedades-propifai/")
    suspend fun getPropiedadesPropifai(
        @Query("tipo_propiedad") tipoPropiedad: String? = null,
        @Query("departamento") departamento: String? = null,
        @Query("precio_min") precioMin: Double? = null,
        @Query("precio_max") precioMax: Double? = null,
        @Query("page") page: Int = 1
    ): Response<PropifaiResponse>
    
    // Buscar comparables
    @POST("comparables/")
    suspend fun buscarComparables(@Body request: ComparablesRequest): Response<ComparablesResponse>
}
```

Crea `app/src/main/java/com/tuapp/api/RetrofitClient.kt`:

```kotlin
package com.tuapp.api

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {
    
    // Cambia esta URL según tu entorno
    private const val BASE_URL = "http://10.0.2.2:8000/api/" // Para emulador Android
    // private const val BASE_URL = "http://192.168.1.X:8000/api/" // Para dispositivo físico
    // private const val BASE_URL = "https://tu-servidor.com/api/" // Para producción
    
    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }
    
    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(loggingInterceptor)
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()
    
    private val retrofit: Retrofit by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }
    
    val apiService: ApiService by lazy {
        retrofit.create(ApiService::class.java)
    }
}
```

## 4. ViewModel y Repositorio

Crea `app/src/main/java/com/tuapp/repository/PropiedadesRepository.kt`:

```kotlin
package com.tuapp.repository

import com.tuapp.api.RetrofitClient
import com.tuapp.models.*
import retrofit2.Response

class PropiedadesRepository {
    
    suspend fun getPropiedadesRaw(
        tipoPropiedad: String? = null,
        condicion: String? = null,
        departamento: String? = null,
        precioMin: Double? = null,
        precioMax: Double? = null,
        page: Int = 1
    ): Response<PropiedadesResponse> {
        return RetrofitClient.apiService.getPropiedadesRaw(
            tipoPropiedad, condicion, departamento, precioMin, precioMax, page
        )
    }
    
    suspend fun getPropiedadesPropifai(
        tipoPropiedad: String? = null,
        departamento: String? = null,
        precioMin: Double? = null,
        precioMax: Double? = null,
        page: Int = 1
    ): Response<PropifaiResponse> {
        return RetrofitClient.apiService.getPropiedadesPropifai(
            tipoPropiedad, departamento, precioMin, precioMax, page
        )
    }
    
    suspend fun buscarComparables(
        lat: Double,
        lng: Double,
        radio: Double = 500.0,
        tipoPropiedad: String? = null,
        metrosConstruccion: Double? = null,
        metrosTerreno: Double? = null,
        habitaciones: Int? = null,
        banos: Int? = null
    ): Response<ComparablesResponse> {
        val request = ComparablesRequest(
            lat = lat,
            lng = lng,
            radio = radio,
            tipo_propiedad = tipoPropiedad,
            metros_construccion = metrosConstruccion,
            metros_terreno = metrosTerreno,
            habitaciones = habitaciones,
            banos = banos
        )
        return RetrofitClient.apiService.buscarComparables(request)
    }
}
```

Crea `app/src/main/java/com/tuapp/viewmodel/PropiedadesViewModel.kt`:

```kotlin
package com.tuapp.viewmodel

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.tuapp.models.*
import com.tuapp.repository.PropiedadesRepository
import kotlinx.coroutines.launch

class PropiedadesViewModel : ViewModel() {
    
    private val repository = PropiedadesRepository()
    
    private val _propiedadesRaw = MutableLiveData<List<PropiedadRaw>>()
    val propiedadesRaw: LiveData<List<PropiedadRaw>> = _propiedadesRaw
    
    private val _propiedadesPropifai = MutableLiveData<List<PropifaiProperty>>()
    val propiedadesPropifai: LiveData<List<PropifaiProperty>> = _propiedadesPropifai
    
    private val _comparables = MutableLiveData<List<Propiedad>>()
    val comparables: LiveData<List<Propiedad>> = _comparables
    
    private val _loading = MutableLiveData<Boolean>()
    val loading: LiveData<Boolean> = _loading
    
    private val _error = MutableLiveData<String>()
    val error: LiveData<String> = _error
    
    fun loadPropiedadesRaw(
        tipoPropiedad: String? = null,
        condicion: String? = null,
        departamento: String? = null
    ) {
        viewModelScope.launch {
            _loading.value = true
            try {
                val response = repository.getPropiedadesRaw(
                    tipoPropiedad, condicion, departamento
                )
                if (response.isSuccessful) {
                    _propiedadesRaw.value = response.body()?.results ?: emptyList()
                } else {
                    _error.value = "Error: ${response.code()} - ${response.message()}"
                }
            } catch (e: Exception) {
                _error.value = "Error de conexión: ${e.message}"
            } finally {
                _loading.value = false
            }
        }
    }
    
    fun buscarComparables(
        lat: Double,
        lng: Double,
        radio: Double = 500.0,
        tipoPropiedad: String? = null
    ) {
        viewModelScope.launch {
            _loading.value = true
            try {
                val response = repository.buscarComparables(
                    lat, lng, radio, tipoPropiedad
                )
                if (response.isSuccessful) {
                    _comparables.value = response.body()?.propiedades ?: emptyList()
                } else {
                    _error.value = "Error: ${response.code()} - ${response.message()}"
                }
            } catch (e: Exception) {
                _error.value = "Error de conexión: ${e.message}"
            } finally {
                _loading.value = false
            }
        }
    }
}
```

## 5. Ejemplos de Uso

### Ejemplo 1: Obtener propiedades raw

```kotlin
// En tu Activity o Fragment
val viewModel: PropiedadesViewModel by viewModels()

// Observar los datos
viewModel.propiedadesRaw.observe(this) { propiedades ->
    // Actualizar RecyclerView con las propiedades
    propiedadesAdapter.submitList(propiedades)
}

viewModel.loading.observe(this) { isLoading ->
    // Mostrar/ocultar ProgressBar
    progressBar.isVisible = isLoading
}

viewModel.error.observe(this) { errorMessage ->
    // Mostrar error al usuario
    Toast.makeText(this, errorMessage, Toast.LENGTH_SHORT).show()
}

// Cargar propiedades
viewModel.loadPropiedadesRaw(
    tipoPropiedad = "Casa",
    condicion = "venta",
    departamento = "Arequipa"
)
```

### Ejemplo 2: Buscar comparables

```kotlin
// Coordenadas de ejemplo (Arequipa centro)
val lat = -16.398
val lng = -71.535

viewModel.buscarComparables(
    lat = lat,
    lng = lng,
    radio = 1000.0, // 1 km
    tipoPropiedad = "Casa"
)

// Observar resultados
viewModel.comparables.observe(this) { propiedades ->
    propiedades.forEach { propiedad ->
        Log.d("Comparables", 
            "Propiedad: ${propiedad.tipo} - Precio: ${propiedad.precio} - Distancia: ${propiedad.distanciaMetros}m")
    }
}
```

### Ejemplo 3: Llamada directa con Retrofit

```kotlin
// En un CoroutineScope
lifecycleScope.launch {
    try {
        val response = RetrofitClient.apiService.buscarComparables(
            ComparablesRequest(
                lat = -16.398,
                lng = -71.535,
                radio = 500.0,
                tipo_propiedad = "Departamento"
            )
        )
        
        if (response.isSuccessful) {
            val comparablesResponse = response.body()
            val propiedades = comparablesResponse?.propiedades ?: emptyList()
            
            // Procesar propiedades
            propiedades.forEach { propiedad ->
                // Acceder a los campos
                val precio = propiedad.precio
                val distancia = propiedad.distanciaMetros
                val imagenUrl = propiedad.imagenUrl
            }
        }
    } catch (e: Exception) {
        // Manejar error
    }
}
```

## 6. Configuración de Red

### Permisos en AndroidManifest.xml

Agrega estos permisos en `app/src/main/AndroidManifest.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">
    
    <!-- Permiso para acceso a internet -->
    <uses-permission android:name="android.permission.INTERNET" />
    
    <!-- Permiso para acceso a red (opcional) -->
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    
    <!-- Si necesitas ubicación para obtener coordenadas -->
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
    
    <application
        android:usesCleartextTraffic="true" <!-- Para HTTP en desarrollo -->
        tools:targetApi="31">
        
        <!-- Tu actividad principal -->
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        
    </application>
</manifest>
```

**Nota:** `android:usesCleartextTraffic="true"` es necesario para conexiones HTTP en desarrollo. En producción usa HTTPS.

## 7. Manejo de Errores

Crea una clase para manejar errores de API:

```kotlin
package com.tuapp.utils

import android.content.Context
import com.tuapp.R
import retrofit2.HttpException
import java.io.IOException
import java.net.SocketTimeoutException

object ErrorHandler {
    
    fun handleException(context: Context, exception: Exception): String {
        return when (exception) {
            is SocketTimeoutException -> context.getString(R.string.error_timeout)
            is IOException -> context.getString(R.string.error_network)
            is HttpException -> {
                when (exception.code()) {
                    400 -> context.getString(R.string.error_bad_request)
                    401 -> context.getString(R.string.error_unauthorized)
                    403 -> context.getString(R.string.error_forbidden)
                    404 -> context.getString(R.string.error_not_found)
                    500 -> context.getString(R.string.error_server)
                    else -> context.getString(R.string.error_unknown)
                }
            }
            else -> context.getString(R.string.error_unknown)
        }
    }
}
```

Agrega estos strings en `app/src/main/res/values/strings.xml`:

```xml
<resources>
    <string name="error_timeout">Tiempo de espera agotado. Intenta nuevamente.</string>
    <string name="error_network">Error de conexión. Verifica tu internet.</string>
    <string name="error_bad_request">Solicitud incorrecta.</string>
    <string name="error_unauthorized">No autorizado.</string>
    <string name="error_forbidden">Acceso prohibido.</string>
    <string name="error_not_found">Recurso no encontrado.</string>
    <string name="error_server">Error del servidor.</string>
    <string name="error_unknown">Error desconocido.</string>
</resources>
```

## 8. Ejemplo Completo de Activity

Crea `app/src/main/java/com/tuapp/ui/MainActivity.kt`:

```kotlin
package com.tuapp.ui

import android.os.Bundle
import android.widget.Toast
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.tuapp.adapters.PropiedadesAdapter
import com.tuapp.databinding.ActivityMainBinding
import com.tuapp.viewmodel.PropiedadesViewModel

class MainActivity : AppCompatActivity() {
    
    private lateinit var binding: ActivityMainBinding
    private val viewModel: PropiedadesViewModel by viewModels()
    private lateinit var propiedadesAdapter: PropiedadesAdapter
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        
        setupRecyclerView()
        setupObservers()
        setupListeners()
        
        // Cargar propiedades al iniciar
        viewModel.loadPropiedadesRaw()
    }
    
    private fun setupRecyclerView() {
        propiedadesAdapter = PropiedadesAdapter { propiedad ->
            // Manejar clic en propiedad
            showPropertyDetails(propiedad)
        }
        
        binding.recyclerView.apply {
            layoutManager = LinearLayoutManager(this@MainActivity)
            adapter = propiedadesAdapter
            setHasFixedSize(true)
        }
    }
    
    private fun setupObservers() {
        viewModel.propiedadesRaw.observe(this) { propiedades ->
            propiedadesAdapter.submitList(propiedades)
        }
        
        viewModel.loading.observe(this) { isLoading ->
            binding.progressBar.isVisible = isLoading
            binding.recyclerView.isVisible = !isLoading
        }
        
        viewModel.error.observe(this) { errorMessage ->
            if (errorMessage.isNotEmpty()) {
                Toast.makeText(this, errorMessage, Toast.LENGTH_LONG).show()
            }
        }
    }
    
    private fun setupListeners() {
        binding.btnBuscarComparables.setOnClickListener {
            buscarComparables()
        }
        
        binding.btnFiltrar.setOnClickListener {
            filtrarPropiedades()
        }
    }
    
    private fun buscarComparables() {
        // Coordenadas de ejemplo (puedes obtenerlas del GPS)
        val lat = -16.398
        val lng = -71.535
        
        viewModel.buscarComparables(
            lat = lat,
            lng = lng,
            radio = 1000.0,
            tipoPropiedad = "Casa"
        )
    }
    
    private fun filtrarPropiedades() {
        val tipo = binding.editTipo.text.toString().trim()
        val departamento = binding.editDepartamento.text.toString().trim()
        
        viewModel.loadPropiedadesRaw(
            tipoPropiedad = if (tipo.isNotEmpty()) tipo else null,
            departamento = if (departamento.isNotEmpty()) departamento else null
        )
    }
    
    private fun showPropertyDetails(propiedad: PropiedadRaw) {
        // Navegar a pantalla de detalles
        val intent = Intent(this, PropertyDetailActivity::class.java).apply {
            putExtra("PROPIEDAD_ID", propiedad.id)
        }
        startActivity(intent)
    }
}
```

## 9. Adapter para RecyclerView

Crea `app/src/main/java/com/tuapp/adapters/PropiedadesAdapter.kt`:

```kotlin
package com.tuapp.adapters

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.bumptech.glide.Glide
import com.tuapp.databinding.ItemPropiedadBinding
import com.tuapp.models.PropiedadRaw

class PropiedadesAdapter(
    private val onItemClick: (PropiedadRaw) -> Unit
) : ListAdapter<PropiedadRaw, PropiedadesAdapter.PropiedadViewHolder>(DiffCallback()) {
    
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): PropiedadViewHolder {
        val binding = ItemPropiedadBinding.inflate(
            LayoutInflater.from(parent.context), parent, false
        )
        return PropiedadViewHolder(binding)
    }
    
    override fun onBindViewHolder(holder: PropiedadViewHolder, position: Int) {
        val propiedad = getItem(position)
        holder.bind(propiedad)
    }
    
    inner class PropiedadViewHolder(
        private val binding: ItemPropiedadBinding
    ) : RecyclerView.ViewHolder(binding.root) {
        
        fun bind(propiedad: PropiedadRaw) {
            binding.apply {
                textTipo.text = propiedad.tipoPropiedad ?: "Sin tipo"
                textPrecio.text = "USD ${propiedad.precioUsd ?: "0"}"
                textUbicacion.text = "${propiedad.distrito ?: ""}, ${propiedad.provincia ?: ""}"
                textHabitaciones.text = "${propiedad.numeroHabitaciones ?: 0} hab."
                textBanos.text = "${propiedad.numeroBanos ?: 0} baños"
                
                // Cargar imagen con Glide
                propiedad.imagenUrl?.let { url ->
                    Glide.with(root.context)
                        .load(url)
                        .placeholder(R.drawable.placeholder_property)
                        .into(imagePropiedad)
                }
                
                root.setOnClickListener {
                    onItemClick(propiedad)
                }
            }
        }
    }
    
    class DiffCallback : DiffUtil.ItemCallback<PropiedadRaw>() {
        override fun areItemsTheSame(oldItem: PropiedadRaw, newItem: PropiedadRaw): Boolean {
            return oldItem.id == newItem.id
        }
        
        override fun areContentsTheSame(oldItem: PropiedadRaw, newItem: PropiedadRaw): Boolean {
            return oldItem == newItem
        }
    }
}
```

## 10. Layouts XML

### activity_main.xml
```xml
<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    xmlns:tools="http://schemas.android.com/tools"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    tools:context=".ui.MainActivity">
    
    <com.google.android.material.appbar.MaterialToolbar
        android:id="@+id/toolbar"
        android:layout_width="match_parent"
        android:layout_height="?attr/actionBarSize"
        app:layout_constraintTop_toTopOf="parent"
        app:title="Propiedades" />
    
    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="horizontal"
        android:padding="8dp"
        app:layout_constraintTop_toBottomOf="@id/toolbar">
        
        <EditText
            android:id="@+id/editTipo"
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:hint="Tipo (Casa, Depto...)"
            android:inputType="text" />
        
        <EditText
            android:id="@+id/editDepartamento"
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:hint="Departamento"
            android:inputType="text" />
        
        <Button
            android:id="@+id/btnFiltrar"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:text="Filtrar" />
    </LinearLayout>
    
    <Button
        android:id="@+id/btnBuscarComparables"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="Buscar Comparables"
        android:layout_margin="8dp"
        app:layout_constraintTop_toBottomOf="@+id/editTipo" />
    
    <androidx.recyclerview.widget.RecyclerView
        android:id="@+id/recyclerView"
        android:layout_width="match_parent"
        android:layout_height="0dp"
        app:layout_constraintTop_toBottomOf="@id/btnBuscarComparables"
        app:layout_constraintBottom_toBottomOf="parent"
        tools:listitem="@layout/item_propiedad" />
    
    <ProgressBar
        android:id="@+id/progressBar"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_gravity="center"
        app:layout_constraintBottom_toBottomOf="parent"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintTop_toTopOf="parent" />
    
</androidx.constraintlayout.widget.ConstraintLayout>
```

### item_propiedad.xml
```xml
<?xml version="1.0" encoding="utf-8"?>
<androidx.cardview.widget.CardView
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:layout_margin="8dp"
    app:cardCornerRadius="8dp"
    app:cardElevation="4dp">
    
    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="horizontal"
        android:padding="12dp">
        
        <ImageView
            android:id="@+id/imagePropiedad"
            android:layout_width="100dp"
            android:layout_height="100dp"
            android:scaleType="centerCrop"
            android:src="@drawable/placeholder_property" />
        
        <LinearLayout
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:orientation="vertical"
            android:paddingStart="12dp">
            
            <TextView
                android:id="@+id/textTipo"
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:text="Casa"
                android:textSize="18sp"
                android:textStyle="bold" />
            
            <TextView
                android:id="@+id/textPrecio"
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:text="USD 250,000"
                android:textSize="16sp"
                android:textColor="@color/primary" />
            
            <TextView
                android:id="@+id/textUbicacion"
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:text="Miraflores, Lima"
                android:textSize="14sp"
                android:textColor="@color/secondary" />
            
            <LinearLayout
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:orientation="horizontal"
                android:layout_marginTop="8dp">
                
                <TextView
                    android:id="@+id/textHabitaciones"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:text="3 hab."
                    android:textSize="14sp" />
                
                <TextView
                    android:id="@+id/textBanos"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:text="2 baños"
                    android:textSize="14sp"
                    android:layout_marginStart="12dp" />
            </LinearLayout>
        </LinearLayout>
    </LinearLayout>
</androidx.cardview.widget.CardView>
```

## 11. Configuración Final

### build.gradle (Module: app)
Asegúrate de tener estas configuraciones:

```gradle
android {
    compileSdk 34
    
    defaultConfig {
        applicationId "com.tuapp"
        minSdk 24
        targetSdk 34
        versionCode 1
        versionName "1.0"
        
        // Habilitar viewBinding
        buildFeatures {
            viewBinding true
        }
    }
    
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }
    
    kotlinOptions {
        jvmTarget = '1.8'
    }
}
```

## 12. Pruebas Rápidas

### Para probar con emulador:
1. Ejecuta el servidor Django en tu computadora
2. Usa la URL: `http://10.0.2.2:8000/api/` en `RetrofitClient`
3. Asegúrate de que el servidor esté corriendo en el puerto 8000

### Para probar con dispositivo físico:
1. Conéctate a la misma red WiFi
2. Usa la IP de tu computadora: `http://192.168.1.X:8000/api/`
3. Deshabilita el firewall temporalmente si es necesario

## 13. Solución de Problemas Comunes

### Error: "Cleartext HTTP traffic not permitted"
Solución: Agrega `android:usesCleartextTraffic="true"` en el `AndroidManifest.xml` o configura Network Security Config.

### Error: "Connection refused"
Solución: Verifica que el servidor esté corriendo y que la IP/URL sea correcta.

### Error: "Timeout"
Solución: Aumenta los timeouts en `RetrofitClient` o verifica la conexión de red.

## 14. Recursos Adicionales

- [Documentación oficial de Retrofit](https://square.github.io/retrofit/)
- [Guía de Coroutines en Android](https://developer.android.com/kotlin/coroutines)
- [MVVM Architecture Guide](https://developer.android.com/jetpack/guide)

---

## 📞 Soporte

Si encuentras problemas con la implementación:

1. Verifica que los endpoints de la API estén funcionando en el navegador
2. Revisa los logs de Retrofit en Logcat
3. Asegúrate de tener los permisos de internet en el manifest
4. Verifica que estés usando la URL correcta para tu entorno

¡Tu aplicación Android ahora está lista para consumir la API de propiedades y buscar comparables!