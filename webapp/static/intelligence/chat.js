// chat.js - Versión simplificada y funcional para Propifai Intelligence Chat

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM cargado, inicializando chat...');
    
    // Estado de la aplicación
    const state = {
        messages: [],
        files: [],
        memory: {},
        activeInstruction: 'general',
        isThinking: false,
        sidebarVisible: true,
        currentConversationId: null
    };

    // Elementos DOM
    const elements = {
        messagesContainer: document.getElementById('messages-container'),
        chatInput: document.getElementById('chat-input'),
        sendButton: document.getElementById('send-button'),
        sidebar: document.getElementById('sidebar'),
        memoryContent: document.getElementById('memory-content'),
        instructionsList: document.getElementById('instructions-list'),
        filesList: document.getElementById('files-list'),
        uploadTrigger: document.getElementById('upload-trigger'),
        thinkingIndicator: document.getElementById('thinking-indicator'),
        clearChat: document.getElementById('clear-chat'),
        exportChat: document.getElementById('export-chat'),
        attachFile: document.getElementById('attach-file'),
        refreshMemory: document.getElementById('refresh-memory'),
        addInstruction: document.getElementById('add-instruction'),
        fileCount: document.getElementById('file-count'),
        toggleSidebarBtn: document.querySelector('.toggle-sidebar')
    };

    // URLs API
    const apiUrls = {
        chat: '/api/v1/intelligence/chat-web/api/',
        upload: '/api/v1/intelligence/chat-web/upload/'
    };

    // Inicializar
    init();

    function init() {
        console.log('Inicializando chat.js...');
        console.log('Elementos encontrados:', {
            sendButton: elements.sendButton ? 'Sí' : 'No',
            chatInput: elements.chatInput ? 'Sí' : 'No',
            clearChat: elements.clearChat ? 'Sí' : 'No',
            exportChat: elements.exportChat ? 'Sí' : 'No'
        });
        
        bindEvents();
        loadInitialData();
        setupAutoResize();
        
        console.log('Inicialización completada');
    }

    function bindEvents() {
        console.log('Vinculando eventos...');
        
        // Envío de mensajes
        if (elements.sendButton) {
            elements.sendButton.addEventListener('click', sendMessage);
            console.log('Evento click vinculado a sendButton');
        } else {
            console.error('sendButton no encontrado');
        }
        
        if (elements.chatInput) {
            elements.chatInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
            console.log('Evento keydown vinculado a chatInput');
        } else {
            console.error('chatInput no encontrado');
        }

        // Toggle sidebar
        if (elements.toggleSidebarBtn) {
            elements.toggleSidebarBtn.addEventListener('click', toggleSidebar);
            console.log('Evento click vinculado a toggle-sidebar');
        }

        // Instrucciones
        if (elements.instructionsList) {
            elements.instructionsList.addEventListener('click', function(e) {
                const instructionItem = e.target.closest('.instruction-item');
                if (instructionItem) {
                    setActiveInstruction(instructionItem.dataset.instruction);
                }
            });
            console.log('Evento click vinculado a instructionsList');
        }

        // Archivos
        if (elements.uploadTrigger) {
            elements.uploadTrigger.addEventListener('click', triggerFileUpload);
            console.log('Evento click vinculado a uploadTrigger');
        }
        
        if (elements.attachFile) {
            elements.attachFile.addEventListener('click', triggerFileUpload);
            console.log('Evento click vinculado a attachFile');
        }

        // Acciones
        if (elements.clearChat) {
            elements.clearChat.addEventListener('click', clearChat);
            console.log('Evento click vinculado a clearChat');
        }
        
        if (elements.exportChat) {
            elements.exportChat.addEventListener('click', exportChat);
            console.log('Evento click vinculado a exportChat');
        }
        
        if (elements.refreshMemory) {
            elements.refreshMemory.addEventListener('click', loadMemory);
            console.log('Evento click vinculado a refreshMemory');
        }
        
        if (elements.addInstruction) {
            elements.addInstruction.addEventListener('click', addCustomInstruction);
            console.log('Evento click vinculado a addInstruction');
        }
        
        console.log('Vinculación de eventos completada');
    }

    function loadInitialData() {
        loadMemory();
        updateFileCount();
    }

    function loadMemory() {
        console.log('Cargando memoria...');
        
        // Obtener datos reales del DOM (renderizados por Django)
        const userElements = document.querySelectorAll('.memory-value');
        if (userElements.length >= 5) {
            const userName = userElements[0].textContent.trim();
            const userLevel = userElements[1].textContent.trim();
            const activeContext = userElements[2].textContent.trim();
            const factsCount = userElements[3].textContent.trim();
            const collectionsCount = userElements[4].textContent.trim();
            
            // Extraer solo el número del nivel
            const levelMatch = userLevel.match(/Nivel\s*(\d+)/);
            const levelNumber = levelMatch ? levelMatch[1] : "1";
            
            // Extraer solo el número de hechos
            const factsMatch = factsCount.match(/(\d+)/);
            const factsNumber = factsMatch ? factsMatch[1] : "0";
            
            // Extraer solo el número de colecciones
            const collectionsMatch = collectionsCount.match(/(\d+)/);
            const collectionsNumber = collectionsMatch ? collectionsMatch[1] : "0";
            
            // Datos reales del backend
            state.memory = {
                user: {
                    name: userName,
                    level: `Nivel ${levelNumber}`,
                    lastActive: "Activo ahora"
                },
                context: {
                    activeProject: activeContext !== "Sin contexto activo" ? activeContext : "Sin proyecto activo",
                    recentSearches: ["Propiedades", "Mercado", "Análisis"]
                },
                facts: [
                    `Tienes ${factsNumber} hechos registrados en tu memoria`,
                    `Acceso a ${collectionsNumber} colecciones de inteligencia`,
                    `Nivel de acceso: ${levelNumber}`
                ]
            };
            
            console.log('Memoria cargada:', state.memory);
        } else {
            // Fallback a datos mínimos
            state.memory = {
                user: {
                    name: "Usuario",
                    level: "Nivel 1",
                    lastActive: "Activo ahora"
                },
                context: {
                    activeProject: "Sin proyecto activo",
                    recentSearches: []
                },
                facts: [
                    "Sistema de inteligencia inmobiliaria",
                    "Asistente para búsqueda y análisis"
                ]
            };
            console.log('Memoria cargada (fallback):', state.memory);
        }
        
        renderMemory();
    }

    function renderMemory() {
        if (!elements.memoryContent) return;
        
        const { memory } = state;
        
        let html = `
            <div class="memory-item">
                <div class="memory-label"><i class="fas fa-user"></i> Usuario</div>
                <div class="memory-value">${memory.user?.name || 'No disponible'}</div>
            </div>
            <div class="memory-item">
                <div class="memory-label"><i class="fas fa-shield-alt"></i> Nivel</div>
                <div class="memory-value">${memory.user?.level || 'Nivel 1'}</div>
            </div>
            <div class="memory-item">
                <div class="memory-label"><i class="fas fa-project-diagram"></i> Proyecto activo</div>
                <div class="memory-value">${memory.context?.activeProject || 'Sin proyecto activo'}</div>
            </div>
        `;

        if (memory.facts && memory.facts.length > 0) {
            html += `
                <div class="memory-item">
                    <div class="memory-label"><i class="fas fa-lightbulb"></i> Hechos importantes</div>
                    <div class="memory-value">
                        <ul style="margin: 0; padding-left: 20px;">
                            ${memory.facts.slice(0, 3).map(fact => `<li>${fact}</li>`).join('')}
                        </ul>
                    </div>
                </div>
            `;
        }

        elements.memoryContent.innerHTML = html;
        console.log('Memoria renderizada');
    }

    async function sendMessage() {
        console.log('Intentando enviar mensaje...');
        const message = elements.chatInput.value.trim();
        
        if (!message || state.isThinking) {
            console.log('Mensaje vacío o pensando, no se envía');
            return;
        }

        // Agregar mensaje del usuario
        addMessage('user', message);
        elements.chatInput.value = '';
        updateSendButtonState();
        
        // Mostrar indicador de pensamiento
        setStateThinking(true);

        try {
            console.log('Enviando mensaje a API:', message);
            
            // Obtener user_id del contexto de Django si está disponible
            const user_id = window.djangoContext?.user_id || '';
            
            // Construir datos de solicitud según lo que espera el backend
            const requestData = {
                message: message,
                use_memory: true,
                use_rag: true,
                collections: []
            };

            // Si hay un user_id válido (no vacío), incluirlo
            if (user_id && user_id.trim() !== '') {
                requestData.user_id = user_id;
            } else {
                // Si no hay user_id, usar un email temporal para pasar la validación
                requestData.email = 'usuario_temporal@propifai.com';
            }

            // Incluir conversationId si existe
            if (state.currentConversationId) {
                requestData.conversation_id = state.currentConversationId;
            }

            console.log('Datos enviados:', requestData);

            const response = await fetch(apiUrls.chat, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                credentials: 'same-origin',
                body: JSON.stringify(requestData)
            });

            console.log('Respuesta recibida, status:', response.status);
            
            if (!response.ok) {
                // Intentar obtener más detalles del error
                let errorDetail = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorDetail += ` - ${JSON.stringify(errorData)}`;
                } catch (e) {
                    // Ignorar si no se puede parsear JSON
                }
                throw new Error(errorDetail);
            }

            const data = await response.json();
            console.log('Datos recibidos:', data);
            
            // Agregar respuesta del asistente
            addMessage('assistant', data.response || data.message || 'No se recibió respuesta');
            
            // Actualizar memoria si viene en la respuesta
            if (data.memory) {
                state.memory = { ...state.memory, ...data.memory };
                renderMemory();
            }

            // Actualizar ID de conversación
            if (data.conversationId) {
                state.currentConversationId = data.conversationId;
            }

        } catch (error) {
            console.error('Error enviando mensaje:', error);
            addMessage('system', `Error: ${error.message}. Por favor, intenta nuevamente.`);
        } finally {
            setStateThinking(false);
        }
    }

    function addMessage(role, content) {
        const message = {
            id: Date.now(),
            role: role,
            content: content,
            timestamp: new Date().toLocaleTimeString('es-PE', { 
                hour: '2-digit', 
                minute: '2-digit' 
            })
        };

        state.messages.push(message);
        renderMessage(message);
        scrollToBottom();
    }

    function renderMessage(message) {
        if (!elements.messagesContainer) return;
        
        const messageElement = document.createElement('div');
        messageElement.className = `message message-${message.role}`;
        
        let content = message.content;
        if (typeof content === 'object') {
            content = JSON.stringify(content, null, 2);
        }
        
        messageElement.innerHTML = `
            <div>${escapeHtml(content)}</div>
            <div class="message-time">${message.timestamp}</div>
        `;
        
        elements.messagesContainer.appendChild(messageElement);
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function setupAutoResize() {
        if (!elements.chatInput) return;
        
        const textarea = elements.chatInput;
        
        textarea.addEventListener('input', function() {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
            updateSendButtonState();
        });
    }

    function updateSendButtonState() {
        if (!elements.sendButton) return;
        
        const hasText = elements.chatInput ? elements.chatInput.value.trim().length > 0 : false;
        elements.sendButton.disabled = !hasText || state.isThinking;
    }

    function setStateThinking(isThinking) {
        state.isThinking = isThinking;
        
        if (isThinking) {
            if (elements.thinkingIndicator) {
                elements.thinkingIndicator.classList.add('active');
            }
            if (elements.chatInput) {
                elements.chatInput.disabled = true;
            }
            if (elements.sendButton) {
                elements.sendButton.disabled = true;
            }
            addTypingIndicator();
        } else {
            if (elements.thinkingIndicator) {
                elements.thinkingIndicator.classList.remove('active');
            }
            if (elements.chatInput) {
                elements.chatInput.disabled = false;
            }
            updateSendButtonState();
            removeTypingIndicator();
        }
    }

    function addTypingIndicator() {
        if (!elements.messagesContainer) return;
        
        const typingElement = document.createElement('div');
        typingElement.className = 'typing-indicator';
        typingElement.id = 'typing-indicator';
        typingElement.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <span>Escribiendo...</span>
        `;
        
        elements.messagesContainer.appendChild(typingElement);
        scrollToBottom();
    }

    function removeTypingIndicator() {
        const typingElement = document.getElementById('typing-indicator');
        if (typingElement) {
            typingElement.remove();
        }
    }

    function scrollToBottom() {
        if (elements.messagesContainer) {
            elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
        }
    }

    function toggleSidebar() {
        if (!elements.sidebar) return;
        
        state.sidebarVisible = !state.sidebarVisible;
        elements.sidebar.classList.toggle('collapsed');
        
        const toggleButton = document.querySelector('.toggle-sidebar i');
        if (toggleButton) {
            toggleButton.className = state.sidebarVisible ? 'fas fa-chevron-left' : 'fas fa-chevron-right';
        }
    }

    function setActiveInstruction(instruction) {
        state.activeInstruction = instruction;
        
        // Actualizar UI
        document.querySelectorAll('.instruction-item').forEach(item => {
            item.classList.toggle('active', item.dataset.instruction === instruction);
        });
        
        // Agregar mensaje del sistema
        const instructionNames = {
            general: 'Asistente general',
            analisis: 'Análisis de mercado',
            busqueda: 'Búsqueda de propiedades',
            requerimientos: 'Gestión de requerimientos'
        };
        
        addMessage('system', `Modo cambiado a: ${instructionNames[instruction] || instruction}`);
    }

    function addCustomInstruction() {
        const instruction = prompt('Ingresa una nueva instrucción personalizada:');
        if (instruction) {
            const instructionItem = document.createElement('div');
            instructionItem.className = 'instruction-item';
            instructionItem.dataset.instruction = 'custom';
            instructionItem.innerHTML = `<i class="fas fa-plus-circle"></i> ${instruction}`;
            
            if (elements.instructionsList) {
                elements.instructionsList.appendChild(instructionItem);
            }
            setActiveInstruction('custom');
        }
    }

    function triggerFileUpload() {
        console.log('Trigger file upload - creando input de archivo');
        // Crear input de tipo file dinámicamente
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.multiple = true;
        fileInput.accept = '.pdf,.jpg,.jpeg,.png,.gif,.txt,.xlsx,.xls,.doc,.docx';
        fileInput.style.display = 'none';
        
        // Manejar selección de archivos
        fileInput.addEventListener('change', function(event) {
            const files = Array.from(event.target.files);
            if (files.length === 0) return;
            
            console.log(`Archivos seleccionados: ${files.length}`);
            
            // Subir cada archivo
            files.forEach(file => {
                uploadFile(file);
            });
            
            // Limpiar input
            fileInput.value = '';
        });
        
        // Agregar al DOM y disparar click
        document.body.appendChild(fileInput);
        fileInput.click();
        // Remover después de usar
        setTimeout(() => {
            document.body.removeChild(fileInput);
        }, 100);
    }
    
    function uploadFile(file) {
        console.log(`Subiendo archivo: ${file.name} (${file.size} bytes)`);
        
        // Validar tamaño (max 10MB)
        const maxSize = 10 * 1024 * 1024; // 10MB
        if (file.size > maxSize) {
            alert(`El archivo ${file.name} es demasiado grande (máximo 10MB)`);
            return;
        }
        
        // Validar tipo - manejar múltiples tipos MIME para Excel y casos donde file.type esté vacío
        const allowedTypes = [
            'image/jpeg', 'image/png', 'image/gif',
            'application/pdf', 'text/plain',
            // Tipos MIME para Excel
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', // .xlsx
            'application/vnd.ms-excel', // .xls
            'application/excel',
            'application/x-excel',
            'application/x-msexcel',
            // Tipos MIME para Word
            'application/msword', // .doc
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // .docx
            // Otros tipos de Office
            'application/vnd.oasis.opendocument.spreadsheet', // .ods
            'application/vnd.oasis.opendocument.text' // .odt
        ];
        
        // También validar por extensión como fallback
        const allowedExtensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.txt',
                                  '.xlsx', '.xls', '.doc', '.docx', '.ods', '.odt'];
        
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        const fileType = file.type.toLowerCase();
        
        // Verificar si el tipo MIME está permitido O la extensión está permitida
        const isTypeAllowed = allowedTypes.some(type => fileType.includes(type.toLowerCase().replace('*', '')));
        const isExtensionAllowed = allowedExtensions.includes(fileExtension);
        
        if (!isTypeAllowed && !isExtensionAllowed) {
            alert(`Tipo de archivo no permitido: ${file.type || 'tipo desconocido'}. Solo se permiten PDF, imágenes, texto y documentos de Office.`);
            return;
        }
        
        // Mostrar indicador de subida
        addMessage('system', `Subiendo archivo: ${file.name}...`);
        
        // Crear FormData
        const formData = new FormData();
        formData.append('file', file);
        
        // Obtener user_id y conversation_id del estado (si existen)
        const user_id = state.user?.id || '';
        const conversation_id = state.currentConversationId || '';
        
        if (user_id) formData.append('user_id', user_id);
        if (conversation_id) formData.append('conversation_id', conversation_id);
        
        // Obtener token CSRF
        const csrfToken = getCsrfToken();
        
        // Realizar petición POST
        fetch(apiUrls.upload, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrfToken
            },
            credentials: 'same-origin'
        })
        .then(response => response.json())
        .then(data => {
            console.log('Respuesta de subida:', data);
            
            if (data.success) {
                // Agregar archivo a la lista
                addFileToList({
                    name: file.name,
                    size: file.size,
                    type: file.type,
                    uploaded_at: new Date().toISOString(),
                    info: data.file_info
                });
                
                addMessage('system', `Archivo "${file.name}" subido correctamente.`);
            } else {
                addMessage('system', `Error al subir "${file.name}": ${data.error || 'Error desconocido'}`);
            }
        })
        .catch(error => {
            console.error('Error en subida:', error);
            addMessage('system', `Error de conexión al subir "${file.name}".`);
        });
    }
    
    function addFileToList(fileData) {
        // Agregar al estado
        state.files.push(fileData);
        
        // Actualizar contador
        updateFileCount();
        
        // Actualizar UI si existe la lista de archivos
        if (elements.filesList) {
            const emptyState = elements.filesList.querySelector('.empty-state');
            if (emptyState) {
                emptyState.style.display = 'none';
            }
            
            // Crear elemento de archivo
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            
            // Determinar icono según tipo
            let iconClass = 'fas fa-file';
            if (fileData.type.includes('image')) iconClass = 'fas fa-file-image';
            else if (fileData.type.includes('pdf')) iconClass = 'fas fa-file-pdf';
            else if (fileData.type.includes('text')) iconClass = 'fas fa-file-alt';
            else if (fileData.type.includes('excel') || fileData.type.includes('spreadsheet')) iconClass = 'fas fa-file-excel';
            else if (fileData.type.includes('word') || fileData.type.includes('document')) iconClass = 'fas fa-file-word';
            
            // Formatear tamaño
            const formatSize = (bytes) => {
                if (bytes < 1024) return bytes + ' B';
                if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
                return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
            };
            
            fileItem.innerHTML = `
                <div class="file-icon ${fileData.type.includes('image') ? 'image' : fileData.type.includes('pdf') ? 'pdf' : 'text'}">
                    <i class="${iconClass}"></i>
                </div>
                <div class="file-info">
                    <div class="file-name">${fileData.name}</div>
                    <div class="file-size">${formatSize(fileData.size)} • ${new Date(fileData.uploaded_at).toLocaleTimeString()}</div>
                </div>
                <div class="file-actions">
                    <button class="file-action" title="Ver archivo">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="file-action" title="Eliminar">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
            
            // Agregar a la lista
            elements.filesList.appendChild(fileItem);
            
            // Agregar eventos a los botones
            const viewBtn = fileItem.querySelector('.file-actions .fa-eye').closest('button');
            const deleteBtn = fileItem.querySelector('.file-actions .fa-trash').closest('button');
            
            viewBtn.addEventListener('click', () => {
                alert(`Vista previa de ${fileData.name} (funcionalidad en desarrollo)`);
            });
            
            deleteBtn.addEventListener('click', () => {
                if (confirm(`¿Eliminar ${fileData.name}?`)) {
                    // Eliminar del estado
                    state.files = state.files.filter(f => f !== fileData);
                    // Eliminar de la UI
                    fileItem.remove();
                    updateFileCount();
                    
                    // Si no hay archivos, mostrar estado vacío
                    if (state.files.length === 0 && elements.filesList) {
                        const emptyState = elements.filesList.querySelector('.empty-state');
                        if (emptyState) {
                            emptyState.style.display = 'block';
                        }
                    }
                }
            });
        }
    }

    function clearChat() {
        if (confirm('¿Estás seguro de que quieres limpiar la conversación?')) {
            state.messages = [];
            if (elements.messagesContainer) {
                elements.messagesContainer.innerHTML = `
                    <div class="message message-system">
                        <i class="fas fa-robot"></i> ¡Hola! Soy tu asistente de Propifai Intelligence. ¿En qué puedo ayudarte hoy?
                    </div>
                `;
            }
            addMessage('system', 'Conversación limpiada');
        }
    }

    function exportChat() {
        const chatContent = state.messages.map(msg => 
            `[${msg.timestamp}] ${msg.role.toUpperCase()}: ${msg.content}`
        ).join('\n\n');
        
        const blob = new Blob([chatContent], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat-${new Date().toISOString().split('T')[0]}.txt`;
        a.click();
        URL.revokeObjectURL(url);
        
        addMessage('system', 'Conversación exportada');
    }

    function updateFileCount() {
        if (elements.fileCount) {
            elements.fileCount.textContent = `${state.files.length} archivo${state.files.length !== 1 ? 's' : ''}`;
        }
    }

    function getCsrfToken() {
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        return cookieValue || '';
    }
});