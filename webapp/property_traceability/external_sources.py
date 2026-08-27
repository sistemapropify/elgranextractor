import logging
from collections import defaultdict
from pathlib import PurePosixPath
from urllib.parse import quote

from django.db import connections

logger = logging.getLogger(__name__)

PROPIFY_MEDIA_BASE_URL = "https://propifymedia01.blob.core.windows.net/media"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv"}


def resolve_propifai_media_url(value):
    """Convierte la ruta guardada en dbpropify_be en una URL pública del contenedor media."""
    if value is None:
        return ""
    raw = str(value).strip().replace("\\", "/")
    if not raw:
        return ""
    if raw.startswith("//"):
        return f"https:{raw}"
    if raw.lower().startswith(("http://", "https://", "data:")):
        return raw
    if ".blob.core.windows.net/" in raw.lower():
        return f"https://{raw.lstrip('/')}"
    path = raw.lstrip("/")
    if path.lower().startswith("media/"):
        path = path[6:]
    encoded_path = "/".join(quote(part, safe="-_.~()") for part in path.split("/") if part)
    return f"{PROPIFY_MEDIA_BASE_URL}/{encoded_path}" if encoded_path else ""


def enrich_media_row(row):
    item = dict(row)
    item["file_url"] = resolve_propifai_media_url(item.get("file"))
    item["thumbnail_url"] = resolve_propifai_media_url(item.get("thumbnail"))
    item["wp_source_url_resolved"] = resolve_propifai_media_url(item.get("wp_source_url"))
    item["resolved_url"] = item["file_url"] or item["wp_source_url_resolved"] or item["thumbnail_url"]
    item["preview_url"] = item["thumbnail_url"] or item["file_url"] or item["wp_source_url_resolved"]
    return item


def enrich_document_row(row):
    item = dict(row)
    item["file_url"] = resolve_propifai_media_url(item.get("file"))
    return item


def load_user_names(ids):
    """Resuelve el nombre completo de los usuarios (tabla [user] en dbpropify_be)."""
    ids = [int(value) for value in ids if value is not None]
    if not ids:
        return {}
    placeholders = ",".join(["%s"] * len(ids))
    try:
        with connections["propifai"].cursor() as cursor:
            cursor.execute(f"""
                SELECT id, first_name, last_name
                FROM [user]
                WHERE id IN ({placeholders})
            """, ids)
            names = {}
            for row in _rows(cursor):
                full = " ".join(part for part in (row.get("first_name"), row.get("last_name")) if part).strip()
                names[row["id"]] = full or "Usuario"
            return names
    except Exception:
        logger.exception("No se pudieron resolver los creadores de documentos")
        return {}


def _media_extension(item):
    raw = item.get("resolved_url") or item.get("file") or item.get("wp_source_url") or ""
    path = str(raw).split("?", 1)[0].split("#", 1)[0]
    return PurePosixPath(path.lower()).suffix


def _rows(cursor):
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def fetch_external_evidence(property_ids):
    """Lee hechos de dbpropify_be sin imponer un orden de etapas."""
    ids = [int(value) for value in property_ids if value is not None]
    evidence = defaultdict(lambda: {"documents": [], "media": [], "events": [], "proposals": []})
    if not ids:
        return evidence
    placeholders = ",".join(["%s"] * len(ids))
    try:
        with connections["propifai"].cursor() as cursor:
            cursor.execute(f"""
                SELECT pd.id, pd.property_id, pd.[file], pd.status, pd.legal_status,
                       pd.legal_reviewed_at, pd.legal_reviewed_by_id,
                       pd.legal_observation, pd.notes, pd.valid_from, pd.valid_to,
                       pd.document_scope, pd.document_type_id, pd.created_at,
                       pd.updated_at, pd.created_by_id,
                       dt.code AS document_code, dt.name AS document_name
                FROM property_document pd
                LEFT JOIN document_type dt ON dt.id = pd.document_type_id
                WHERE pd.property_id IN ({placeholders})
                ORDER BY pd.created_at
            """, ids)
            document_rows = []
            for row in _rows(cursor):
                doc = enrich_document_row(row)
                evidence[row["property_id"]]["documents"].append(doc)
                document_rows.append(doc)
            creator_names = load_user_names({doc.get("created_by_id") for doc in document_rows})
            for doc in document_rows:
                doc["created_by_name"] = creator_names.get(doc.get("created_by_id")) or ""

            cursor.execute(f"""
                SELECT id, property_id, media_type, [file], thumbnail, title, label,
                       [order], wp_media_id, wp_source_url, wp_last_sync,
                       created_by_id, created_at, updated_at
                FROM property_media
                WHERE property_id IN ({placeholders})
                ORDER BY [order], created_at
            """, ids)
            for row in _rows(cursor):
                evidence[row["property_id"]]["media"].append(enrich_media_row(row))

            cursor.execute(f"""
                SELECT e.id, e.property_id, e.title, e.description, e.status,
                       e.completed, e.start_time, e.end_time, e.created_at,
                       e.proposal_id, et.name AS event_type
                FROM event e
                LEFT JOIN event_type et ON et.id = e.event_type_id
                WHERE e.property_id IN ({placeholders})
                ORDER BY COALESCE(e.start_time, e.created_at)
            """, ids)
            for row in _rows(cursor):
                evidence[row["property_id"]]["events"].append(row)

            cursor.execute(f"""
                SELECT id, property_id, amount, status, created_at, responded_at,
                       message, response_message
                FROM proposal
                WHERE property_id IN ({placeholders})
                ORDER BY created_at
            """, ids)
            for row in _rows(cursor):
                evidence[row["property_id"]]["proposals"].append(row)
    except Exception:
        logger.exception("No se pudieron leer evidencias de trazabilidad desde dbpropify_be")
    return evidence


