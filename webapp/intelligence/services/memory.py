"""
Servicio de memoria para gestionar contexto conversacional, extraer hechos
y mantener coherencia a lo largo de múltiples interacciones.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import json
import os
import re

from django.utils import timezone
from django.conf import settings

from ..models import User, Conversation, Fact, Role, AppConfig


class MemoryService:
    """
    Servicio centralizado para gestión de memoria de conversación.
    """
    
    # Configuración desde variables de entorno
    SESSION_TIMEOUT_HOURS = int(os.environ.get('MEMORY_SESSION_TIMEOUT_HOURS', 24))
    MAX_MESSAGES_BEFORE_SUMMARY = int(os.environ.get('MEMORY_MAX_MESSAGES_BEFORE_SUMMARY', 20))
    EXTRACT_FACTS_ENABLED = os.environ.get('MEMORY_EXTRACT_FACTS_ENABLED', 'true').lower() == 'true'
    
    def __init__(self, user_id: str = None):
        """
        Constructor para MemoryService.
        
        Args:
            user_id: ID del usuario (string UUID)
        """
        self.user_id = user_id
        if user_id:
            try:
                self.user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.user = None
        else:
            self.user = None
    
    @staticmethod
    def get_or_create_user(identifier: str, channel: str = 'unknown', metadata: Optional[Dict] = None) -> User:
        """
        Busca usuario por phone o email. Si no existe, crea nuevo con rol por defecto (nivel 1).
        
        Args:
            identifier: phone o email del usuario
            channel: canal de comunicación (web, whatsapp, mobile, etc.)
            metadata: metadatos adicionales del usuario
            
        Returns:
            Objeto User (existente o nuevo)
        """
        # Determinar si identifier es phone o email
        is_email = '@' in identifier
        
        user = None
        
        if is_email:
            try:
                user = User.objects.get(email=identifier)
            except User.DoesNotExist:
                pass
        else:
            try:
                user = User.objects.get(phone=identifier)
            except User.DoesNotExist:
                pass
        
        if not user:
            # Crear nuevo usuario con rol por defecto (nivel 1)
            try:
                default_role = Role.objects.filter(level=1).first()
                if not default_role:
                    default_role = Role.objects.create(
                        name='Usuario Básico',
                        level=1,
                        capabilities={'memory': True, 'knowledge_base': False, 'metrics': False, 'projects': False},
                        description='Rol por defecto para usuarios nuevos'
                    )
            except Exception:
                # Si hay error, crear rol mínimo
                default_role = Role.objects.create(
                    name='Usuario Básico',
                    level=1,
                    capabilities={'memory': True},
                    description='Rol por defecto'
                )
            
            # Preparar datos del usuario
            user_data = {
                'role': default_role,
                'is_active': True,
                'metadata': metadata or {}
            }
            
            if is_email:
                user_data['email'] = identifier
            else:
                user_data['phone'] = identifier
            
            # Agregar metadata de canal
            user_metadata = user_data['metadata']
            if 'channels' not in user_metadata:
                user_metadata['channels'] = []
            
            if channel not in user_metadata['channels']:
                user_metadata['channels'].append(channel)
            
            user_metadata['first_seen'] = timezone.now().isoformat()
            user_metadata['last_seen'] = timezone.now().isoformat()
            
            user = User.objects.create(**user_data)
        else:
            # Actualizar metadata existente
            if metadata:
                user_metadata = user.metadata or {}
                user_metadata.update(metadata)
                
                # Actualizar canal si es nuevo
                if 'channels' not in user_metadata:
                    user_metadata['channels'] = []
                
                if channel not in user_metadata['channels']:
                    user_metadata['channels'].append(channel)
                
                user_metadata['last_seen'] = timezone.now().isoformat()
                user.metadata = user_metadata
                user.save()
        
        return user
    
    @staticmethod
    def get_active_session(user_id: uuid.UUID, app_id: str, session_id: Optional[str] = None) -> Conversation:
        """
        Busca sesión activa (actualizada en últimas 24h). Si no existe, crea nueva.
        
        Args:
            user_id: ID del usuario
            app_id: ID de la app (ej: 'web-clientes', 'dashboard-admin')
            session_id: ID de sesión específico (opcional)
            
        Returns:
            Objeto Conversation (existente o nuevo)
        """
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValueError(f"Usuario con ID {user_id} no encontrado")
        
        try:
            app = AppConfig.objects.get(id=app_id)
        except AppConfig.DoesNotExist:
            # Crear app básica si no existe
            app = AppConfig.objects.create(
                id=app_id,
                name=f'App {app_id}',
                level=1,
                capabilities={'memory': True},
                is_active=True
            )
        
        # Calcular límite de tiempo para sesiones activas
        timeout_threshold = timezone.now() - timedelta(hours=MemoryService.SESSION_TIMEOUT_HOURS)
        
        # Buscar sesión activa
        conversation = None
        
        if session_id:
            # Buscar por session_id específico
            conversation = Conversation.objects.filter(
                user=user,
                app=app,
                session_id=session_id,
                is_active=True
            ).first()
            
            # Si la sesión existe pero es muy antigua, crear nueva
            if conversation and conversation.last_message_at < timeout_threshold:
                conversation.is_active = False
                conversation.save()
                conversation = None
        
        if not conversation:
            # Buscar cualquier sesión activa reciente para este usuario y app
            conversation = Conversation.objects.filter(
                user=user,
                app=app,
                is_active=True,
                last_message_at__gte=timeout_threshold
            ).order_by('-last_message_at').first()
        
        if not conversation:
            # Crear nueva sesión
            if not session_id:
                session_id = f'sess_{uuid.uuid4().hex[:16]}'
            
            conversation = Conversation.objects.create(
                user=user,
                app=app,
                session_id=session_id,
                messages=[],
                context_summary='',
                metadata={
                    'app_id': app_id,
                    'channel': 'unknown',
                    'created_at': timezone.now().isoformat()
                },
                is_active=True
            )
        
        return conversation
    
    @staticmethod
    def load_conversation_context(session_id: uuid.UUID) -> Dict[str, Any]:
        """
        Carga el contexto completo de una conversación.
        
        Args:
            session_id: ID de la sesión (UUID de Conversation)
            
        Returns:
            Dict con messages, facts, summary
        """
        try:
            conversation = Conversation.objects.get(id=session_id)
        except Conversation.DoesNotExist:
            raise ValueError(f"Conversación con ID {session_id} no encontrada")
        
        # Obtener hechos del usuario
        user_facts = Fact.objects.filter(
            user=conversation.user,
            is_active=True
        ).order_by('-confidence')[:10]  # Top 10 hechos más confiables
        
        facts_list = [
            {
                'subject': fact.subject,
                'relation': fact.relation,
                'object': fact.object,
                'confidence': fact.confidence
            }
            for fact in user_facts
        ]
        
        # Preparar mensajes recientes (últimos 10)
        recent_messages = conversation.messages[-10:] if conversation.messages else []
        
        return {
            'messages': recent_messages,
            'facts': facts_list,
            'summary': conversation.context_summary,
            'user_id': str(conversation.user.id),
            'session_id': conversation.session_id
        }
    
    @staticmethod
    def save_message(session_id: uuid.UUID, role: str, content: str) -> None:
        """
        Agrega un mensaje a la conversación. Si hay más de MAX_MESSAGES_BEFORE_SUMMARY,
        genera resumen y archiva mensajes antiguos.
        
        Args:
            session_id: ID de la sesión (UUID de Conversation)
            role: 'user' o 'assistant'
            content: contenido del mensaje
        """
        try:
            conversation = Conversation.objects.get(id=session_id)
        except Conversation.DoesNotExist:
            raise ValueError(f"Conversación con ID {session_id} no encontrada")
        
        # Crear objeto mensaje
        message = {
            'role': role,
            'content': content,
            'timestamp': timezone.now().isoformat()
        }
        
        # Agregar a la lista de mensajes
        messages = conversation.messages
        messages.append(message)
        
        # Verificar si necesitamos generar resumen
        if len(messages) > MemoryService.MAX_MESSAGES_BEFORE_SUMMARY:
            # Generar resumen de los primeros 10 mensajes
            old_messages = messages[:10]
            summary_text = MemoryService._generate_summary(old_messages, conversation.context_summary)
            
            # Actualizar resumen de contexto
            if conversation.context_summary:
                conversation.context_summary = f"{conversation.context_summary}\n{summary_text}"
            else:
                conversation.context_summary = summary_text
            
            # Mantener solo los últimos 10 mensajes
            conversation.messages = messages[-10:]
        else:
            conversation.messages = messages
        
        # Actualizar timestamp de último mensaje
        conversation.last_message_at = timezone.now()
        conversation.save()
    
    @staticmethod
    def _generate_summary(messages: List[Dict], existing_summary: str = '') -> str:
        """
        Genera un resumen de los mensajes proporcionados.
        
        En esta implementación básica, crea un resumen simple.
        En una implementación real, se usaría un LLM.
        
        Args:
            messages: Lista de mensajes a resumir
            existing_summary: Resumen existente para contexto
            
        Returns:
            Texto de resumen
        """
        if not messages:
            return ""
        
        # Contar mensajes por rol
        user_count = sum(1 for msg in messages if msg.get('role') == 'user')
        assistant_count = sum(1 for msg in messages if msg.get('role') == 'assistant')
        
        # Extraer temas principales (implementación simple)
        user_messages = [msg.get('content', '') for msg in messages if msg.get('role') == 'user']
        all_text = ' '.join(user_messages)[:500]  # Limitar longitud
        
        # Generar resumen básico
        summary = f"Conversación con {user_count} mensajes del usuario y {assistant_count} respuestas. "
        
        # Detectar temas comunes (implementación simplificada)
        topics = []
        if any(word in all_text.lower() for word in ['departamento', 'casa', 'propiedad', 'inmueble']):
            topics.append('búsqueda de propiedad')
        if any(word in all_text.lower() for word in ['precio', 'presupuesto', 'costo', 'dólar']):
            topics.append('presupuesto')
        if any(word in all_text.lower() for word in ['cayma', 'yanahuara', 'cercado', 'zona']):
            topics.append('ubicación')
        
        if topics:
            summary += f"Temas tratados: {', '.join(topics)}. "
        
        # Agregar marca de tiempo
        summary += f"(Resumen generado el {timezone.now().strftime('%d/%m/%Y %H:%M')})"
        
        return summary
    
    @staticmethod
    def extract_and_save_facts(user_id: uuid.UUID, message: str, response: str) -> List[Dict]:
        """
        Extrae hechos implícitos del mensaje y respuesta usando LLM.
        Primero intenta usar DeepSeek API, si falla usa reglas simples.

        Args:
            user_id: ID del usuario
            message: mensaje del usuario
            response: respuesta del asistente

        Returns:
            Lista de hechos extraídos
        """
        if not MemoryService.EXTRACT_FACTS_ENABLED:
            return []
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return []
        
        # Intentar extracción con DeepSeek primero
        deepseek_facts = MemoryService._extract_facts_with_deepseek(message, response)
        
        # Si DeepSeek extrajo hechos, usarlos
        if deepseek_facts:
            facts = deepseek_facts
        else:
            # Fallback a reglas simples
            facts = MemoryService._extract_facts_with_rules(message)
        
        # Guardar hechos en la base de datos
        saved_facts = []
        for fact_data in facts:
            # Verificar si el hecho ya existe
            existing = Fact.objects.filter(
                user=user,
                subject=fact_data['subject'],
                relation=fact_data['relation'],
                object=fact_data['object']
            ).first()
            
            if not existing:
                fact = Fact.objects.create(
                    user=user,
                    subject=fact_data['subject'],
                    relation=fact_data['relation'],
                    object=fact_data['object'],
                    confidence=fact_data['confidence'],
                    metadata={
                        'source': 'deepseek_extraction' if deepseek_facts else 'rule_extraction',
                        'extracted_at': timezone.now().isoformat(),
                        'original_message': message[:500]  # Guardar parte del mensaje original
                    }
                )
                saved_facts.append({
                    'id': str(fact.id),
                    'subject': fact.subject,
                    'relation': fact.relation,
                    'object': fact.object,
                    'confidence': fact.confidence
                })
        
        return saved_facts
    
    @staticmethod
    def _extract_facts_with_deepseek(message: str, response: str) -> List[Dict]:
        """
        Extrae hechos relevantes usando DeepSeek API con enfoque flexible.
        Identifica cualquier información relevante sobre el usuario, sus preferencias,
        experiencias, o contexto mencionado en la conversación.
        
        Args:
            message: Mensaje del usuario
            response: Respuesta del asistente
            
        Returns:
            Lista de hechos extraídos en formato (sujeto, relación, objeto) o lista vacía si falla
        """
        try:
            from .llm import LLMService
            
            # Combinar mensaje y respuesta para contexto
            combined_text = f"Usuario: {message}\nAsistente: {response}"
            
            # Prompt para extracción flexible de hechos
            system_prompt = """Eres un experto en extracción de información relevante de conversaciones.
