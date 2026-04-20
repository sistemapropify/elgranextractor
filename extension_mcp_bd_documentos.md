# Extensión: Procesamiento de Documentos desde Bases de Datos

## Contexto y Necesidad

En Propifai, existe una tabla con documentos de cada propiedad:
- Contratos de corretaje
- Autovaluos
- DNI de propietarios
- Títulos de propiedad
- Recibos de servicios
- Otros documentos

El MCP debe poder **leer y analizar estos documentos directamente desde la base de datos** para:
1. Verificar que estén correctamente elaborados
2. Detectar errores de tipeo y formato
3. Validar consistencia de datos
4. Comparar con información de mercado (ACM)
5. Generar reportes de calidad

## Arquitectura para Acceso a BD

### Conector Genérico de Bases de Datos

```python
# mcp_client/db_connectors.py
from sqlalchemy import create_engine, text
import tempfile
import os

class DatabaseConnector:
    """Conector genérico para diferentes bases de datos"""
    
    SUPPORTED_DB_TYPES = ['mssql', 'postgresql', 'mysql', 'sqlite']
    
    def __init__(self, db_type='mssql', connection_string=None, app_id='propify'):
        self.db_type = db_type
        self.connection_string = connection_string
        self.app_id = app_id
        self.engine = self._create_engine()
    
    def _create_engine(self):
        """Crea engine SQLAlchemy según tipo de BD"""
        if self.db_type == 'mssql':
            # Azure SQL / SQL Server
            return create_engine(
                self.connection_string,
                connect_args={'timeout': 30}
            )
        elif self.db_type == 'postgresql':
            return create_engine(self.connection_string)
        elif self.db_type == 'mysql':
            return create_engine(self.connection_string)
        elif self.db_type == 'sqlite':
            return create_engine(self.connection_string)
        else:
            raise ValueError(f"Tipo de BD no soportado: {self.db_type}")
    
    def get_document_blob(self, table_name, document_id, blob_column='document_content'):
        """Obtiene documento BLOB desde una tabla"""
        query = f"SELECT {blob_column} FROM {table_name} WHERE id = :doc_id"
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), {'doc_id': document_id})
                row = result.fetchone()
                
                if row and row[0]:
                    return row[0]  # Retorna el BLOB
                else:
                    return None
                    
        except Exception as e:
            raise Exception(f"Error obteniendo documento: {str(e)}")
    
    def get_documents_by_property(self, property_id, document_types=None):
        """Obtiene todos los documentos de una propiedad"""
        query = """
        SELECT id, document_type, document_name, document_content, 
               file_path, created_at, uploaded_by
        FROM property_documents 
        WHERE property_id = :prop_id
        """
        
        params = {'prop_id': property_id}
        
        if document_types:
            query += " AND document_type IN :doc_types"
            params['doc_types'] = tuple(document_types)
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params)
                return [
                    {
                        'id': row[0],
                        'document_type': row[1],
                        'document_name': row[2],
                        'document_content': row[3],
                        'file_path': row[4],
                        'created_at': row[5],
                        'uploaded_by': row[6]
                    }
                    for row in result.fetchall()
                ]
                
        except Exception as e:
            raise Exception(f"Error obteniendo documentos: {str(e)}")
    
    def save_blob_to_temp_file(self, blob_data, file_extension='.pdf'):
        """Guarda un BLOB en archivo temporal para procesamiento"""
        if not blob_data:
            return None
            
        with tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=file_extension,
            mode='wb'
        ) as tmp_file:
            tmp_file.write(blob_data)
            return tmp_file.name
    
    def update_document_analysis(self, document_id, analysis_result):
        """Actualiza el documento con resultados de análisis"""
        query = """
        UPDATE property_documents 
        SET mcp_analysis_result = :analysis_result,
            last_analyzed_at = CURRENT_TIMESTAMP,
            validation_status = :status
        WHERE id = :doc_id
        """
        
        # Determinar status basado en análisis
        status = 'valid'
        if analysis_result.get('errors'):
            status = 'error'
        elif analysis_result.get('warnings'):
            status = 'warning'
        
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text(query),
                    {
                        'analysis_result': json.dumps(analysis_result),
                        'status': status,
                        'doc_id': document_id
                    }
                )
                conn.commit()
                
        except Exception as e:
            raise Exception(f"Error actualizando análisis: {str(e)}")
```

## Herramientas MCP para Análisis de Documentos en BD

### 1. Análisis de Contratos de Corretaje

