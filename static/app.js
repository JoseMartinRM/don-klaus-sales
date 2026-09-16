// Global component definition for Alpine.js
function instaFlowApp() {
    return {
        currentTab: 'crm',
        stats: {
            total_leads_captured: 0,
            total_dms_sent: 0,
            total_public_replies: 0,
            total_ai_replies: 0,
            total_purchases: 0,
            total_revenue_usd: 0,
            stage_counts: {
                comento: 0,
                respondio: 0,
                recibio_pdf: 0,
                vio_oferta: 0,
                click_checkout: 0,
                compro: 0,
                perdido: 0
            },
            segments: {
                sueldo: 0,
                deuda: 0,
                sin_definir: 0
            },
            ab_tests: {
                dm1: {
                    variant_a: { sent: 0, engaged: 0, rate: 0 },
                    variant_b: { sent: 0, engaged: 0, rate: 0 }
                },
                followup3: {
                    variant_a: { sent: 0, sales: 0, rate: 0 },
                    variant_b: { sent: 0, sales: 0, rate: 0 }
                }
            },
            objections: {},
            top_reels: []
        },
        
        // Settings
        settings: {
            company_name: 'Sistema Don Klaus',
            company_description: 'Mentoría y protocolos financieros para blindar su sueldo y liquidar deudas de por vida.',
            sales_tone: 'sobrio, formal (usted), empático pero implacable contra excusas, de alto valor y cierre consultivo.',
            gemini_api_key: '',
            meta_access_token: '',
            meta_verify_token: 'instaflow_verify_token_secure_2026',
            hotmart_webhook_token: ''
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
        
        // Leads & CRM Filters
        leads: [],
        inactiveLeads: [],
        leadFilterStage: '',
        leadFilterSegment: '',
        pendingFollowups: [],
        isRunningFollowups: false,
        logs: [],
        
        // Simulator State
        simUsername: 'carlos_inversor',
        simComment: 'QUIERO',
        simPostId: 'reel_101',
        simIsProcessing: false,
        simPostComments: [
            { username: 'carlos_inversor', text: 'Quiero las reglas de Don Klaus 🔥', time: 'hace 5m', isReply: false }
        ],
        simDmMessages: [],
        simUserChatMessage: '',
        simIsAiTyping: false,
        simSegment: 'SUELDO',
        simStage: 'comento',
        
        // Notification Toast
        toast: { show: false, message: '', type: 'success' },

        showToast(msg, type = 'success') {
            this.toast = { show: true, message: msg, type };
            setTimeout(() => { this.toast.show = false; }, 3500);
        },

        // Meta Connection Status
        metaStatus: { connected: false, account: null },

        async init() {
            console.log("Don Klaus Sales CRM App Inicializada");
            await this.loadStats();
            await this.loadMetaStatus();
            await this.loadCampaigns();
            await this.loadProducts();
            await this.loadSettings();
            await this.loadLeads();
            await this.loadInactiveLeads();
            await this.loadPendingFollowups();
            await this.loadLogs();

            // Refresh periodic
            setInterval(() => {
                this.loadStats();
                this.loadMetaStatus();
                if (this.currentTab === 'crm' || this.currentTab === 'logs') {
                    this.loadLeads();
                    this.loadInactiveLeads();
                    this.loadPendingFollowups();
                }
            }, 6000);
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
                const res = await fetch('/api/metrics/funnel');
                if (res.ok) this.stats = await res.json();
            } catch (e) {
                console.error("Error loading stats:", e);
            }
        },

        async resetStats() {
            if (!confirm('¿Desea reiniciar todos los contadores, leads y registros a cero?')) return;
            try {
                const res = await fetch('/api/stats/reset', { method: 'POST' });
                if (res.ok) {
                    this.showToast('Contadores y registros reiniciados');
                    await this.loadStats();
                    await this.loadLeads();
                    await this.loadInactiveLeads();
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
                name: 'Campaña Don Klaus - Diagnóstico y Conversión',
                keywords: 'QUIERO, REGLAS, PDF, INFO, SUELDO, DEUDA',
                match_mode: 'contains',
                post_id_filter: '',
                public_replies: [
                    'Listo @username, le escribí por mensaje privado para que lo revise con calma. ⚔️',
                    'Le dejé un mensaje directo, @username. Mírelo cuando tenga un minuto. 📩'
                ],
                dm_messages: [
                    {
                        text: 'Hola @username 👋 Vi su comentario. ¿Su mayor problema hoy es ordenar su Sueldo o liquidar Deudas?',
                        delay_seconds: 0
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
            this.editingCampaign.public_replies.push('Listo @username, le envié un mensaje directo al privado. 📩');
        },

        removePublicReply(index) {
            this.editingCampaign.public_replies.splice(index, 1);
        },

        async saveCampaign() {
            if (!this.editingCampaign.name || !this.editingCampaign.keywords) {
                this.showToast('Nombre y palabras clave son obligatorios', 'error');
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
                    this.showToast(isNew ? 'Campaña creada' : 'Campaña actualizada');
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
                this.showToast(`Campaña ${camp.is_active ? 'activada' : 'pausada'}`);
                await this.loadStats();
            } catch (e) {
                this.showToast('Error al actualizar estado', 'error');
            }
        },

        async deleteCampaign(campId) {
            if (!confirm('¿Eliminar esta campaña?')) return;
            try {
                const res = await fetch(`/api/campaigns/${campId}`, { method: 'DELETE' });
                if (res.ok) {
                    this.showToast('Campaña eliminada');
                    await this.loadCampaigns();
                    await this.loadStats();
                }
            } catch (e) {
                this.showToast('Error al eliminar', 'error');
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
                this.showToast('Nombre, precio y link de compra son obligatorios', 'error');
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
                this.showToast('Error al eliminar', 'error');
            }
        },

        // --- CRM LEADS & 24H WINDOW LOGIC ---
        async loadLeads() {
            try {
                let url = '/api/crm/leads?limit=200';
                if (this.leadFilterStage) url += `&stage=${this.leadFilterStage}`;
                if (this.leadFilterSegment) url += `&segment=${this.leadFilterSegment}`;
                const res = await fetch(url);
                if (res.ok) this.leads = await res.json();
            } catch (e) {
                console.error("Error loading leads:", e);
            }
        },

        async loadInactiveLeads() {
            try {
                const res = await fetch('/api/crm/7day-leads?limit=50');
                if (res.ok) this.inactiveLeads = await res.json();
            } catch (e) {
                console.error("Error loading inactive leads:", e);
            }
        },

        async loadPendingFollowups() {
            try {
                const res = await fetch('/api/followups/pending');
                if (res.ok) {
                    const data = await res.json();
                    this.pendingFollowups = data.leads || [];
                }
            } catch (e) {
                console.error("Error loading pending followups:", e);
            }
        },

        async triggerFollowupsNow() {
            this.isRunningFollowups = true;
            try {
                const res = await fetch('/api/followups/run', { method: 'POST' });
                const data = await res.json();
                this.showToast(`Seguimientos 24h procesados: ${data.processed} enviados`);
                await this.loadPendingFollowups();
                await this.loadStats();
                await this.loadLeads();
            } catch (e) {
                this.showToast('Error ejecutando seguimientos', 'error');
            } finally {
                this.isRunningFollowups = false;
            }
        },

        async loadLogs() {
            try {
                const res = await fetch('/api/logs?limit=150');
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
                        post_id: this.simPostId || 'reel_101'
                    })
                });
                const data = await res.json();

                if (data.matched) {
                    // 1. Respuesta pública
                    setTimeout(() => {
                        this.simPostComments.push({
                            username: 'sistemadonklaus',
                            text: data.public_reply,
                            time: 'Ahora',
                            isReply: true
                        });
                    }, 500);

                    // 2. DM 1 Diagnóstico
                    setTimeout(() => {
                        this.simDmMessages = [{
                            sender: 'bot',
                            text: data.dm_text,
                            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                            quick_replies: data.quick_replies
                        }];
                        this.$nextTick(() => {
                            const chatBox = document.getElementById('sim-dm-chatbox');
                            if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;
                        });
                    }, 1200);

                    this.showToast(`¡Diagnóstico DM 1 (Var ${data.dm_variant}) activado!`);
                } else {
                    this.showToast(data.message, 'warning');
                }
            } catch (e) {
                this.showToast('Error ejecutando simulador', 'error');
            } finally {
                this.simIsProcessing = false;
            }
        },

        async sendSimUserChatMessage(customText = null) {
            const text = (customText || this.simUserChatMessage || '').trim();
            if (!text) return;

            this.simUserChatMessage = '';

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
                        message_text: text,
                        segment: this.simSegment,
                        stage: this.simStage
                    })
                });
                const data = await res.json();

                setTimeout(() => {
                    this.simIsAiTyping = false;
                    this.simDmMessages.push({
                        sender: 'bot',
                        text: data.reply,
                        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                        escalation: data.escalation
                    });
                    this.$nextTick(() => {
                        const chatBox = document.getElementById('sim-dm-chatbox');
                        if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;
                    });
                }, 600);

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
        },

        getTimeRemaining(lastIso) {
            if (!lastIso) return 'Expirado';
            const last = new Date(lastIso);
            const now = new Date();
            const diffMs = (last.getTime() + (24 * 60 * 60 * 1000)) - now.getTime();
            if (diffMs <= 0) return 'Ventana 24h Cerrada 🛑';
            const hours = Math.floor(diffMs / (1000 * 60 * 60));
            const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
            return `Quedan ${hours}h ${mins}m ⏱️`;
        }
    };
}

window.instaFlowApp = instaFlowApp;

if (window.Alpine) {
    Alpine.data('instaFlowApp', instaFlowApp);
} else {
    document.addEventListener('alpine:init', () => {
        Alpine.data('instaFlowApp', instaFlowApp);
    });
}

