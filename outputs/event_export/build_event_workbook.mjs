import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const workDir = "D:/PROMETEO/outputs/event_export";
const data = JSON.parse(
  await fs.readFile(`${workDir}/event_export_data.json`, "utf8"),
);
const schema = JSON.parse(
  await fs.readFile(`${workDir}/event_schema.json`, "utf8"),
);
const outputPath = `${workDir}/auditoria_eventos_crm_2026-07-30.xlsx`;

const workbook = Workbook.create();
const summarySheet = workbook.worksheets.add("Resumen");
const eventsSheet = workbook.worksheets.add("Eventos");
const dictionarySheet = workbook.worksheets.add("Diccionario");

const colors = {
  navy: "#17365D",
  blue: "#2F75B5",
  lightBlue: "#D9EAF7",
  orange: "#F4B183",
  lightOrange: "#FCE4D6",
  green: "#70AD47",
  lightGreen: "#E2F0D9",
  red: "#C00000",
  lightRed: "#F4CCCC",
  gray: "#E7E6E6",
  darkGray: "#595959",
  white: "#FFFFFF",
};

const eventKeys = Object.keys(data.events[0] || {});
const originalFields = new Set(schema.columns.map((column) => column.name));
const descriptiveFields = new Set(
  eventKeys.filter((key) => !originalFields.has(key)),
);
const eventHeaders = eventKeys.map((key) => {
  const labels = {
    id: "ID evento",
    created_at: "Creado",
    updated_at: "Actualizado",
    code: "Código",
    title: "Título",
    description: "Descripción",
    tracing: "Trazabilidad",
    start_time: "Inicio",
    end_time: "Fin",
    status: "Estado",
    is_active: "Activo",
    assigned_agent_id: "ID agente asignado",
    assigned_agent_name: "Agente asignado",
    contact_id: "ID contacto",
    contact_name: "Contacto",
    contact_phone: "Teléfono contacto",
    contact_email: "Email contacto",
    created_by_id: "ID creador",
    created_by_name: "Creado por",
    event_type_id: "ID tipo evento",
    event_type_name: "Tipo de evento",
    property_id: "ID propiedad",
    property_code: "Código propiedad",
    property_title: "Propiedad",
    updated_by_id: "ID actualizador",
    updated_by_name: "Actualizado por",
    lead_id: "ID lead",
    lead_contact_name: "Lead / contacto",
    lead_contact_phone: "Teléfono lead",
    lead_chatwoot_id: "ID Chatwoot",
    match_id: "ID match",
    match_description: "Match",
    proposal_id: "ID propuesta",
    proposal_description: "Propuesta",
    completed: "Completado",
  };
  return labels[key] || key;
});

function excelColumn(index) {
  let value = index + 1;
  let result = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    result = String.fromCharCode(65 + remainder) + result;
    value = Math.floor((value - 1) / 26);
  }
  return result;
}

function typedEventValue(key, value) {
  if (value == null) return null;
  if (["created_at", "updated_at", "start_time", "end_time"].includes(key)) {
    return new Date(value);
  }
  if (["is_active", "completed"].includes(key)) return Boolean(value);
  if (
    key === "code" ||
    key.endsWith("_phone") ||
    key.endsWith("_chatwoot_id")
  ) {
    return String(value);
  }
  return value;
}

const eventRows = data.events.map((event) =>
  eventKeys.map((key) => typedEventValue(key, event[key])),
);
const lastEventRow = eventRows.length + 1;
const lastEventCol = excelColumn(eventKeys.length - 1);

eventsSheet.getRangeByIndexes(0, 0, 1, eventHeaders.length).values = [
  eventHeaders,
];
eventsSheet.getRangeByIndexes(1, 0, eventRows.length, eventHeaders.length).values =
  eventRows;
eventsSheet.showGridLines = false;
eventsSheet.freezePanes.freezeRows(1);
eventsSheet.freezePanes.freezeColumns(5);
eventsSheet.getRange(`A1:${lastEventCol}1`).format = {
  fill: colors.navy,
  font: { bold: true, color: colors.white },
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "medium", color: colors.navy },
};
eventsSheet.getRange(`A1:${lastEventCol}1`).format.rowHeight = 36;
eventsSheet.getRange(`A2:${lastEventCol}${lastEventRow}`).format = {
  verticalAlignment: "top",
  borders: {
    insideHorizontal: { style: "thin", color: "#D9E2F3" },
  },
};

