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
    
    class Meta:
        db_table = 'properties'
        managed = False  # La tabla ya existe en la base de datos
        
    def __str__(self):
        return f"{self.code} - {self.real_address or 'Sin dirección'}"