Tu tarea es identificar hechos importantes, preferencias, experiencias o información contextual
que el usuario ha compartido en esta conversación.

INSTRUCCIONES:
1. Analiza el texto y extrae cualquier información relevante sobre:
   - El usuario (nombre, trabajo, intereses, experiencias, preferencias)
   - Contexto personal (dónde vive, trabaja, estudia)
   - Eventos mencionados (pasados, presentes o futuros)
   - Preferencias y gustos personales
   - Cualquier dato que pueda ser útil para futuras interacciones

2. Para cada hecho identificado, estructura la información como una tripleta:
   - SUJETO: Entidad principal (usualmente "usuario" o entidad mencionada)
   - RELACIÓN: Tipo de información (ej: "trabaja_en", "vive_en", "le_gusta", "mencionó", "tiene", "prefiere")
   - OBJETO: Valor o descripción del hecho

3. Considera relevante cualquier información que:
   - Sea personal o única al usuario
   - Podría ser útil recordar en futuras conversaciones
   - Muestra preferencias, hábitos o contexto personal
   - Incluye eventos o experiencias compartidas

4. Ejemplos de hechos válidos:
   - Usuario mencionó que trabaja en el área de sistemas → (usuario, trabaja_en_area, sistemas)
   - Usuario dijo que vive en Arequipa → (usuario, vive_en, Arequipa)
   - Usuario compartió que ayer fue a comer sushi → (usuario, mencionó_evento, ayer fue a comer sushi)
   - Usuario expresó interés en departamentos en Cayma → (usuario, interesa_propiedades_en, Cayma)
   - Usuario mencionó que le gusta el café → (usuario, le_gusta, café)