def property_ids_for_fact_view(view_name):
    queries = {
        "visits": "SELECT DISTINCT e.property_id FROM event e JOIN event_type et ON et.id=e.event_type_id WHERE LOWER(et.name)='visita' AND e.property_id IS NOT NULL",
        "offer": "SELECT DISTINCT property_id FROM proposal WHERE property_id IS NOT NULL",
        "closed": "SELECT DISTINCT e.property_id FROM event e JOIN event_type et ON et.id=e.event_type_id WHERE LOWER(et.name)='cierre' AND e.property_id IS NOT NULL",
        "ready": "SELECT DISTINCT pd.property_id FROM property_document pd JOIN document_type dt ON dt.id=pd.document_type_id WHERE dt.code='103' AND pd.[file] IS NOT NULL AND EXISTS (SELECT 1 FROM property_media pm WHERE pm.property_id=pd.property_id)",
    }
    sql = queries.get(view_name)
    if not sql:
        return None
    try:
        with connections["propifai"].cursor() as cursor:
            cursor.execute(sql)
            return [row[0] for row in cursor.fetchall()]
    except Exception:
        logger.exception("No se pudo resolver la vista rápida %s", view_name)
        return []


def summarize_evidence(prop, facts):
    documents = facts.get("documents", [])
    media = facts.get("media", [])
    events = facts.get("events", [])
    proposals = facts.get("proposals", [])
    document_codes = {str(item.get("document_code") or "").strip() for item in documents}
    contract = next((item for item in documents if str(item.get("document_code")) == "103" and item.get("file")), None)
    reviewed = [item for item in documents if str(item.get("legal_status") or "").lower() in {"approved", "aprobado", "vigente"}]
    videos = [
        item for item in media
        if "video" in str(item.get("media_type") or "").lower() or _media_extension(item) in VIDEO_EXTENSIONS
    ]
    video_ids = {item.get("id") for item in videos}
    images = [
        item for item in media
        if item.get("resolved_url")
        and item.get("id") not in video_ids
    ]
    event_names = [str(item.get("event_type") or "").lower() for item in events]
    visits = [item for item in events if str(item.get("event_type") or "").lower() == "visita"]
    captures = [item for item in events if str(item.get("event_type") or "").lower() == "captación"]
    closings = [item for item in events if str(item.get("event_type") or "").lower() == "cierre"]
    notary = [item for item in events if "notar" in (str(item.get("title") or "") + " " + str(item.get("description") or "")).lower()]
    accepted_statuses = {"accepted", "aceptada", "aceptado", "approved", "aprobada", "aprobado"}
    accepted = [item for item in proposals if str(item.get("status") or "").lower() in accepted_statuses]
    media_first = min((item.get("created_at") for item in media if item.get("created_at")), default=None)
    visit_first = min((item.get("start_time") or item.get("created_at") for item in visits if item.get("start_time") or item.get("created_at")), default=None)
    proposal_first = min((item.get("created_at") for item in proposals if item.get("created_at")), default=None)
    return {
        "documents": documents,
        "document_codes": document_codes,
        "contract": contract,
        "reviewed_documents": reviewed,
        "media": media,
        "images": images,
        "videos": videos,
        "events": events,
        "captures": captures,
        "visits": visits,
        "proposals": proposals,
        "accepted_proposals": accepted,
        "closings": closings,
        "notary_events": notary,
        "published": bool(getattr(prop, "wp_post_id", None)),
        "publication_at": getattr(prop, "wp_last_sync", None),
        "resolved_video_url": resolve_propifai_media_url(getattr(prop, "video_url", None)),
        "media_first": media_first,
        "visit_first": visit_first,
        "proposal_first": proposal_first,
    }