```typescript
// mcp-file-processor/src/tools/contract-analysis.ts
export const contractAnalysisTools = {
  validate_brokerage_contract: {
    description: "Valida contratos de corretaje inmobiliario",
    inputSchema: {
      type: "object",
      properties: {
        contract_content: { type: "string" },
        expected_parties: { type: "array", items: { type: "string" } },
        property_details: { type: "object" }
      },
      required: ["contract_content"]
    },
    handler: async (args: any) => {
      const content = args.contract_content;
      
      // Campos requeridos en contrato de corretaje
      const required_sections = [
        "IDENTIFICACIÓN DE LAS PARTES",
        "OBJETO DEL CONTRATO", 
        "PRECIO DE VENTA",
        "COMISIÓN DEL CORREDOR",
        "PLAZOS Y CONDICIONES",
        "OBLIGACIONES DE LAS PARTES",
        "FIRMAS Y FECHAS"
      ];
      
      // Extraer secciones del contrato
      const extracted_sections = extractContractSections(content);
      
      // Validar presencia de secciones requeridas
      const missing_sections = required_sections.filter(
        section => !extracted_sections[section]
      );
      
      // Validar datos específicos
      const validations = [];
      
      // Validar formato de precio
      if (extracted_sections["PRECIO DE VENTA"]) {
        const priceValidation = validatePriceFormat(
          extracted_sections["PRECIO DE VENTA"],
          args.property_details?.currency || "PEN"
        );
        validations.push(...priceValidation.issues);
      }
      
      // Validar comisión (debe ser porcentaje)
      if (extracted_sections["COMISIÓN DEL CORREDOR"]) {
        const commissionValidation = validateCommission(
          extracted_sections["COMISIÓN DEL CORREDOR"]
        );
        validations.push(...commissionValidation.issues);
      }
      
      // Buscar errores de tipeo comunes
      const typos = findCommonTypos(content, "contract_spanish");
      
      // Verificar consistencia de fechas
      const dateIssues = validateContractDates(extracted_sections);
      
      return {
        is_valid: missing_sections.length === 0 && validations.length === 0,
        missing_sections,
        validation_issues: validations,
        typos_found: typos,
        date_issues: dateIssues,
        extracted_data: {
          parties: extractParties(extracted_sections["IDENTIFICACIÓN DE LAS PARTES"]),
          price: extractPrice(extracted_sections["PRECIO DE VENTA"]),
          commission: extractCommission(extracted_sections["COMISIÓN DEL CORREDOR"]),
          dates: extractDates(content)
        },
        recommendations: generateContractRecommendations(
          missing_sections, 
          validations, 
          typos
        )
      };
    }
  }
};
```

### 2. Validación de Autovaluos

```typescript
// mcp-file-processor/src/tools/autoavaluo-analysis.ts
export const autoavaluoAnalysisTools = {
  analyze_autoavaluo: {
    description: "Analiza autovaluos y compara con mercado",
    handler: async (args: any) => {
      const content = args.document_content;
      
      // Extraer datos del autovaluo
      const autoavaluoData = await extractAutoavaluoData(content);
      
      // Validaciones básicas
      const validations = [];
      
      // 1. Validar que tenga todos los campos requeridos
      const requiredFields = [
        'valor_total', 'valor_terreno', 'valor_construccion',
        'area_total', 'area_construida', 'fecha_valuo',
        'profesional_valuador', 'numero_registro'
      ];
      
      const missingFields = requiredFields.filter(
        field => !autoavaluoData[field]
      );
      
      // 2. Validar consistencia matemática
      if (autoavaluoData.valor_total && autoavaluoData.valor_terreno && autoavaluoData.valor_construccion) {
        const calculatedTotal = autoavaluoData.valor_terreno + autoavaluoData.valor_construccion;
        const difference = Math.abs(autoavaluoData.valor_total - calculatedTotal);
        const tolerance = autoavaluoData.valor_total * 0.01; // 1% de tolerancia
        
        if (difference > tolerance) {
          validations.push({
            type: 'math_inconsistency',
            message: `El valor total (${autoavaluoData.valor_total}) no coincide con la suma de terreno (${autoavaluoData.valor_terreno}) + construcción (${autoavaluoData.valor_construccion}) = ${calculatedTotal}`,
            severity: 'error'
          });
        }
      }
      
      // 3. Validar rangos razonables
      if (autoavaluoData.valor_total) {
        const pricePerM2 = autoavaluoData.valor_total / (autoavaluoData.area_total || 1);
        
        // Obtener rangos de mercado para la zona
        const marketRanges = await getMarketPriceRanges(
          autoavaluoData.ubicacion,
          autoavaluoData.tipo_propiedad
        );
        
        if (pricePerM2 < marketRanges.min * 0.7) {
          validations.push({
            type: 'below_market',
            message: `El valor por m² (S/.${pricePerM2.toFixed(2)}) está muy por debajo del mercado (S/.${marketRanges.min} - S/.${marketRanges.max})`,
            severity: 'warning'
          });
        }
        
        if (pricePerM2 > marketRanges.max * 1.3) {
          validations.push({
            type: 'above_market',
            message: `El valor por m² (S/.${pricePerM2.toFixed(2)}) está muy por encima del mercado (S/.${marketRanges.min} - S/.${marketRanges.max})`,
            severity: 'warning'
          });
        }
      }
      
      // 4. Buscar errores de tipeo
      const typos = await findTyposInDocument(content, 'real_estate_spanish');
      
      return {
        autoavaluo_data: autoavaluoData,
        is_valid: missingFields.length === 0 && validations.filter(v => v.severity === 'error').length === 0,
        missing_fields: missingFields,
        validations,
        typos_found: typos,
        market_comparison: await compareWithMarket(autoavaluoData),
        recommendations: generateAutoavaluoRecommendations(autoavaluoData, validations)
      };
    }
  }
};
```

