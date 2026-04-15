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
        En esta implementación, usa reglas simples. En producción, se integraría con DeepSeek.
        
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
        
        # Hechos predefinidos a detectar (implementación simplificada)
        facts = []
        
        # Detectar nombre
        name_keywords = ['me llamo', 'soy', 'nombre es', 'mi nombre']
        for keyword in name_keywords:
            if keyword in message.lower():
                # Extraer nombre (implementación simple)
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
        
        # Detectar ubicación
        location_keywords = ['cayma', 'yanahuara', 'cercado', 'sachaca', 'miraflores', 'paucarpata']
        for keyword in location_keywords:
            if keyword in message.lower():
                facts.append({
                    'subject': 'usuario',
                    'relation': 'ubicacion_preferida',
                    'object': keyword.capitalize(),
                    'confidence': 0.75
                })
                break
        
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
                        'source': 'auto_extraction',
                        'extracted_at': timezone.now().isoformat()
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