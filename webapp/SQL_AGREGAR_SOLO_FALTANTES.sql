-- Verificar y agregar SOLO las columnas que NO existen
-- Ejecuta esto en SQL Server

USE [tu_base_de_datos];
GO

-- Solo agrega si NO existe
IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'captura_capturacruda' AND COLUMN_NAME = 'estado_http')
BEGIN
    ALTER TABLE captura_capturacruda ADD estado_http NVARCHAR(15) NULL DEFAULT 'exito';
    PRINT 'Agregada: estado_http';
END
ELSE
    PRINT 'Ya existe: estado_http';
GO

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'captura_capturacruda' AND COLUMN_NAME = 'estado_procesamiento')
BEGIN
    ALTER TABLE captura_capturacruda ADD estado_procesamiento NVARCHAR(20) NULL DEFAULT 'pendiente';
    PRINT 'Agregada: estado_procesamiento';
END
ELSE
    PRINT 'Ya existe: estado_procesamiento';
GO

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'captura_capturacruda' AND COLUMN_NAME = 'tipo_documento')
BEGIN
    ALTER TABLE captura_capturacruda ADD tipo_documento NVARCHAR(20) NULL DEFAULT 'html';
    PRINT 'Agregada: tipo_documento';
END
ELSE
    PRINT 'Ya existe: tipo_documento';
GO

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'captura_capturacruda' AND COLUMN_NAME = 'contenido_binario_blob')
BEGIN
    ALTER TABLE captura_capturacruda ADD contenido_binario_blob NVARCHAR(255) NULL DEFAULT '';
    PRINT 'Agregada: contenido_binario_blob';
END
ELSE
    PRINT 'Ya existe: contenido_binario_blob';
GO

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'captura_capturacruda' AND COLUMN_NAME = 'texto_extraido')
BEGIN
    ALTER TABLE captura_capturacruda ADD texto_extraido NVARCHAR(MAX) NULL;
    PRINT 'Agregada: texto_extraido';
END
ELSE
    PRINT 'Ya existe: texto_extraido';
GO

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'captura_capturacruda' AND COLUMN_NAME = 'azure_blob_url')
BEGIN
    ALTER TABLE captura_capturacruda ADD azure_blob_url NVARCHAR(500) NULL DEFAULT '';
    PRINT 'Agregada: azure_blob_url';
END
ELSE
    PRINT 'Ya existe: azure_blob_url';
GO

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'captura_capturacruda' AND COLUMN_NAME = 'azure_blob_name')
BEGIN
    ALTER TABLE captura_capturacruda ADD azure_blob_name NVARCHAR(255) NULL DEFAULT '';
    PRINT 'Agregada: azure_blob_name';
END
ELSE
    PRINT 'Ya existe: azure_blob_name';
GO

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'captura_capturacruda' AND COLUMN_NAME = 'metadata_tecnica')
BEGIN
    ALTER TABLE captura_capturacruda ADD metadata_tecnica NVARCHAR(MAX) NULL DEFAULT '{}';
    PRINT 'Agregada: metadata_tecnica';
END
ELSE
    PRINT 'Ya existe: metadata_tecnica';
GO

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'captura_capturacruda' AND COLUMN_NAME = 'pdf_tiene_texto')
BEGIN
    ALTER TABLE captura_capturacruda ADD pdf_tiene_texto BIT NULL;
    PRINT 'Agregada: pdf_tiene_texto';
END
ELSE
    PRINT 'Ya existe: pdf_tiene_texto';
GO

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'captura_capturacruda' AND COLUMN_NAME = 'pdf_num_paginas')
BEGIN
    ALTER TABLE captura_capturacruda ADD pdf_num_paginas INT NULL;
    PRINT 'Agregada: pdf_num_paginas';
END
ELSE
    PRINT 'Ya existe: pdf_num_paginas';
GO

PRINT '=== PROCESO COMPLETADO ===';
GO