### 3. Verificación de DNI

```typescript
// mcp-file-processor/src/tools/dni-analysis.ts
export const dniAnalysisTools = {
  validate_dni_document: {
    description: "Valida documentos DNI y extrae información",
    handler: async (args: any) => {
      const content = args.document_content;
      
      // Para DNI escaneados, usar OCR
      const extractedText = await performOCR(content);
      
      // Patrones para extraer datos del DNI peruano
      const patterns = {
        dni_number: /\b\d{8}\b/,
        nombres: /NOMBRES?[\s:]+([A-ZÁÉÍÓÚÑ\s]+)/i,
        apellidos: /APELLIDOS?[\s:]+([A-ZÁÉÍÓÚÑ\s]+)/i,
        fecha_nacimiento: /F\.? NAC\.?[\s:]+(\d{2}[\/\-]\d{2}[\/\-]\d{4})/i,
        sexo: /SEXO[\s:]+([MF])/i,
        fecha_emision: /F\.? EMIS\.?[\s:]+(\d{2}[\/\-]\d{2}[\/\-]\d{4})/i,
        fecha_caducidad: /F\.? CAD\.?[\s:]+(\d{2}[\/\-]\d{2}[\/\-]\d{4})/i
      };
      
      const extractedData = {};
      Object.entries(patterns).forEach(([key, pattern]) => {
        const match = extractedText.match(pattern);
        if (match) {
          extractedData[key] = match[1].trim();
        }
      });
      
      // Validaciones
      const validations = [];
      
      // Validar dígito verificador del DNI
      if (extractedData.dni_number) {
        const isValidDNI = validatePeruvianDNI(extractedData.dni_number);
        if (!isValidDNI) {
          validations.push({
            type: 'invalid_dni',
            message: 'Número de DNI inválido (dígito verificador incorrecto)',
            severity: 'error'
          });
        }
      }
      
      // Validar fechas
      if (extractedData.fecha_nacimiento) {
        const birthDate = parseDate(extractedData.fecha_nacimiento);
        if (birthDate > new Date()) {
          validations.push({
            type: 'future_birth_date',
            message: 'Fecha de nacimiento en el futuro',
            severity: 'error'
          });
        }
      }
      
      if (extractedData.fecha_caducidad) {
        const expiryDate = parseDate(extractedData.fecha_caducidad);
        if (expiryDate < new Date()) {
          validations.push({
            type: 'expired_dni',
            message: 'DNI vencido',
            severity: 'warning'
          });
        }
      }
      
      // Verificar que nombres y apellidos no contengan números
      if (extractedData.nombres && /\d/.test(extractedData.nombres)) {
        validations.push({
          type: 'numbers_in_name',
          message: 'Nombres contienen números',
          severity: 'warning'
        });
      }
      
      return {
        extracted_data: extractedData,
        is_valid: validations.filter(v => v.severity === 'error').length === 0,
        validations,
        ocr_confidence: args.ocr_confidence || 0.85,
        recommendations: generateDNIRecommendations(extractedData, validations)
      };
    }
  }
};
```

## Integración con el Sistema Existente

### Modelo de Documentos de Propiedad (si no existe)

```python
# propifai/models.py
from django.db import models
import json

class PropertyDocument(models.Model):
    """Documentos asociados a propiedades en Propifai"""
    
    DOCUMENT_TYPES = [
        ('contrato_corretaje', 'Contrato de Corretaje'),
        ('autoavaluo', 'Autovaluo'),
        ('dni_propietario', 'DNI Propietario'),
        ('dni_arrendatario', 'DNI Arrendatario'),
        ('titulo_propiedad', 'Título de Propiedad'),
        ('recibo_servicios', 'Recibo de Servicios'),
        ('planos', 'Planos'),
        ('fotos', 'Fotos'),
        ('otros', 'Otros')
    ]
    
    VALIDATION_STATUS = [
        ('pending', 'Pendiente'),
        ('valid', 'Válido'),
        ('warning', 'Con Advertencias'),
        ('error', 'Con Errores'),
        ('manual_review', 'Revisión Manual')
    ]
    
    property = models.ForeignKey(
        'Propiedad', 
        on_delete=models.CASCADE, 
        related_name='documents'
    )
    document_type = models.CharField(
        max_length=50, 
        choices=DOCUMENT_TYPES
    )
    document_name = models.CharField(max_length=255)
    
    # Opción 1: FileField (recomendado para archivos grandes)
    document_file = models.FileField(
        upload_to='property_documents/%Y/%m/%d/',
        null=True,
        blank=True
    )
    
    # Opción 2: BLOB en BD (para documentos pequeños)
    document_content = models.BinaryField(null=True, blank=True)
    
    # Metadatos
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        'User', 
        on_delete=models.SET_NULL, 
        null=True
    )
    
    # Campos de validación MCP
    validation_status = models.CharField(
        max_length=20,
        choices=VALIDATION_STATUS,
        default='pending'
    )