for (const key of ["created_at", "updated_at", "start_time", "end_time"]) {
  const index = eventKeys.indexOf(key);
  const column = excelColumn(index);
  eventsSheet.getRange(`${column}2:${column}${lastEventRow}`).format.numberFormat =
    "yyyy-mm-dd hh:mm";
}

for (const key of descriptiveFields) {
  const index = eventKeys.indexOf(key);
  const column = excelColumn(index);
  eventsSheet.getRange(`${column}2:${column}${lastEventRow}`).format.fill =
    colors.lightBlue;
}

const leadIdColumn = excelColumn(eventKeys.indexOf("lead_id"));
eventsSheet
  .getRange(`${leadIdColumn}2:${leadIdColumn}${lastEventRow}`)
  .conditionalFormats.add("containsBlanks", {
    format: { fill: colors.lightRed, font: { color: colors.red } },
  });

eventsSheet.tables.add(
  `A1:${lastEventCol}${lastEventRow}`,
  true,
  "EventosCRM",
);

const widthMap = {
  id: 11,
  created_at: 18,
  updated_at: 18,
  code: 14,
  title: 34,
  description: 45,
  tracing: 34,
  start_time: 18,
  end_time: 18,
  status: 14,
  is_active: 10,
  assigned_agent_id: 13,
  assigned_agent_name: 24,
  contact_id: 13,
  contact_name: 25,
  contact_phone: 17,
  contact_email: 27,
  created_by_id: 13,
  created_by_name: 24,
  event_type_id: 13,
  event_type_name: 20,
  property_id: 13,
  property_code: 17,
  property_title: 38,
  updated_by_id: 13,
  updated_by_name: 24,
  lead_id: 13,
  lead_contact_name: 25,
  lead_contact_phone: 17,
  lead_chatwoot_id: 14,
  match_id: 13,
  match_description: 40,
  proposal_id: 13,
  proposal_description: 42,
  completed: 12,
};
eventKeys.forEach((key, index) => {
  const column = excelColumn(index);
  eventsSheet.getRange(`${column}:${column}`).format.columnWidth =
    widthMap[key] || 18;
});
eventsSheet.getRange(`E2:G${lastEventRow}`).format.wrapText = true;
eventsSheet.getRange(`X2:X${lastEventRow}`).format.wrapText = true;
eventsSheet.getRange(`AF2:AH${lastEventRow}`).format.wrapText = true;

summarySheet.showGridLines = false;
summarySheet.getRange("A1:H1").merge();
summarySheet.getRange("A1").values = [
  ["Auditoría completa de eventos del CRM"],
];
summarySheet.getRange("A1:H1").format = {
  fill: colors.navy,
  font: { bold: true, color: colors.white, size: 18 },
  verticalAlignment: "center",
};
summarySheet.getRange("A1:H1").format.rowHeight = 34;
summarySheet.getRange("A2:H2").merge();
summarySheet.getRange("A2").values = [[
  `Fuente: dbpropify_be.dbo.event · extracción de solo lectura · ${data.generated_at}`,
]];
summarySheet.getRange("A2:H2").format = {
  fill: colors.lightBlue,
  font: { color: colors.darkGray, italic: true },
};

summarySheet.getRange("A4:B8").values = [
  ["Indicador", "Valor"],
  ["Total de eventos", null],
  ["Eventos con lead_id", null],
  ["Eventos sin lead_id", null],
  ["% sin lead_id", null],
];
summarySheet.getRange("B5").formulas = [[
  `=COUNTA('Eventos'!$A$2:$A$${lastEventRow})`,
]];
summarySheet.getRange("B6").formulas = [[
  `=COUNT('Eventos'!$${leadIdColumn}$2:$${leadIdColumn}$${lastEventRow})`,
]];
summarySheet.getRange("B7").formulas = [["=B5-B6"]];
summarySheet.getRange("B8").formulas = [["=IFERROR(B7/B5,0)"]];
summarySheet.getRange("A4:B4").format = {
  fill: colors.blue,
  font: { bold: true, color: colors.white },
};
summarySheet.getRange("A5:B8").format.borders = {
  preset: "all",
  style: "thin",
  color: "#B4C6E7",
};
summarySheet.getRange("B5:B7").format.numberFormat = "#,##0";
summarySheet.getRange("B8").format.numberFormat = "0.0%";
summarySheet.getRange("A7:B8").format.fill = colors.lightRed;
summarySheet.getRange("A7:B8").format.font = {
  bold: true,
  color: colors.red,
};

