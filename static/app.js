// Global component definition for Alpine.js
function instaFlowApp() {
    return {
        currentTab: 'campaigns',
        stats: {
            active_campaigns: 1,
            total_leads_captured: 0,
            total_dms_sent: 0,
            total_public_replies: 0,
            total_ai_replies: 0
        },
        
        // Settings
        settings: {
            company_name: 'Mi Negocio / Tienda',
            company_description: 'Venta de productos y servicios con atención personalizada.',
            sales_tone: 'amable, persuasivo, profesional y enfocado en cerrar la venta.',
            gemini_api_key: '',
            meta_access_token: '',
            meta_verify_token: 'instaflow_verify_token_secure_2026'
        },
        isSavingSettings: false,
        
        // Campaigns
        campaigns: [],
        editingCampaign: null,
        campaignModalOpen: false,
        
        // Products & AI
        products: [],
        editingProduct: null,
        productModalOpen: false,
        
        // Leads & Logs
        leads: [],
        logs: [],
        
        // Simulator State
        simUsername: 'maria_compradora',
        simComment: 'QUIERO',
        simPostId: '',
        simIsProcessing: false,
        simPostComments: [
            { username: 'carlos_fit', text: '¡Excelente contenido! 🔥', time: 'hace 2h', isReply: false }
        ],
        simDmMessages: [],
        simUserChatMessage: '',
        simIsAiTyping: false,
        
        // Notification Toast
        toast: { show: false, message: '', type: 'success' },

        showToast(msg, type = 'success') {
            this.toast = { show: true, message: msg, type };
            setTimeout(() => { this.toast.show = false; }, 3500);
        },

        // Meta Connection Status
        metaStatus: { connected: false, account: null },

        async init() {
            console.log("InstaFlow App Inicializada correctamente");
            await this.loadStats();
            await this.loadMetaStatus();
            await this.loadCampaigns();
            await this.loadProducts();
            await this.loadSettings();
            await this.loadLeads();
            await this.loadLogs();

            // Refresh stats periodically
            setInterval(() => {
                this.loadStats();
                this.loadMetaStatus();
                if (this.currentTab === 'logs') {
                    this.loadLogs();
                    this.loadLeads();
                }
            }, 5000);
        },

        async loadMetaStatus() {
            try {
                const res = await fetch('/api/meta/status');
                if (res.ok) this.metaStatus = await res.json();
            } catch (e) {
                console.error("Error loading meta status:", e);
            }
        },

        async loadStats() {
            try {
                const res = await fetch('/api/stats');
                if (res.ok) this.stats = await res.json();
            } catch (e) {
                console.error("Error loading stats:", e);
            }
        },

        async resetStats() {
            if (!confirm('¿Deseas reiniciar todos los contadores, leads y registros a cero?')) return;
            try {
                const res = await fetch('/api/stats/reset', { method: 'POST' });
                if (res.ok) {
                    this.showToast('Contadores y registros reiniciados a cero');
                    await this.loadStats();
                    await this.loadLeads();
                    await this.loadLogs();
                }
            } catch (e) {
                this.showToast('Error al reiniciar', 'error');
            }
        },

        async loadSettings() {
            try {
                const res = await fetch('/api/settings');
                if (res.ok) {
                    const data = await res.json();
                    this.settings = Object.assign(this.settings, data);
                }
            } catch (e) {
                console.error("Error loading settings:", e);
            }
        },

        async saveSettings() {
            this.isSavingSettings = true;
            try {
                const res = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.settings)
                });
                if (res.ok) {
                    this.showToast('Configuración guardada exitosamente');
                } else {
                    this.showToast('Error al guardar configuración', 'error');
                }
            } catch (e) {
                this.showToast('Error de conexión', 'error');
            } finally {
                this.isSavingSettings = false;
            }
        },

        // --- CAMPAIGNS LOGIC ---
        async loadCampaigns() {
            try {
                const res = await fetch('/api/campaigns');
                if (res.ok) this.campaigns = await res.json();
            } catch (e) {
                console.error("Error loading campaigns:", e);
            }
        },

        openNewCampaignModal() {
            this.editingCampaign = {
                id: null,
                name: 'Nueva Campaña de Ventas',
                keywords: 'QUIERO, PRECIO, INFO, LINK',
                match_mode: 'contains',
                post_id_filter: '',
                public_replies: [
                    '¡Te envié toda la información por mensaje directo! 📩✨',
                    '¡Listo! Revisa tu bandeja de entrada para ver el link 🚀'
                ],
                dm_messages: [
                    {
                        text: '¡Hola @username! 👋 Gracias por tu interés. Aquí tienes toda la información de nuestra promo exclusiva 🔥',
                        delay_seconds: 0
                    },
                    {
                        text: '👉 Accede y compra directamente aquí:\nhttps://mitienda.com/oferta\n\n¿Tienes alguna duda sobre pagos o envíos? Escríbeme y te ayudo.',
                        delay_seconds: 2
                    }
                ],
                is_active: 1,
                enable_ai_agent: 1
            };
            this.campaignModalOpen = true;
        },

        editCampaign(camp) {
            this.editingCampaign = JSON.parse(JSON.stringify(camp));
            this.campaignModalOpen = true;
        },

        addPublicReply() {
            if (!this.editingCampaign.public_replies) this.editingCampaign.public_replies = [];
            this.editingCampaign.public_replies.push('¡Listo! Revisa tu mensaje directo 📩');
        },

        removePublicReply(index) {
            this.editingCampaign.public_replies.splice(index, 1);
        },

        addDmStep() {
            if (!this.editingCampaign.dm_messages) this.editingCampaign.dm_messages = [];
            this.editingCampaign.dm_messages.push({
                text: 'Nuevo mensaje con más detalles o enlace de compra...',
                delay_seconds: 2
            });
        },

        removeDmStep(index) {
            this.editingCampaign.dm_messages.splice(index, 1);
        },

        async saveCampaign() {
            if (!this.editingCampaign.name || !this.editingCampaign.keywords) {
                this.showToast('Por favor completa el nombre y las palabras clave', 'error');
                return;
            }

            const isNew = !this.editingCampaign.id;
            const url = isNew ? '/api/campaigns' : `/api/campaigns/${this.editingCampaign.id}`;
            const method = isNew ? 'POST' : 'PUT';

            try {
                const res = await fetch(url, {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.editingCampaign)
                });
                if (res.ok) {
                    this.showToast(isNew ? 'Campaña creada exitosamente' : 'Campaña actualizada');
                    this.campaignModalOpen = false;
                    await this.loadCampaigns();
                    await this.loadStats();
                }
            } catch (e) {
                this.showToast('Error al guardar campaña', 'error');
            }
        },

        async toggleCampaignStatus(camp) {
            camp.is_active = camp.is_active ? 0 : 1;
            try {
                await fetch(`/api/campaigns/${camp.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(camp)
                });
                this.showToast(`Campaña ${camp.is_active ? 'activada' : 'desactivada'}`);
                await this.loadStats();
            } catch (e) {
                this.showToast('Error al actualizar estado', 'error');
            }
        },

        async deleteCampaign(campId) {
            if (!confirm('¿Estás seguro de eliminar esta campaña?')) return;
            try {
                const res = await fetch(`/api/campaigns/${campId}`, { method: 'DELETE' });
                if (res.ok) {
                    this.showToast('Campaña eliminada');
                    await this.loadCampaigns();
                    await this.loadStats();
                }
            } catch (e) {
                this.showToast('Error al eliminar campaña', 'error');
            }
        },

        // --- PRODUCTS LOGIC ---
        async loadProducts() {
            try {
                const res = await fetch('/api/products');
                if (res.ok) this.products = await res.json();
            } catch (e) {
                console.error("Error loading products:", e);
            }
        },

        openNewProductModal() {
            this.editingProduct = {
                id: null,
                name: '',
                description: '',
                price: '',
                payment_link: '',
                benefits: '',
                faq: '',
                is_available: 1
            };
            this.productModalOpen = true;
        },

        editProduct(prod) {
            this.editingProduct = JSON.parse(JSON.stringify(prod));
            this.productModalOpen = true;
        },

        async saveProduct() {
            if (!this.editingProduct.name || !this.editingProduct.price || !this.editingProduct.payment_link) {
                this.showToast('Nombre, precio y enlace de compra son obligatorios', 'error');
                return;
            }

            const isNew = !this.editingProduct.id;
            const url = isNew ? '/api/products' : `/api/products/${this.editingProduct.id}`;
            const method = isNew ? 'POST' : 'PUT';

            try {
                const res = await fetch(url, {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.editingProduct)
                });
                if (res.ok) {
                    this.showToast(isNew ? 'Producto añadido' : 'Producto actualizado');
                    this.productModalOpen = false;
                    await this.loadProducts();
                }
            } catch (e) {
                this.showToast('Error al guardar producto', 'error');
            }
        },

        async deleteProduct(prodId) {
            if (!confirm('¿Eliminar este producto?')) return;
            try {
                await fetch(`/api/products/${prodId}`, { method: 'DELETE' });
                this.showToast('Producto eliminado');
                await this.loadProducts();
            } catch (e) {
                this.showToast('Error al eliminar producto', 'error');
            }
        },

        // --- LEADS & LOGS ---
        async loadLeads() {
            try {
                const res = await fetch('/api/leads');
                if (res.ok) this.leads = await res.json();
            } catch (e) {
                console.error("Error loading leads:", e);
            }
        },

        async loadLogs() {
            try {
                const res = await fetch('/api/logs');
                if (res.ok) this.logs = await res.json();
            } catch (e) {
                console.error("Error loading logs:", e);
            }
        },

        // --- SIMULATOR LOGIC ---
        async runSimulatorComment() {
            if (!this.simComment || !this.simComment.trim()) return;

            const userText = this.simComment.trim();
            const username = this.simUsername.trim() || 'cliente';

            // Add user's comment to feed
            this.simPostComments.push({
                username,
                text: userText,
                time: 'Ahora',
                isReply: false
            });

            this.simIsProcessing = true;
            this.simComment = '';

            try {
                const res = await fetch('/api/simulator/comment', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username,
                        comment_text: userText,
                        post_id: this.simPostId || 'post_default'
                    })
                });
                const data = await res.json();

                if (data.matched) {
                    // 1. Simulate public comment response
                    setTimeout(() => {
                        this.simPostComments.push({
                            username: 'mitienda_oficial',
                            text: data.public_reply,
                            time: 'Ahora',
                            isReply: true
                        });
                    }, 600);

                    // 2. Clear old DMs and play the new DM sequence
                    this.simDmMessages = [];
                    let accumulatedDelay = 1000;

                    data.dm_messages.forEach((step, idx) => {
                        const stepDelay = Math.max(step.delay_seconds * 1000, 800);
                        accumulatedDelay += stepDelay;

                        setTimeout(() => {
                            this.simDmMessages.push({
                                sender: 'bot',
                                text: step.text,
                                time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                            });
                            this.$nextTick(() => {
                                const chatBox = document.getElementById('sim-dm-chatbox');
                                if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;
                            });
                        }, accumulatedDelay);
                    });

                    this.showToast(`¡Campaña '${data.campaign_name}' activada! Secuencia enviada.`);
                } else {
                    this.showToast(data.message, 'warning');
                }
            } catch (e) {
                this.showToast('Error ejecutando simulador', 'error');
            } finally {
                this.simIsProcessing = false;
            }
        },

        async sendSimUserChatMessage() {
            if (!this.simUserChatMessage || !this.simUserChatMessage.trim()) return;

            const text = this.simUserChatMessage.trim();
            this.simUserChatMessage = '';

            // Add user message to DM
            this.simDmMessages.push({
                sender: 'user',
                text,
                time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            });

            this.simIsAiTyping = true;
            this.$nextTick(() => {
                const chatBox = document.getElementById('sim-dm-chatbox');
                if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;
            });

            try {
                const res = await fetch('/api/simulator/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: 'sim_user_test',
                        username: this.simUsername || 'cliente',
                        message_text: text
                    })
                });
                const data = await res.json();

                setTimeout(() => {
                    this.simIsAiTyping = false;
                    this.simDmMessages.push({
                        sender: 'bot',
                        text: data.reply,
                        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    });
                    this.$nextTick(() => {
                        const chatBox = document.getElementById('sim-dm-chatbox');
                        if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;
                    });
                }, 800);

            } catch (e) {
                this.simIsAiTyping = false;
                this.showToast('Error en respuesta de IA', 'error');
            }
        },

        copyToClipboard(text) {
            navigator.clipboard.writeText(text);
            this.showToast('Copiado al portapapeles 📋');
        },

        formatDate(isoString) {
            if (!isoString) return '-';
            const d = new Date(isoString);
            return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
    };
}

// Make it available globally for Alpine
window.instaFlowApp = instaFlowApp;

if (window.Alpine) {
    Alpine.data('instaFlowApp', instaFlowApp);
} else {
    document.addEventListener('alpine:init', () => {
        Alpine.data('instaFlowApp', instaFlowApp);
    });
}