5. Devuelve SOLO un array JSON con objetos que tengan: subject, relation, object, confidence
   - confidence: 0.0 a 1.0 basado en qué tan explícita es la información

FORMATO DE SALIDA:
[
  {
    "subject": "usuario",
    "relation": "trabaja_en_area",
    "object": "sistemas",
    "confidence": 0.9
  },
  {
    "subject": "usuario",
    "relation": "vive_en",
    "object": "Arequipa",
    "confidence": 0.85
  }
]"""
            
            messages = [
                {"role": "user", "content": f"Extrae hechos relevantes de esta conversación:\n\n{combined_text}"}
            ]
            
            # Llamar a DeepSeek con prompt personalizado
            success, api_message, api_response = LLMService._call_deepseek_api(
                messages=messages,
                system_prompt=system_prompt
            )
            
            if not success or not api_response:
                return []
            
            # Extraer JSON de la respuesta
            content = api_response.get("content", "")
            if not content:
                return []
            
            # Buscar JSON en la respuesta (puede estar entre ```json ``` o directamente)
            import json
            import re
            
            # Intentar encontrar JSON en la respuesta
            json_match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    facts = json.loads(json_str)
                    # Validar estructura básica
                    if isinstance(facts, list):
                        validated_facts = []
                        for fact in facts:
                            if all(key in fact for key in ['subject', 'relation', 'object']):
                                # Asegurar confidence
                                if 'confidence' not in fact:
                                    fact['confidence'] = 0.8
                                validated_facts.append(fact)
                        return validated_facts
                except json.JSONDecodeError:
                    pass
            
            # Si no se pudo extraer JSON estructurado, intentar análisis más simple
            # Buscar patrones de tripletas en texto plano
            facts = []
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                # Buscar patrones como "usuario trabaja_en_area sistemas"
                if 'usuario' in line.lower() and any(rel in line.lower() for rel in ['trabaja', 'vive', 'le gusta', 'mencionó', 'tiene', 'prefiere']):
                    # Extraer partes
                    parts = line.split()
                    if len(parts) >= 3:
                        # Intentar inferir estructura
                        subject = 'usuario'
                        relation = parts[1] if len(parts) > 1 else 'mencionó'
                        object_text = ' '.join(parts[2:])[:150]
                        
                        facts.append({
                            'subject': subject,
                            'relation': relation,
                            'object': object_text,
                            'confidence': 0.7
                        })
            
            return facts
            
        except Exception as e:
            # Log error pero continuar con reglas simples
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error en extracción flexible con DeepSeek: {str(e)}")
            return []
    
    @staticmethod
    def _extract_facts_with_rules(message: str) -> List[Dict]:
        """
        Extrae hechos usando reglas simples (fallback).
        
        Args:
            message: Mensaje del usuario
            
        Returns:
            Lista de hechos extraídos
        """
        facts = []
        
        # Detectar nombre
        name_keywords = ['me llamo', 'soy', 'nombre es', 'mi nombre']
        for keyword in name_keywords:
            if keyword in message.lower():
                parts = message.lower().split(keyword)
                if len(parts) > 1:
                    name = parts[1].strip().split()[0].capitalize()
                    if len(name) > 1:  # Evitar nombres de una letra
                        facts.append({
                            'subject': 'usuario',
                            'relation': 'tiene_nombre',
                            'object': name,
                            'confidence': 0.9
                        })
                        break
        
        # Detectar área de trabajo
        work_keywords = ['trabajo en', 'soy de', 'área de', 'departamento de', 'trabajo en el área']
        for keyword in work_keywords:
            if keyword in message.lower():
                parts = message.lower().split(keyword)
                if len(parts) > 1:
                    area = parts[1].strip().split('.')[0].split(',')[0].strip()
                    if area and len(area) > 2:
                        facts.append({
                            'subject': 'usuario',
                            'relation': 'trabaja_en_area',
                            'object': area.capitalize(),
                            'confidence': 0.85
                        })
                        break
        
        # Detectar empresa/inmobiliaria
        company_keywords = ['inmobiliaria', 'propify', 'propifai', 'empresa', 'trabajo en']
        for keyword in company_keywords:
            if keyword in message.lower():
                # Buscar contexto de empresa
                if 'propify' in message.lower() or 'propifai' in message.lower():
                    facts.append({
                        'subject': 'usuario',
                        'relation': 'trabaja_en',
                        'object': 'Propifai',
                        'confidence': 0.9
                    })
                    break
        
        # Detectar ubicación
        location_keywords = ['cayma', 'yanahuara', 'cercado', 'sachaca', 'miraflores', 'paucarpata', 'arequipa', 'vivo en', 'vivo en']
        for keyword in location_keywords:
            if keyword in message.lower():
                facts.append({
                    'subject': 'usuario',
                    'relation': 'vive_en',
                    'object': keyword.capitalize(),
                    'confidence': 0.75
                })
                break
        
        # Detectar búsqueda de propiedad
        property_keywords = ['departamento', 'casa', 'propiedad', 'inmueble', 'terreno', 'local']
        for keyword in property_keywords:
            if keyword in message.lower():
                facts.append({
                    'subject': 'usuario',
                    'relation': 'busca',
                    'object': keyword,
                    'confidence': 0.85
                })
                break
        
        # Detectar presupuesto
        price_patterns = [
            r'(\$|USD|S\/\.|soles?)\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',
            r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(\$|USD|S\/\.|soles?)'
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            if matches:
                for match in matches:
                    amount = match[1] if match[0] in ['$', 'USD', 'S/.', 'soles'] else match[0]
                    currency = match[0] if match[0] in ['$', 'USD', 'S/.', 'soles'] else match[1]
                    facts.append({
                        'subject': 'usuario',
                        'relation': 'presupuesto',
                        'object': f"{amount} {currency}",
                        'confidence': 0.8
                    })
                    break
        
        # Detectar eventos personales (ej: "ayer fui a comer")
        event_patterns = [
            r'(ayer|hoy|mañana|la semana pasada)\s+(fui|fuimos|voy|vamos|comí|comimos|estuve|estuvimos)',
            r'(me gusta|disfruto|me encanta)\s+[a-záéíóúñ\s]+',
        ]
        
        for pattern in event_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            if matches:
                # Extraer fragmento relevante
                for match in matches:
                    if isinstance(match, tuple):
                        event_text = ' '.join(match)
                    else:
                        event_text = match
                    
                    # Buscar contexto alrededor del match
                    start = max(0, message.lower().find(event_text) - 50)
                    end = min(len(message), start + 100)
                    context = message[start:end].strip()
                    
                    if context:
                        facts.append({
                            'subject': 'usuario',
                            'relation': 'menciono_evento',
                            'object': context[:150],
                            'confidence': 0.7
                        })
                        break
        
        return facts
    
    @staticmethod
    def build_prompt_with_memory(context: Dict[str, Any], capability_instructions: str = '') -> str:
        """
        Construye el prompt para el LLM con memoria de contexto.
        
        Args:
            context: Diccionario con messages, facts, summary (de load_conversation_context)
            capability_instructions: Instrucciones específicas de capacidades según nivel de app
            
        Returns:
            Prompt completo para enviar al LLM
        """
        user_facts = context.get('facts', [])
        context_summary = context.get('summary', '')
        recent_messages = context.get('messages', [])
        user_id = context.get('user_id', 'desconocido')
        
        # Formatear hechos conocidos
        facts_text = ""
        if user_facts:
            facts_lines = []
            for fact in user_facts:
                facts_lines.append(f"- {fact['subject']} {fact['relation']} {fact['object']} (confianza: {fact['confidence']})")
            facts_text = "\n".join(facts_lines)
        else:
            facts_text = "No hay hechos conocidos sobre este usuario aún."
        
        # Formatear conversación reciente
        conversation_text = ""
        for msg in recent_messages:
            role = "Usuario" if msg.get('role') == 'user' else "Asistente"
            content = msg.get('content', '')
            conversation_text += f"{role}: {content}\n"
        
        # Construir prompt completo según SPEC-002
        prompt = f"""Eres el asistente inteligente de Propifai, una inmobiliaria en Arequipa, Perú.