summarySheet.getRange("D4:H7").values = [
  ["Hallazgo", null, null, null, null],
  [
    "El dashboard no debe interpretar todo registro de event como visita registrada de un lead.",
    null,
    null,
    null,
    null,
  ],
  [
    "Solo deben contarse eventos con lead_id no nulo y, además, con el tipo de evento correcto.",
    null,
    null,
    null,
    null,
  ],
  [
    "Los registros sin lead_id permanecen en la exportación para auditoría.",
    null,
    null,
    null,
    null,
  ],
];
summarySheet.getRange("D4:H4").merge();
summarySheet.getRange("D5:H5").merge();
summarySheet.getRange("D6:H6").merge();
summarySheet.getRange("D7:H7").merge();
summarySheet.getRange("D4:H4").format = {
  fill: colors.orange,
  font: { bold: true, color: "#7F4125" },
};
summarySheet.getRange("D5:H7").format = {
  fill: colors.lightOrange,
  wrapText: true,
  verticalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: colors.orange },
};
summarySheet.getRange("D5:H7").format.rowHeight = 35;

const typeStart = 11;
summarySheet.getRange(`A${typeStart}:D${typeStart}`).values = [[
  "Tipo de evento",
  "Total",
  "Con lead",
  "Sin lead",
]];
summarySheet
  .getRangeByIndexes(typeStart, 0, data.by_type.length, 4)
  .values = data.by_type.map((row) => [
    row.event_type,
    row.total,
    row.with_lead,
    row.without_lead,
  ]);
const typeEnd = typeStart + data.by_type.length;
summarySheet.getRange(`A${typeStart}:D${typeStart}`).format = {
  fill: colors.blue,
  font: { bold: true, color: colors.white },
};
summarySheet.getRange(`B${typeStart + 1}:D${typeEnd}`).format.numberFormat =
  "#,##0";
summarySheet.tables.add(
  `A${typeStart}:D${typeEnd}`,
  true,
  "ResumenPorTipo",
);

const statusStart = 11;
summarySheet.getRange(`F${statusStart}:I${statusStart}`).values = [[
  "Estado",
  "Total",
  "Con lead",
  "Sin lead",
]];
summarySheet
  .getRangeByIndexes(statusStart, 5, data.by_status.length, 4)
  .values = data.by_status.map((row) => [
    row.status,
    row.total,
    row.with_lead,
    row.without_lead,
  ]);
const statusEnd = statusStart + data.by_status.length;
summarySheet.getRange(`F${statusStart}:I${statusStart}`).format = {
  fill: colors.blue,
  font: { bold: true, color: colors.white },
};
summarySheet.getRange(`G${statusStart + 1}:I${statusEnd}`).format.numberFormat =
  "#,##0";
summarySheet.tables.add(
  `F${statusStart}:I${statusEnd}`,
  true,
  "ResumenPorEstado",
);

summarySheet.getRange("A:A").format.columnWidth = 28;
summarySheet.getRange("B:D").format.columnWidth = 15;
summarySheet.getRange("E:E").format.columnWidth = 4;
summarySheet.getRange("F:F").format.columnWidth = 20;
summarySheet.getRange("G:I").format.columnWidth = 15;
summarySheet.freezePanes.freezeRows(2);

