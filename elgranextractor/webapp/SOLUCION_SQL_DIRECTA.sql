-- ============================================
-- SOLUCIÓN: Agregar columnas faltantes
-- Ejecuta esto en SQL Server Management Studio
-- ============================================

-- Primero verifica que estás en la base de datos correcta
-- Reemplaza 'nombre_bd' con el nombre real de tu base de datos
USE [nombre_bd];
GO

-- Agregar las columnas que faltan
ALTER TABLE captura_capturacruda ADD estado_http NVARCHAR(15) NULL DEFAULT 'exito';
GO

ALTER TABLE captura_capturacruda ADD estado_procesamiento NVARCHAR(20) NULL DEFAULT 'pendiente';
GO

ALTER TABLE captura_capturacruda ADD tipo_documento NVARCHAR(20) NULL DEFAULT 'html';
GO

ALTER TABLE captura_capturacruda ADD contenido_binario_blob NVARCHAR(255) NULL DEFAULT '';
GO

ALTER TABLE captura_capturacruda ADD texto_extraido NVARCHAR(MAX) NULL;
GO

ALTER TABLE captura_capturacruda ADD azure_blob_url NVARCHAR(500) NULL DEFAULT '';
GO

ALTER TABLE captura_capturacruda ADD azure_blob_name NVARCHAR(255) NULL DEFAULT '';
GO

ALTER TABLE captura_capturacruda ADD metadata_tecnica NVARCHAR(MAX) NULL DEFAULT '{}';
GO

ALTER TABLE captura_capturacruda ADD pdf_tiene_texto BIT NULL;
GO

ALTER TABLE captura_capturacruda ADD pdf_num_paginas INT NULL;
GO

-- Verificar que se agregaron correctamente
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'captura_capturacruda'
ORDER BY ORDINAL_POSITION;
GO

-- Si todo salió bien, deberías ver todas las columnas nuevas listadas
PRINT 'Columnas agregadas exitosamente!'
GO
