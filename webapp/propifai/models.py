from django.db import models
from .mapeo_ubicaciones import (
    obtener_nombre_departamento,
    obtener_nombre_provincia,
    obtener_nombre_distrito,
    formatear_ubicacion
)


class PropifaiProperty(models.Model):
    """Modelo para propiedades de la base de datos Propifai."""
    
    # Campos principales
    id = models.BigIntegerField(primary_key=True)
    code = models.CharField(max_length=20)
    codigo_unico_propiedad = models.CharField(max_length=11, blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    # Características de la propiedad
    antiquity_years = models.IntegerField(blank=True, null=True)
    delivery_date = models.DateField(blank=True, null=True)
    price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    maintenance_fee = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    has_maintenance = models.BooleanField(default=False)
    
    # Dimensiones y espacios
    floors = models.IntegerField(blank=True, null=True)
    bedrooms = models.IntegerField(blank=True, null=True)
    bathrooms = models.IntegerField(blank=True, null=True)
    half_bathrooms = models.IntegerField(blank=True, null=True)
    garage_spaces = models.IntegerField(blank=True, null=True)
    
    # Áreas
    land_area = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    built_area = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    front_measure = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    depth_measure = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    
    # Ubicación
    real_address = models.TextField(blank=True, null=True)
    exact_address = models.CharField(max_length=512, blank=True, null=True)
    coordinates = models.CharField(max_length=512, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    province = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    urbanization = models.CharField(max_length=100, blank=True, null=True)
    
    # Amenidades y zonificación
    amenities = models.TextField(blank=True, null=True)
    zoning = models.CharField(max_length=100, blank=True, null=True)
    
    # Fechas
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    
    # Estados
    is_active = models.BooleanField(default=False)
    is_ready_for_sale = models.BooleanField(default=False)
    is_draft = models.BooleanField(default=False)
    is_project = models.BooleanField(default=False)
    
    # Información adicional
    project_name = models.CharField(max_length=200, blank=True, null=True)
    ascensor = models.CharField(max_length=3, blank=True, null=True)
    availability_status = models.CharField(max_length=20)
    unit_location = models.CharField(max_length=20, blank=True, null=True)
    
    # Campos para parseo de coordenadas
    @property
    def latitude(self):
        """Extrae la latitud de la columna coordinates."""
        if self.coordinates:
            try:
                parts = self.coordinates.split(',')
                if len(parts) >= 2:
                    return float(parts[0].strip())
            except (ValueError, AttributeError):
                pass
        return None
    
    @property
    def longitude(self):
        """Extrae la longitud de la columna coordinates."""
        if self.coordinates:
            try:
                parts = self.coordinates.split(',')
                if len(parts) >= 2:
                    return float(parts[1].strip())
            except (ValueError, AttributeError):
                pass
        return None
    
    @property
    def precio_formateado(self):
        """Devuelve el precio formateado como string."""
        if self.price:
            return f"S/. {self.price:,.2f}"
        return "No especificado"
    
    @property
    def tipo_propiedad(self):
        """Devuelve el tipo de propiedad basado en campos relacionados."""
        # En una implementación real, se obtendría de property_type_id
        return "Propiedad"
    
    @property
    def es_externo(self):
        """Indica si es una propiedad externa (para compatibilidad con template)."""
        return True
    
    @property
    def fuente_excel(self):
        """Fuente para compatibilidad con template."""
        return "Propify DB"
    
    @property
    def departamento_nombre(self):
        """Devuelve el nombre del departamento en lugar del índice."""
        return obtener_nombre_departamento(self.department)
    
    @property
    def provincia_nombre(self):
        """Devuelve el nombre de la provincia en lugar del índice."""
        return obtener_nombre_provincia(self.province)
    
    @property
    def distrito_nombre(self):
        """Devuelve el nombre del distrito en lugar del índice."""
        return obtener_nombre_distrito(self.district)
    
    @property
    def ubicacion_completa(self):
        """Devuelve la ubicación completa formateada con nombres."""
        return formatear_ubicacion(
            self.department,
            self.province,
            self.district,
            separador=", "
        )
    
    @property
    def ubicacion_para_tarjeta(self):
        """Devuelve la ubicación formateada para mostrar en tarjetas."""
        # Prioridad: distrito, provincia, departamento
        partes = []
        if self.distrito_nombre and self.distrito_nombre != str(self.district):
            partes.append(self.distrito_nombre)
        if self.provincia_nombre and self.provincia_nombre != str(self.province):
            partes.append(self.provincia_nombre)
        if self.departamento_nombre and self.departamento_nombre != str(self.department):
            partes.append(self.departamento_nombre)
        
        if partes:
            return ", ".join(partes)
        
        # Si no hay nombres mapeados, mostrar los índices
        return f"Distrito {self.district}, Provincia {self.province}, Departamento {self.department}"
    
    @property
    def imagen_url(self):
        """
        Devuelve la URL de la imagen de la propiedad desde Azure Storage.
        Las imágenes se almacenan en: https://propifymedia01.blob.core.windows.net/media/{code}.jpg
        """
        if not self.code:
            return None
        
        # Formato de URL base proporcionado por el usuario
        base_url = "https://propifymedia01.blob.core.windows.net/media"
        
        # Intentar con diferentes extensiones comunes
        extensions = ['.jpg', '.jpeg', '.png', '.webp']
        
        # Primero intentar con el código exacto
        for ext in extensions:
            # Si el código ya tiene extensión, usarlo directamente
            if self.code.lower().endswith(tuple(extensions)):
                return f"{base_url}/{self.code}"
        
        # Si no tiene extensión, probar con extensiones
        for ext in extensions:
            potential_url = f"{base_url}/{self.code}{ext}"
            # Nota: En una implementación real, podríamos verificar si el blob existe
            # pero para el template basta con devolver la URL
            return potential_url
        
        # Si no hay código válido, devolver None
        return None
    
    @property
    def imagenes_relacionadas(self):
        """
        Devuelve las imágenes relacionadas con esta propiedad.
        """
        # Importar aquí para evitar import circular
        from .models import PropertyImage
        return PropertyImage.objects.filter(property_id=self.id).order_by('id')
    
    @property
    def primera_imagen_url(self):
        """
        Devuelve la URL de la primera imagen asociada a esta propiedad.
        Usa la tabla property_images relacionada.
        """
        # Obtener la primera imagen relacionada
        primera_imagen = self.imagenes_relacionadas.first()
        if primera_imagen and primera_imagen.image:
            # Convertir ruta relativa a URL completa de Azure Storage
            return self._convertir_a_url_azure(primera_imagen.image)
        return None
    
    def _convertir_a_url_azure(self, ruta_relativa):
        """
        Convierte una ruta relativa de imagen a URL completa de Azure Storage.
        Ejemplo: 'properties/images/archivo.jpg' ->
                 'https://propifymedia01.blob.core.windows.net/media/properties/images/archivo.jpg'
        """
        if not ruta_relativa:
            return None
        
        # Si ya es una URL completa, devolverla tal cual
        if ruta_relativa.startswith(('http://', 'https://')):
            return ruta_relativa
        
        # Base URL de Azure Storage proporcionada por el usuario
        base_url = "https://propifymedia01.blob.core.windows.net/media"
        
        # Asegurar que la ruta no comience con /
        if ruta_relativa.startswith('/'):
            ruta_relativa = ruta_relativa[1:]
        
        # Codificar cada segmento de la ruta para manejar caracteres especiales
        import urllib.parse
        parts = ruta_relativa.split('/')
        encoded_parts = [urllib.parse.quote(part) for part in parts]
        encoded_path = '/'.join(encoded_parts)
        
        # Construir URL completa
        return f"{base_url}/{encoded_path}"
    
    # Sobrescribir la propiedad imagen_url para usar la primera imagen real
    @property
    def imagen_url(self):
        """
        Devuelve la URL de la imagen de la propiedad.
        Prioridad: 1) Imagen de property_images, 2) URL generada desde código.
        """
        # Primero intentar con la imagen real de la tabla property_images
        url_real = self.primera_imagen_url
        if url_real:
            return url_real
        
        # Si no hay imagen real, usar la URL generada desde el código
        return self._imagen_url_generada()
    
    def _imagen_url_generada(self):
        """Método privado para generar URL desde código (lógica anterior)."""
        if not self.code:
            return None
        
        base_url = "https://propifymedia01.blob.core.windows.net/media"
        extensions = ['.jpg', '.jpeg', '.png', '.webp']
        
        # Primero intentar con el código exacto
        for ext in extensions:
            if self.code.lower().endswith(tuple(extensions)):
                return f"{base_url}/{self.code}"
        
        # Si no tiene extensión, probar con extensiones
        for ext in extensions:
            potential_url = f"{base_url}/{self.code}{ext}"
            return potential_url
        
        return None
    
    class Meta:
        db_table = 'properties'
        managed = False  # La tabla ya existe en la base de datos
        
    def __str__(self):
        return f"{self.code} - {self.real_address or 'Sin dirección'}"


class PropertyImage(models.Model):
    """
    Modelo para imágenes de propiedades en la base de datos Propifai.
    Tabla: property_images
    """
    # Campos principales - basados en la información del usuario
    id = models.BigIntegerField(primary_key=True)
    property_id = models.BigIntegerField(db_column='property_id')  # Columna para relación con properties
    image = models.CharField(max_length=500, blank=True, null=True, db_column='image')  # URL de la imagen
    
    # Otros campos comunes (ajustar si existen)
    # order = models.IntegerField(default=0, blank=True, null=True, db_column='order')
    # created_at = models.DateTimeField(blank=True, null=True, db_column='created_at')
    # updated_at = models.DateTimeField(blank=True, null=True, db_column='updated_at')
    
    class Meta:
        db_table = 'property_images'
        managed = False  # La tabla ya existe en la base de datos
        
    def __str__(self):
        return f"Imagen {self.id} para propiedad {self.property_id}"


class Event(models.Model):
    """Modelo para eventos de propiedades en la base de datos Propifai."""
    id = models.BigIntegerField(primary_key=True)
    code = models.CharField(max_length=20)
    titulo = models.CharField(max_length=200)
    fecha_evento = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    detalle = models.TextField()
    interesado = models.CharField(max_length=200)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    is_active = models.BooleanField()
    created_by = models.ForeignKey('User', on_delete=models.CASCADE, related_name='eventos_creados', db_column='created_by_id')
    property = models.ForeignKey('PropifaiProperty', on_delete=models.CASCADE, null=True, db_column='property_id')
    event_type = models.ForeignKey('EventType', on_delete=models.CASCADE, db_column='event_type_id')
    contact_id = models.BigIntegerField(null=True)
    assigned_agent = models.ForeignKey('User', on_delete=models.CASCADE, null=True, related_name='eventos_asignados', db_column='assigned_agent_id')
    seguimiento = models.TextField()
    lead_id = models.BigIntegerField(null=True)
    proposal_id = models.BigIntegerField(null=True)
    status = models.CharField(max_length=20)
    rejection_reason = models.TextField()

    class Meta:
        db_table = 'events'
        managed = False

    def __str__(self):
        return f"{self.code} - {self.titulo}"


class EventType(models.Model):
    """Modelo para tipos de eventos."""
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7)
    is_active = models.BooleanField()
    created_at = models.DateTimeField()

    class Meta:
        db_table = 'event_types'
        managed = False

    def __str__(self):
        return self.name


class PropertyStatus(models.Model):
    """Modelo para estados de propiedades."""
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    description = models.TextField()
    order = models.IntegerField()
    is_active = models.BooleanField()

    class Meta:
        db_table = 'property_statuses'
        managed = False

    def __str__(self):
        return self.name


class PropertyType(models.Model):
    """Modelo para tipos de propiedades."""
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    is_active = models.BooleanField()

    class Meta:
        db_table = 'property_types'
        managed = False

    def __str__(self):
        return self.name


class User(models.Model):
    """Modelo para usuarios (agentes) de la base de datos Propifai."""
    id = models.BigIntegerField(primary_key=True)
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(null=True)
    is_superuser = models.BooleanField()
    username = models.CharField(max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.BooleanField()
    is_active = models.BooleanField()
    date_joined = models.DateTimeField()
    phone = models.CharField(max_length=20)
    is_verified = models.BooleanField()
    commission_rate = models.DecimalField(max_digits=10, decimal_places=2)
    is_active_agent = models.BooleanField()
    area_id = models.BigIntegerField(null=True)
    role_id = models.BigIntegerField(null=True)

    class Meta:
        db_table = 'users'
        managed = False

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def nombre_completo(self):
        return f"{self.first_name} {self.last_name}"
