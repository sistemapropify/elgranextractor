-- Script SQL para agregar columnas faltantes a la tabla ingestas_propiedadraw
-- Ejecutar en SQL Server Management Studio o con sqlcmd

USE [tu_base_de_datos]; -- Reemplaza con el nombre de tu base de datos

BEGIN TRY
    ALTER TABLE ingestas_propiedadraw ADD condicion NVARCHAR(20) NULL;
    PRINT 'Columna "condicion" agregada exitosamente.';
END TRY
BEGIN CATCH
    PRINT 'La columna "condicion" ya existe o error: ' + ERROR_MESSAGE();
END CATCH

BEGIN TRY
    ALTER TABLE ingestas_propiedadraw ADD propiedad_verificada BIT NULL;
    PRINT 'Columna "propiedad_verificada" agregada exitosamente.';
END TRY
BEGIN CATCH
    PRINT 'La columna "propiedad_verificada" ya existe o error: ' + ERROR_MESSAGE();
END CATCH

-- Actualizar valores por defecto
UPDATE ingestas_propiedadraw SET condicion = 'no_especificado' WHERE condicion IS NULL;
PRINT 'Valores de "condicion" actualizados.';

UPDATE ingestas_propiedadraw SET propiedad_verificada = 0 WHERE propiedad_verificada IS NULL;
PRINT 'Valores de "propiedad_verificada" actualizados.';

-- Verificar columnas
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'ingestas_propiedadraw'
ORDER BY ORDINAL_POSITION;