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
        currentConversationId: null,
        thinkingTimers: [],
        artifacts: [],
        activeArtifactId: null,
        activeGalleryIndex: 0
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
        toggleSidebarBtn: document.querySelector('.toggle-sidebar'),
        workspaceShell: document.getElementById('workspace-shell'),
        artifactPanel: document.getElementById('artifact-panel'),
        artifactContent: document.getElementById('artifact-content'),
        artifactResizer: document.getElementById('artifact-resizer'),
        artifactToggle: document.getElementById('artifact-toggle'),
        closeArtifact: document.getElementById('close-artifact'),
        mobileNavToggle: document.getElementById('mobile-nav-toggle'),
        mobileScrim: document.getElementById('mobile-scrim'),
        newChat: document.getElementById('new-chat')
    };

    // URLs API
    const apiUrls = {
        chat: '/api/v1/intelligence/chat-web/api/',
        upload: '/api/v1/intelligence/chat-web/upload/',
        propertyDetail: '/api/v1/intelligence/chat-web/properties/'
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
        restoreWorkspacePreferences();
        
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

        if (elements.artifactToggle) {
            elements.artifactToggle.addEventListener('click', toggleArtifactPanel);
        }

        if (elements.closeArtifact) {
            elements.closeArtifact.addEventListener('click', closeArtifactPanel);
        }

        setupArtifactResizer();

        if (elements.mobileNavToggle) {
            elements.mobileNavToggle.addEventListener('click', function() {
                elements.workspaceShell?.classList.toggle('mobile-nav-open');
            });
        }

        if (elements.mobileScrim) {
            elements.mobileScrim.addEventListener('click', function() {
                elements.workspaceShell?.classList.remove('mobile-nav-open');
                if (window.innerWidth <= 1180) closeArtifactPanel();
            });
        }

        if (elements.newChat) {
            elements.newChat.addEventListener('click', clearChat);
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
            
            // ── MOSTRAR PROCESO DE PENSAMIENTO ──
            // Si hay reasoning_steps reales del AgentGraphBuilder, reemplazar la simulación
            if (data.reasoning_steps && data.reasoning_steps.length > 0) {
                replaceWithRealSteps(data.reasoning_steps);
            }
            // Si no hay reasoning_steps, la simulación ya se está mostrando
            
            // ── AVISO DE FALLBACK ──
            // Si el AgentGraph falló y se usó el sistema antiguo, mostrar advertencia
            if (data.fallback_notice) {
                const traceContainer = document.getElementById('thinking-trace');
                if (traceContainer) {
                    const fallbackEl = document.createElement('div');
                    fallbackEl.className = 'thinking-step step-error';
                    fallbackEl.style.opacity = '1';
                    fallbackEl.style.transform = 'translateX(0)';
                    fallbackEl.innerHTML = `
                        <span class="step-icon">⚠️</span>
                        <div class="step-content">
                            <div class="step-title">Sistema de respaldo activado</div>
                            <div class="step-desc">${escapeHtml(data.fallback_notice)}</div>
                        </div>
                    `;
                    traceContainer.appendChild(fallbackEl);
                    scrollToBottom();
                }
            }
            
            // Agregar respuesta del asistente
            addMessage('assistant', data.response || data.message || 'No se recibió respuesta');

            if (Array.isArray(data.artifacts) && data.artifacts.length > 0) {
                handleArtifacts(data.artifacts);
            }
            
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
        
        // Detectar contenido HTML (envuelto en __HTML__...__HTML__)
        let renderedContent;
        if (typeof content === 'string' && content.startsWith('__HTML__') && content.endsWith('__HTML__')) {
            // Extraer el HTML interno y renderizarlo sin escapar
            let html = content.slice(8, -8);  // Quitar __HTML__ del inicio y final
            // Separar intro texto (antes del primer <) del HTML
            let textEnd = html.indexOf('<');
            if (textEnd > 0) {
                let textPart = escapeHtml(html.substring(0, textEnd));
                let htmlPart = html.substring(textEnd);
                renderedContent = `<div style="margin-bottom:8px;">${textPart}</div><div>${htmlPart}</div>`;
            } else {
                renderedContent = html;
            }
        } else {
            renderedContent = message.role === 'assistant'
                ? renderAssistantContent(content)
                : escapeHtml(content);
        }

        messageElement.innerHTML = `
            <div class="message-content">${renderedContent}</div>
            <div class="message-time">${message.timestamp}</div>
        `;
        
        elements.messagesContainer.appendChild(messageElement);
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Renderizador restringido para respuestas del asistente.
     * Primero escapa todo el contenido y después habilita únicamente un
     * subconjunto controlado de Markdown. No acepta HTML del modelo.
     */
    function renderAssistantContent(content) {
        const text = String(content || '').trim();
        const propertyPattern = /(\d+)\.\s+\*\*(.+?)\*\*\s*([\s\S]*?)(?=(?:\s+\d+\.\s+\*\*)|$)/g;
        const matches = Array.from(text.matchAll(propertyPattern));

        if (matches.length >= 2) {
            const intro = text.slice(0, matches[0].index).trim();
            const cards = matches.map((match, index) => {
                let details = match[3].trim();
                let closing = '';

                // Separar la conclusión que el LLM suele pegar a la última propiedad.
                if (index === matches.length - 1) {
                    const closingMatch = details.match(/\s+(Todos los datos|Si quieres|Si deseas|¿Te gustaría|Puedo ayudarte)[\s\S]*$/i);
                    if (closingMatch && closingMatch.index !== undefined) {
                        closing = details.slice(closingMatch.index).trim();
                        details = details.slice(0, closingMatch.index).trim();
                    }
                }

                return {
                    number: match[1],
                    title: match[2],
                    details,
                    closing
                };
            });

            const closingText = cards.map(card => card.closing).filter(Boolean).join(' ');
            return `
                ${intro ? `<p class="assistant-summary">${renderInlineMarkdown(intro)}</p>` : ''}
                <ol class="property-response-list">
                    ${cards.map(card => `
                        <li class="property-response-card">
                            <span class="property-response-number">${escapeHtml(card.number)}</span>
                            <div>
                                <h3>${renderInlineMarkdown(card.title)}</h3>
                                <p>${renderPropertyDetails(card.details)}</p>
                            </div>
                        </li>
                    `).join('')}
                </ol>
                ${closingText ? `<p class="assistant-closing">${renderInlineMarkdown(closingText)}</p>` : ''}
            `;
        }

        return renderInlineMarkdown(text)
            .replace(/\r?\n\r?\n/g, '</p><p>')
            .replace(/\r?\n/g, '<br>');
    }

    function renderInlineMarkdown(text) {
        return escapeHtml(String(text || ''))
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/__(.+?)__/g, '<strong>$1</strong>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/(^|[^\*])\*([^\*\n]+)\*/g, '$1<em>$2</em>');
    }

    function renderPropertyDetails(details) {
        const formattedDetails = String(details || '')
            .replace(/D[oó]lares\s+(\d+(?:\.\d+)?)/gi, (_, value) =>
                `US$ ${Number(value).toLocaleString('en-US', { maximumFractionDigits: 0 })}`
            )
            .replace(/Soles\s+(\d+(?:\.\d+)?)/gi, (_, value) =>
                `S/ ${Number(value).toLocaleString('es-PE', { maximumFractionDigits: 0 })}`
            );

        return renderInlineMarkdown(formattedDetails)
            .replace(/\s*·\s*/g, '<span class="property-detail-separator" aria-hidden="true"></span>')
            .replace(/\b(Precio|Tipo|Distrito|Estado|Área|Dormitorios|Baños):/gi, '<strong class="property-detail-label">$1:</strong>');
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
            // En lugar de puntitos, mostrar proceso simulado
            addThinkingTraceSimulated();
        } else {
            clearThinkingTimers();
            if (elements.thinkingIndicator) {
                elements.thinkingIndicator.classList.remove('active');
            }
            if (elements.chatInput) {
                elements.chatInput.disabled = false;
            }
            updateSendButtonState();
            // NO remover el thinking trace aquí - se maneja en sendMessage()
        }
    }

    /**
     * Muestra un proceso de pensamiento SIMULADO mientras se espera la respuesta.
     * Esto reemplaza los puntitos "Escribiendo..." por pasos con íconos.
     * Cuando llegan los reasoning_steps reales, se reemplazan.
     */
    function addThinkingTraceSimulated() {
        if (!elements.messagesContainer) return;

        clearThinkingTimers();
        
        // Remover trace anterior si existe
        const oldTrace = document.getElementById('thinking-trace');
        if (oldTrace) oldTrace.remove();
        
        const traceContainer = document.createElement('div');
        traceContainer.className = 'thinking-trace';
        traceContainer.id = 'thinking-trace';
        elements.messagesContainer.appendChild(traceContainer);
        scrollToBottom();
        
        // Pasos simulados genéricos (si no llegan pasos reales, estos se quedan)
        const simulatedSteps = [
            { icon: '🧠', title: 'Analizando consulta...', type: 'router', delay: 800 },
            { icon: '🔍', title: 'Buscando información...', type: 'action', delay: 1500 },
            { icon: '💭', title: 'Procesando resultados...', type: 'think', delay: 1500 },
            { icon: '📝', title: 'Generando respuesta...', type: 'formatter', delay: 1200 },
        ];
        
        let cumulativeDelay = 300;
        simulatedSteps.forEach((step, i) => {
            cumulativeDelay += step.delay;
            const timerId = setTimeout(() => {
                const trace = document.getElementById('thinking-trace');
                if (!trace) return;
                
                const stepEl = document.createElement('div');
                stepEl.className = `thinking-step step-${step.type}`;
                stepEl.innerHTML = `
                    <span class="step-icon">${step.icon}</span>
                    <div class="step-content">
                        <div class="step-title">${escapeHtml(step.title)}</div>
                    </div>
                `;
                trace.appendChild(stepEl);
                requestAnimationFrame(() => stepEl.classList.add('visible'));
                scrollToBottom();
            }, cumulativeDelay);
            state.thinkingTimers.push(timerId);
        });
    }

    function clearThinkingTimers() {
        state.thinkingTimers.forEach(timerId => clearTimeout(timerId));
        state.thinkingTimers = [];
    }

    /**
     * Inserta los pasos reales antes de la respuesta. Se renderizan de forma
     * sincrónica para evitar que temporizadores pendientes los añadan al final.
     */
    function replaceWithRealSteps(realSteps) {
        const traceContainer = document.getElementById('thinking-trace');
        if (!traceContainer) return;

        clearThinkingTimers();
        traceContainer.innerHTML = '';
        if (!realSteps || realSteps.length === 0) return;

        realSteps.forEach((step) => {
            const stepEl = document.createElement('div');
            stepEl.className = `thinking-step step-${step.type} visible`;
            stepEl.innerHTML = `
                <span class="step-icon">${step.icon}</span>
                <div class="step-content">
                    <div class="step-title">${escapeHtml(step.title)}</div>
                    ${step.description ? `<div class="step-desc">${escapeHtml(step.description)}</div>` : ''}
                </div>
            `;
            traceContainer.appendChild(stepEl);
        });

        const divider = document.createElement('div');
        divider.className = 'thinking-trace-divider';
        divider.innerHTML = '<span>Respuesta generada</span>';
        traceContainer.appendChild(divider);
        scrollToBottom();
    }

    function removeTypingIndicator() {
        // Ya no se usa - reemplazado por thinking trace
    }

    function scrollToBottom() {
        if (elements.messagesContainer) {
            const scroll = () => {
                elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
            };
            scroll();
            requestAnimationFrame(scroll);
        }
    }

    function toggleSidebar() {
        if (!elements.sidebar || !elements.workspaceShell) return;

        state.sidebarVisible = !state.sidebarVisible;
        elements.workspaceShell.classList.toggle('sidebar-collapsed', !state.sidebarVisible);
        localStorage.setItem('propifai.sidebarCollapsed', String(!state.sidebarVisible));
        setArtifactWidth(getArtifactWidth());

        const toggleButton = document.querySelector('.toggle-sidebar i');
        if (toggleButton) {
            toggleButton.className = 'fas fa-chevron-left';
        }
    }

    function toggleArtifactPanel() {
        if (!elements.workspaceShell) return;
        const willClose = !elements.workspaceShell.classList.contains('artifact-closed');
        elements.workspaceShell.classList.toggle('artifact-closed', willClose);
        localStorage.setItem('propifai.artifactClosed', String(willClose));
    }

    function closeArtifactPanel() {
        if (!elements.workspaceShell) return;
        elements.workspaceShell.classList.add('artifact-closed');
        localStorage.setItem('propifai.artifactClosed', 'true');
    }

    function restoreWorkspacePreferences() {
        if (!elements.workspaceShell) return;
        const sidebarCollapsed = localStorage.getItem('propifai.sidebarCollapsed') === 'true';
        const artifactClosed = localStorage.getItem('propifai.artifactClosed') === 'true';
        const storedArtifactWidth = Number(localStorage.getItem('propifai.artifactWidth'));
        if (Number.isFinite(storedArtifactWidth) && storedArtifactWidth > 0) {
            setArtifactWidth(storedArtifactWidth);
        }
        elements.workspaceShell.classList.toggle('sidebar-collapsed', sidebarCollapsed);
        elements.workspaceShell.classList.toggle('artifact-closed', artifactClosed);
        state.sidebarVisible = !sidebarCollapsed;
    }

    function setupArtifactResizer() {
        if (!elements.artifactResizer || !elements.workspaceShell) return;

        let pointerId = null;

        elements.artifactResizer.addEventListener('pointerdown', function(event) {
            if (window.innerWidth <= 1180) return;
            pointerId = event.pointerId;
            elements.artifactResizer.setPointerCapture(pointerId);
            elements.workspaceShell.classList.add('resizing-artifact');
            event.preventDefault();
        });

        elements.artifactResizer.addEventListener('pointermove', function(event) {
            if (pointerId !== event.pointerId) return;
            setArtifactWidth(window.innerWidth - event.clientX);
        });

        const finishResize = function(event) {
            if (pointerId !== event.pointerId) return;
            pointerId = null;
            elements.workspaceShell.classList.remove('resizing-artifact');
            const width = getArtifactWidth();
            localStorage.setItem('propifai.artifactWidth', String(width));
        };

        elements.artifactResizer.addEventListener('pointerup', finishResize);
        elements.artifactResizer.addEventListener('pointercancel', finishResize);

        elements.artifactResizer.addEventListener('keydown', function(event) {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
            event.preventDefault();
            const step = event.shiftKey ? 50 : 20;
            let width = getArtifactWidth();
            if (event.key === 'ArrowLeft') width += step;
            if (event.key === 'ArrowRight') width -= step;
            if (event.key === 'Home') width = 320;
            if (event.key === 'End') width = getArtifactWidthLimits().max;
            setArtifactWidth(width);
            localStorage.setItem('propifai.artifactWidth', String(getArtifactWidth()));
        });

        window.addEventListener('resize', function() {
            if (window.innerWidth > 1180) {
                setArtifactWidth(getArtifactWidth());
            }
        });
    }

    function getArtifactWidthLimits() {
        const sidebarWidth = elements.workspaceShell?.classList.contains('sidebar-collapsed') ? 76 : 268;
        const minimumChatWidth = 480;
        const maximumByViewport = window.innerWidth - sidebarWidth - minimumChatWidth - 1;
        return {
            min: 320,
            max: Math.max(320, Math.min(720, maximumByViewport))
        };
    }

    function setArtifactWidth(requestedWidth) {
        if (!elements.workspaceShell) return;
        const limits = getArtifactWidthLimits();
        const width = Math.round(Math.min(limits.max, Math.max(limits.min, requestedWidth)));
        elements.workspaceShell.style.setProperty('--artifact-width', `${width}px`);
        elements.artifactResizer?.setAttribute('aria-valuemax', String(limits.max));
        elements.artifactResizer?.setAttribute('aria-valuenow', String(width));
    }

    function getArtifactWidth() {
        if (!elements.workspaceShell) return 390;
        const value = getComputedStyle(elements.workspaceShell).getPropertyValue('--artifact-width');
        return Number.parseFloat(value) || 390;
    }

    function handleArtifacts(artifacts) {
        const validArtifacts = artifacts.filter(artifact =>
            artifact && artifact.type === 'property_collection' && Array.isArray(artifact.items)
        );
        if (validArtifacts.length === 0) return;

        validArtifacts.forEach(artifact => {
            const existingIndex = state.artifacts.findIndex(item => item.id === artifact.id);
            if (existingIndex >= 0) state.artifacts[existingIndex] = artifact;
            else state.artifacts.push(artifact);
        });

        const activeArtifact = validArtifacts[0];
        state.activeArtifactId = activeArtifact.id;
        elements.workspaceShell?.classList.remove('artifact-closed');
        localStorage.setItem('propifai.artifactClosed', 'false');
        renderPropertyCollection(activeArtifact);
        connectConversationCards(activeArtifact);
    }

    function connectConversationCards(artifact) {
        const assistantMessages = elements.messagesContainer?.querySelectorAll('.message-assistant');
        const latestMessage = assistantMessages?.[assistantMessages.length - 1];
        const cards = latestMessage?.querySelectorAll('.property-response-card') || [];
        cards.forEach((card, index) => {
            const property = artifact.items[index];
            if (!property) return;
            card.classList.add('is-clickable');
            card.tabIndex = 0;
            card.setAttribute('role', 'button');
            card.setAttribute('aria-label', `Ver detalle de ${property.title}`);
            card.addEventListener('click', () => loadPropertyDetail(property.id));
            card.addEventListener('keydown', event => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    loadPropertyDetail(property.id);
                }
            });
        });
    }

    function renderPropertyCollection(artifact) {
        if (!elements.artifactContent) return;
        const items = artifact.items || [];
        elements.artifactContent.innerHTML = `
            <div class="property-collection">
                <div class="property-collection-toolbar">
                    <div>
                        <span class="eyebrow">Propiedades verificadas</span>
                        <h3>${escapeHtml(artifact.title || 'Propiedades encontradas')}</h3>
                        <p>${items.length} resultado${items.length === 1 ? '' : 's'}</p>
                    </div>
                    <span class="view-pill"><i class="fa-solid fa-grip"></i> Tarjetas</span>
                </div>
                <div class="property-artifact-grid">
                    ${items.map(property => renderPropertyArtifactCard(property)).join('')}
                </div>
            </div>
        `;

        elements.artifactContent.querySelectorAll('[data-property-id]').forEach(card => {
            card.addEventListener('click', () => loadPropertyDetail(card.dataset.propertyId));
            card.addEventListener('keydown', event => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    loadPropertyDetail(card.dataset.propertyId);
                }
            });
        });
        elements.artifactContent.querySelectorAll('.property-card-media img').forEach(image => {
            image.addEventListener('error', function() {
                const media = image.closest('.property-card-media');
                image.remove();
                if (media && !media.querySelector('.property-image-fallback')) {
                    const fallback = document.createElement('span');
                    fallback.className = 'property-image-fallback';
                    fallback.innerHTML = '<i class="fa-regular fa-image"></i>';
                    media.prepend(fallback);
                }
            }, { once: true });
        });
    }

    function renderPropertyArtifactCard(property) {
        const image = safeMediaUrl(property.images?.[0]?.url);
        const price = formatPropertyPrice(property.price, property.currency);
        const meta = [
            property.area_m2 ? `${formatNumber(property.area_m2)} m²` : '',
            property.bedrooms != null ? `${property.bedrooms} dorm.` : '',
            property.bathrooms != null ? `${formatNumber(property.bathrooms)} baños` : ''
        ].filter(Boolean);
        return `
            <article class="property-artifact-card" data-property-id="${escapeHtml(property.id)}" tabindex="0" role="button">
                <div class="property-card-media">
                    ${image
                        ? `<img src="${image}" alt="${escapeHtml(property.title)}" loading="lazy">`
                        : '<span><i class="fa-regular fa-image"></i></span>'}
                    ${property.status ? `<span class="property-status">${escapeHtml(property.status)}</span>` : ''}
                </div>
                <div class="property-card-copy">
                    <span class="property-code">${escapeHtml(property.code || property.property_type || 'Propiedad')}</span>
                    <h4>${escapeHtml(property.title)}</h4>
                    <strong class="property-price">${escapeHtml(price)}</strong>
                    <p><i class="fa-solid fa-location-dot"></i> ${escapeHtml(property.district || 'Ubicación no registrada')}</p>
                    ${meta.length ? `<div class="property-meta">${meta.map(value => `<span>${escapeHtml(value)}</span>`).join('')}</div>` : ''}
                    <button type="button">Ver detalle <i class="fa-solid fa-arrow-right"></i></button>
                </div>
            </article>
        `;
    }

    async function loadPropertyDetail(propertyId) {
        if (!elements.artifactContent || !propertyId) return;
        elements.workspaceShell?.classList.remove('artifact-closed');
        elements.artifactContent.innerHTML = `
            <div class="artifact-loading"><span class="spinner"></span><p>Cargando ficha completa…</p></div>
        `;
        try {
            const response = await fetch(`${apiUrls.propertyDetail}${encodeURIComponent(propertyId)}/`, {
                credentials: 'same-origin'
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'No se pudo cargar la propiedad.');
            }
            state.activeGalleryIndex = 0;
            renderPropertyDetail(data.property);
        } catch (error) {
            elements.artifactContent.innerHTML = `
                <div class="artifact-error">
                    <i class="fa-solid fa-circle-exclamation"></i>
                    <h3>No pudimos abrir la ficha</h3>
                    <p>${escapeHtml(error.message)}</p>
                    <button type="button" id="back-to-properties-error">Volver a resultados</button>
                </div>
            `;
            document.getElementById('back-to-properties-error')?.addEventListener('click', renderActiveArtifact);
        }
    }

    function renderPropertyDetail(property) {
        if (!elements.artifactContent) return;
        const gallery = (property.gallery || [])
            .map(image => ({...image, url: safeMediaUrl(image.url)}))
            .filter(image => image.url);
        const specs = property.specs || {};
        const featureLabels = {
            bedrooms: 'Dormitorios', bathrooms: 'Baños', half_bathrooms: 'Medios baños',
            land_area: 'Área de terreno', built_area: 'Área construida',
            garage_spaces: 'Estacionamientos', antiquity_years: 'Antigüedad',
            floors_total: 'Pisos', front_measure: 'Frente', depth_measure: 'Fondo'
        };
        const featureEntries = Object.entries(featureLabels)
            .filter(([key]) => specs[key] !== null && specs[key] !== undefined && specs[key] !== '')
            .map(([key, label]) => {
                const areaSuffix = ['land_area', 'built_area'].includes(key) ? ' m²' : '';
                return `<div><span>${label}</span><strong>${escapeHtml(formatNumber(specs[key]))}${areaSuffix}</strong></div>`;
            }).join('');

        elements.artifactContent.innerHTML = `
            <div class="property-detail">
                <button class="back-button" id="back-to-properties" type="button">
                    <i class="fa-solid fa-arrow-left"></i> Volver a resultados
                </button>
                <section class="property-gallery" aria-label="Galería de la propiedad">
                    <div class="property-gallery-stage">
                        ${gallery.length
                            ? `<img id="property-gallery-main" src="${gallery[0].url}" alt="${escapeHtml(gallery[0].alt || property.title)}">`
                            : '<div class="gallery-empty"><i class="fa-regular fa-image"></i><span>Sin fotografías registradas</span></div>'}
                        ${gallery.length > 1 ? `
                            <button class="gallery-arrow gallery-prev" type="button" aria-label="Fotografía anterior"><i class="fa-solid fa-chevron-left"></i></button>
                            <button class="gallery-arrow gallery-next" type="button" aria-label="Fotografía siguiente"><i class="fa-solid fa-chevron-right"></i></button>
                            <span class="gallery-counter" id="gallery-counter">1 / ${gallery.length}</span>
                        ` : ''}
                    </div>
                    ${gallery.length > 1 ? `
                        <div class="property-thumbnails">
                            ${gallery.map((image, index) => `
                                <button type="button" data-gallery-index="${index}" class="${index === 0 ? 'active' : ''}">
                                    <img src="${image.url}" alt="Miniatura ${index + 1}" loading="lazy">
                                </button>
                            `).join('')}
                        </div>
                    ` : ''}
                </section>
                ${renderPropertyVideos(property.videos || [])}
                <section class="property-detail-heading">
                    <span>${escapeHtml(property.code || property.property_type || 'Propiedad')}</span>
                    <h3>${escapeHtml(property.title)}</h3>
                    <strong>${escapeHtml(formatPropertyPrice(property.price, property.currency))}</strong>
                    <p><i class="fa-solid fa-location-dot"></i> ${escapeHtml(property.address || property.district || 'Ubicación no registrada')}</p>
                </section>
                <section class="detail-section">
                    <h4>Información principal</h4>
                    <div class="detail-facts">
                        ${detailFact('Tipo', property.property_type)}
                        ${detailFact('Operación', property.operation_type)}
                        ${detailFact('Estado', property.status)}
                        ${detailFact('Condición', property.condition)}
                        ${detailFact('Distrito', property.district)}
                        ${detailFact('Mantenimiento', property.maintenance_fee != null ? formatPropertyPrice(property.maintenance_fee, property.currency) : null)}
                    </div>
                </section>
                ${featureEntries ? `<section class="detail-section"><h4>Características</h4><div class="detail-facts">${featureEntries}</div></section>` : ''}
                ${property.description ? `<section class="detail-section"><h4>Descripción</h4><p class="property-description">${escapeHtml(property.description)}</p></section>` : ''}
                <footer class="property-source">
                    <i class="fa-solid fa-shield-check"></i>
                    <span>Fuente: ${escapeHtml(property.source?.name || 'Propify DB')} · ID ${escapeHtml(property.id)}</span>
                </footer>
            </div>
        `;

        document.getElementById('back-to-properties')?.addEventListener('click', renderActiveArtifact);
        setupGallery(gallery);
    }

    function renderPropertyVideos(videos) {
        const safeVideos = videos.map(safeMediaUrl).filter(Boolean);
        if (safeVideos.length === 0) return '';
        return `
            <section class="property-videos">
                <h4><i class="fa-solid fa-circle-play"></i> Videos</h4>
                ${safeVideos.map(url => {
                    const direct = /\.(mp4|webm|ogg)(?:\?.*)?$/i.test(url);
                    return direct
                        ? `<video controls preload="metadata"><source src="${url}"></video>`
                        : `<a href="${url}" target="_blank" rel="noopener noreferrer"><i class="fa-solid fa-play"></i> Ver video de la propiedad</a>`;
                }).join('')}
            </section>
        `;
    }

    function setupGallery(gallery) {
        if (gallery.length <= 1) return;
        const main = document.getElementById('property-gallery-main');
        const counter = document.getElementById('gallery-counter');
        const thumbnails = Array.from(elements.artifactContent.querySelectorAll('[data-gallery-index]'));
        const show = index => {
            state.activeGalleryIndex = (index + gallery.length) % gallery.length;
            main.src = gallery[state.activeGalleryIndex].url;
            main.alt = gallery[state.activeGalleryIndex].alt || `Fotografía ${state.activeGalleryIndex + 1}`;
            counter.textContent = `${state.activeGalleryIndex + 1} / ${gallery.length}`;
            thumbnails.forEach((button, buttonIndex) => button.classList.toggle('active', buttonIndex === state.activeGalleryIndex));
        };
        elements.artifactContent.querySelector('.gallery-prev')?.addEventListener('click', () => show(state.activeGalleryIndex - 1));
        elements.artifactContent.querySelector('.gallery-next')?.addEventListener('click', () => show(state.activeGalleryIndex + 1));
        thumbnails.forEach(button => button.addEventListener('click', () => show(Number(button.dataset.galleryIndex))));
    }

    function renderActiveArtifact() {
        const artifact = state.artifacts.find(item => item.id === state.activeArtifactId);
        if (artifact) renderPropertyCollection(artifact);
    }

    function detailFact(label, value) {
        if (value === null || value === undefined || value === '') return '';
        return `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></div>`;
    }

    function safeMediaUrl(value) {
        if (!value) return '';
        try {
            const url = new URL(value, window.location.origin);
            return url.protocol === 'https:' || url.origin === window.location.origin
                ? escapeHtml(url.href)
                : '';
        } catch (_) {
            return '';
        }
    }

    function formatPropertyPrice(value, currency) {
        const number = Number(value);
        if (!Number.isFinite(number)) return 'Precio no registrado';
        const code = String(currency || '').toUpperCase().includes('SOL') || currency === 'PEN' ? 'PEN' : 'USD';
        return new Intl.NumberFormat('es-PE', {
            style: 'currency', currency: code, maximumFractionDigits: 0
        }).format(number);
    }

    function formatNumber(value) {
        const number = Number(value);
        return Number.isFinite(number)
            ? new Intl.NumberFormat('es-PE', { maximumFractionDigits: 2 }).format(number)
            : String(value ?? '');
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