const relationMap = new Map(
  schema.foreign_keys.map((fk) => [fk.source_column, fk]),
);
const descriptorMap = {
  assigned_agent_id: "assigned_agent_name",
  contact_id: "contact_name, contact_phone, contact_email",
  created_by_id: "created_by_name",
  event_type_id: "event_type_name",
  property_id: "property_code, property_title",
  updated_by_id: "updated_by_name",
  lead_id: "lead_contact_name, lead_contact_phone, lead_chatwoot_id",
  match_id: "match_description",
  proposal_id: "proposal_description",
};
const dictionaryRows = schema.columns.map((column) => {
  const relation = relationMap.get(column.name);
  return [
    column.position,
    column.name,
    column.type,
    column.nullable === "YES" ? "Sí" : "No",
    relation ? `${relation.target_table}.${relation.target_column}` : "",
    descriptorMap[column.name] || "",
    relation
      ? "ID original conservado; descripción resuelta mediante LEFT JOIN."
      : "Campo original de dbo.event.",
  ];
});
dictionarySheet.getRange("A1:G1").merge();
dictionarySheet.getRange("A1").values = [[
  "Diccionario de campos y vinculaciones",
]];
dictionarySheet.getRange("A1:G1").format = {
  fill: colors.navy,
  font: { bold: true, color: colors.white, size: 16 },
};
dictionarySheet.getRange("A2:G2").values = [[
  "Posición",
  "Campo original",
  "Tipo SQL",
  "Admite NULL",
  "Relación",
  "Columnas descriptivas",
  "Tratamiento en el Excel",
]];
dictionarySheet
  .getRangeByIndexes(2, 0, dictionaryRows.length, 7)
  .values = dictionaryRows;
const dictionaryEnd = dictionaryRows.length + 2;
dictionarySheet.getRange("A2:G2").format = {
  fill: colors.blue,
  font: { bold: true, color: colors.white },
  wrapText: true,
};
dictionarySheet.getRange(`A3:G${dictionaryEnd}`).format = {
  verticalAlignment: "top",
  borders: {
    insideHorizontal: { style: "thin", color: "#D9E2F3" },
  },
};
dictionarySheet.getRange(`F3:G${dictionaryEnd}`).format.wrapText = true;
dictionarySheet.tables.add(
  `A2:G${dictionaryEnd}`,
  true,
  "DiccionarioEventos",
);
dictionarySheet.getRange("A:A").format.columnWidth = 11;
dictionarySheet.getRange("B:B").format.columnWidth = 24;
dictionarySheet.getRange("C:C").format.columnWidth = 15;
dictionarySheet.getRange("D:D").format.columnWidth = 14;
dictionarySheet.getRange("E:E").format.columnWidth = 28;
dictionarySheet.getRange("F:F").format.columnWidth = 38;
dictionarySheet.getRange("G:G").format.columnWidth = 52;
dictionarySheet.freezePanes.freezeRows(2);
dictionarySheet.showGridLines = false;

const previewSummary = await workbook.render({
  sheetName: "Resumen",
  range: `A1:I${Math.max(typeEnd, statusEnd)}`,
  scale: 1.5,
  format: "png",
});
await fs.writeFile(
  `${workDir}/preview_resumen.png`,
  new Uint8Array(await previewSummary.arrayBuffer()),
);
const previewEvents = await workbook.render({
  sheetName: "Eventos",
  range: "A1:U12",
  scale: 1,
  format: "png",
});
await fs.writeFile(
  `${workDir}/preview_eventos.png`,
  new Uint8Array(await previewEvents.arrayBuffer()),
);
const previewDictionary = await workbook.render({
  sheetName: "Diccionario",
  range: `A1:G${dictionaryEnd}`,
  scale: 1.2,
  format: "png",
});
await fs.writeFile(
  `${workDir}/preview_diccionario.png`,
  new Uint8Array(await previewDictionary.arrayBuffer()),
);

const inspection = await workbook.inspect({
  kind: "table",
  range: "Resumen!A1:I20",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 9,
});
await fs.writeFile(`${workDir}/inspection.ndjson`, inspection.ndjson, "utf8");
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
await fs.writeFile(`${workDir}/formula_errors.ndjson`, errors.ndjson, "utf8");

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(
  JSON.stringify({
    outputPath,
    rows: eventRows.length,
    columns: eventHeaders.length,
    lastEventRow,
  }),
);
