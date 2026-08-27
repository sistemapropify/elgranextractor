from dataclasses import dataclass


@dataclass(frozen=True)
class StageDefinition:
    key: str
    label: str
    order: int
    area: str
    sla_hours: int | None


STAGES = (
    StageDefinition("captation", "Captación", 1, "Comercial", 24),
    StageDefinition("draft", "Borrador", 2, "Comercial", 48),
    StageDefinition("documentation", "Documentación", 3, "Legal", 120),
    StageDefinition("legal_review", "Revisión legal", 4, "Legal", 72),
    StageDefinition("brokerage_contract", "Contrato de corretaje", 5, "Comercial", 72),
    StageDefinition("marketing", "Producción de marketing", 6, "Marketing", 96),
    StageDefinition("publication", "Publicación", 7, "Marketing", 24),
    StageDefinition("advertising", "Publicidad", 8, "Marketing", 48),
    StageDefinition("visits", "Visitas", 9, "Comercial", 504),
    StageDefinition("offer", "Propuesta", 10, "Comercial", 72),
    StageDefinition("accepted_offer", "Propuesta aceptada", 11, "Comercial", 48),
    StageDefinition("notary", "Notaría", 12, "Legal", 168),
    StageDefinition("disbursement", "Desembolso", 13, "Administración", 72),
    StageDefinition("closed", "Cerrada", 14, "Administración", None),
)

STAGE_BY_KEY = {stage.key: stage for stage in STAGES}

# Documentos que componen exclusivamente la etapa 03. Los códigos son los de
# document_type en dbpropify_be; cada documento aporta un tercio del avance.
DOCUMENTATION_DOCUMENT_TYPES = (
    ("107", "DNI del titular"),
    ("110", "Partida registral"),
    ("106", "Autovalúo"),
)

# Puertas obligatorias: la etapa destino no se habilita hasta cumplirlas.
STAGE_GATES = {
    "legal_review": ("mandatory_documents_complete",),
    "brokerage_contract": ("legal_review_approved",),
    "publication": (
        "mandatory_documents_complete",
        "legal_review_approved",
        "brokerage_contract_signed",
        "marketing_material_approved",
    ),
    "advertising": ("property_published", "campaign_budget_approved"),
    "accepted_offer": ("formal_offer_registered", "owner_acceptance_registered"),
    "notary": ("accepted_offer_registered", "closing_documents_complete"),
    "disbursement": ("notarial_signature_complete",),
    "closed": ("disbursement_confirmed",),
}

DEFAULT_REQUIREMENTS = {
    "documentation": (
        ("owner_dni", "DNI del propietario", True),
        ("registry_record", "Partida registral", True),
        ("property_appraisal", "Autovalúo", True),
    ),
    "legal_review": (("legal_review_approved", "Aprobación legal", True),),
    "brokerage_contract": (("brokerage_contract_signed", "Contrato de corretaje firmado", True),),
    "marketing": (
        ("photos_approved", "Fotografías aprobadas", True),
        ("copy_approved", "Texto comercial aprobado", True),
        ("video_approved", "Video aprobado", False),
        ("floor_plan_approved", "Plano aprobado", False),
    ),
    "publication": (
        ("property_published", "Publicación activa", True),
        ("campaign_budget_approved", "Presupuesto de campaña aprobado", True),
    ),
    "offer": (("formal_offer_registered", "Propuesta formal registrada", True),),
    "accepted_offer": (
        ("owner_acceptance_registered", "Aceptación del propietario", True),
        ("closing_documents_complete", "Documentos de cierre completos", True),
    ),
    "notary": (("notarial_signature_complete", "Firma notarial completada", True),),
    "disbursement": (("disbursement_confirmed", "Desembolso confirmado", True),),
}