CONTEXTO DEL USUARIO:
- ID: {user_id}
- Hechos conocidos:
{facts_text}
- Resumen histórico: {context_summary if context_summary else 'No hay resumen histórico disponible.'}

CONVERSACIÓN RECIENTE:
{conversation_text}

INSTRUCCIONES DE CAPACIDADES:
{capability_instructions if capability_instructions else 'Puedes acceder a la base de datos de propiedades, realizar matching con requerimientos, y proporcionar análisis de mercado.'}

INSTRUCCIONES PARA EL ASISTENTE:
1. Usa el contexto del usuario para personalizar tus respuestas.
2. Mantén coherencia con conversaciones anteriores.
3. Si el usuario menciona información nueva que pueda ser relevante para futuras interacciones, anótala mentalmente.
4. Sé conciso pero útil, enfocado en el mercado inmobiliario de Arequipa.
5. Si no sabes algo, admítelo y ofrece buscar la información.

Ahora responde al último mensaje del usuario."""
        
        return prompt
    
    def _normalize_text(self, text: str) -> str:
        """
        Normaliza texto para comparación: minúsculas, elimina tildes y caracteres especiales.
        
        Args:
            text: Texto a normalizar
            
        Returns:
            Texto normalizado
        """
        if not text:
            return ""
        
        # Convertir a minúsculas
        text = text.lower()
        
        # Reemplazar tildes (implementación básica)
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n',
            'ü': 'u', '¿': '', '?': '', '¡': '', '!': '', '.': '', ',': '',
            ';': '', ':': '', '(': '', ')': '', '[': '', ']': '', '{': '',
            '}': '', '"': '', "'": '', '`': '', '~': '', '@': '', '#': '',
            '$': '', '%': '', '^': '', '&': '', '*': '', '+': '', '=': '',
            '<': '', '>': '', '/': '', '\\': '', '|': ''
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Eliminar espacios extra
        text = ' '.join(text.split())
        
        return text
    
    def _calculate_relevance_score(self, query: str, text: str, base_confidence: float) -> float:
        """
        Calcula puntuación de relevancia entre consulta y texto.
        
        Args:
            query: Consulta del usuario (normalizada)
            text: Texto a comparar (normalizado)
            base_confidence: Confianza base del hecho (0.0-1.0)
            
        Returns:
            Puntuación de relevancia (0.0-1.0)
        """
        if not query or not text:
            return 0.0
        
        # Peso de la confianza base
        confidence_weight = 0.3
        
        # Peso de coincidencia exacta de palabras
        exact_match_weight = 0.4
        
        # Peso de coincidencia parcial (substrings)
        partial_match_weight = 0.3
        
        score = 0.0
        
        # Contribución de la confianza base
        score += base_confidence * confidence_weight
        
        # Dividir en palabras
        query_words = set(query.split())
        text_words = set(text.split())
        
        # Coincidencia exacta de palabras
        common_words = query_words.intersection(text_words)
        if common_words:
            exact_match_ratio = len(common_words) / max(len(query_words), 1)
            score += exact_match_ratio * exact_match_weight
        
        # Coincidencia parcial (substrings)
        # Verificar si palabras de la consulta aparecen como substrings en el texto
        partial_matches = 0
        for q_word in query_words:
            if len(q_word) > 2 and q_word in text:
                partial_matches += 1
        
        if partial_matches > 0:
            partial_match_ratio = partial_matches / max(len(query_words), 1)
            score += partial_match_ratio * partial_match_weight
        
        # Bonus por coincidencia de palabras clave importantes
        important_keywords = ['trabajo', 'trabaja', 'area', 'área', 'sistemas', 'empresa',
                             'propify', 'vive', 'yanahuara', 'cayma', 'nombre', 'llama',
                             'presupuesto', 'familia', 'evento', 'comer', 'sushi']
        
        for keyword in important_keywords:
            normalized_keyword = self._normalize_text(keyword)
            if normalized_keyword in query and normalized_keyword in text:
                score += 0.1  # Bonus pequeño
        
        # Asegurar que el score esté entre 0.0 y 1.0
        return min(max(score, 0.0), 1.0)
    
    def get_relevant_context(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Obtiene contexto relevante de la memoria del usuario basado en la consulta.
        
        Args:
            query: Consulta del usuario
            limit: Número máximo de hechos/conversaciones a retornar
            
        Returns:
            Lista de diccionarios con contexto relevante
        """
        if not self.user:
            return []
        
        # Obtener todos los hechos del usuario (más de los necesarios para filtrar)
        facts = Fact.objects.filter(
            user=self.user,
            is_active=True
        ).order_by('-confidence')[:20]  # Obtener más para filtrar
        
        # Obtener conversaciones recientes
        conversations = Conversation.objects.filter(
            user=self.user,
            is_active=True
        ).order_by('-last_message_at')[:3]
        
        context_items = []
        
        # Agregar hechos con puntuación de relevancia
        query_lower = self._normalize_text(query)
        for fact in facts:
            fact_text = f"{fact.subject} {fact.relation} {fact.object}"
            normalized_fact = self._normalize_text(fact_text)
            
            # Calcular puntuación de relevancia
            relevance_score = self._calculate_relevance_score(
                query_lower, normalized_fact, fact.confidence
            )
            
            context_items.append({
                'type': 'fact',
                'content': fact_text,
                'confidence': fact.confidence,
                'relevance_score': relevance_score,
                'source': 'memory',
                'timestamp': fact.created_at.isoformat() if fact.created_at else None,
                'fact_id': fact.id
            })
        
        # Agregar mensajes recientes de conversaciones
        for conv in conversations:
            if conv.messages:
                recent_messages = conv.messages[-3:]  # Últimos 3 mensajes
                for msg in recent_messages:
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    if content:
                        normalized_content = self._normalize_text(content)
                        relevance_score = self._calculate_relevance_score(
                            query_lower, normalized_content, 0.5
                        )
                        
                        context_items.append({
                            'type': 'conversation',
                            'role': role,
                            'content': content[:200],  # Limitar longitud
                            'relevance_score': relevance_score,
                            'source': 'conversation',
                            'conversation_id': str(conv.id),
                            'timestamp': msg.get('timestamp')
                        })
        
        # Ordenar por puntuación de relevancia (más relevante primero)
        context_items.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        # Tomar los más relevantes
        relevant_items = context_items[:limit]
        
        # Si no hay items con relevancia > 0, devolver los más recientes/hechos con mayor confianza
        if not relevant_items or all(item.get('relevance_score', 0) <= 0 for item in relevant_items):
            # Devolver hechos recientes con mayor confianza
            recent_facts = Fact.objects.filter(
                user=self.user,
                is_active=True
            ).order_by('-created_at', '-confidence')[:limit]
            
            relevant_items = []
            for fact in recent_facts:
                relevant_items.append({
                    'type': 'fact',
                    'content': f"{fact.subject} {fact.relation} {fact.object}",
                    'confidence': fact.confidence,
                    'relevance_score': 0.1,  # Puntuación baja para indicar que no es muy relevante
                    'source': 'memory',
                    'timestamp': fact.created_at.isoformat() if fact.created_at else None,
                    'fact_id': fact.id
                })
        
        return relevant_items[:limit]
    
    def add_fact(self, fact_text: str, category: str, confidence_score: float,
                 source: str = 'chat_web', metadata: Dict = None) -> Dict:
        """
        Agrega un hecho a la memoria del usuario.
        
        Args:
            fact_text: Texto del hecho
            category: Categoría del hecho
            confidence_score: Puntuación de confianza (0.0-1.0)
            source: Fuente del hecho
            metadata: Metadatos adicionales
            
        Returns:
            Diccionario con información del hecho creado
        """
        if not self.user:
            return {'error': 'Usuario no disponible'}
        
        # Parsear fact_text para extraer subject, relation, object si es posible
        # Implementación simple: tratar todo como subject
        subject = 'usuario'
        relation = 'mencionó'
        object_text = fact_text[:100]  # Limitar longitud
        
        fact = Fact.objects.create(
            user=self.user,
            subject=subject,
            relation=relation,
            object=object_text,
            confidence=confidence_score,
            category=category,
            metadata={
                'source': source,
                'added_at': timezone.now().isoformat(),
                'original_text': fact_text,
                **(metadata or {})
            }
        )
        
        return {
            'id': str(fact.id),
            'subject': fact.subject,
            'relation': fact.relation,
            'object': fact.object,
            'confidence': fact.confidence,
            'category': fact.category
        }