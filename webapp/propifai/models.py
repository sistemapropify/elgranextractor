import logging
from decimal import Decimal
from django.db import models, connections
from django.conf import settings

logger = logging.getLogger(__name__)


class PropifaiProperty(models.Model):
    """
    Modelo para propiedades de la base de datos Propifai (dbpropify_be).
    
    NOTA IMPORTANTE: Este modelo refleja SOLO los campos que existen en la tabla `property`
    de dbpropify_be. Los campos de especificaciones (bedrooms, bathrooms, areas, amenities, etc.)
    están en la tabla `property_specs` (relación 1:1).
    
    Para acceder a specs, usar el método `get_specs()` que hace raw SQL JOIN.
    """
    
    # === CAMPOS REALES DE LA TABLA `property` EN dbpropify_be ===
    id = models.BigIntegerField(primary_key=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    
    # Identificadores
    code = models.CharField(max_length=50, null=True, blank=True)
    uuid = models.CharField(max_length=36, null=True, blank=True)
    wp_post_id = models.BigIntegerField(null=True, blank=True)
    wp_slug = models.CharField(max_length=200, null=True, blank=True)
    wp_last_sync = models.DateTimeField(null=True, blank=True)
    
    # Información principal
    title = models.CharField(max_length=500, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    
    # Precios
    price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    maintenance_fee = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Ubicación
    map_address = models.TextField(null=True, blank=True)
    display_address = models.TextField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # Datos registrales
    registry_number = models.CharField(max_length=100, null=True, blank=True)
    
    # Flags
    is_project = models.BooleanField(default=False, null=True, blank=True)
    is_visible = models.BooleanField(default=True, null=True, blank=True)
    project_name = models.CharField(max_length=500, null=True, blank=True)
    video_url = models.TextField(null=True, blank=True)
    
    # Foreign Keys (como BigIntegerField porque son BD externa)
    contact_id = models.BigIntegerField(null=True, blank=True)
    created_by_id = models.BigIntegerField(null=True, blank=True)
    currency_id = models.BigIntegerField(null=True, blank=True, db_column='currency_id')
    district_id = models.BigIntegerField(null=True, blank=True, db_column='district_id')
    operation_type_id = models.BigIntegerField(null=True, blank=True, db_column='operation_type_id')
    payment_method_id = models.BigIntegerField(null=True, blank=True)
    property_condition_id = models.BigIntegerField(null=True, blank=True, db_column='property_condition_id')
    property_status_id = models.BigIntegerField(null=True, blank=True)
    property_subtype_id = models.BigIntegerField(null=True, blank=True)
    property_type_id = models.BigIntegerField(null=True, blank=True, db_column='property_type_id')
    responsible_id = models.BigIntegerField(null=True, blank=True)
    updated_by_id = models.BigIntegerField(null=True, blank=True)
    urbanization_id = models.BigIntegerField(null=True, blank=True)
    parent_project_id = models.BigIntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'property'
        managed = False
    
    def __str__(self):
        return f"{self.code or '?'} - {self.title or 'Sin título'}"
    
    # ============================================================
    # MÉTODOS PARA ACCEDER A property_specs (relación 1:1)
    # ============================================================
    
    def get_specs(self, using='propifai'):
        """
        Obtiene los specs de la propiedad desde la tabla property_specs.
        
        Returns:
            Dict con los campos de property_specs, o None si no existe.
        """
        try:
            with connections['propifai'].cursor() as cursor:
                cursor.execute(f"""
                    SELECT
                        bedrooms, bathrooms, half_bathrooms,
                        has_elevator, land_area, built_area,
                        front_measure, depth_measure, area_unit, linear_unit,
                        garage_spaces, garage_type, parking_cost_included, parking_cost,
                        antiquity_years, delivery_date,
                        has_security, has_pool, has_garden, has_bbq, has_terrace,
                        has_air_conditioning, has_laundry_area, has_service_room, pet_friendly,
                        floors_total, unit_location
                    FROM property_specs
                    WHERE property_id = %s
                """, [self.id])
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
            return None
        except Exception as e:
            logger.error(f"Error al obtener specs para property {self.id}: {e}")
            return None
    
    def get_specs_value(self, field_name, default=None):
        """Obtiene un valor específico de property_specs."""
        specs = self.get_specs()
        if specs:
            return specs.get(field_name, default)
        return default
    
    # ============================================================
    # PROPIEDADES DE CONVENIENCIA (compatibilidad con código existente)
    # ============================================================
    
    @property
    def bedrooms(self):
        return self.get_specs_value('bedrooms')
    
    @property
    def bathrooms(self):
        return self.get_specs_value('bathrooms')
    
    @property
    def half_bathrooms(self):
        return self.get_specs_value('half_bathrooms')
    
    @property
    def has_elevator(self):
        return self.get_specs_value('has_elevator')
    
    @property
    def land_area(self):
        return self.get_specs_value('land_area')
    
    @property
    def built_area(self):
        return self.get_specs_value('built_area')
    
    @property
    def front_measure(self):
        return self.get_specs_value('front_measure')
    
    @property
    def depth_measure(self):
        return self.get_specs_value('depth_measure')
    
    @property
    def garage_spaces(self):
        return self.get_specs_value('garage_spaces')
    
    @property
    def antiquity_years(self):
        return self.get_specs_value('antiquity_years')
    
    @property
    def delivery_date(self):
        return self.get_specs_value('delivery_date')
    
    @property
    def pet_friendly(self):
        return self.get_specs_value('pet_friendly')
    
    @property
    def floors_total(self):
        return self.get_specs_value('floors_total')
    
    @property
    def unit_location(self):
        return self.get_specs_value('unit_location')
    
    @property
    def has_pool(self):
        return self.get_specs_value('has_pool')
    
    @property
    def has_garden(self):
        return self.get_specs_value('has_garden')
    
    @property
    def has_bbq(self):
        return self.get_specs_value('has_bbq')
    
    @property
    def has_terrace(self):
        return self.get_specs_value('has_terrace')
    
    @property
    def has_air_conditioning(self):
        return self.get_specs_value('has_air_conditioning')
    
    @property
    def has_laundry_area(self):
        return self.get_specs_value('has_laundry_area')
    
    @property
    def has_service_room(self):
        return self.get_specs_value('has_service_room')
    
    @property
    def amenities(self):
        """
        Construye un texto de amenities a partir de los booleanos de property_specs.
        """
        specs = self.get_specs()
        if not specs:
            return None
        amenities_list = []
        if specs.get('has_pool'):
            amenities_list.append('piscina')
        if specs.get('has_garden'):
            amenities_list.append('jardín')
        if specs.get('has_bbq'):
            amenities_list.append('bbq')
        if specs.get('has_terrace'):
            amenities_list.append('terraza')
        if specs.get('has_air_conditioning'):
            amenities_list.append('aire acondicionado')
        if specs.get('has_laundry_area'):
            amenities_list.append('lavandería')
        if specs.get('has_service_room'):
            amenities_list.append('cuarto de servicio')
        if specs.get('has_elevator'):
            amenities_list.append('ascensor')
        if specs.get('has_security'):
            amenities_list.append('seguridad')
        if specs.get('pet_friendly'):
            amenities_list.append('mascotas permitidas')
        return ', '.join(amenities_list) if amenities_list else None
    
    @property
    def ascensor(self):
        """Compatibilidad: retorna 'sí' o 'no' basado en has_elevator."""
        val = self.get_specs_value('has_elevator')
        if val is True:
            return 'sí'
        elif val is False:
            return 'no'
        return None
    
    @property
    def coordinates(self):
        """Compatibilidad: construye 'lat,lng' desde latitude, longitude."""
        if self.latitude and self.longitude:
            return f"{self.latitude},{self.longitude}"
        return None
    
    @property
    def real_address(self):
        """Compatibilidad: alias de map_address."""
        return self.map_address
    
    @property
    def district(self):
        """Compatibilidad: retorna district_id como string (como antes)."""
        return str(self.district_id) if self.district_id else None
    
    @property
    def distrito_nombre(self):
        """Obtiene el nombre del distrito desde la tabla district."""
        if not self.district_id:
            return None
        try:
            with connections['propifai'].cursor() as cursor:
                cursor.execute("""
                    SELECT name FROM district WHERE id = %s
                """, [self.district_id])
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception:
            return None
    
    @property
    def tipo_propiedad(self):
        """Obtiene el nombre del tipo de propiedad desde property_type."""
        if not self.property_type_id:
            return "Propiedad"
        try:
            with connections['propifai'].cursor() as cursor:
                cursor.execute("""
                    SELECT name FROM property_type WHERE id = %s
                """, [self.property_type_id])
                row = cursor.fetchone()
                return row[0] if row else "Propiedad"
        except Exception:
            return "Propiedad"
    
    @property
    def precio_formateado(self):
        """Devuelve el precio formateado como string."""
        if self.price:
            return f"S/. {self.price:,.2f}"
        return "No especificado"
    
    @property
    def es_externo(self):
        return True
    
    @property
    def fuente_excel(self):
        return "Propify DB"
    
    @property
    def departamento_nombre(self):
        return "Arequipa"
    
    @property
    def provincia_nombre(self):
        return "Arequipa"
    
    @property
    def ubicacion_completa(self):
        distrito = self.distrito_nombre or f"Distrito {self.district_id}"
        return f"Arequipa, Arequipa, {distrito}"
    
    @property
    def ubicacion_para_tarjeta(self):
        return self.distrito_nombre or f"Distrito {self.district_id}"
    
    @property
    def imagen_url(self):
        """Devuelve URL de imagen desde Azure Storage."""
        if not self.code:
            return None
        base_url = "https://propifymedia01.blob.core.windows.net/media"
        extensions = ['.jpg', '.jpeg', '.png', '.webp']
        if self.code.lower().endswith(tuple(extensions)):
            return f"{base_url}/{self.code}"
        return f"{base_url}/{self.code}.jpg"
    
    @property
    def imagenes_relacionadas(self):
        from .models import PropertyImage
        return PropertyImage.objects.filter(property_id=self.id).order_by('id')
    
    @property
    def primera_imagen_url(self):
        primera_imagen = self.imagenes_relacionadas.first()
        if primera_imagen and primera_imagen.image:
            return self._convertir_a_url_azure(primera_imagen.image)
        return None
    
    def _convertir_a_url_azure(self, ruta_relativa):
        if not ruta_relativa:
            return None
        if ruta_relativa.startswith(('http://', 'https://')):
            return ruta_relativa
        base_url = "https://propifymedia01.blob.core.windows.net/media"
        if ruta_relativa.startswith('/'):
            ruta_relativa = ruta_relativa[1:]
        import urllib.parse
        parts = ruta_relativa.split('/')
        encoded_parts = [urllib.parse.quote(part) for part in parts]
        encoded_path = '/'.join(encoded_parts)
        return f"{base_url}/{encoded_path}"


class PropertyImage(models.Model):
    """
    Modelo para imágenes de propiedades en la base de datos Propifai.
    Tabla: property_images
    """
    id = models.BigIntegerField(primary_key=True)
    property_id = models.BigIntegerField(db_column='property_id')
    image = models.CharField(max_length=500, blank=True, null=True, db_column='image')
    
    class Meta:
        db_table = 'property_images'
        managed = False
        
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
    """
    Modelo para tipos de propiedades.
    NOTA: La tabla real en dbpropify_be se llama 'property_type' (singular).
    """
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    created_by_id = models.BigIntegerField(null=True, blank=True)
    updated_by_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'property_type'  # CORREGIDO: antes era 'property_types' (plural)
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
